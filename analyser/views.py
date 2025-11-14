# analyser/views.py

import logging
import json
import traceback

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse

from casos.models import Caso
from .models import ModeloAnalise, ResultadoAnalise
from .services import AnalyserService
from clientes.models import Cliente
from produtos.models import Produto
from campos_custom.models import EstruturaDeCampos

logger = logging.getLogger(__name__)


@login_required
def listar_modelos(request):
    """Lista modelos de análise."""
    modelos = ModeloAnalise.objects.select_related('cliente', 'produto').order_by('-data_criacao')
    context = {'modelos': modelos}
    return render(request, 'analyser/listar_modelos.html', context)


@login_required
def criar_ou_editar_modelo(request, pk=None):
    """Cria um novo modelo ou edita um existente."""
    modelo = get_object_or_404(ModeloAnalise, pk=pk) if pk else None

    if request.method == 'POST':
        try:
            nome = request.POST.get('nome')
            cliente_id = request.POST.get('cliente')
            produto_id = request.POST.get('produto')

            if not all([nome, cliente_id, produto_id]):
                raise ValueError("Nome, Cliente e Produto são obrigatórios.")

            descricoes_campos = {
                key.replace('descricao_', ''): value.strip()
                for key, value in request.POST.items() if key.startswith('descricao_') and value.strip()
            }

            fields_to_update = {
                'nome': nome,
                'descricao': request.POST.get('descricao', ''),
                'cliente_id': cliente_id,
                'produto_id': produto_id,
                'instrucoes_gerais': request.POST.get('instrucoes_gerais', ''),
                'gerar_resumo': request.POST.get('gerar_resumo') == 'on',
                'descricoes_campos': descricoes_campos,
                'criado_por': request.user if not modelo else modelo.criado_por
            }

            if modelo:
                for key, value in fields_to_update.items():
                    setattr(modelo, key, value)
                modelo.save()
                messages.success(request, f'✅ Modelo "{modelo.nome}" atualizado com sucesso!')
            else:
                modelo = ModeloAnalise.objects.create(**fields_to_update)
                messages.success(request, f'✅ Modelo "{modelo.nome}" criado com sucesso!')
            
            return redirect('analyser:listar_modelos')
        except Exception as e:
            messages.error(request, f"❌ Erro ao salvar o modelo: {e}")

    context = {
        'modelo': modelo,
        'campos': modelo.get_campos_para_extrair() if modelo else [],
        'clientes': Cliente.objects.all().order_by('nome'),
        'produtos': Produto.objects.all().order_by('nome'),
    }
    return render(request, 'analyser/criar_modelo.html', context)


@login_required
def ajax_buscar_campos(request):
    """
    AJAX: Retorna uma lista padronizada de campos (padrão + personalizados)
    para um determinado Cliente e Produto.
    """
    cliente_id = request.GET.get('cliente_id')
    produto_id = request.GET.get('produto_id')
    
    if not cliente_id or not produto_id:
        return JsonResponse({'campos': []})
    
    # --- 1. Define os campos padrão do sistema ---
    campos = [
        {'nome_variavel': 'titulo', 'nome_campo': 'Título do Caso', 'tipo_campo': 'TEXTO', 'is_padrao': True},
        {'nome_variavel': 'data_entrada', 'nome_campo': 'Data de Entrada', 'tipo_campo': 'DATA', 'is_padrao': True},
        {'nome_variavel': 'valor_apurado', 'nome_campo': 'Valor Apurado', 'tipo_campo': 'MOEDA', 'is_padrao': True},
    ]
    
    # --- 2. Busca e adiciona os campos personalizados ---
    try:
        # prefetch_related('campos') otimiza a consulta, buscando todos os campos
        # relacionados em uma única query adicional, evitando o problema N+1.
        estrutura = EstruturaDeCampos.objects.prefetch_related('campos').get(
            cliente_id=cliente_id, 
            produto_id=produto_id
        )
        
        # Itera sobre os campos já carregados em memória
        for campo in estrutura.campos.all():
            campos.append({
                'nome_variavel': campo.nome_variavel,
                'nome_campo': campo.nome_campo,
                'tipo_campo': campo.tipo_campo,
                'is_padrao': False,
                'campo_id': campo.id  # Mantém o ID se for útil no frontend
            })
            
    except EstruturaDeCampos.DoesNotExist:
        # Se não houver estrutura, a função simplesmente retornará os campos padrão.
        pass
    
    # --- 3. Retorna a lista completa como JSON ---
    return JsonResponse({'campos': campos})

@login_required
def selecionar_arquivos(request, caso_id):
    """Tela para selecionar arquivos e modelo para análise."""
    caso = get_object_or_404(Caso, pk=caso_id)
    modelos = ModeloAnalise.objects.filter(
        cliente=caso.cliente, produto=caso.produto, ativo=True
    ).order_by('nome')
    analises_anteriores = ResultadoAnalise.objects.filter(caso=caso).order_by('-data_criacao')[:5]
    
    context = {
        'caso': caso,
        'modelos': modelos,
        'tem_modelos': modelos.exists(),
        'analises_anteriores': analises_anteriores,
    }
    return render(request, 'analyser/selecionar_arquivos.html', context)


# analyser/views.py

@login_required
def iniciar_analise(request, caso_id):
    """
    Valida os dados do formulário e dispara o processo de análise.
    """
    if request.method != 'POST':
        return redirect('analyser:selecionar_arquivos', caso_id=caso_id)

    logger.info(f"🚀 [VIEW: iniciar_analise] - Requisição recebida para Caso ID: {caso_id} por {request.user.username}")

    caso = get_object_or_404(Caso, pk=caso_id)
    modelo_id = request.POST.get('modelo_id')
    arquivos_json_str = request.POST.get('arquivos_selecionados_ids')

    logger.info(f"📋 Dados recebidos: Modelo ID={modelo_id}, Arquivos JSON='{arquivos_json_str}'")

    # --- 1. Validação dos Dados de Entrada ---
    try:
        if not modelo_id or not arquivos_json_str:
            raise ValueError("Modelo e arquivos são obrigatórios.")
        
        modelo = get_object_or_404(ModeloAnalise, pk=modelo_id)
        arquivos_info = json.loads(arquivos_json_str)
        
        if not isinstance(arquivos_info, list) or not arquivos_info:
            raise ValueError("A lista de arquivos selecionados é inválida ou está vazia.")

    except (ValueError, json.JSONDecodeError, ModeloAnalise.DoesNotExist) as e:
        logger.error(f"❌ Erro de validação na entrada: {e}")
        messages.error(request, f"Erro nos dados enviados: {e}")
        return redirect('analyser:selecionar_arquivos', caso_id=caso_id)

    # --- 2. Disparar a Análise ---
    try:
        logger.info(f"✅ Dados validados. Modelo: '{modelo.nome}', Arquivos: {len(arquivos_info)}. Disparando análise...")

        # =================================================================
        # PONTO DE MELHORIA FUTURA: Mover para uma tarefa Celery
        # from .tasks import executar_analise_task
        # executar_analise_task.delay(caso.id, modelo.id, arquivos_info, request.user.id)
        # =================================================================
        
        # Por enquanto, executamos diretamente (sincronamente)
        service = AnalyserService(
            caso=caso,
            modelo_analise=modelo,
            arquivos_selecionados=arquivos_info,
            usuario=request.user
        )
        resultado = service.executar_analise()
        
        # --- 3. Tratar o Resultado da Execução Síncrona ---
        if resultado.status == 'CONCLUIDO':
            logger.info(f"✅ SUCESSO: Análise síncrona concluída. Redirecionando para resultado ID: {resultado.id}")
            messages.success(request, f"Análise com o modelo '{modelo.nome}' foi concluída com sucesso!")
            return redirect('analyser:resultado_analise', resultado_id=resultado.id)
        else:
            logger.error(f"❌ FALHA: Análise síncrona terminou com status '{resultado.status}'. Mensagem: {resultado.mensagem_erro}")
            messages.error(request, f"A análise falhou: {resultado.mensagem_erro}")
            return redirect('analyser:selecionar_arquivos', caso_id=caso_id)

    except Exception as e:
        logger.error(f"❌ Erro inesperado ao instanciar ou executar o AnalyserService: {e}", exc_info=True)
        messages.error(request, f"Ocorreu um erro inesperado ao iniciar a análise: {e}")
        return redirect('analyser:selecionar_arquivos', caso_id=caso_id)

@login_required
def carregar_arquivos_sharepoint(request, caso_id):
    """
    View para o HTMX buscar e renderizar a árvore de arquivos do SharePoint.
    Agora suporta carregar conteúdo de subpastas.
    """
    caso = get_object_or_404(Caso, pk=caso_id)
    
    # Pega o ID da pasta da URL (se for uma subpasta) ou usa a raiz do caso
    folder_id = request.GET.get('folder_id', caso.sharepoint_folder_id)

    if not folder_id:
        return HttpResponse("<div class='alert alert-warning'>⚠️ Este caso não possui uma pasta no SharePoint.</div>")

    try:
        from integrations.sharepoint import SharePoint
        sp = SharePoint()
        conteudo = sp.listar_conteudo_pasta(folder_id)

        pastas = []
        arquivos = []
        for item in conteudo:
            # Formata o item para o template
            tipo = item.get('file', {}).get('mimeType', '')
            icona_css, cor_css = "fa-solid fa-file", "#64748b"
            if 'folder' in item:
                icona_css, cor_css = "fa-solid fa-folder", "#f59e0b"
            elif 'pdf' in tipo: icona_css, cor_css = "fa-solid fa-file-pdf", "#ef4444"
            elif 'word' in tipo: icona_css, cor_css = "fa-solid fa-file-word", "#2563eb"
            # ... adicione mais tipos se precisar

            item_formatado = {
                'id': item['id'],
                'name': item['name'],
                'is_folder': 'folder' in item,
                'icona_css': icona_css,
                'cor_css': cor_css
            }
            
            if item_formatado['is_folder']:
                pastas.append(item_formatado)
            else:
                arquivos.append(item_formatado)

    except Exception as e:
        return HttpResponse(f"<div class='alert alert-warning'>❌ Erro ao conectar com o SharePoint: {e}</div>")
        
    context = {
        'pastas': sorted(pastas, key=lambda p: p['name']),
        'arquivos': sorted(arquivos, key=lambda a: a['name']),
        'caso_id': caso_id,
    }
    return render(request, 'analyser/partials/arvore_arquivos.html', context)
@login_required
def resultado_analise(request, resultado_id):
    """Exibe resultado de uma análise."""
    resultado = get_object_or_404(ResultadoAnalise.objects.select_related('caso', 'modelo_usado'), pk=resultado_id)
    logs = resultado.logs.all().order_by('timestamp')
    context = {'resultado': resultado, 'caso': resultado.caso, 'logs': logs}
    return render(request, 'analyser/resultado_analise.html', context)


@login_required
def aplicar_ao_caso(request, resultado_id):
    """Aplica dados extraídos por uma análise ao caso."""
    resultado = get_object_or_404(ResultadoAnalise, pk=resultado_id)
    
    if resultado.status != 'CONCLUIDO' or resultado.aplicado_ao_caso:
        messages.warning(request, 'Esta análise não pode ser (ou já foi) aplicada.')
        return redirect('analyser:resultado_analise', resultado_id=resultado.id)
    
    try:
        service = AnalyserService(
            caso=resultado.caso,
            modelo_analise=resultado.modelo_usado,
            arquivos_selecionados=resultado.arquivos_analisados,
            usuario=request.user
        )
        service.resultado = resultado # Atribui o resultado existente ao service
        service.aplicar_ao_caso()
        
        messages.success(request, f'✅ Dados da análise foram aplicados ao Caso #{resultado.caso.id}!')
        return redirect('casos:detalhe_caso', pk=resultado.caso.id)
        
    except Exception as e:
        messages.error(request, f'❌ Erro ao aplicar dados: {str(e)}')
        return redirect('analyser:resultado_analise', resultado_id=resultado.id)


@login_required
def deletar_modelo(request, pk):
    """Deleta um modelo de análise."""
    modelo = get_object_or_404(ModeloAnalise, pk=pk)
    if request.method == 'POST':
        nome = modelo.nome
        modelo.delete()
        messages.success(request, f'✅ Modelo "{nome}" deletado com sucesso!')
        return redirect('analyser:listar_modelos')
    return render(request, 'analyser/confirmar_delete.html', {'modelo': modelo})