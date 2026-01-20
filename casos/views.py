# casos/views.py
# ==============================================================================
# Sistema de Gestão de Casos - Views Principais
# ==============================================================================

import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, date
from django.db.models import ProtectedError

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.db.models import Sum, Q 
from django.views.decorators.http import require_POST
from django.forms import formset_factory
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from io import BytesIO

# --- DRF ---
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication

# --- Imports de Outros Apps ---
from clientes.models import Cliente
from produtos.models import Produto
from campos_custom.models import (
    EstruturaDeCampos,
    CampoPersonalizado,
    GrupoCampos,
    InstanciaGrupoValor,
    ValorCampoPersonalizado,
    OpcoesListaPersonalizada
)
from integrations.sharepoint import SharePoint

# --- Imports Locais (do app 'casos') ---
from .models import (
    Caso,
    Andamento,
    ModeloAndamento,
    Timesheet,
    Acordo,
    Parcela,
    Despesa,
    FluxoInterno,
    Tomador,
    TomadorEmail,
    TomadorTelefone
)
from .forms import (
    CasoDinamicoForm,
    AndamentoForm,
    TimesheetForm,
    AcordoForm,
    DespesaForm,
    BaseGrupoForm,
    CasoInfoBasicasForm,
    CasoDadosAdicionaisForm,
    TomadorForm
)
from .folder_utils import recriar_estrutura_de_pastas
from .serializers import CasoSerializer
import openpyxl

# PDF Imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
logger = logging.getLogger('casos_app')
User = get_user_model()

try:
    from .utils import get_cabecalho_exportacao
except ImportError:
    def get_cabecalho_exportacao(cliente=None, produto=None):
        return ([], [], {})

try:
    from .tasks import processar_linha_importacao
except ImportError:
    def processar_linha_importacao(*args, **kwargs):
        logger.critical("Tarefa Celery não encontrada!")

# ==============================================================================
# VIEWS DE TOMADOR
# ==============================================================================
@login_required
def exportar_tomadores_excel(request):
    queryset = Tomador.objects.prefetch_related('casos__cliente', 'casos__produto')
    q = request.GET.get('q')
    if q:
        queryset = queryset.filter(Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Relatorio Tomadores"
    headers = ["Nome do Tomador", "CPF/CNPJ", "Cliente", "Produto", "Número do Aviso / Título", "Status"]
    ws.append(headers)

    for tomador in queryset:
        casos = tomador.casos.all()
        if casos.exists():
            for caso in casos:
                ws.append([
                    tomador.nome, tomador.cpf_cnpj or "-",
                    caso.cliente.nome if caso.cliente else "-",
                    caso.produto.nome if caso.produto else "-",
                    caso.titulo or f"Caso #{caso.id}",
                    caso.get_status_display()
                ])
        else:
            ws.append([tomador.nome, tomador.cpf_cnpj or "-", "-", "-", "-", "Sem casos"])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="relatorio_tomadores.xlsx"'
    wb.save(response)
    return response

@login_required
def exportar_tomadores_pdf(request):
    queryset = Tomador.objects.prefetch_related('casos__cliente', 'casos__produto')
    q = request.GET.get('q')
    if q:
        queryset = queryset.filter(Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q))

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_tomadores.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_normal.fontSize = 9

    elements.append(Paragraph("Relatório Detalhado de Tomadores e Casos", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [["Tomador", "Cliente", "Produto", "Aviso / Título", "Status"]]
    for tomador in queryset:
        casos = tomador.casos.all()
        if casos.exists():
            for caso in casos:
                data.append([
                    Paragraph(tomador.nome[:40], style_normal),
                    Paragraph(caso.cliente.nome if caso.cliente else "-", style_normal),
                    Paragraph(caso.produto.nome if caso.produto else "-", style_normal),
                    Paragraph(str(caso.titulo)[:40], style_normal),
                    Paragraph(caso.get_status_display(), style_normal)
                ])
        else:
            data.append([Paragraph(tomador.nome, style_normal), "-", "-", "-", "Sem casos"])

    table = Table(data, colWidths=[180, 150, 150, 180, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    doc.build(elements)
    return response

@require_POST
@login_required
def trocar_tomador_do_caso(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    novo_tomador_id = request.POST.get('novo_tomador')
    if novo_tomador_id:
        try:
            novo_tomador = Tomador.objects.get(id=novo_tomador_id)
            antigo_tomador_nome = caso.tomador.nome if caso.tomador else "Ninguém"
            caso.tomador = novo_tomador
            caso.save()
            FluxoInterno.objects.create(
                caso=caso, tipo_evento='EDICAO',
                descricao=f"Tomador alterado de '{antigo_tomador_nome}' para '{novo_tomador.nome}'.",
                autor=request.user
            )
            messages.success(request, f"✅ Tomador alterado para: {novo_tomador.nome}")
        except Tomador.DoesNotExist:
            messages.error(request, "Tomador não existe.")
    return redirect('casos:detalhe_caso', pk=pk)

class TomadorListView(ListView):
    model = Tomador
    template_name = 'casos/tomador_list.html'
    context_object_name = 'tomadores'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q')
        if q: queryset = queryset.filter(Q(nome__icontains=q) | Q(cpf_cnpj__icontains=q))
        return queryset

class TomadorCreateView(CreateView):
    model = Tomador
    form_class = TomadorForm
    template_name = 'casos/tomador_form.html'
    success_url = reverse_lazy('casos:lista_tomadores')
    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            for email in self.request.POST.getlist('lista_emails'):
                if email.strip(): TomadorEmail.objects.create(tomador=self.object, email=email.strip())
            for fone in self.request.POST.getlist('lista_telefones'):
                if fone.strip(): TomadorTelefone.objects.create(tomador=self.object, telefone=fone.strip())
        return redirect(self.get_success_url())

class TomadorUpdateView(UpdateView):
    model = Tomador
    form_class = TomadorForm
    template_name = 'casos/tomador_form.html'
    success_url = reverse_lazy('casos:lista_tomadores')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['casos_vinculados'] = self.object.casos.all().select_related('cliente', 'produto')
        context['emails'] = self.object.emails.all()
        context['telefones'] = self.object.telefones.all()
        context['todos_tomadores'] = Tomador.objects.exclude(id=self.object.id).order_by('nome')
        return context
    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            for email in self.request.POST.getlist('lista_emails'):
                if email.strip(): TomadorEmail.objects.create(tomador=self.object, email=email.strip())
            for fone in self.request.POST.getlist('lista_telefones'):
                if fone.strip(): TomadorTelefone.objects.create(tomador=self.object, telefone=fone.strip())
        return redirect(self.get_success_url())

@require_POST
@login_required
def criar_tomador_ajax(request):
    form = TomadorForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            tomador = form.save()
            for email in request.POST.getlist('lista_emails'):
                if email.strip(): TomadorEmail.objects.create(tomador=tomador, email=email.strip())
            return JsonResponse({'success': True, 'id': tomador.id, 'text': tomador.nome})
    return JsonResponse({'success': False, 'errors': form.errors})

# ==============================================================================
# CRIAR CASO (LOGICA DE MOEDA ATUALIZADA)
# ==============================================================================
@login_required
def criar_caso(request, cliente_id, produto_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    produto = get_object_or_404(Produto, id=produto_id)

    try:
        estrutura = EstruturaDeCampos.objects.prefetch_related(
            'ordenamentos_simples__campo', 'grupos_repetiveis__ordenamentos_grupo__campo'
        ).get(cliente=cliente, produto=produto)
    except EstruturaDeCampos.DoesNotExist:
        messages.error(request, "Estrutura não definida.")
        return redirect('casos:selecionar_produto_cliente')

    if request.method == 'POST':
        # --- LIMPEZA DE MOEDA PARA VALORES ALTOS ---
        post_data = request.POST.copy()
        
        # Limpa o campo fixo valor_apurado
        if post_data.get('valor_apurado'):
            val_limpo = post_data['valor_apurado'].replace('.', '').replace(',', '.')
            post_data['valor_apurado'] = val_limpo

        # Limpa campos dinâmicos que possam ser moeda/decimal
        for key, value in post_data.items():
            if 'campo_personalizado' in key and value and isinstance(value, str):
                if ',' in value: # Provável valor mascarado do Brasil
                    post_data[key] = value.replace('.', '').replace(',', '.')

        form = CasoDinamicoForm(post_data, cliente=cliente, produto=produto)
    else:
        form = CasoDinamicoForm(cliente=cliente, produto=produto)

    grupo_formsets = {}
    for grupo in estrutura.grupos_repetiveis.all():
        GrupoFormSet = formset_factory(BaseGrupoForm, extra=1, can_delete=True)
        prefix = f'grupo_{grupo.id}'
        kwargs = {'grupo_campos': grupo, 'cliente': cliente, 'produto': produto}
        if request.method == 'POST':
            formset = GrupoFormSet(post_data, prefix=prefix, form_kwargs=kwargs)
        else:
            formset = GrupoFormSet(prefix=prefix, form_kwargs=kwargs)
        grupo_formsets[grupo.id] = (grupo, formset)

    if request.method == 'POST':
        formsets_validos = all(fs.is_valid() for _, fs in grupo_formsets.values())
        if form.is_valid() and formsets_validos:
            try:
                with transaction.atomic():
                    # Lógica de Título Automático
                    dados_titulo = {}
                    dados_limpos = form.cleaned_data
                    for eco in estrutura.ordenamentos_simples.all():
                        val = dados_limpos.get(f'campo_personalizado_{eco.campo.id}', '')
                        dados_titulo[eco.campo.nome_variavel] = str(val)

                    titulo_final = produto.padrao_titulo or ""
                    for chave, valor in dados_titulo.items():
                        titulo_final = titulo_final.replace(f"{{{chave}}}", valor)
                    
                    if not titulo_final.strip(): titulo_final = f"Caso {cliente.nome}"

                    novo_caso = form.save(commit=False)
                    novo_caso.cliente = cliente
                    novo_caso.produto = produto
                    novo_caso.titulo = titulo_final
                    novo_caso.save()

                    # Salvar campos simples
                    for eco in estrutura.ordenamentos_simples.all():
                        val = dados_limpos.get(f'campo_personalizado_{eco.campo.id}')
                        if val is not None:
                            ValorCampoPersonalizado.objects.create(caso=novo_caso, campo=eco.campo, valor=str(val))

                    # Salvar formsets
                    for grupo, formset in grupo_formsets.values():
                        for idx, f in enumerate(formset):
                            if not f.has_changed() or f.cleaned_data.get('DELETE'): continue
                            inst = InstanciaGrupoValor.objects.create(caso=novo_caso, grupo=grupo, ordem_instancia=idx)
                            for conf in grupo.ordenamentos_grupo.all():
                                val_f = f.cleaned_data.get(f'campo_personalizado_{conf.campo.id}')
                                ValorCampoPersonalizado.objects.create(instancia_grupo=inst, campo=conf.campo, valor=str(val_f))

                    messages.success(request, f"✅ Caso criado!")
                    return redirect('casos:detalhe_caso', pk=novo_caso.pk)
            except Exception as e:
                messages.error(request, f"Erro: {e}")

    return render(request, 'casos/criar_caso_form.html', {
        'cliente': cliente, 'produto': produto, 'form': form,
        'grupo_formsets': grupo_formsets.values(), 'estrutura': estrutura
    })

# ==============================================================================
# DETALHE DO CASO
# ==============================================================================
@login_required
def detalhe_caso(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    
    if request.method == 'POST':
        edit_modal = request.POST.get('edit_modal')
        
        if edit_modal == 'info-basicas':
            # --- LIMPEZA DE MOEDA NO EDITAR ---
            post_data = request.POST.copy()
            valor_bruto = post_data.get('valor_apurado', '')
            if valor_bruto:
                val_limpo = valor_bruto.replace('R$', '').replace('.', '').replace(',', '.').strip()
                caso.valor_apurado = Decimal(val_limpo)
            
            caso.status = post_data.get('status', caso.status)
            if post_data.get('data_entrada'): caso.data_entrada = post_data.get('data_entrada')
            
            adv_id = post_data.get('advogado_responsavel')
            caso.advogado_responsavel_id = adv_id if adv_id else None
            caso.save()
            messages.success(request, '✅ Informações atualizadas!')
            return redirect('casos:detalhe_caso', pk=pk)

        elif edit_modal == 'dados-adicionais':
            # Atualiza campos personalizados dinâmicos
            for key, value in request.POST.items():
                if key.startswith('campo_'):
                    c_id = key.replace('campo_', '')
                    # Limpeza rápida se for moeda (detectado por vírgula)
                    if isinstance(value, str) and ',' in value:
                        value = value.replace('.', '').replace(',', '.')
                    
                    val_obj, _ = ValorCampoPersonalizado.objects.get_or_create(
                        caso=caso, campo_id=c_id, instancia_grupo__isnull=True
                    )
                    val_obj.valor = value
                    val_obj.save()
            messages.success(request, '✅ Dados atualizados!')
            return redirect('casos:detalhe_caso', pk=pk)

    # Renderização normal do detalhe
    context = {
        'caso': caso,
        'form_andamento': AndamentoForm(),
        'form_timesheet': TimesheetForm(user=request.user),
        'form_acordo': AcordoForm(user=request.user),
        'form_despesa': DespesaForm(user=request.user),
        'andamentos': caso.andamentos.all().order_by('-data_andamento'),
        'timesheets': caso.timesheets.all(),
        'acordos': caso.acordos.all(),
        'despesas': caso.despesas.all(),
        'fluxo_interno': caso.fluxo_interno.all().order_by('-data_evento'),
        'form_info_basicas': CasoInfoBasicasForm(instance=caso),
        'valores_personalizados': caso.valores_personalizados.filter(instancia_grupo__isnull=True).select_related('campo'),
        'grupos_de_valores_salvos': caso.grupos_de_valores.all().prefetch_related('valores__campo'),
    }
    return render(request, 'casos/detalhe_caso.html', context)

# ==============================================================================
# DASHBOARD EXECUTIVO
# ==============================================================================
@login_required
def dashboard_view(request):
    ano_atual = timezone.now().year
    anos_disponiveis = list(range(ano_atual, ano_atual - 5, -1))
    ano_selecionado = request.GET.get('ano', str(ano_atual))
    
    casos_ano = Caso.objects.filter(data_entrada__year=ano_selecionado)
    
    context = {
        'ano_selecionado': ano_selecionado,
        'anos_disponiveis': anos_disponiveis,
        'total_casos_ano': casos_ano.count(),
        'casos_ativos': casos_ano.filter(status='ATIVO').count(),
        'periodo': request.GET.get('periodo', 'hoje'),
    }
    return render(request, 'casos/dashboard.html', context)

# ==============================================================================
# SHAREPOINT & ANEXOS
# ==============================================================================
@login_required
def carregar_painel_anexos(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    if not caso.sharepoint_folder_id:
        return render(request, 'casos/partials/painel_anexos_criar.html', {'caso': caso})
    
    try:
        sp = SharePoint()
        itens = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
        return render(request, 'casos/partials/painel_anexos.html', {
            'caso': caso, 'itens': itens, 'folder_id': caso.sharepoint_folder_id
        })
    except Exception as e:
        return HttpResponse(f"Erro SharePoint: {e}")

@login_required
def upload_arquivo_sharepoint(request, caso_pk):
    caso = get_object_or_404(Caso, pk=caso_pk)
    if request.method == 'POST' and request.FILES.get('arquivo'):
        sp = SharePoint()
        pasta_id = request.POST.get('pasta_id', caso.sharepoint_folder_id)
        sp.fazer_upload(request.FILES['arquivo'], pasta_id)
        return carregar_painel_anexos(request, caso_pk)
    return JsonResponse({'error': 'Falha no upload'}, status=400)

# ==============================================================================
# LISTA DE CASOS E FILTROS
# ==============================================================================
@login_required
def lista_casos(request):
    casos_list = Caso.objects.select_related('cliente', 'produto', 'advogado_responsavel').all().order_by('-id')
    
    q = request.GET.get('filtro_titulo')
    if q: casos_list = casos_list.filter(titulo__icontains=q)
    
    cliente_id = request.GET.get('filtro_cliente')
    if cliente_id: casos_list = casos_list.filter(cliente_id=cliente_id)

    status = request.GET.get('filtro_status')
    if status: casos_list = casos_list.filter(status=status)

    paginator = Paginator(casos_list, 20)
    page = request.GET.get('page')
    casos = paginator.get_page(page)

    return render(request, 'casos/lista_casos.html', {
        'casos': casos,
        'todos_clientes': Cliente.objects.all(),
        'todos_produtos': Produto.objects.all(),
        'status_choices': Caso.STATUS_CHOICES
    })

# ==============================================================================
# OUTRAS VIEWS (TIMESHEET, ACORDOS, ETC)
# ==============================================================================
@login_required
def editar_timesheet(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk)
    if request.method == 'POST':
        form = TimesheetForm(request.POST, instance=ts)
        if form.is_valid():
            form.save()
            return redirect('casos:detalhe_caso', pk=ts.caso.pk)
    return render(request, 'casos/timesheet_form.html', {'form': TimesheetForm(instance=ts)})

@login_required
def selecionar_produto_cliente(request):
    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    return render(request, 'casos/selecionar_produto_cliente.html', {'clientes': clientes, 'produtos': produtos})

@login_required
def obter_detalhes_tomador(request, pk):
    tomador = get_object_or_404(Tomador, pk=pk)
    return JsonResponse({
        'success': True,
        'cpf_cnpj': tomador.cpf_cnpj,
        'emails': list(tomador.emails.values_list('email', flat=True)),
        'telefones': list(tomador.telefones.values_list('telefone', flat=True))
    })

# FIM DO ARQUIVO