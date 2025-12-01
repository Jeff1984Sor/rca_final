# casos/views.py
# ==============================================================================
# Sistema de Gestão de Casos - Views Principais
# ==============================================================================

# ==============================================================================
# 1. IMPORTS PADRÃO DO PYTHON
# ==============================================================================
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.urls import reverse
from django.db.models import Sum
from django.views.decorators.http import require_POST
from django.forms import formset_factory
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, date
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication # ✅ ADICIONE ESTA LINHA
from rest_framework.permissions import IsAuthenticated

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
    FluxoInterno
)
from .forms import (
    CasoDinamicoForm,
    AndamentoForm,
    TimesheetForm,
    AcordoForm,
    DespesaForm,
    BaseGrupoForm,
    # Adicionando os forms dos modais que criamos
    CasoInfoBasicasForm,
    CasoDadosAdicionaisForm
)
from .folder_utils import recriar_estrutura_de_pastas
from .serializers import CasoSerializer

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
@require_POST
@login_required
def recriar_pastas_sharepoint(request, pk):
    """
    View chamada por um botão para forçar a recriação da estrutura de pastas.
    """
    caso = get_object_or_404(Caso, pk=pk)
    try:
        # Limpa o ID antigo e inválido antes de tentar de novo
        caso.sharepoint_folder_id = None
        caso.save(update_fields=['sharepoint_folder_id'])

        # Chama a mesma lógica do signal
        folder_id = recriar_estrutura_de_pastas(caso)

        # Se tudo deu certo, renderiza a lista de arquivos da pasta recém-criada
        sp = SharePoint()
        conteudo = sp.listar_conteudo_pasta(folder_id)
        context = {
            'caso': caso,
            'itens': conteudo,
            'folder_id': folder_id,
            'root_folder_id': folder_id,
            'folder_name': "Raiz"
        }
        return render(request, 'casos/partials/lista_arquivos.html', context)

    except Exception as e:
        # Se falhar, retorna uma mensagem de erro clara para o usuário
        return HttpResponse(f"<div class='alert alert-danger'><strong>Falha ao recriar pastas:</strong> {e}</div>")
    
@login_required
def carregar_painel_anexos(request, pk):
    """Carrega o painel de anexos do SharePoint via HTMX"""
    caso = get_object_or_404(Caso, pk=pk)
    
    # ✅ NOVO: Detecta se está no modo analyser
    modo = request.GET.get('modo', 'anexos')
    
    # Se não tem pasta, mostra tela para criar
    if not caso.sharepoint_folder_id:
        logger.warning(f"Caso {pk} não possui pasta no SharePoint")
        return render(request, 'casos/partials/painel_anexos_criar.html', {'caso': caso})
    
    try:
        sp = SharePoint()
        
        # Verifica se a pasta existe
        try:
            folder_details = sp.get_item_details(caso.sharepoint_folder_id)
        except Exception as e:
            logger.error(f"Pasta {caso.sharepoint_folder_id} não encontrada: {e}")
            caso.sharepoint_folder_id = None
            caso.save()
            return render(request, 'casos/partials/painel_anexos_criar.html', {'caso': caso})
        
        # Lista o conteúdo
        itens = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
        
        context = {
            'caso': caso,
            'itens': itens,
            'folder_id': caso.sharepoint_folder_id,
            'root_folder_id': caso.sharepoint_folder_id,
            'folder_name': f"Caso #{caso.id}",
            'folder_details': folder_details,
            'modo': modo  # ✅ NOVO: Passa o modo para o template
        }
        
        logger.info(f"✅ {len(itens)} itens carregados para caso {pk} (modo: {modo})")
        
        # ✅ NOVO: Usa template diferente no modo analyser
        if modo == 'analyser':
            return render(request, 'casos/partials/painel_anexos_analyser.html', context)
        else:
            return render(request, 'casos/partials/painel_anexos.html', context)
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar anexos: {e}", exc_info=True)
        context = {
            'caso': caso,
            'mensagem_erro': f"Erro ao conectar ao SharePoint: {str(e)}"
        }
        return render(request, 'casos/partials/painel_anexos_erro.html', context)

@require_POST
@login_required
def criar_pastas_sharepoint(request, caso_pk):
    """Cria a estrutura de pastas do caso no SharePoint"""
    caso = get_object_or_404(Caso, pk=caso_pk)
    
    try:
        sp = SharePoint()
        
        # 1. Cria pasta do caso (usando o ID como nome)
        nome_pasta_caso = str(caso.id)
        logger.info(f"📁 Criando pasta: {nome_pasta_caso}")
        
        pasta_caso_id = sp.criar_pasta_caso(nome_pasta_caso)
        
        # 2. Salva o ID no modelo
        caso.sharepoint_folder_id = pasta_caso_id
        caso.save()
        
        logger.info(f"✅ Pasta criada: {pasta_caso_id}")
        
        # 3. Recarrega o painel
        return carregar_painel_anexos(request, caso_pk)
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar pastas: {e}", exc_info=True)
        return render(request, 'casos/partials/painel_anexos_erro.html', {
            'caso': caso,
            'mensagem_erro': f"Erro ao criar pasta: {str(e)}"
        })
@login_required
def baixar_arquivo_sharepoint(request, caso_pk, arquivo_id):
    """Download de arquivo"""
    caso = get_object_or_404(Caso, pk=caso_pk)
    
    try:
        sp = SharePoint()
        
        # Baixa o arquivo
        conteudo = sp.baixar_arquivo(arquivo_id)
        
        # Obtém o nome
        info = sp.obter_info_arquivo(arquivo_id)
        nome = info.get('name', 'arquivo')
        
        logger.info(f"✅ Download: {nome}")
        
        # Retorna o arquivo
        response = HttpResponse(conteudo, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{nome}"'
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Erro no download: {e}", exc_info=True)
        messages.error(request, f"Erro ao baixar: {str(e)}")
        return redirect('casos:detalhe_caso', pk=caso_pk)
    
@login_required
def listar_arquivos_para_analise(request, pk):
    """Lista arquivos para análise IA"""
    caso = get_object_or_404(Caso, pk=pk)
    
    try:
        sp = SharePoint()
        
        # Verifica se a pasta existe
        if not caso.sharepoint_folder_id:
            return JsonResponse({
                'success': False,
                'arquivos': [],
                'mensagem': 'Pasta não encontrada'
            })
        
        # Lista todos os itens
        itens = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
        
        # Filtra apenas arquivos (não pastas)
        arquivos = [
            {
                'id': item['id'],
                'name': item['name'],
                'size': item.get('size', 0),
                'mimeType': item.get('mimeType', 'application/octet-stream'),
                'webUrl': item.get('webUrl'),
            }
            for item in itens 
            if not item.get('folder')  # Exclui pastas
        ]
        
        logger.info(f"✅ {len(arquivos)} arquivo(s) encontrado(s)")
        
        return JsonResponse({
            'success': True,
            'arquivos': arquivos,
            'total': len(arquivos)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar arquivos: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
@login_required
def carregar_painel_analyser(request, pk):
    """Carrega o painel de análise IA com arquivos do caso"""
    caso = get_object_or_404(Caso, pk=pk)
    
    try:
        # Importa o modelo correto
        try:
            from analyser.models import ModeloAnalise
            modelos = ModeloAnalise.objects.all()
            logger.info(f"✅ {len(modelos)} modelos de análise encontrados")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar ModeloAnalise: {e}")
            modelos = []
        
        context = {
            'caso': caso,
            'modelos': modelos,
        }
        
        logger.info(f"✅ Carregando painel analyser para caso {pk}")
        return render(request, 'casos/partials/painel_analyser.html', context)
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar painel analyser: {e}", exc_info=True)
        return render(request, 'casos/partials/painel_analyser_erro.html', {
            'caso': caso,
            'erro': str(e)
        })
    
@require_POST
@login_required
def criar_pasta_para_caso(request, pk):
    """
    Cria a pasta principal para um caso e salva o ID no modelo.
    """
    caso = get_object_or_404(Caso, pk=pk)
    try:
        sp = SharePoint()
        # Cria a pasta usando o ID do caso como nome (ex: "29")
        folder_id = sp.criar_pasta_caso(str(caso.pk))
        
        # ✅ SALVA O NOVO ID NO CASO
        caso.sharepoint_folder_id = folder_id
        caso.save()

        # Após criar e salvar, renderiza o painel de arquivos já com a pasta vazia.
        conteudo = sp.listar_conteudo_pasta(folder_id)
        context = {
            'caso': caso,
            'itens': conteudo,
            'folder_id': folder_id,
            'root_folder_id': folder_id,
            'folder_name': "Raiz"
        }
        return render(request, 'casos/partials/lista_arquivos.html', context)
    except Exception as e:
        return HttpResponse(f"<div class='alert alert-danger'>Erro ao criar pasta: {e}</div>")

@require_POST
@login_required
def criar_pasta_raiz_sharepoint(request):
    """Cria uma nova pasta na raiz do SharePoint."""
    try:
        nome_nova_pasta = request.POST.get('nome_pasta')
        if not nome_nova_pasta:
            return HttpResponse("<p style='color: red;'>O nome da pasta não pode ser vazio.</p>", status=400)

        sp = SharePoint()
        # ✅ USA A FUNÇÃO CORRETA PARA CRIAR NA RAIZ
        sp.criar_pasta_caso(nome_nova_pasta) 
    
    except Exception as e:
        logger.error(f"Erro ao criar pasta na raiz: {e}", exc_info=True)
        return HttpResponse(f"<p style='color: red;'>Erro ao criar pasta: {e}</p>", status=500)

    # Após o sucesso, força um refresh completo da página para mostrar a nova pasta
    response = HttpResponse(status=200)
    response['HX-Refresh'] = 'true'
    return response

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

# casos/views.py

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

    # ========================================
    # 🎨 PROCESSAMENTO DOS MODALS DE EDIÇÃO (Sua lógica original mantida)
    # ========================================
    if request.method == 'POST':
        edit_modal = request.POST.get('edit_modal')
        
        # MODAL: Informações Básicas
        if edit_modal == 'info-basicas':
            try:
                caso.status = request.POST.get('status', caso.status)
                
                data_entrada = request.POST.get('data_entrada')
                if data_entrada:
                    caso.data_entrada = data_entrada
                
                valor_apurado = request.POST.get('valor_apurado', '').strip()
                if valor_apurado:
                    valor_apurado = valor_apurado.replace('R$', '').replace('.', '').replace(',', '.').strip()
                    caso.valor_apurado = Decimal(valor_apurado)
                
                advogado_id = request.POST.get('advogado_responsavel')
                if advogado_id:
                    caso.advogado_responsavel_id = advogado_id
                else:
                    caso.advogado_responsavel = None
                
                caso.save()
                
                FluxoInterno.objects.create(
                    caso=caso,
                    tipo_evento='EDICAO',
                    descricao='Informações básicas do caso foram atualizadas.',
                    autor=request.user
                )
                
                messages.success(request, '✅ Informações básicas atualizadas com sucesso!')
                return redirect('casos:detalhe_caso', pk=caso.pk)
            except Exception as e:
                messages.error(request, f'❌ Erro ao atualizar: {str(e)}')
                return redirect('casos:detalhe_caso', pk=caso.pk)
        
        # MODAL: Dados Adicionais (Campos Personalizados Simples)
        elif edit_modal == 'dados-adicionais':
            try:
                campos_atualizados = 0
                
                for key, value in request.POST.items():
                    if key.startswith('campo_'):
                        campo_id = key.replace('campo_', '')
                        try:
                            valor_obj = ValorCampoPersonalizado.objects.get(
                                caso=caso,
                                campo_id=campo_id,
                                instancia_grupo__isnull=True
                            )
                            valor_obj.valor = value
                            valor_obj.save()
                            campos_atualizados += 1
                        except ValorCampoPersonalizado.DoesNotExist:
                            try:
                                campo = CampoPersonalizado.objects.get(id=campo_id)
                                ValorCampoPersonalizado.objects.create(
                                    caso=caso,
                                    campo=campo,
                                    valor=value
                                )
                                campos_atualizados += 1
                            except:
                                pass
                
                # ✅ PROCESSAR CHECKBOXES NÃO MARCADOS (campos booleanos que são False)
                estrutura = EstruturaDeCampos.objects.filter(
                    cliente=caso.cliente,
                    produto=caso.produto
                ).prefetch_related('campos').first()
                
                if estrutura:
                    campos_booleanos = estrutura.campos.filter(tipo_campo='BOOLEANO')
                    
                    for campo_bool in campos_booleanos:
                        campo_key = f'campo_{campo_bool.id}'
                        if campo_key not in request.POST:
                            # Checkbox não veio no POST = estava desmarcado
                            try:
                                valor_obj = ValorCampoPersonalizado.objects.get(
                                    caso=caso,
                                    campo=campo_bool,
                                    instancia_grupo__isnull=True
                                )
                                valor_obj.valor = 'False'
                                valor_obj.save()
                            except ValorCampoPersonalizado.DoesNotExist:
                                ValorCampoPersonalizado.objects.create(
                                    caso=caso,
                                    campo=campo_bool,
                                    valor='False'
                                )
                
                FluxoInterno.objects.create(
                    caso=caso,
                    tipo_evento='EDICAO',
                    descricao=f'Dados adicionais atualizados ({campos_atualizados} campo(s)).',
                    autor=request.user
                )
                
                messages.success(request, f'✅ {campos_atualizados} campo(s) atualizado(s) com sucesso!')
                return redirect('casos:detalhe_caso', pk=caso.pk)
            except Exception as e:
                messages.error(request, f'❌ Erro ao atualizar: {str(e)}')
                return redirect('casos:detalhe_caso', pk=caso.pk)
        
        # MODAL: Grupos Repetíveis
        elif edit_modal and edit_modal.startswith('grupo-'):
            # ... (Sua lógica de grupo repetível original) ...
            pass
        
        # ========================================
        # 📝 FORMS NORMAIS (ANDAMENTO, TIMESHEET, ETC)
        # ========================================
        elif 'submit_andamento' in request.POST:
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
                
    # ========================================
    # 📊 PREPARAÇÃO DO CONTEXTO (GET)
    # ========================================
    
    # ✅ ADIÇÃO DAS 4 LINHAS NECESSÁRIAS AQUI
    form_info_basicas = CasoInfoBasicasForm(instance=caso)
    valores_personalizados_simples = caso.valores_personalizados.filter(
        instancia_grupo__isnull=True
    ).select_related('campo')
    form_dados_adicionais = CasoDadosAdicionaisForm(
        campos_personalizados=valores_personalizados_simples
    )
    
    # (O resto da sua lógica de contexto continua exatamente igual)
    
    # Busca estrutura e valores
    analises = caso.analises.all().order_by('-data_criacao')[:10]
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
                valores_para_template.append(valor_salvo)
            else:
                placeholder = ValorCampoPersonalizado(campo=campo_definicao, valor=None)
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
        'analises': analises,
        'folder_name': folder_name,
        
        # ✅ ADICIONANDO OS FORMULÁRIOS DOS MODAIS AO CONTEXTO
        'form_info_basicas': form_info_basicas,
        'form_dados_adicionais': form_dados_adicionais,
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
    """Carrega conteúdo de uma subpasta (navegação)"""
    caso_pk = request.GET.get('caso_pk')
    root_folder_id = request.GET.get('root_folder_id', folder_id)
    modo = request.GET.get('modo', 'anexos')  # ✅ NOVO
    
    caso = get_object_or_404(Caso, pk=caso_pk) if caso_pk else None
    
    try:
        sp = SharePoint()
        
        folder_details = sp.get_item_details(folder_id)
        itens = sp.listar_conteudo_pasta(folder_id)
        
        logger.info(f"📂 Navegando para '{folder_details.get('name')}' (modo: {modo})")
        
        context = {
            'caso': caso,
            'itens': itens,
            'folder_id': folder_id,
            'root_folder_id': root_folder_id,
            'folder_name': folder_details.get('name', 'Pasta'),
            'folder_details': folder_details,
            'modo': modo  # ✅ NOVO
        }
        
        # ✅ NOVO: Template diferente por modo
        if modo == 'analyser':
            return render(request, 'casos/partials/painel_anexos_analyser.html', context)
        else:
            return render(request, 'casos/partials/painel_anexos.html', context)
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar pasta: {e}", exc_info=True)
        return HttpResponse(f"<div class='alert alert-danger'>Erro: {e}</div>")

@login_required
def upload_arquivo_sharepoint(request, caso_pk):
    """Upload de arquivo via HTMX"""
    caso = get_object_or_404(Caso, pk=caso_pk)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        pasta_id = request.POST.get('pasta_id', caso.sharepoint_folder_id)
        arquivo = request.FILES.get('arquivo')
        
        if not arquivo:
            return JsonResponse({'error': 'Nenhum arquivo enviado'}, status=400)
        
        logger.info(f"📤 Upload: {arquivo.name} -> {pasta_id}")
        
        sp = SharePoint()
        resultado = sp.fazer_upload(arquivo, pasta_id)
        
        logger.info(f"✅ Upload concluído: {resultado}")
        
        # Recarrega o painel
        return carregar_painel_anexos(request, caso_pk)
        
    except Exception as e:
        logger.error(f"❌ Erro no upload: {e}", exc_info=True)
        return render(request, 'casos/partials/painel_anexos_erro.html', {
            'caso': caso,
            'mensagem_erro': f"Erro no upload: {str(e)}"
        })
@login_required
def deletar_arquivo_sharepoint(request, caso_pk):
    """Deleta um arquivo do SharePoint"""
    caso = get_object_or_404(Caso, pk=caso_pk)
    arquivo_id = request.GET.get('arquivo_id')
    
    if not arquivo_id:
        return JsonResponse({'error': 'ID do arquivo não fornecido'}, status=400)
    
    try:
        sp = SharePoint()
        
        # Obtém o nome antes de deletar (para log)
        try:
            info = sp.obter_info_arquivo(arquivo_id)
            nome = info.get('name', 'arquivo')
        except:
            nome = 'arquivo'
        
        # Deleta o arquivo
        sp.excluir_item(arquivo_id)
        
        logger.info(f"🗑️ Arquivo '{nome}' deletado com sucesso")
        
        # Recarrega o painel
        return carregar_painel_anexos(request, caso_pk)
        
    except Exception as e:
        logger.error(f"❌ Erro ao deletar arquivo: {e}", exc_info=True)
        return render(request, 'casos/partials/painel_anexos_erro.html', {
            'caso': caso,
            'mensagem_erro': f"Erro ao deletar arquivo: {str(e)}"
        })
    
@login_required
def preview_anexo(request, item_id):
    """Gera preview de arquivo do SharePoint."""
    try:
        sp = SharePoint()
        preview_url = sp.get_preview_url(item_id)
    except Exception as e:
        return HttpResponse(f"<p style='color:red;'>Erro: {e}</p>")
    
    return HttpResponse(f'<iframe src="{preview_url}"></iframe>')


@login_required
def criar_pasta_sharepoint(request, caso_pk):
    """Cria uma subpasta dentro da pasta do caso"""
    caso = get_object_or_404(Caso, pk=caso_pk)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        nome_pasta = request.POST.get('nome_pasta', '').strip()
        
        if not nome_pasta:
            return JsonResponse({'error': 'Nome obrigatório'}, status=400)
        
        sp = SharePoint()
        
        # Cria subpasta dentro da pasta do caso
        nova_pasta = sp.criar_subpasta(caso.sharepoint_folder_id, nome_pasta)
        
        logger.info(f"✅ Subpasta '{nome_pasta}' criada: {nova_pasta['id']}")
        
        # Recarrega o painel
        return carregar_painel_anexos(request, caso_pk)
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar subpasta: {e}", exc_info=True)
        return render(request, 'casos/partials/painel_anexos_erro.html', {
            'caso': caso,
            'mensagem_erro': f"Erro: {str(e)}"
        })


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

@login_required
def analyser_navegador(request, pk):
    """Carrega navegador de arquivos para o Analyser (raiz)"""
    caso = get_object_or_404(Caso, pk=pk)
    
    if not caso.sharepoint_folder_id:
        return HttpResponse(
            '<div class="analyser-empty-state">'
            '<i class="fa-solid fa-folder-plus"></i>'
            '<h3>Pasta não encontrada</h3>'
            '<p>Este caso ainda não possui pasta no SharePoint.</p>'
            '</div>'
        )
    
    try:
        sp = SharePoint()
        itens = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
        
        context = {
            'caso': caso,
            'itens': itens,
            'folder_id': caso.sharepoint_folder_id,
            'root_folder_id': caso.sharepoint_folder_id,
            'folder_name': f'Caso #{caso.id}'
        }
        
        return render(request, 'casos/partials/analyser_navegador.html', context)
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar navegador: {e}", exc_info=True)
        return HttpResponse(f'<div class="alert alert-danger">Erro: {e}</div>')


@login_required
def analyser_navegador_pasta(request, pk, folder_id):
    """Navega para uma subpasta no Analyser"""
    caso = get_object_or_404(Caso, pk=pk)
    root_folder_id = request.GET.get('root_folder_id', folder_id)
    
    try:
        sp = SharePoint()
        
        folder_details = sp.get_item_details(folder_id)
        itens = sp.listar_conteudo_pasta(folder_id)
        
        context = {
            'caso': caso,
            'itens': itens,
            'folder_id': folder_id,
            'root_folder_id': root_folder_id,
            'folder_name': folder_details.get('name', 'Pasta'),
            'folder_details': folder_details
        }
        
        return render(request, 'casos/partials/analyser_navegador.html', context)
        
    except Exception as e:
        logger.error(f"❌ Erro ao navegar: {e}", exc_info=True)
        return HttpResponse(f'<div class="alert alert-danger">Erro: {e}</div>')