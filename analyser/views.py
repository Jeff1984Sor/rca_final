# analyser/views.py - CORRIGIDO COM IMPORTS CERTOS

import logging
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from casos.models import Caso
from .models import ResultadoAnalise, LogAnalise, ModeloAnalise
from .services import AnalyserService
from integrations.sharepoint import SharePoint
from clientes.models import Cliente  # ✅ CORRIGIDO
from produtos.models import Produto  # ✅ CORRIGIDO
from campos_custom.models import CampoPersonalizado
from django.contrib import messages


logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def selecionar_arquivos(request, caso_id):
    """Página para seleção de arquivos e modelo para análise."""
    caso = get_object_or_404(Caso, id=caso_id)
    modelos = ModeloAnalise.objects.filter(ativo=True)
    
    try:
        sp = SharePoint()
        # Lista arquivos da RAIZ do SharePoint
        itens = sp.listar_arquivos_pasta_raiz()
        
        logger.info(f"📁 Encontrados {len(itens)} itens na raiz para o caso #{caso.id}")
        
    except Exception as e:
        logger.error(f"Erro ao listar arquivos do caso: {e}", exc_info=True)
        itens = []
    
    context = {
        'caso': caso,
        'modelos': modelos,
        'itens': itens,
    }
    return render(request, 'analyser/selecionar_arquivos.html', context)


@login_required
@require_http_methods(["GET"])
def carregar_arquivos_navegacao(request, caso_id):
    """HTMX - Carrega arquivos de uma subpasta."""
    folder_id = request.GET.get('folder_id')
    caso = get_object_or_404(Caso, id=caso_id)
    
    sp = SharePoint()
    itens = sp.listar_arquivos_pasta(folder_id) if folder_id else sp.listar_arquivos_pasta_raiz()
    
    context = {'itens': itens, 'caso': caso}
    return render(request, 'analyser/partials/_file_grid.html', context)


@login_required
@require_http_methods(["POST"])
def iniciar_analise(request, caso_id):
    """Inicia a análise com os arquivos selecionados."""
    caso = get_object_or_404(Caso, id=caso_id)
    
    modelo_id = request.POST.get('modelo_id')
    arquivos_ids = request.POST.getlist('arquivos_selecionados')
    
    if not modelo_id or not arquivos_ids:
        return JsonResponse({
            'type': 'log',
            'data': {'level': 'ERROR', 'message': '❌ Selecione um modelo e pelo menos um arquivo.'}
        })
    
    modelo = get_object_or_404(ModeloAnalise, id=modelo_id)
    sp = SharePoint()
    
    # Prepara informações dos arquivos
    arquivos_info = []
    for arquivo_id in arquivos_ids:
        item = sp.get_item_details(arquivo_id)
        arquivos_info.append({
            'id': arquivo_id,
            'name': item.get('name', 'desconhecido'),
            'type': item.get('file', {}).get('mimeType', 'application/pdf'),
        })
    
    # Cria resultado de análise
    resultado = ResultadoAnalise.objects.create(
        caso=caso,
        modelo_usado=modelo,
        arquivos_analisados=arquivos_info,
        status='PROCESSANDO',
        criado_por=request.user
    )
    
    # Inicia análise em background
    try:
        service = AnalyserService(caso, modelo, arquivos_info, request.user, resultado.id)
        service.executar_analise()
    except Exception as e:
        logger.error(f"Erro ao iniciar análise: {e}")
        resultado.status = 'ERRO'
        resultado.mensagem_erro = str(e)
        resultado.save()
    
    # Redireciona para resultado
    return redirect('analyser:resultado_analise', resultado_id=resultado.id)


@login_required
@require_http_methods(["GET"])
def resultado_analise(request, resultado_id):
    """Página com o resultado da análise e logs."""
    resultado = get_object_or_404(ResultadoAnalise, id=resultado_id)
    caso = resultado.caso
    
    context = {
        'resultado': resultado,
        'caso': caso,
    }
    return render(request, 'analyser/resultado_analise.html', context)


@login_required
@require_http_methods(["GET"])
def carregar_logs(request, resultado_id):
    """HTMX - Carrega e atualiza os logs da análise."""
    resultado = get_object_or_404(ResultadoAnalise, id=resultado_id)
    logs = resultado.logs.all().order_by('timestamp')
    
    context = {
        'resultado': resultado,
        'logs': logs,
    }
    return render(request, 'analyser/partials/lista_logs.html', context)


@login_required
@require_http_methods(["GET"])
def listar_modelos(request):
    """Lista todos os modelos de análise."""
    modelos = ModeloAnalise.objects.all().order_by('-data_criacao')
    
    context = {'modelos': modelos}
    return render(request, 'analyser/listar_modelos.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def criar_modelo(request):
    """Cria um novo modelo de análise."""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        instrucoes = request.POST.get('instrucoes_gerais', '')
        gerar_resumo = request.POST.get('gerar_resumo') == 'on'
        
        cliente = get_object_or_404(Cliente, id=cliente_id)
        produto = get_object_or_404(Produto, id=produto_id)
        
        # Verifica se já existe um modelo com este nome
        if ModeloAnalise.objects.filter(nome=nome, cliente=cliente, produto=produto).exists():
            messages.error(request, f"❌ Já existe um modelo chamado '{nome}' para {cliente.nome} - {produto.nome}. Use um nome diferente!")
            return redirect('analyser:criar_modelo')
        
        try:
            modelo = ModeloAnalise.objects.create(
                nome=nome,
                descricao=descricao,
                cliente=cliente,
                produto=produto,
                instrucoes_gerais=instrucoes,
                gerar_resumo=gerar_resumo,
                criado_por=request.user
            )
            
            # Salva descrições dos campos
            descricoes = {}
            for chave, valor in request.POST.items():
                if chave.startswith('descricao_') and chave != 'descricao':
                    nome_variavel = chave.replace('descricao_', '')
                    descricoes[nome_variavel] = valor
            
            modelo.descricoes_campos = descricoes
            modelo.save()
            
            logger.info(f"✅ Modelo '{nome}' criado com sucesso")
            messages.success(request, f"✅ Modelo '{nome}' criado com sucesso!")
            return redirect('analyser:listar_modelos')
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar modelo: {e}")
            messages.error(request, f"❌ Erro ao criar modelo: {str(e)}")
            return redirect('analyser:criar_modelo')
    
    clientes = Cliente.objects.all()
    produtos = Produto.objects.all()
    
    context = {
        'clientes': clientes,
        'produtos': produtos,
    }
    return render(request, 'analyser/criar_modelo.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def editar_modelo(request, pk):
    """Edita um modelo existente."""
    modelo = get_object_or_404(ModeloAnalise, id=pk)
    
    if request.method == 'POST':
        modelo.nome = request.POST.get('nome')
        modelo.descricao = request.POST.get('descricao', '')
        modelo.instrucoes_gerais = request.POST.get('instrucoes_gerais', '')
        modelo.gerar_resumo = request.POST.get('gerar_resumo') == 'on'
        
        descricoes = {}
        
        # Percorre todos os dados POST procurando por descricao_*
        for chave, valor in request.POST.items():
            if chave.startswith('descricao_') and chave != 'descricao':
                nome_variavel = chave.replace('descricao_', '')
                descricoes[nome_variavel] = valor
        
        modelo.descricoes_campos = descricoes
        modelo.save()
        
        logger.info(f"✅ Modelo '{modelo.nome}' atualizado com sucesso")
        return redirect('analyser:listar_modelos')
    
    clientes = Cliente.objects.all()
    produtos = Produto.objects.all()
    
    context = {
        'modelo': modelo,
        'clientes': clientes,
        'produtos': produtos,
    }
    return render(request, 'analyser/criar_modelo.html', context)

@login_required
@require_http_methods(["POST"])
def deletar_modelo(request, pk):
    """Deleta um modelo de análise."""
    modelo = get_object_or_404(ModeloAnalise, id=pk)
    modelo.delete()
    return redirect('analyser:listar_modelos')


@login_required
@require_http_methods(["GET"])
def ajax_buscar_campos(request):
    """AJAX - Busca campos para um cliente e produto."""
    cliente_id = request.GET.get('cliente_id')
    produto_id = request.GET.get('produto_id')
    
    logger.info(f"🔍 Buscando campos - Cliente: {cliente_id}, Produto: {produto_id}")
    
    try:
        from campos_custom.models import EstruturaDeCampos
        
        # Busca a Estrutura de Campos para este cliente e produto
        estrutura = EstruturaDeCampos.objects.filter(
            cliente_id=cliente_id,
            produto_id=produto_id
        ).first()
        
        if not estrutura:
            logger.warning(f"⚠️ Nenhuma estrutura encontrada para Cliente {cliente_id}, Produto {produto_id}")
            return JsonResponse({'campos': []})
        
        # Busca os campos da estrutura
        campos = estrutura.campos.all().values('id', 'nome_campo', 'nome_variavel', 'tipo_campo')
        
        campos_list = list(campos)
        logger.info(f"✅ Encontrados {len(campos_list)} campos")
        
        return JsonResponse({'campos': campos_list})
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar campos: {e}", exc_info=True)
        return JsonResponse({
            'campos': [],
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def aplicar_ao_caso(request, resultado_id):
    """Aplica os dados da análise ao caso."""
    resultado = get_object_or_404(ResultadoAnalise, id=resultado_id)
    
    if resultado.status != 'CONCLUIDO':
        logger.warning(f"❌ Tentativa de aplicar análise não concluída: {resultado_id}")
        return JsonResponse({
            'error': 'Análise não foi concluída. Status atual: ' + resultado.status
        }, status=400)
    
    try:
        logger.info(f"📊 Aplicando dados da análise #{resultado_id} ao caso #{resultado.caso.id}...")
        
        service = AnalyserService(
            resultado.caso,
            resultado.modelo_usado,
            resultado.arquivos_analisados,
            request.user,
            resultado.id
        )
        
        # Aplica os dados
        service.aplicar_ao_caso()
        
        logger.info(f"✅ Dados aplicados com sucesso ao caso #{resultado.caso.id}")
        
        return JsonResponse({
            'success': True,
            'message': '✅ Dados aplicados com sucesso ao caso!',
            'caso_url': f'/casos/{resultado.caso.id}/'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao aplicar dados: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Erro ao aplicar dados: {str(e)}'
        }, status=400)


# ============================================================================
# DEBUG - FUNÇÃO DE DIAGNÓSTICO
# ============================================================================

@login_required
@require_http_methods(["GET"])
def debug_pasta_caso(request, caso_id):
    """Debug - Mostra a estrutura de pastas do caso."""
    caso = get_object_or_404(Caso, id=caso_id)
    
    try:
        sp = SharePoint()
        nome_pasta = f"Caso #{caso.id}"
        
        # Lista a raiz
        print(f"\n{'='*60}")
        print(f"🔍 DEBUGANDO PASTA DO CASO #{caso.id}")
        print(f"{'='*60}\n")
        
        itens_raiz = sp.listar_arquivos_pasta_raiz()
        print(f"📁 Itens na RAIZ: {len(itens_raiz)}\n")
        
        for item in itens_raiz:
            eh_pasta = bool(item.get('folder'))
            print(f"   - {item['name']}")
            print(f"     ID: {item['id']}")
            print(f"     É pasta: {eh_pasta}")
            print(f"     Tamanho: {item.get('size', 0)} bytes\n")
            
            logger.info(f"   - {item['name']} (ID: {item['id']}, É pasta: {eh_pasta})")
        
        # Tenta encontrar a pasta do caso
        pasta_encontrada = None
        for item in itens_raiz:
            if item['name'].lower() == nome_pasta.lower() and item.get('folder'):
                pasta_encontrada = item
                break
        
        if pasta_encontrada:
            print(f"✅ Pasta '{nome_pasta}' encontrada!")
            print(f"   ID: {pasta_encontrada['id']}\n")
            logger.info(f"✅ Pasta '{nome_pasta}' encontrada! ID: {pasta_encontrada['id']}")
            
            # Lista conteúdo da pasta do caso
            itens_caso = sp.listar_arquivos_pasta(pasta_encontrada['id'])
            print(f"📄 Arquivos na pasta do caso: {len(itens_caso)}\n")
            
            for item in itens_caso:
                print(f"   - {item['name']} (ID: {item['id']})")
                logger.info(f"   - {item['name']} (ID: {item['id']})")
            
            print(f"\n{'='*60}\n")
            
            return JsonResponse({
                'status': 'OK',
                'pasta_id': pasta_encontrada['id'],
                'pasta_nome': pasta_encontrada['name'],
                'arquivos_encontrados': len(itens_caso),
                'arquivos': itens_caso
            })
        else:
            pastas_disponiveis = [item['name'] for item in itens_raiz if item.get('folder')]
            print(f"❌ Pasta '{nome_pasta}' NÃO encontrada na raiz!")
            print(f"   Pastas disponíveis: {pastas_disponiveis}\n")
            print(f"{'='*60}\n")
            
            logger.warning(f"❌ Pasta '{nome_pasta}' NÃO encontrada na raiz")
            logger.info(f"Pastas disponíveis: {pastas_disponiveis}")
            
            return JsonResponse({
                'status': 'ERRO',
                'mensagem': f"Pasta '{nome_pasta}' não encontrada",
                'pastas_na_raiz': pastas_disponiveis,
                'procurando_por': nome_pasta
            }, status=404)
    
    except Exception as e:
        print(f"\n❌ ERRO ao debugar pasta: {e}\n")
        logger.error(f"❌ Erro ao debugar pasta: {e}", exc_info=True)
        return JsonResponse({'status': 'ERRO', 'mensagem': str(e)}, status=500)