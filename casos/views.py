# casos/views.py
# ==============================================================================
# Sistema de Gestão de Casos - Views Principais
# ==============================================================================

# ==============================================================================
# 1. IMPORTS PADRÃO DO PYTHON
# ==============================================================================
import logging
import re
from io import BytesIO
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation

# ==============================================================================
# 2. IMPORTS DE TERCEIROS
# ==============================================================================
import openpyxl
import requests
from dateutil.relativedelta import relativedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from datetime import date, datetime

# ==============================================================================
# 3. IMPORTS DO DJANGO
# ==============================================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import Sum
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.utils.formats import number_format

# ==============================================================================
# 4. IMPORTS LOCAIS
# ==============================================================================
from clientes.models import Cliente
from produtos.models import Produto
from campos_custom.models import (
    EstruturaDeCampos,
    InstanciaGrupoValor,
    ValorCampoPersonalizado,
    OpcoesListaPersonalizada
)
from .models import (
    Caso, Andamento, ModeloAndamento, Timesheet,
    Acordo, Parcela, Despesa, FluxoInterno
)
from .forms import (
    CasoDinamicoForm, AndamentoForm, TimesheetForm,
    AcordoForm, DespesaForm, BaseGrupoForm
)
from .serializers import CasoSerializer
from integrations.sharepoint import SharePoint

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
logger = logging.getLogger('casos_app')
User = get_user_model()

# Importa funções auxiliares (com fallback)
try:
    from .utils import get_cabecalho_exportacao
except ImportError:
    logger.warning("utils.get_cabecalho_exportacao não encontrado")
    def get_cabecalho_exportacao(cliente=None, produto=None):
        return ([], [], {})

try:
    from .tasks import processar_linha_importacao
except ImportError:
    logger.warning("tasks.processar_linha_importacao não encontrado")
    def processar_linha_importacao(*args, **kwargs):
        logger.critical("Tarefa Celery não encontrada!")


# ==============================================================================
# VIEWS DE SELEÇÃO
# ==============================================================================

@login_required
def selecionar_produto_cliente(request):
    """Tela de seleção de Cliente e Produto antes de criar caso."""
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        if cliente_id and produto_id:
            return redirect('casos:criar_caso', cliente_id=cliente_id, produto_id=produto_id)
    
    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    
    context = {
        'clientes': clientes,
        'produtos': produtos
    }
    return render(request, 'casos/selecionar_produto_cliente.html', context)


# ==============================================================================
# CRIAR CASO (✅ CORRIGIDO 100%)
# ==============================================================================

@login_required
def criar_caso(request, cliente_id, produto_id):
    """
    ✅ VERSÃO CORRIGIDA E COMPLETA
    Cria um novo caso com campos dinâmicos (simples + grupos repetíveis).
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    produto = get_object_or_404(Produto, id=produto_id)

    # Busca estrutura de campos
    try:
        estrutura = EstruturaDeCampos.objects.prefetch_related(
            'ordenamentos_simples__campo',
            'grupos_repetiveis__ordenamentos_grupo__campo'
        ).get(cliente=cliente, produto=produto)
    except EstruturaDeCampos.DoesNotExist:
        messages.error(
            request,
            f"❌ Estrutura de campos não definida para {cliente.nome} + {produto.nome}. "
            "Configure no Admin antes de criar casos."
        )
        return redirect('casos:selecionar_produto_cliente')

    # ========================================
    # Formulário principal
    # ========================================
    if request.method == 'POST':
        form = CasoDinamicoForm(request.POST, cliente=cliente, produto=produto)
    else:
        form = CasoDinamicoForm(cliente=cliente, produto=produto)

    # ========================================
    # Formsets dos grupos repetíveis
    # ========================================
    grupo_formsets = {}
    
    for grupo in estrutura.grupos_repetiveis.all():
        GrupoFormSet = formset_factory(
            BaseGrupoForm,
            extra=1,
            can_delete=True
        )
        
        prefix = f'grupo_{grupo.id}'
        kwargs = {
            'grupo_campos': grupo,
            'cliente': cliente,
            'produto': produto
        }
        
        if request.method == 'POST':
            formset = GrupoFormSet(request.POST, prefix=prefix, form_kwargs=kwargs)
        else:
            formset = GrupoFormSet(prefix=prefix, form_kwargs=kwargs)
        
        grupo_formsets[grupo.id] = (grupo, formset)

    # ========================================
    # Processamento do POST
    # ========================================
    if request.method == 'POST':
        formsets_validos = all(fs.is_valid() for _, fs in grupo_formsets.values())

        if form.is_valid() and formsets_validos:
            dados_limpos_principal = form.cleaned_data

            try:
                with transaction.atomic():
                    # 1. Gera título
                    dados_titulo_combinados = {}

                    # Campos simples
                    for eco in estrutura.ordenamentos_simples.select_related('campo'):
                        campo = eco.campo
                        valor = dados_limpos_principal.get(f'campo_personalizado_{campo.id}', '')
                        dados_titulo_combinados[campo.nome_variavel] = str(valor)

                    # Campos do primeiro grupo preenchido
                    for grupo, formset in grupo_formsets.values():
                        primeiro_form_valido = next(
                            (fd for fd in formset.cleaned_data 
                             if fd and not fd.get('DELETE', False)),
                            None
                        )
                        if primeiro_form_valido:
                            for config in grupo.ordenamentos_grupo.select_related('campo'):
                                campo_grupo = config.campo
                                valor = primeiro_form_valido.get(
                                    f'campo_personalizado_{campo_grupo.id}',
                                    ''
                                )
                                dados_titulo_combinados[campo_grupo.nome_variavel] = str(valor)
                            break

                    # Gera título
                    titulo_final = produto.padrao_titulo or dados_limpos_principal.get('titulo_manual', '')
                    for chave, valor in dados_titulo_combinados.items():
                        titulo_final = titulo_final.replace(f'{{{chave}}}', valor)

                    # 2. Cria caso
                    novo_caso = form.save(commit=False)
                    novo_caso.cliente = cliente
                    novo_caso.produto = produto
                    novo_caso.titulo = titulo_final
                    novo_caso.save()
                    form.save_m2m()

                    logger.info(f"Caso #{novo_caso.id} criado: {titulo_final}")

                    # 3. Salva campos simples
                    for eco in estrutura.ordenamentos_simples.select_related('campo'):
                        campo = eco.campo
                        valor = dados_limpos_principal.get(f'campo_personalizado_{campo.id}')
                        
                        if valor is not None:
                            # Converte lista para string (LISTA_MULTIPLA)
                            if isinstance(valor, list):
                                valor = ', '.join(str(v) for v in valor)
                            
                            ValorCampoPersonalizado.objects.create(
                                caso=novo_caso,
                                instancia_grupo=None,
                                campo=campo,
                                valor=str(valor)
                            )

                    # 4. Salva grupos repetíveis
                    for grupo, formset in grupo_formsets.values():
                        for index, form_grupo in enumerate(formset):
                            if not form_grupo.has_changed() or form_grupo.cleaned_data.get('DELETE', False):
                                continue

                            instancia = InstanciaGrupoValor.objects.create(
                                caso=novo_caso,
                                grupo=grupo,
                                ordem_instancia=index
                            )

                            for config in grupo.ordenamentos_grupo.select_related('campo'):
                                campo_grupo = config.campo
                                valor = form_grupo.cleaned_data.get(
                                    f'campo_personalizado_{campo_grupo.id}'
                                )
                                
                                if valor is not None:
                                    if isinstance(valor, list):
                                        valor = ', '.join(str(v) for v in valor)
                                    
                                    ValorCampoPersonalizado.objects.create(
                                        caso=None,
                                        instancia_grupo=instancia,
                                        campo=campo_grupo,
                                        valor=str(valor)
                                    )

                    messages.success(
                        request,
                        f"✅ Caso '{novo_caso.titulo}' criado com sucesso!"
                    )
                    return redirect('casos:detalhe_caso', pk=novo_caso.pk)

            except Exception as e:
                logger.error(f"Erro ao salvar caso: {e}", exc_info=True)
                messages.error(request, f"❌ Erro ao salvar o caso: {e}")
        
        else:
            # Mostra erros
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Campo '{field}': {error}")
            
            for grupo, formset in grupo_formsets.values():
                if formset.errors:
                    messages.error(
                        request,
                        f"Erro no grupo '{grupo.nome_grupo}': {formset.errors}"
                    )

    context = {
        'cliente': cliente,
        'produto': produto,
        'form': form,
        'grupo_formsets': grupo_formsets.values(),
        'estrutura': estrutura,
    }
    
    return render(request, 'casos/criar_caso_form.html', context)


# ==============================================================================
# LISTA DE CASOS
# ==============================================================================

@login_required
def lista_casos(request):
    """Lista todos os casos com filtros."""
    casos_list = Caso.objects.select_related(
        'cliente', 'produto', 'advogado_responsavel'
    ).all().order_by('-id')
    
    # Filtros
    filtro_titulo = request.GET.get('filtro_titulo', '')
    filtro_cliente = request.GET.get('filtro_cliente', '')
    filtro_produto = request.GET.get('filtro_produto', '')
    filtro_status = request.GET.get('filtro_status', '')
    filtro_advogado = request.GET.get('filtro_advogado', '')

    if filtro_titulo:
        casos_list = casos_list.filter(titulo__icontains=filtro_titulo)
    if filtro_cliente:
        casos_list = casos_list.filter(cliente_id=filtro_cliente)
    if filtro_produto:
        casos_list = casos_list.filter(produto_id=filtro_produto)
    if filtro_status:
        casos_list = casos_list.filter(status=filtro_status)
    if filtro_advogado:
        casos_list = casos_list.filter(advogado_responsavel_id=filtro_advogado)

    context = {
        'casos': casos_list,
        'valores_filtro': request.GET,
        'todos_clientes': Cliente.objects.all().order_by('nome'),
        'todos_produtos': Produto.objects.all().order_by('nome'),
        'todos_advogados': User.objects.all().order_by('first_name', 'username'),
        'status_choices': Caso.STATUS_CHOICES,
    }
    return render(request, 'casos/lista_casos.html', context)


# ==============================================================================
# DETALHE DO CASO
# ==============================================================================

@login_required
def detalhe_caso(request, pk):
    """Exibe detalhes completos de um caso."""
    caso = get_object_or_404(Caso, pk=pk)
    caso.refresh_from_db()

    # Forms padrão
    form_andamento = AndamentoForm()
    form_timesheet = TimesheetForm(user=request.user)
    form_acordo = AcordoForm(user=request.user)
    form_despesa = DespesaForm(user=request.user)

    # Processamento POST
    if request.method == 'POST':
        if 'submit_andamento' in request.POST:
            form_andamento = AndamentoForm(request.POST)
            if form_andamento.is_valid():
                novo_andamento = form_andamento.save(commit=False)
                novo_andamento.caso = caso
                novo_andamento.autor = request.user
                novo_andamento.save()
                FluxoInterno.objects.create(
                    caso=caso,
                    tipo_evento='ANDAMENTO',
                    descricao="Novo andamento adicionado.",
                    autor=request.user
                )
                return redirect(f"{reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})}?aba=andamentos")

        elif 'submit_timesheet' in request.POST:
            form_timesheet = TimesheetForm(request.POST, user=request.user)
            if form_timesheet.is_valid():
                novo_timesheet = form_timesheet.save(commit=False)
                tempo_str = request.POST.get('tempo', '00:00')
                try:
                    horas, minutos = map(int, tempo_str.split(':'))
                    novo_timesheet.tempo = timedelta(hours=horas, minutes=minutos)
                except (ValueError, TypeError):
                    form_timesheet.add_error('tempo', 'Formato inválido. Use HH:MM.')
                else:
                    novo_timesheet.caso = caso
                    novo_timesheet.save()
                    FluxoInterno.objects.create(
                        caso=caso,
                        tipo_evento='TIMESHEET',
                        descricao=f"Lançamento de {novo_timesheet.tempo}.",
                        autor=request.user
                    )
                    Andamento.objects.create(
                        caso=caso,
                        data_andamento=novo_timesheet.data_execucao,
                        descricao=f"Timesheet:\nTempo: {tempo_str}",
                        autor=request.user
                    )
                    return redirect(f"{reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})}?aba=timesheet")

        elif 'submit_acordo' in request.POST:
            form_acordo = AcordoForm(request.POST, user=request.user)
            if form_acordo.is_valid():
                novo_acordo = form_acordo.save(commit=False)
                novo_acordo.caso = caso
                novo_acordo.save()
                FluxoInterno.objects.create(
                    caso=caso,
                    tipo_evento='ACORDO',
                    descricao=f"Acordo de R$ {novo_acordo.valor_total}.",
                    autor=request.user
                )
                return redirect(f"{reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})}?aba=acordos")

        elif 'submit_despesa' in request.POST:
            form_despesa = DespesaForm(request.POST, user=request.user)
            if form_despesa.is_valid():
                nova_despesa = form_despesa.save(commit=False)
                nova_despesa.caso = caso
                nova_despesa.save()
                FluxoInterno.objects.create(
                    caso=caso,
                    tipo_evento='DESPESA',
                    descricao=f"Despesa de R$ {nova_despesa.valor}.",
                    autor=request.user
                )
                return redirect(f"{reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})}?aba=despesas")

    # Busca estrutura e valores
    estrutura = EstruturaDeCampos.objects.filter(
        cliente=caso.cliente,
        produto=caso.produto
    ).prefetch_related('campos').first()
    
    valores_para_template = []

    if estrutura:
        valores_salvos_dict = {
            valor.campo.id: valor
            for valor in caso.valores_personalizados.select_related('campo').all()
        }
        campos_ordenados = estrutura.campos.all().order_by('estruturacampoordenado__order')

        for campo_definicao in campos_ordenados:
            valor_salvo = valores_salvos_dict.get(campo_definicao.id)
            if valor_salvo:
                valor_salvo.valor_tratado = valor_salvo.valor
                
                # Tratamento de data
                if campo_definicao.tipo_campo == 'DATA' and valor_salvo.valor:
                    try:
                        valor_salvo.valor_tratado = datetime.strptime(
                            valor_salvo.valor.split(' ')[0],
                            '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        pass
                
                # Tratamento de moeda
                elif campo_definicao.tipo_campo == 'MOEDA' and valor_salvo.valor:
                    try:
                        valor_decimal = Decimal(valor_salvo.valor)
                        valor_salvo.valor_tratado = f"R$ {number_format(valor_decimal, decimal_pos=2, force_grouping=True)}"
                    except (InvalidOperation, ValueError):
                        pass
                
                valores_para_template.append(valor_salvo)
            else:
                placeholder = ValorCampoPersonalizado(campo=campo_definicao, valor=None)
                placeholder.valor_tratado = None
                valores_para_template.append(placeholder)

    grupos_de_valores_salvos = caso.grupos_de_valores.select_related(
        'grupo'
    ).prefetch_related(
        'valores__campo'
    ).order_by('grupo__nome_grupo', 'ordem_instancia')

    # Dados adicionais
    andamentos = caso.andamentos.select_related('autor').all()
    modelos_andamento = ModeloAndamento.objects.all()
    timesheets = caso.timesheets.select_related('advogado').all()
    acordos = caso.acordos.prefetch_related('parcelas').all()
    despesas = caso.despesas.select_related('advogado').all()
    historico_fases = caso.historico_fases.select_related('fase').order_by('data_entrada')
    acoes_pendentes = caso.acoes_pendentes.filter(status='PENDENTE').select_related('acao', 'responsavel')
    acoes_concluidas = caso.acoes_pendentes.filter(status='CONCLUIDA').select_related('acao', 'concluida_por').order_by('-data_conclusao')

    # Agregações
    soma_tempo_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_tempo_obj['total_tempo']
    saldo_devedor_total = sum(
        sum(p.valor_parcela for p in acordo.parcelas.all() if p.status == 'EMITIDA')
        for acordo in acordos
    )
    soma_despesas_obj = despesas.aggregate(total_despesas=Sum('valor'))
    total_despesas = soma_despesas_obj['total_despesas'] or Decimal('0.00')
    fluxo_interno = caso.fluxo_interno.select_related('autor').all()

    # SharePoint anexos
    itens_anexos = []
    folder_name = "Raiz"
    if caso.sharepoint_folder_id:
        try:
            sp = SharePoint()
            itens_anexos = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
        except Exception as e:
            logger.error(f"Erro ao buscar anexos: {e}")

    context = {
        'caso': caso,
        'form_andamento': form_andamento,
        'form_timesheet': form_timesheet,
        'form_acordo': form_acordo,
        'form_despesa': form_despesa,
        'valores_personalizados': valores_para_template,
        'grupos_de_valores_salvos': grupos_de_valores_salvos,
        'andamentos': andamentos,
        'modelos_andamento': modelos_andamento,
        'timesheets': timesheets,
        'acordos': acordos,
        'despesas': despesas,
        'historico_fases': historico_fases,
        'acoes_pendentes': acoes_pendentes,
        'acoes_concluidas': acoes_concluidas,
        'fluxo_interno': fluxo_interno,
        'tempo_total': tempo_total,
        'saldo_devedor_total': saldo_devedor_total,
        'total_despesas': total_despesas,
        'itens': itens_anexos,
        'folder_id': caso.sharepoint_folder_id,
        'root_folder_id': caso.sharepoint_folder_id,
        'folder_name': folder_name,
    }

    return render(request, 'casos/detalhe_caso.html', context)


# ==============================================================================
# EDITAR CASO (✅ CORRIGIDO)
# ==============================================================================

@login_required
def editar_caso(request, pk):
    """Edita um caso existente."""
    caso = get_object_or_404(Caso, pk=pk)
    cliente = caso.cliente
    produto = caso.produto

    try:
        estrutura = EstruturaDeCampos.objects.prefetch_related(
            'campos',
            'grupos_repetiveis__campos'
        ).get(cliente=cliente, produto=produto)
    except EstruturaDeCampos.DoesNotExist:
        messages.error(request, "Estrutura de campos não definida.")
        return redirect('casos:lista_casos')

    # Form principal
    if request.method == 'POST':
        form = CasoDinamicoForm(
            request.POST,
            instance=caso,
            cliente=cliente,
            produto=produto
        )
    else:
        form = CasoDinamicoForm(
            instance=caso,
            cliente=cliente,
            produto=produto
        )

    # Formsets para grupos
    grupo_formsets = {}
    for grupo in estrutura.grupos_repetiveis.all():
        GrupoFormSet = formset_factory(BaseGrupoForm, extra=0, can_delete=True)
        prefix = f'grupo_{grupo.id}'
        kwargs = {'grupo_campos': grupo, 'cliente': cliente, 'produto': produto}

        # Dados iniciais
        instancias_salvas = caso.grupos_de_valores.filter(grupo=grupo).prefetch_related('valores__campo')
        initial_data = []
        for instancia in instancias_salvas:
            dados_instancia = {}
            for valor in instancia.valores.all():
                dados_instancia[f'campo_personalizado_{valor.campo.id}'] = valor.valor
            initial_data.append(dados_instancia)

        if not initial_data:
            initial_data = [{}]

        if request.method == 'POST':
            formset = GrupoFormSet(request.POST, prefix=prefix, form_kwargs=kwargs, initial=initial_data)
        else:
            formset = GrupoFormSet(prefix=prefix, form_kwargs=kwargs, initial=initial_data)
        
        grupo_formsets[grupo.id] = (grupo, formset)

    # Processamento POST
    if request.method == 'POST':
        formsets_validos = all(fs.is_valid() for _, fs in grupo_formsets.values())

        if form.is_valid() and formsets_validos:
            try:
                with transaction.atomic():
                    # Gera título
                    dados_titulo_combinados = {}
                    for campo in estrutura.campos.all():
                        valor = form.cleaned_data.get(f'campo_personalizado_{campo.id}') or ''
                        dados_titulo_combinados[campo.nome_variavel] = str(valor)

                    for grupo, formset in grupo_formsets.values():
                        for form_grupo in formset.forms:
                            if form_grupo.has_changed() and not form_grupo.cleaned_data.get('DELETE', False):
                                for campo_grupo in grupo.campos.all():
                                    valor = form_grupo.cleaned_data.get(f'campo_personalizado_{campo_grupo.id}') or ''
                                    dados_titulo_combinados[campo_grupo.nome_variavel] = str(valor)

                    titulo_final = produto.padrao_titulo or form.cleaned_data.get('titulo_manual', '')
                    for chave, valor in dados_titulo_combinados.items():
                        titulo_final = titulo_final.replace(f'{{{chave}}}', valor)

                    # Salva caso
                    caso = form.save(commit=False)
                    caso.titulo = titulo_final
                    caso.save()
                    form.save_m2m()

                    # Remove valores antigos
                    caso.valores_personalizados.all().delete()
                    caso.grupos_de_valores.all().delete()

                    # Salva campos simples
                    for campo in estrutura.campos.all():
                        valor = form.cleaned_data.get(f'campo_personalizado_{campo.id}')
                        if valor is not None:
                            if isinstance(valor, list):
                                valor = ', '.join(str(v) for v in valor)
                            
                            ValorCampoPersonalizado.objects.create(
                                caso=caso,
                                instancia_grupo=None,
                                campo=campo,
                                valor=str(valor)
                            )

                    # Salva grupos
                    for grupo, formset in grupo_formsets.values():
                        for index, form_grupo in enumerate(formset.forms):
                            if form_grupo.has_changed() and not form_grupo.cleaned_data.get('DELETE', False):
                                instancia = InstanciaGrupoValor.objects.create(
                                    caso=caso,
                                    grupo=grupo,
                                    ordem_instancia=index
                                )
                                for campo_grupo in grupo.campos.all():
                                    valor = form_grupo.cleaned_data.get(f'campo_personalizado_{campo_grupo.id}')
                                    if valor is not None:
                                        if isinstance(valor, list):
                                            valor = ', '.join(str(v) for v in valor)
                                        
                                        ValorCampoPersonalizado.objects.create(
                                            caso=None,
                                            instancia_grupo=instancia,
                                            campo=campo_grupo,
                                            valor=str(valor)
                                        )

                messages.success(request, f"✅ Caso '{caso.titulo}' editado com sucesso.")
                return redirect('casos:detalhe_caso', pk=caso.pk)

            except Exception as e:
                logger.error(f"Erro ao atualizar caso: {e}", exc_info=True)
                messages.error(request, f"❌ Erro ao atualizar: {e}")

    context = {
        'caso': caso,
        'form': form,
        'grupo_formsets': grupo_formsets.values()
    }
    return render(request, 'casos/editar_caso.html', context)


# ==============================================================================
# EXPORTAÇÃO EXCEL
# ==============================================================================

@login_required
def exportar_casos_excel(request):
    """Exporta casos filtrados para Excel."""
    logger.info(f"Exportação iniciada por: {request.user.username}")
    
    # Filtros
    filtro_titulo = request.GET.get('filtro_titulo', '')
    filtro_cliente_id = request.GET.get('filtro_cliente', '')
    filtro_produto_id = request.GET.get('filtro_produto', '')
    filtro_status = request.GET.get('filtro_status', '')
    filtro_advogado_id = request.GET.get('filtro_advogado', '')

    casos_queryset = Caso.objects.all().select_related(
        'cliente', 'produto', 'advogado_responsavel'
    ).prefetch_related(
        'valores_personalizados__campo'
    ).order_by('-data_entrada')

    if filtro_titulo:
        casos_queryset = casos_queryset.filter(titulo__icontains=filtro_titulo)
    if filtro_status:
        casos_queryset = casos_queryset.filter(status=filtro_status)
    if filtro_advogado_id:
        casos_queryset = casos_queryset.filter(advogado_responsavel_id=filtro_advogado_id)
    if filtro_cliente_id:
        casos_queryset = casos_queryset.filter(cliente_id=filtro_cliente_id)
    if filtro_produto_id:
        casos_queryset = casos_queryset.filter(produto_id=filtro_produto_id)

    total_casos = casos_queryset.count()
    logger.debug(f"{total_casos} casos para exportar.")
    
    if total_casos == 0:
        messages.warning(request, "Nenhum caso encontrado.")
        return redirect('casos:lista_casos')

    # Cabeçalho
    try:
        lista_chaves, lista_cabecalhos, campos_tipo_map = get_cabecalho_exportacao(
            cliente=None,
            produto=None
        )
    except Exception as e:
        logger.error(f"Erro ao gerar cabeçalho: {e}", exc_info=True)
        messages.error(request, "Erro ao gerar cabeçalho.")
        return redirect('casos:lista_casos')
    
    # Excel
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Exportacao Casos'
    
    sheet.append(lista_cabecalhos)
    
    # Linhas de dados
    for caso in casos_queryset:
        linha_dados = []
        
        valores_personalizados_case = {
            f'personalizado_{v.campo.nome_variavel}': v.valor
            for v in caso.valores_personalizados.all()
        }
        
        for chave in lista_chaves:
            valor = ''

            # Campo Fixo
            if not chave.startswith('personalizado_'):
                if '__' in chave:
                    try:
                        partes = chave.split('__')
                        obj = getattr(caso, partes[0], None)
                        valor = getattr(obj, partes[1], '') if obj else ''
                    except Exception:
                        valor = ''
                elif chave == 'status':
                    valor = caso.get_status_display()
                else:
                    valor = getattr(caso, chave, '')
            
            # Campo Personalizado
            else:
                valor = valores_personalizados_case.get(chave, '')
            
            # Formatação de data
            tipo_do_campo = campos_tipo_map.get(chave)
            
            if isinstance(valor, (datetime, date)):
                valor = valor.strftime('%d/%m/%Y')
            
            elif tipo_do_campo == 'DATA' and valor:
                parsed_date = None
                formatos_data = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y')
                for fmt in formatos_data:
                    try:
                        parsed_date = datetime.strptime(str(valor), fmt).date()
                        break
                    except (ValueError, TypeError):
                        continue
                
                if parsed_date:
                    valor = parsed_date.strftime('%d/%m/%Y')
                else:
                    valor = str(valor)
            
            else:
                valor = str(valor) if valor is not None else ''
                
            linha_dados.append(valor)

        sheet.append(linha_dados)
            
    # Resposta
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = 'casos_export_filtrado.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    logger.info(f"Exportação ({total_casos} casos) concluída.")
    return response


@login_required
def exportar_andamentos_excel(request, pk):
    """Exporta andamentos de um caso."""
    caso = get_object_or_404(Caso, pk=pk)
    andamentos = caso.andamentos.select_related('autor').order_by('data_andamento')
    
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f'Andamentos Caso #{caso.id}'
    
    headers = ['Data do Andamento', 'Descrição', 'Criado por', 'Data de Criação']
    sheet.append(headers)
    
    for andamento in andamentos:
        autor_nome = '-'
        if andamento.autor:
            autor_nome = andamento.autor.get_full_name() or andamento.autor.username
        
        data_andamento_formatada = andamento.data_andamento.strftime('%d/%m/%Y')
        data_criacao_formatada = timezone.localtime(andamento.data_criacao).strftime('%d/%m/%Y %H:%M')
        
        sheet.append([
            data_andamento_formatada,
            andamento.descricao,
            autor_nome,
            data_criacao_formatada,
        ])
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="andamentos_caso_{caso.id}.xlsx"'
    workbook.save(response)
    return response


@login_required
def exportar_timesheet_excel(request, pk):
    """Exporta timesheet de um caso."""
    caso = get_object_or_404(Caso, pk=pk)
    timesheets = caso.timesheets.select_related('advogado').order_by('data_execucao')

    soma_total_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_total_obj['total_tempo'] or timedelta(0)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f'Timesheet Caso #{caso.id}'

    headers = ['Data da Execução', 'Advogado', 'Descrição', 'Tempo Gasto']
    sheet.append(headers)

    for ts in timesheets:
        advogado_nome = '-'
        if ts.advogado:
            advogado_nome = ts.advogado.get_full_name() or ts.advogado.username
        
        tempo_str = str(ts.tempo)

        sheet.append([
            ts.data_execucao.strftime('%d/%m/%Y'),
            advogado_nome,
            ts.descricao,
            tempo_str,
        ])
    
    sheet.append([])
    
    from openpyxl.styles import Font
    bold_font = Font(bold=True)
    
    linha_total = ['', '', 'Total:', str(tempo_total)]
    sheet.append(linha_total)

    sheet['C' + str(sheet.max_row)].font = bold_font
    sheet['D' + str(sheet.max_row)].font = bold_font

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="timesheet_caso_{caso.id}.xlsx"'
    
    workbook.save(response)
    return response


@login_required
def exportar_timesheet_pdf(request, pk):
    """Exporta timesheet em PDF."""
    caso = get_object_or_404(Caso, pk=pk)
    timesheets = caso.timesheets.select_related('advogado').order_by('data_execucao')
    soma_total_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_total_obj['total_tempo'] or timedelta(0)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=inch/2,
        leftMargin=inch/2,
        topMargin=inch/2,
        bottomMargin=inch/2
    )
    
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Relatório de Timesheet - Caso #{caso.id}", styles['h1']))
    story.append(Paragraph(f"<b>Cliente:</b> {caso.cliente.nome}", styles['Normal']))
    story.append(Paragraph(f"<b>Produto:</b> {caso.produto.nome}", styles['Normal']))
    story.append(Spacer(1, 0.25*inch))

    data = [['Data', 'Advogado', 'Descrição', 'Tempo Gasto']]
    
    for ts in timesheets:
        advogado_nome = ts.advogado.get_full_name() or ts.advogado.username if ts.advogado else '-'
        data.append([
            ts.data_execucao.strftime('%d/%m/%Y'),
            advogado_nome,
            Paragraph(ts.descricao.replace('\n', '<br/>'), styles['Normal']),
            str(ts.tempo)
        ])

    data.append(['', '', Paragraph("<b>Total:</b>", styles['Normal']), Paragraph(f"<b>{str(tempo_total)}</b>", styles['Normal'])])

    table = Table(data, colWidths=[1.2*inch, 1.5*inch, 3.3*inch, 1.2*inch])
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ALIGN', (2, -1), (3, -1), 'RIGHT'),
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
    ])
    table.setStyle(style)
    
    story.append(table)
    doc.build(story)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="timesheet_caso_{caso.id}.pdf"'
    
    return response


# ==============================================================================
# EDIÇÃO DE TIMESHEET/DESPESA/ACORDO
# ==============================================================================

@login_required
def editar_timesheet(request, pk):
    """Edita um lançamento de timesheet."""
    timesheet = get_object_or_404(Timesheet, pk=pk)
    caso = timesheet.caso

    if request.method == 'POST':
        form = TimesheetForm(request.POST, instance=timesheet)
        if form.is_valid():
            ts_editado = form.save(commit=False)
            tempo_str = request.POST.get('tempo')
            try:
                horas, minutos = map(int, tempo_str.split(':'))
                ts_editado.tempo = timedelta(hours=horas, minutes=minutos)
            except (ValueError, TypeError):
                form.add_error('tempo', 'Formato inválido. Use HH:MM.')
            else:
                ts_editado.save()
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=timesheet')
    else:
        initial_data = {}
        if timesheet.tempo:
            total_seconds = int(timesheet.tempo.total_seconds())
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            initial_data['tempo'] = f"{str(horas).zfill(2)}:{str(minutos).zfill(2)}"
        
        form = TimesheetForm(instance=timesheet, initial=initial_data)

    context = {
        'form': form,
        'timesheet': timesheet,
        'caso': caso,
    }
    return render(request, 'casos/timesheet_form.html', context)


@login_required
def deletar_timesheet(request, pk):
    """Deleta um timesheet."""
    timesheet = get_object_or_404(Timesheet, pk=pk)
    caso = timesheet.caso

    if request.method == 'POST':
        timesheet.delete()
        url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
        return redirect(f'{url_destino}?aba=timesheet')
    
    context = {
        'timesheet': timesheet,
        'caso': caso,
    }
    return render(request, 'casos/timesheet_confirm_delete.html', context)


@require_POST
@login_required
def quitar_parcela(request, pk):
    """Toggle status de parcela (HTMX)."""
    parcela = get_object_or_404(Parcela, pk=pk)
    
    if parcela.status == 'QUITADA':
        parcela.status = 'EMITIDA'
        parcela.data_pagamento = None
    else:
        parcela.status = 'QUITADA'
        parcela.data_pagamento = date.today()
    
    parcela.save()
    
    return render(request, 'casos/partials/parcela_linha.html', {'parcela': parcela})


@login_required
def editar_acordo(request, pk):
    """Edita um acordo."""
    acordo = get_object_or_404(Acordo, pk=pk)
    caso = acordo.caso

    if request.method == 'POST':
        form = AcordoForm(request.POST, instance=acordo, user=request.user)
        if form.is_valid():
            acordo_editado = form.save()

            # Recria parcelas
            acordo_editado.parcelas.all().delete()

            valor_total = acordo_editado.valor_total
            num_parcelas = acordo_editado.numero_parcelas
            valor_parcela = round(Decimal(valor_total) / num_parcelas, 2)
            
            for i in range(num_parcelas):
                data_vencimento = acordo_editado.data_primeira_parcela + relativedelta(months=i)
                Parcela.objects.create(
                    acordo=acordo_editado,
                    numero_parcela=i + 1,
                    valor_parcela=valor_parcela,
                    data_vencimento=data_vencimento,
                )
            
            soma_parcelas = valor_parcela * num_parcelas
            diferenca = valor_total - soma_parcelas
            if diferenca != 0:
                ultima_parcela = acordo_editado.parcelas.order_by('-numero_parcela').first()
                if ultima_parcela:
                    ultima_parcela.valor_parcela += diferenca
                    ultima_parcela.save()
            
            url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
            return redirect(f'{url_destino}?aba=acordos')
    else:
        form = AcordoForm(instance=acordo, user=request.user)
    
    context = {
        'form_acordo': form,
        'acordo': acordo,
        'caso': caso,
    }
    return render(request, 'casos/acordo_form.html', context)


@login_required
def editar_despesa(request, pk):
    """Edita uma despesa."""
    despesa = get_object_or_404(Despesa, pk=pk)
    caso = despesa.caso
    
    if request.method == 'POST':
        form = DespesaForm(request.POST, instance=despesa, user=request.user)
        if form.is_valid():
            form.save()
            url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
            return redirect(f'{url_destino}?aba=despesas')
    else:
        form = DespesaForm(instance=despesa, user=request.user)
    
    context = {
        'form_despesa': form,
        'despesa': despesa,
        'caso': caso
    }
    return render(request, 'casos/despesa_form.html', context)


# ==============================================================================
# SHAREPOINT (HTMX)
# ==============================================================================

@login_required
def carregar_conteudo_pasta(request, folder_id):
    """Carrega conteúdo de pasta do SharePoint (HTMX)."""
    folder_name = "Raiz"
    try:
        sp = SharePoint()
        conteudo = sp.listar_conteudo_pasta(folder_id)
        
        if folder_id != request.GET.get('root_folder_id'):
            folder_details = sp.get_folder_details(folder_id)
            folder_name = folder_details.get('name')

    except Exception as e:
        conteudo = None
        logger.error(f"Erro ao buscar conteúdo: {e}")

    context = {
        'itens': conteudo,
        'folder_id': folder_id,
        'folder_name': folder_name,
        'root_folder_id': request.GET.get('root_folder_id', folder_id)
    }
    return render(request, 'casos/partials/lista_arquivos.html', context)


@require_POST
@login_required
def upload_arquivo_sharepoint(request, folder_id):
    """Upload de arquivo para SharePoint (HTMX)."""
    try:
        sp = SharePoint()
        files_uploaded = request.FILES.getlist('arquivos')
        
        if not files_uploaded:
            logger.warning("Nenhum arquivo enviado.")
            return HttpResponse("<p style='color: red;'>Nenhum arquivo selecionado.</p>", status=400)

        for file in files_uploaded:
            logger.info(f"Upload: {file.name}")
            sp.upload_arquivo(folder_id, file.name, file.read())

    except Exception as e:
        logger.error(f"Erro no upload: {e}", exc_info=True)
        return HttpResponse(f"<p style='color: red;'>Erro: {e}</p>", status=500)

    # Recarrega lista
    sp = SharePoint()
    root_folder_id = request.POST.get('root_folder_id')
    conteudo = sp.listar_conteudo_pasta(folder_id)
    
    folder_name = "Raiz"
    if root_folder_id != folder_id:
        try:
            folder_details = sp.get_folder_details(folder_id)
            folder_name = folder_details.get('name')
        except Exception:
            pass

    context = {
        'itens': conteudo,
        'folder_id': folder_id,
        'root_folder_id': root_folder_id,
        'folder_name': folder_name,
    }
    
    return render(request, 'casos/partials/lista_arquivos.html', context)


@login_required
def preview_anexo(request, item_id):
    """Gera preview de arquivo do SharePoint."""
    try:
        sp = SharePoint()
        preview_url = sp.get_preview_url(item_id)
    except Exception as e:
        return HttpResponse(f"<p style='color:red;'>Erro: {e}</p>")
    
    return HttpResponse(f'<iframe src="{preview_url}"></iframe>')


@require_POST
@login_required
def criar_pasta_sharepoint(request, parent_folder_id):
    """Cria subpasta no SharePoint (HTMX)."""
    try:
        nome_nova_pasta = request.POST.get('nome_pasta')
        if not nome_nova_pasta:
            return HttpResponse("<p style='color: red;'>Nome vazio.</p>", status=400)

        sp = SharePoint()
        sp.criar_subpasta(parent_folder_id, nome_nova_pasta)
    
    except Exception as e:
        logger.error(f"Erro ao criar pasta: {e}", exc_info=True)
        return HttpResponse(f"<p style='color: red;'>Erro: {e}</p>", status=500)

    # Recarrega lista
    sp = SharePoint()
    root_folder_id = request.POST.get('root_folder_id')
    conteudo = sp.listar_conteudo_pasta(parent_folder_id)
    
    folder_name = "Raiz"
    if root_folder_id != parent_folder_id:
        try:
            folder_details = sp.get_folder_details(parent_folder_id)
            folder_name = folder_details.get('name')
        except Exception:
            pass

    context = {
        'itens': conteudo,
        'folder_id': parent_folder_id,
        'root_folder_id': root_folder_id,
        'folder_name': folder_name,
    }
    return render(request, 'casos/partials/lista_arquivos.html', context)


@require_POST
@login_required
def excluir_anexo_sharepoint(request, item_id):
    """Exclui arquivo do SharePoint (HTMX)."""
    try:
        sp = SharePoint()
        sp.excluir_item(item_id)
        
    except Exception as e:
        logger.error(f"Erro ao excluir: {e}", exc_info=True)
        return HttpResponse(f"<p style='color:red;'>Erro: {e}</p>", status=400)
    
    # Força refresh da página
    response = HttpResponse(status=200)
    response['HX-Refresh'] = 'true'
    return response


# ==============================================================================
# API (DRF)
# ==============================================================================

class CasoAPIViewSet(viewsets.ModelViewSet):
    """API ViewSet para Casos."""
    queryset = Caso.objects.all().order_by('-data_criacao')
    serializer_class = CasoSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        """Auto-define data_encerramento ao mudar status."""
        if 'status' in serializer.validated_data:
            if serializer.validated_data['status'] == 'ENCERRADO':
                if not serializer.instance.data_encerramento:
                    serializer.validated_data['data_encerramento'] = timezone.now().date()
        serializer.save()


# ==============================================================================
# IMPORTAÇÃO/EXPORTAÇÃO DINÂMICA
# ==============================================================================

@login_required
def selecionar_filtros_exportacao(request):
    """Seleção de Cliente/Produto para exportação."""
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        
        if cliente_id and produto_id:
            return redirect('casos:exportar_casos_dinamico', cliente_id=cliente_id, produto_id=produto_id)
            
    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    
    context = {
        'clientes': clientes,
        'produtos': produtos,
        'titulo': 'Exportação Dinâmica de Casos'
    }
    return render(request, 'casos/selecionar_filtros_exportacao.html', context)


@login_required
def exportar_casos_dinamico(request, cliente_id, produto_id):
    """Exporta casos para Cliente+Produto específico."""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    produto = get_object_or_404(Produto, id=produto_id)

    lista_chaves, lista_cabecalhos = get_cabecalho_exportacao(cliente, produto)
    
    casos_queryset = Caso.objects.filter(
        cliente=cliente,
        produto=produto
    ).select_related(
        'cliente',
        'produto',
        'advogado_responsavel'
    ).prefetch_related(
        'valores_personalizados__campo'
    ).order_by('-data_entrada')
    
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f'Export_{produto.nome[:30]}'
    
    sheet.append(lista_cabecalhos)
    sheet.append(lista_chaves)
    
    for caso in casos_queryset:
        linha_dados = []
        
        valores_personalizados_case = {
            f'personalizado_{v.campo.nome_variavel}': v.valor
            for v in caso.valores_personalizados.all()
        }
        
        for chave in lista_chaves:
            valor = '-'

            if not chave.startswith('personalizado_'):
                if '__' in chave:
                    partes = chave.split('__')
                    obj = getattr(caso, partes[0], None)
                    valor = getattr(obj, partes[1], '-') if obj else '-'
                elif chave == 'status':
                    valor = caso.get_status_display()
                else:
                    valor = getattr(caso, chave, '-')
            else:
                valor = valores_personalizados_case.get(chave, '-')
            
            linha_dados.append(str(valor))

        sheet.append(linha_dados)
        
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'casos_{cliente.nome}_{produto.nome}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def importar_casos_view(request):
    """View de importação de casos via Excel."""
    if request.method == 'GET':
        try:
            clientes = Cliente.objects.all().order_by('nome')
            produtos = Produto.objects.all().order_by('nome')
            
            context = {
                'clientes': clientes,
                'produtos': produtos,
                'titulo': 'Importação Massiva de Casos'
            }
            return render(request, 'casos/importar_casos_form.html', context)
        
        except Exception as e:
            logger.error(f"Erro ao carregar importação: {e}", exc_info=True)
            messages.error(request, "Erro ao carregar página.")
            return redirect('casos:lista_casos')

    elif request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        arquivo_excel = request.FILES.get('arquivo_excel')

        if not (cliente_id and produto_id and arquivo_excel):
            messages.error(request, "Todos os campos são obrigatórios.")
            clientes = Cliente.objects.all().order_by('nome')
            produtos = Produto.objects.all().order_by('nome')
            context = {
                'clientes': clientes,
                'produtos': produtos,
                'titulo': 'Importação Massiva de Casos'
            }
            return render(request, 'casos/importar_casos_form.html', context)

        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            produto = get_object_or_404(Produto, id=produto_id)

            logger.info(f"Importação: {arquivo_excel.name} | C:{cliente_id} P:{produto_id} | User:{request.user.username}")

            # Busca estrutura
            lista_chaves_validas, _ = get_cabecalho_exportacao(cliente, produto)
            chaves_validas_set = set(lista_chaves_validas)
            
            estrutura_campos = EstruturaDeCampos.objects.filter(
                cliente=cliente,
                produto=produto
            ).prefetch_related('campos').first()

            campos_meta_map = {
                cm.nome_variavel: cm
                for cm in estrutura_campos.campos.all()
            } if estrutura_campos else {}
            
            logger.debug(f"Campos encontrados: {list(campos_meta_map.keys())}")

            # Carrega Excel
            workbook = openpyxl.load_workbook(arquivo_excel, data_only=True)
            sheet = workbook.active
            
            logger.info(f"Excel carregado: '{sheet.title}' | Linhas: {sheet.max_row}")

            if sheet.max_row < 2:
                raise ValidationError("Planilha vazia.")

            # Lê cabeçalho
            excel_headers_raw = [cell.value for cell in sheet[1]]
            excel_headers = [
                str(h).strip().lower().replace(' ', '_') if h else ''
                for h in excel_headers_raw
            ]
            
            logger.info(f"Cabeçalhos: {excel_headers_raw}")

            # Cria header_map
            header_map = {}
            variaveis_lower = {
                nome_var.lower(): nome_var
                for nome_var in campos_meta_map.keys()
            }

            for excel_header_norm in excel_headers:
                if not excel_header_norm:
                    continue

                chave_mapeada = None

                # Tentativa 1: Campo fixo
                if excel_header_norm in chaves_validas_set and not excel_header_norm.startswith('personalizado_') and '__' not in excel_header_norm:
                    chave_mapeada = excel_header_norm
                
                # Tentativa 2: Campo personalizado
                elif excel_header_norm in variaveis_lower:
                    nome_variavel_original = variaveis_lower[excel_header_norm]
                    chave_completa = f'personalizado_{nome_variavel_original}'
                    if chave_completa in chaves_validas_set:
                        chave_mapeada = nome_variavel_original
                
                # Tentativa 3: Com prefixo
                elif excel_header_norm.startswith('personalizado_'):
                    nome_base = excel_header_norm.split('personalizado_', 1)[1]
                    if nome_base in variaveis_lower:
                        nome_variavel_original = variaveis_lower[nome_base]
                        chave_completa = f'personalizado_{nome_variavel_original}'
                        if chave_completa in chaves_validas_set:
                            chave_mapeada = nome_variavel_original
                
                if chave_mapeada:
                    header_map[excel_header_norm] = chave_mapeada
                elif excel_header_norm:
                    logger.warning(f"Header '{excel_header_norm}' ignorado")
            
            logger.info(f"Header map: {header_map}")

            mapeamentos_uteis = {k: v for k, v in header_map.items() if k != '_row_index'}
            if not mapeamentos_uteis:
                raise ValidationError("Nenhum cabeçalho corresponde aos campos esperados.")

            # Prepara tarefas Celery
            total_linhas = sheet.max_row - 1
            delay_segundos = 10
            linhas_enviadas = 0

            logger.info(f"Enviando {total_linhas} tarefas (delay: {delay_segundos}s)")

            campos_meta_map_serializable = {
                nome_var: campo.id
                for nome_var, campo in campos_meta_map.items()
            }

            for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                linha_dados = dict(zip(excel_headers, row))
                linha_dados['_row_index'] = row_index

                linha_dados_mapeada = {
                    k: v for k, v in linha_dados.items()
                    

                    if k in header_map or k == '_row_index'
                }
                
                if not any(v for k, v in linha_dados_mapeada.items() if k != '_row_index' and v is not None):
                    logger.info(f"Linha {row_index} vazia, pulada.")
                    continue

                logger.debug(f"Enviando linha {row_index} para Celery")

                processar_linha_importacao.apply_async(
                    args=[
                        linha_dados_mapeada,
                        cliente.id,
                        produto.id,
                        header_map,
                        list(chaves_validas_set),
                        campos_meta_map_serializable,
                        produto.padrao_titulo,
                        estrutura_campos.id if estrutura_campos else None
                    ],
                    countdown=linhas_enviadas * delay_segundos
                )
                linhas_enviadas += 1
            
            if linhas_enviadas == 0:
                messages.warning(request, "Nenhuma linha válida encontrada.")
                return redirect('casos:importar_casos_view')

            messages.success(
                request,
                f"✅ Importação iniciada! {linhas_enviadas} casos enviados para processamento. "
                f"Acompanhe os logs do Celery."
            )
            return redirect('casos:importar_casos_view')

        except ValidationError as e:
            logger.error(f"Erro de validação: {e.message}")
            messages.error(request, f"❌ Erro: {e.message}")
            clientes = Cliente.objects.all().order_by('nome')
            produtos = Produto.objects.all().order_by('nome')
            context = {
                'clientes': clientes,
                'produtos': produtos,
                'titulo': 'Importação Massiva de Casos'
            }
            return render(request, 'casos/importar_casos_form.html', context)
        
        except Exception as e:
            logger.error(f"Erro inesperado: {e}", exc_info=True)
            messages.error(request, "❌ Erro inesperado. Verifique os logs.")
            return redirect('casos:importar_casos_view')

    logger.warning(f"Método {request.method} inesperado")
    return redirect('casos:importar_casos_view')
@login_required
@require_POST
def editar_info_basicas(request, pk):
    """
    Edita informações básicas do caso via HTMX
    """
    caso = get_object_or_404(Caso, pk=pk)
    
    caso.status = request.POST.get('status')
    caso.data_entrada = request.POST.get('data_entrada')
    caso.valor_apurado = request.POST.get('valor_apurado')
    caso.advogado_responsavel_id = request.POST.get('advogado_responsavel')
    caso.save()
    
    # Retorna o card atualizado
    context = {'caso': caso}
    return render(request, 'casos/partials/card_info_basicas.html', context)


@login_required
@require_POST
def editar_dados_adicionais(request, pk):
    """
    Edita dados adicionais do caso via HTMX
    """
    caso = get_object_or_404(Caso, pk=pk)
    
    # Atualiza campos
    caso.sinistro_todo = request.POST.get('sinistro_todo')
    caso.acao = request.POST.get('acao')
    # ... outros campos ...
    caso.save()
    
    # Retorna o card atualizado
    context = {'caso': caso}
    return render(request, 'casos/partials/card_dados_adicionais.html', context)

@login_required
def visao_casos_prazo(request):
    """
    Nova tela que lista casos com foco no prazo final, com filtros avançados.
    """
    # 1. Busca inicial: pega todos os casos ativos
    casos_list = Caso.objects.select_related(
        'cliente', 'produto', 'advogado_responsavel'
    ).filter(status='ATIVO')

    # 2. Aplica os filtros padrão (Cliente, Produto, Advogado)
    filtro_cliente = request.GET.get('filtro_cliente', '')
    filtro_produto = request.GET.get('filtro_produto', '')
    filtro_advogado = request.GET.get('filtro_advogado', '')

    if filtro_cliente:
        casos_list = casos_list.filter(cliente_id=filtro_cliente)
    if filtro_produto:
        casos_list = casos_list.filter(produto_id=filtro_produto)
    if filtro_advogado:
        casos_list = casos_list.filter(advogado_responsavel_id=filtro_advogado)

    # 3. Aplica o filtro de data (feito em Python, pois o campo é calculado)
    prazo_inicio_str = request.GET.get('prazo_inicio', '')
    prazo_fim_str = request.GET.get('prazo_fim', '')
    
    casos_filtrados_final = []

    if prazo_inicio_str or prazo_fim_str:
        try:
            prazo_inicio = datetime.strptime(prazo_inicio_str, '%Y-%m-%d').date() if prazo_inicio_str else None
            prazo_fim = datetime.strptime(prazo_fim_str, '%Y-%m-%d').date() if prazo_fim_str else None

            for caso in casos_list:
                prazo_final = caso.prazo_final_calculado
                if prazo_final:
                    # Verifica se o prazo do caso está dentro do intervalo
                    if prazo_inicio and prazo_fim:
                        if prazo_inicio <= prazo_final <= prazo_fim:
                            casos_filtrados_final.append(caso)
                    elif prazo_inicio:
                        if prazo_final >= prazo_inicio:
                            casos_filtrados_final.append(caso)
                    elif prazo_fim:
                        if prazo_final <= prazo_fim:
                            casos_filtrados_final.append(caso)
            casos_list = casos_filtrados_final # Substitui a lista pela filtrada
        except ValueError:
            messages.error(request, "Formato de data inválido. Use AAAA-MM-DD.")
            casos_list = [] # Retorna uma lista vazia se a data for inválida
    
    # 4. Ordena a lista final pelo prazo (mais próximos primeiro)
    # Usamos uma chave de ordenação que lida com prazos nulos
    casos_list = sorted(
        casos_list, 
        key=lambda caso: caso.prazo_final_calculado or date.max, 
        reverse=False
    )
    
    context = {
        'casos': casos_list,
        'valores_filtro': request.GET,
        'todos_clientes': Cliente.objects.all().order_by('nome'),
        'todos_produtos': Produto.objects.all().order_by('nome'),
        'todos_advogados': User.objects.filter(is_active=True).order_by('first_name', 'username'),
        'hoje': date.today(), # Passa a data de hoje para o template
    }
    return render(request, 'casos/visao_casos_prazo.html', context)