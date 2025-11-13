# analyser/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
import json
import 
from django.http import JsonResponse

from casos.models import Caso
from .models import ModeloAnalise, ResultadoAnalise
from .services import AnalyserService
from campos_custom.models import CampoPersonalizado

@login_required
def listar_modelos(request):
    """Lista modelos."""
    modelos = ModeloAnalise.objects.all().order_by('-data_criacao')
    
    context = {
        'modelos': modelos
    }
    
    return render(request, 'analyser/listar_modelos.html', context)


@login_required
def criar_modelo(request):
    """Cria novo modelo."""
    
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        instrucoes_gerais = request.POST.get('instrucoes_gerais')
        gerar_resumo = request.POST.get('gerar_resumo') == 'on'
        
        # Montar descrições dos campos
        descricoes_campos = {}
        for key in request.POST:
            if key.startswith('descricao_'):
                campo_nome = key.replace('descricao_', '')
                descricao_campo = request.POST.get(key, '').strip()
                if descricao_campo:
                    descricoes_campos[campo_nome] = descricao_campo
        
        # Criar modelo
        modelo = ModeloAnalise.objects.create(
            nome=nome,
            descricao=descricao,
            cliente_id=cliente_id,
            produto_id=produto_id,
            descricoes_campos=descricoes_campos,
            instrucoes_gerais=instrucoes_gerais,
            gerar_resumo=gerar_resumo,
            criado_por=request.user
        )
        
        messages.success(request, f'✅ Modelo "{modelo.nome}" criado com sucesso!')
        return redirect('analyser:listar_modelos')
    
    # GET
    from clientes.models import Cliente
    from produtos.models import Produto
    
    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    
    context = {
        'clientes': clientes,
        'produtos': produtos,
    }
    
    return render(request, 'analyser/criar_modelo.html', context)


@login_required
def editar_modelo(request, pk):
    """Edita modelo."""
    
    modelo = get_object_or_404(ModeloAnalise, pk=pk)
    
    if request.method == 'POST':
        modelo.nome = request.POST.get('nome')
        modelo.descricao = request.POST.get('descricao', '')
        modelo.cliente_id = request.POST.get('cliente')
        modelo.produto_id = request.POST.get('produto')
        modelo.instrucoes_gerais = request.POST.get('instrucoes_gerais')
        modelo.gerar_resumo = request.POST.get('gerar_resumo') == 'on'
        
        descricoes_campos = {}
        for key in request.POST:
            if key.startswith('descricao_'):
                campo_nome = key.replace('descricao_', '')
                descricao_campo = request.POST.get(key, '').strip()
                if descricao_campo:
                    descricoes_campos[campo_nome] = descricao_campo
        
        modelo.descricoes_campos = descricoes_campos
        modelo.save()
        
        messages.success(request, f'✅ Modelo "{modelo.nome}" atualizado!')
        return redirect('analyser:listar_modelos')
    
    # GET
    from clientes.models import Cliente
    from produtos.models import Produto
    
    campos = modelo.get_campos_para_extrair()
    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    
    context = {
        'modelo': modelo,
        'campos': campos,
        'clientes': clientes,
        'produtos': produtos,
    }
    
    return render(request, 'analyser/criar_modelo.html', context)


@login_required
def ajax_buscar_campos(request):
    """AJAX: Retorna campos quando seleciona produto."""
    
    produto_id = request.GET.get('produto_id')
    cliente_id = request.GET.get('cliente_id')
    
    if not produto_id or not cliente_id:
        return JsonResponse({'campos': []})
    
    campos = []
    
    # Campos padrão do Caso
    campos_padrao = [
        {'nome': 'titulo', 'label': 'Título do Caso', 'tipo': 'TEXTO'},
        {'nome': 'data_entrada', 'label': 'Data de Entrada', 'tipo': 'DATA'},
        {'nome': 'valor_apurado', 'label': 'Valor Apurado', 'tipo': 'MOEDA'},
    ]
    
    for cp in campos_padrao:
        campos.append({
            'nome': cp['nome'],
            'label': cp['label'],
            'tipo': cp['tipo'],
            'is_padrao': True
        })
    
    # Campos personalizados através da EstruturaDeCampos
    try:
        from campos_custom.models import EstruturaDeCampos, EstruturaCampoOrdenado
        from clientes.models import Cliente
        from produtos.models import Produto
        
        estrutura = EstruturaDeCampos.objects.get(
            cliente_id=cliente_id,
            produto_id=produto_id
        )
        
        # Busca campos ordenados da estrutura
        campos_ordenados = EstruturaCampoOrdenado.objects.filter(
            estrutura=estrutura
        ).select_related('campo').order_by('order')
        
        for campo_ord in campos_ordenados:
            campo = campo_ord.campo
            campos.append({
                'nome': f'campo_{campo.id}',
                'label': campo.nome_campo,
                'tipo': campo.tipo_campo,
                'is_padrao': False
            })
            
    except EstruturaDeCampos.DoesNotExist:
        pass
    except Exception as e:
        print(f"Erro ao buscar campos: {e}")
    
    return JsonResponse({'campos': campos})


@login_required
def selecionar_arquivos(request, caso_id):
    """Tela para selecionar arquivos e modelo antes de iniciar análise."""
    
    caso = get_object_or_404(Caso, pk=caso_id)
    
    # 🔍 DEBUG
    print(f"🔍 DEBUG: Caso #{caso_id} - Cliente: {caso.cliente.nome}, Produto: {caso.produto.nome}")
    
    # ✅ BUSCAR MODELOS PARA ESTE CLIENTE + PRODUTO (ANTES DO POST!)
    modelos = ModeloAnalise.objects.filter(
        cliente=caso.cliente,
        produto=caso.produto,
        ativo=True
    ).order_by('-data_criacao')
    
    print(f"🔍 DEBUG: Modelos encontrados: {modelos.count()}")
    for modelo in modelos:
        print(f"  - {modelo.nome}")
    
    # ========== POST: PROCESSAR ANÁLISE ==========
    if request.method == 'POST':
        print("=" * 80)
        print("🚀 INICIANDO PROCESSAMENTO DA ANÁLISE")
        print("=" * 80)
        
        modelo_id = request.POST.get('modelo_id')
        arquivos_selecionados_json = request.POST.get('arquivos_selecionados', '[]')
        
        print(f"📋 Modelo ID: {modelo_id}")
        print(f"📁 Arquivos JSON: {arquivos_selecionados_json}")
        
        try:
            arquivos_selecionados = json.loads(arquivos_selecionados_json)
            print(f"✅ Arquivos parseados: {len(arquivos_selecionados)} arquivo(s)")
            
            # Busca o modelo
            modelo = get_object_or_404(ModeloAnalise, pk=modelo_id)
            print(f"✅ Modelo encontrado: {modelo.nome}")
            
            # Cria o resultado da análise
            resultado = ResultadoAnalise.objects.create(
                caso=caso,
                modelo_usado=modelo,
                status='PROCESSANDO',
                arquivos_analisados=arquivos_selecionados,
                criado_por=request.user
            )
            print(f"✅ ResultadoAnalise criado: ID={resultado.id}")
            
            # Instancia o service
            service = AnalyserService(
                caso=caso,
                modelo_analise=modelo,
                arquivos_selecionados=arquivos_selecionados,
                usuario=request.user
            )
            
            print(f"🤖 Chamando service.executar_analise()")
            
            # Executa a análise
            resultado_final = service.executar_analise()
            
            print(f"✅ Análise concluída! Status: {resultado_final.status}")
            print("=" * 80)
            
            messages.success(request, '✅ Análise concluída com sucesso!')
            return redirect('analyser:resultado', resultado_id=resultado_final.id)
            
        except Exception as e:
            print(f"❌ ERRO AO PROCESSAR: {e}")
            print(f"❌ Tipo do erro: {type(e)}")
            traceback.print_exc()
            print("=" * 80)
            messages.error(request, f'❌ Erro ao processar análise: {str(e)}')
            # NÃO retorna aqui - deixa renderizar o form com o erro
    
    # ========== GET/POST COM ERRO: PREPARAR CONTEXT ==========
    
    # Buscar arquivos do SharePoint (ou mock)
    arquivos = []
    try:
        if caso.sharepoint_folder_id:
            from integrations.sharepoint import SharePoint
            
            sp = SharePoint()
            arquivos_sp = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
            
            # Converte para formato esperado
            for item in arquivos_sp:
                arquivos.append({
                    'nome': item.get('name'),
                    'id': item.get('id'),
                    'tipo': 'pasta' if 'folder' in item else 'arquivo',
                    'tamanho': item.get('size', 0),
                })
        else:
            # Mock para testes
            arquivos = [
                {'nome': 'Contrato.pdf', 'id': '1', 'tipo': 'arquivo'},
                {'nome': 'Procuração.pdf', 'id': '2', 'tipo': 'arquivo'},
                {'nome': 'Laudo_Pericial.docx', 'id': '3', 'tipo': 'arquivo'},
            ]
    except Exception as e:
        print(f"❌ Erro ao buscar arquivos: {e}")
        # Se der erro, usa mock
        arquivos = [
            {'nome': 'Contrato.pdf', 'id': '1', 'tipo': 'arquivo'},
            {'nome': 'Procuração.pdf', 'id': '2', 'tipo': 'arquivo'},
            {'nome': 'Laudo_Pericial.docx', 'id': '3', 'tipo': 'arquivo'},
        ]
    
    # Buscar análises anteriores
    analises_anteriores = ResultadoAnalise.objects.filter(
        caso=caso
    ).order_by('-data_criacao')[:5]
    
    context = {
        'caso': caso,
        'modelos': modelos,  # ✅ Agora está disponível!
        'arquivos': arquivos,
        'analises_anteriores': analises_anteriores,
    }
    
    return render(request, 'analyser/selecionar_arquivos.html', context)


@login_required
def resultado_analise(request, resultado_id):
    """Exibe resultado."""
    
    resultado = get_object_or_404(ResultadoAnalise, pk=resultado_id)
    logs = resultado.logs.all().order_by('timestamp')
    
    context = {
        'resultado': resultado,
        'caso': resultado.caso,
        'logs': logs
    }
    
    return render(request, 'analyser/resultado_analise.html', context)


@login_required
def aplicar_ao_caso(request, resultado_id):
    """Aplica dados ao caso."""
    
    resultado = get_object_or_404(ResultadoAnalise, pk=resultado_id)
    
    if resultado.status != 'CONCLUIDO':
        messages.error(request, '⚠️ Só é possível aplicar análises concluídas!')
        return redirect('analyser:resultado', resultado_id=resultado.id)
    
    if resultado.aplicado_ao_caso:
        messages.warning(request, '⚠️ Esta análise já foi aplicada!')
        return redirect('analyser:resultado', resultado_id=resultado.id)
    
    try:
        service = AnalyserService(
            caso=resultado.caso,
            modelo_analise=resultado.modelo_usado,
            arquivos_selecionados=resultado.arquivos_analisados,
            usuario=request.user
        )
        service.resultado = resultado
        service.aplicar_ao_caso()
        
        messages.success(request, f'✅ Dados aplicados ao Caso #{resultado.caso.id}!')
        return redirect('casos:detalhe_caso', pk=resultado.caso.id)
        
    except Exception as e:
        messages.error(request, f'❌ Erro: {str(e)}')
        return redirect('analyser:resultado', resultado_id=resultado.id)


@login_required
def deletar_modelo(request, pk):
    """Deleta modelo."""
    modelo = get_object_or_404(ModeloAnalise, pk=pk)
    
    if request.method == 'POST':
        nome = modelo.nome
        modelo.delete()
        messages.success(request, f'✅ Modelo "{nome}" deletado!')
        return redirect('analyser:listar_modelos')
    
    return render(request, 'analyser/confirmar_delete.html', {'modelo': modelo})

@login_required
def carregar_arquivos_sharepoint(request, caso_id):
    """View para o HTMX buscar e renderizar a árvore de arquivos do SharePoint."""
    caso = get_object_or_404(Caso, pk=caso_id)
    if not caso.sharepoint_folder_id:
        return HttpResponse("<div class='alert alert-warning'>⚠️ Este caso não possui uma pasta no SharePoint.</div>")

    try:
        from integrations.sharepoint import SharePoint
        sp = SharePoint()
        # Esta é a chamada REAL para sua integração
        conteudo = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)

        arquivos_formatados = []
        for item in conteudo:
            if not item.get('is_folder'): # Mostrando apenas arquivos
                tipo = item.get('mime_type', '')
                icona_css, cor_css = "fa-solid fa-file", "#64748b" # Ícone padrão
                if 'pdf' in tipo: icona_css, cor_css = "fa-solid fa-file-pdf", "#ef4444"
                elif 'word' in tipo: icona_css, cor_css = "fa-solid fa-file-word", "#2563eb"
                elif 'excel' in tipo: icona_css, cor_css = "fa-solid fa-file-excel", "#10b981"
                elif 'image' in tipo: icona_css, cor_css = "fa-solid fa-file-image", "#8b5cf6"
                
                arquivos_formatados.append({
                    'id': item['id'],
                    'name': item['name'],
                    'icona_css': icona_css,
                    'cor_css': cor_css
                })

    except Exception as e:
        return HttpResponse(f"<div class='alert alert-warning'>❌ Erro ao conectar com o SharePoint: {e}</div>")
        
    context = {'arquivos': arquivos_formatados}
    return render(request, 'analyser/partials/arvore_arquivos.html', context)

@login_required
def iniciar_analise(request, caso_id):
    """Processa o formulário de seleção e inicia a tarefa de análise."""
    if request.method != 'POST':
        return redirect('analyser:selecionar_arquivos', caso_id=caso_id)

    caso = get_object_or_404(Caso, pk=caso_id)
    modelo_id = request.POST.get('modelo_id')
    # O nome do campo hidden foi corrigido para 'arquivos_selecionados_ids'
    arquivos_ids_str = request.POST.get('arquivos_selecionados_ids') 

    if not modelo_id or not arquivos_ids_str:
        messages.error(request, "Você precisa selecionar um modelo e pelo menos um arquivo.")
        return redirect('analyser:selecionar_arquivos', caso_id=caso_id)

    modelo = get_object_or_404(ModeloAnalise, pk=modelo_id)
    arquivos_ids = arquivos_ids_str.split(',')
    
    # Busca os nomes dos arquivos para exibir na mensagem
    # (Esta parte é opcional, mas melhora a experiência)
    try:
        from integrations.sharepoint import SharePoint
        sp = SharePoint()
        arquivos_info = []
        for item_id in arquivos_ids:
            # Você precisará de um método para buscar detalhes de um item por ID
            item_details = sp.get_item_details(item_id) 
            arquivos_info.append({
                'id': item_id,
                'nome': item_details.get('name', 'Arquivo Desconhecido'),
                'tipo': item_details.get('mimeType', 'application/octet-stream')
            })
    except Exception as e:
        # Se falhar, usa uma lista mais simples
        arquivos_info = [{'id': aid} for aid in arquivos_ids]

    # TODO: Disparar tarefa Celery aqui
    # from .tasks import executar_analise_ia
    # executar_analise_ia.delay(caso.id, modelo.id, arquivos_info, request.user.id)

    # Cria um registro de ResultadoAnalise para o histórico
    ResultadoAnalise.objects.create(
        caso=caso,
        modelo_usado=modelo,
        status='PROCESSANDO',
        arquivos_analisados=arquivos_info,
        criado_por=request.user
    )

    messages.success(request, f"Análise com o modelo '{modelo.nome}' foi iniciada! O resultado aparecerá no histórico em breve.")
    return redirect('analyser:selecionar_arquivos', caso_id=caso_id)