# workflow/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import InstanciaAcao, Transicao, HistoricoFase, Fase
from casos.models import Caso, FluxoInterno
from django.contrib.auth import get_user_model
from .models import Fase

User = get_user_model()


def transitar_fase(caso, nova_fase):
    """
    Função auxiliar para mover um caso para uma nova fase.
    Esta função é a 'fonte da verdade' para a transição.
    """
    print(f"Iniciando transição para o caso #{caso.id} para a fase '{nova_fase.nome}'")
    
    # 1. Marca a data de saída da fase antiga (se houver)
    HistoricoFase.objects.filter(caso=caso, data_saida__isnull=True).update(data_saida=timezone.now())
    
    # 2. Atualiza a fase atual no objeto Caso
    caso.fase_atual_wf = nova_fase
    caso.save(update_fields=['fase_atual_wf'])

    # 3. Cria o novo registro no histórico para a nova fase
    HistoricoFase.objects.create(caso=caso, fase=nova_fase)

    # 4. Apaga as ações pendentes antigas
    caso.acoes_pendentes.filter(status='PENDENTE').delete()

    # 5. Cria as novas ações pendentes para a nova fase
    for acao in nova_fase.acoes.all():
        # Define o responsável com a nova regra de prioridade
        responsavel_final = acao.responsavel_padrao or caso.advogado_responsavel

        dados_instancia = {
            'caso': caso,
            'acao': acao,
            'responsavel': responsavel_final, # Usa o responsável definido
            'status': 'PENDENTE'
        }
        
        if acao.prazo_dias > 0:
            from datetime import timedelta
            dados_instancia['data_prazo'] = timezone.now().date() + timedelta(days=acao.prazo_dias)
            
        InstanciaAcao.objects.create(**dados_instancia)
    
    print(f"Caso #{caso.id} transitou com sucesso para '{nova_fase.nome}'")

@require_POST
@login_required
def executar_acao(request, pk):
    instancia_acao = get_object_or_404(InstanciaAcao, pk=pk, status='PENDENTE')
    caso = instancia_acao.caso
    acao = instancia_acao.acao
    
    resposta = request.POST.get('resposta', '')
    comentario = request.POST.get('comentario', '')

    instancia_acao.status = 'CONCLUIDA'
    instancia_acao.concluida_por = request.user
    instancia_acao.data_conclusao = timezone.now()
    instancia_acao.resposta = resposta
    instancia_acao.comentario = comentario
    instancia_acao.save()
    
    if acao.mudar_status_caso_para:
        caso.status = acao.mudar_status_caso_para
        caso.save(update_fields=['status'])
    
    try:
        transicao = Transicao.objects.get(acao=acao, condicao=resposta)
        proxima_fase = transicao.fase_destino
        transitar_fase(caso, proxima_fase)
    except Transicao.DoesNotExist:
        print(f"Nenhuma transição encontrada. O caso permanece na fase '{caso.fase_atual_wf.nome}'.")
    descricao_log = f"Ação '{acao.titulo}' foi concluída."
    if comentario:
        descricao_log += f"\nComentário: {comentario}"
    if resposta:
        descricao_log += f"\nResposta: {resposta}"

    FluxoInterno.objects.create(
        caso=caso,
        tipo_evento='ACAO_WF_CONCLUIDA',
        descricao=descricao_log,
        autor=request.user
    )

    # APÓS TUDO, BUSCA OS DADOS NOVAMENTE PARA ENVIAR AO HTMX
    acoes_pendentes = caso.acoes_pendentes.filter(status='PENDENTE')
    acoes_concluidas = caso.acoes_pendentes.filter(status='CONCLUIDA').order_by('-data_conclusao')
    
    context = {
        'caso': caso,
        'acoes_pendentes': acoes_pendentes,
        'acoes_concluidas': acoes_concluidas,
    }
    return render(request, 'workflow/partials/painel_acoes.html', context)

@login_required
def carregar_painel_acoes(request, caso_id):
    caso = get_object_or_404(Caso, id=caso_id)
    acoes_pendentes = caso.acoes_pendentes.filter(status='PENDENTE')
    acoes_concluidas = caso.acoes_pendentes.filter(status='CONCLUIDA').order_by('-data_conclusao')
    context = {
        'caso': caso,
        'acoes_pendentes': acoes_pendentes,
        'acoes_concluidas': acoes_concluidas,
    }
    return render(request, 'workflow/partials/painel_acoes.html', context)

@login_required
def lista_todas_acoes(request):
    # Começa buscando todas as instâncias de ações, otimizando as buscas
    acoes_list = InstanciaAcao.objects.select_related(
        'caso', 'caso__cliente', 'acao', 'responsavel'
    ).all()

    # --- Lógica de Filtros ---
    filtro_responsavel = request.GET.get('filtro_responsavel', '')
    filtro_status = request.GET.get('filtro_status', '')
    filtro_prazo_de = request.GET.get('filtro_prazo_de', '')
    filtro_prazo_ate = request.GET.get('filtro_prazo_ate', '')

    if filtro_responsavel:
        acoes_list = acoes_list.filter(responsavel_id=filtro_responsavel)
    if filtro_status:
        acoes_list = acoes_list.filter(status=filtro_status)
    if filtro_prazo_de:
        acoes_list = acoes_list.filter(data_prazo__gte=filtro_prazo_de) # gte = Greater Than or Equal
    if filtro_prazo_ate:
        acoes_list = acoes_list.filter(data_prazo__lte=filtro_prazo_ate) # lte = Less Than or Equal
        
    # Ordena por prazo, colocando os mais antigos primeiro
    acoes_list = acoes_list.order_by('data_prazo')

    context = {
        'acoes': acoes_list,
        'valores_filtro': request.GET,
        'todos_responsaveis': User.objects.all().order_by('username'),
        'status_choices': InstanciaAcao.STATUS_CHOICES,
    }
    return render(request, 'workflow/lista_acoes.html', context)

@login_required
def kanban_view(request):
    # 1. Busca todas as fases de todos os workflows para serem as colunas
    todas_fases = Fase.objects.all().order_by('workflow__nome', 'ordem')
    
    # 2. Busca todos os casos que estão em alguma fase do workflow
    casos_no_workflow = Caso.objects.filter(
        status='ATIVO',
        fase_atual_wf__isnull=False
    ).select_related('cliente', 'produto', 'advogado_responsavel', 'fase_atual_wf')

    # 3. Organiza os casos em um dicionário, agrupados por fase
    casos_por_fase = {}
    for caso in casos_no_workflow:
        if caso.fase_atual_wf.id not in casos_por_fase:
            casos_por_fase[caso.fase_atual_wf.id] = []
        casos_por_fase[caso.fase_atual_wf.id].append(caso)

    # Adiciona fases vazias ao dicionário para que todas as colunas apareçam
    for fase in todas_fases:
        if fase.id not in casos_por_fase:
            casos_por_fase[fase.id] = []

    context = {
        'fases': todas_fases,
        'casos_por_fase': casos_por_fase,
    }
    return render(request, 'workflow/kanban.html', context)