# workflow/views.py

"""
Views do sistema de Workflow.
Inclui tanto a nova interface visual quanto as views existentes de execução.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
import json

from .models import (
    Workflow, Fase, Acao, Transicao, TipoPausa,
    InstanciaAcao, HistoricoFase
)
from casos.models import Caso, FluxoInterno
from clientes.models import Cliente
from produtos.models import Produto
from django.contrib.auth import get_user_model

User = get_user_model()


# ==============================================================================
# NOVA INTERFACE - WORKFLOW BUILDER
# ==============================================================================

@login_required
def lista_workflows(request):
    """
    Lista todos os workflows existentes com informações resumidas.
    """
    workflows = Workflow.objects.select_related('cliente', 'produto').prefetch_related('fases').all()
    for workflow in workflows:
        workflow.casos_count = Caso.objects.filter(fase_atual_wf__workflow=workflow).count()
    context = {'workflows': workflows}
    return render(request, 'workflow/lista_workflows.html', context)

@login_required
def workflow_builder(request, pk=None):
    """
    Interface visual para criar/editar workflow.
    """
    workflow = None
    if pk:
        workflow = get_object_or_404(Workflow.objects.select_related('cliente', 'produto'), pk=pk)
    
    context = {
        'workflow': workflow,
        'clientes': Cliente.objects.all().order_by('nome'),
        'produtos': Produto.objects.all().order_by('nome'),
        'tipos_pausa': TipoPausa.objects.filter(ativo=True).order_by('ordem'),
        'usuarios': User.objects.filter(is_active=True).order_by('username'),
        'caso_status_choices': Caso.STATUS_CHOICES,
    }
    return render(request, 'workflow/workflow_builder.html', context)


@login_required
@require_http_methods(["POST"])
def salvar_workflow_json(request):
    """
    ✅✅✅ VERSÃO FINAL COM TRANSIÇÕES DINÂMICAS ✅✅✅
    Salva o workflow lendo as fases de destino definidas pelo usuário.
    """
    try:
        data = json.loads(request.body)
        workflow_id = data.get('workflow_id')
        
        # --- Validações básicas ---
        nome = data.get('nome', '').strip()
        cliente_id = data.get('cliente')
        produto_id = data.get('produto')
        fases_data = data.get('fases', [])
        
        if not all([nome, cliente_id, produto_id]):
            return JsonResponse({'success': False, 'error': 'Nome, Cliente e Produto são obrigatórios.'}, status=400)
        if not fases_data:
            return JsonResponse({'success': False, 'error': 'Adicione pelo menos uma fase.'}, status=400)

        cliente = Cliente.objects.get(pk=cliente_id)
        produto = Produto.objects.get(pk=produto_id)

        with transaction.atomic():
            # 1. CRIA OU ATUALIZA O WORKFLOW
            if workflow_id:
                workflow = get_object_or_404(Workflow, pk=workflow_id)
                if (workflow.cliente_id != cliente.id or workflow.produto_id != produto.id) and \
                   Workflow.objects.filter(cliente=cliente, produto=produto).exclude(pk=workflow_id).exists():
                    raise IntegrityError(f'Já existe um workflow para {cliente.nome} + {produto.nome}')
                workflow.nome, workflow.cliente, workflow.produto = nome, cliente, produto
                workflow.save()
            else:
                workflow = Workflow.objects.create(nome=nome, cliente=cliente, produto=produto)

            # --- LÓGICA DE RECONCILIAÇÃO ---
            fases_existentes_map = {f.id: f for f in workflow.fases.all()}
            acoes_existentes_map = {a.id: a for a in Acao.objects.filter(fase__workflow=workflow)}
            
            fases_processadas_ids, acoes_processadas_ids = set(), set()
            novas_fases_map, novas_acoes_map = {}, {}

            # 2. ATUALIZA/CRIA FASES E AÇÕES
            for ordem, fase_data in enumerate(fases_data, start=1):
                fase_id = fase_data.get('temp_id') if isinstance(fase_data.get('temp_id'), int) else None
                fase = fases_existentes_map.get(fase_id)

                fase_fields = {
                    'workflow': workflow, 'nome': fase_data['nome'].strip(), 'ordem': ordem,
                    'pausar_prazo_automaticamente': fase_data.get('pausar_prazo_automaticamente', False),
                    'tipo_pausa_padrao_id': fase_data.get('tipo_pausa_padrao') or None,
                    'retomar_prazo_ao_sair': fase_data.get('retomar_prazo_ao_sair', False),
                    'cor_fase': fase_data.get('cor_fase', '#6c757d'), 'icone_fase': fase_data.get('icone_fase', 'fa-circle'),
                    'eh_fase_final': (ordem == len(fases_data))
                }

                if fase:
                    for key, value in fase_fields.items(): setattr(fase, key, value)
                    fase.save()
                    fases_processadas_ids.add(fase.id)
                else:
                    fase = Fase.objects.create(**fase_fields)
                    novas_fases_map[fase_data['temp_id']] = fase

                for acao_data in fase_data.get('acoes', []):
                    acao_id = acao_data.get('temp_id') if isinstance(acao_data.get('temp_id'), int) else None
                    acao = acoes_existentes_map.get(acao_id)
                    
                    acao_fields = {
                        'fase': fase, 'titulo': acao_data['titulo'].strip(),
                        'descricao': acao_data.get('descricao', ''), 'tipo': acao_data.get('tipo', 'SIMPLES'),
                        'tipo_responsavel': acao_data.get('tipo_responsavel', 'INTERNO'),
                        'responsavel_padrao_id': acao_data.get('responsavel_padrao') or None,
                        'nome_responsavel_terceiro': acao_data.get('nome_responsavel_terceiro', ''),
                        'pausar_prazo_enquanto_aguarda': acao_data.get('pausar_prazo_enquanto_aguarda', False),
                        'tipo_pausa_acao_id': acao_data.get('tipo_pausa_acao') or None,
                        'prazo_dias': int(acao_data.get('prazo_dias', 0)),
                        'dias_aguardar': int(acao_data.get('dias_aguardar', 0)),
                        'mudar_status_caso_para': acao_data.get('mudar_status_caso_para', '')
                    }

                    if acao:
                        for key, value in acao_fields.items(): setattr(acao, key, value)
                        acao.save()
                        acoes_processadas_ids.add(acao.id)
                    else:
                        acao = Acao.objects.create(**acao_fields)
                        novas_acoes_map[acao_data['temp_id']] = acao

            # 3. DELETA FASES E AÇÕES ÓRFÃS (com segurança)
            acoes_a_deletar_ids = set(acoes_existentes_map.keys()) - acoes_processadas_ids
            if acoes_a_deletar_ids: Acao.objects.filter(id__in=acoes_a_deletar_ids).delete()

            fases_a_deletar_ids = set(fases_existentes_map.keys()) - fases_processadas_ids
            for fase_id in fases_a_deletar_ids:
                fase_a_deletar = fases_existentes_map[fase_id]
                if Caso.objects.filter(fase_atual_wf=fase_a_deletar).exists():
                    raise ValueError(f"Não é possível deletar a fase '{fase_a_deletar.nome}', pois ela está em uso.")
                fase_a_deletar.delete()

            # 4. CRIA AS TRANSIÇÕES DINÂMICAS
            mapa_fases_final = {f.id: f for f in workflow.fases.all()}
            for temp_id, fase_obj in novas_fases_map.items(): mapa_fases_final[temp_id] = fase_obj
            mapa_acoes_final = {a.id: a for a in Acao.objects.filter(fase__workflow=workflow)}
            for temp_id, acao_obj in novas_acoes_map.items(): mapa_acoes_final[temp_id] = acao_obj

            workflow.transicoes.all().delete()
            
            for fase_data in fases_data:
                fase_origem = mapa_fases_final.get(fase_data.get('temp_id'))
                if not fase_origem: continue

                for acao_data in fase_data.get('acoes', []):
                    acao = mapa_acoes_final.get(acao_data.get('temp_id'))
                    if not acao: continue

                    if acao.tipo == 'DECISAO_SN':
                        fase_destino_sim = mapa_fases_final.get(acao_data.get('fase_destino_sim'))
                        if fase_destino_sim:
                            Transicao.objects.create(workflow=workflow, fase_origem=fase_origem, acao=acao, condicao='SIM', fase_destino=fase_destino_sim)
                        
                        fase_destino_nao = mapa_fases_final.get(acao_data.get('fase_destino_nao'))
                        if fase_destino_nao:
                            Transicao.objects.create(workflow=workflow, fase_origem=fase_origem, acao=acao, condicao='NAO', fase_destino=fase_destino_nao)
                    else:
                        fase_destino_padrao = mapa_fases_final.get(acao_data.get('fase_destino_padrao'))
                        if fase_destino_padrao:
                            Transicao.objects.create(workflow=workflow, fase_origem=fase_origem, acao=acao, condicao='', fase_destino=fase_destino_padrao)

            print(f"Workflow '{workflow.nome}' salvo com sucesso!")

        return JsonResponse({'success': True, 'workflow_id': workflow.id, 'message': f'Workflow "{workflow.nome}" salvo com sucesso!'})

    except IntegrityError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Erro interno: {str(e)}'}, status=500)
    
@login_required
def carregar_workflow_json(request, pk):
    """
    Carrega os dados de um workflow em JSON para edição, incluindo transições.
    """
    try:
        workflow = get_object_or_404(Workflow, pk=pk)
        transicoes = workflow.transicoes.all()
        
        fases_data = []
        for fase in workflow.fases.all().order_by('ordem'):
            acoes_data = []
            for acao in fase.acoes.all():
                trans_padrao = transicoes.filter(acao=acao, condicao='').first()
                trans_sim = transicoes.filter(acao=acao, condicao='SIM').first()
                trans_nao = transicoes.filter(acao=acao, condicao='NAO').first()
                
                acoes_data.append({
                    'temp_id': acao.id, 'titulo': acao.titulo, 'descricao': acao.descricao, 'tipo': acao.tipo,
                    'tipo_responsavel': acao.tipo_responsavel, 'responsavel_padrao': acao.responsavel_padrao_id,
                    'nome_responsavel_terceiro': acao.nome_responsavel_terceiro,
                    'pausar_prazo_enquanto_aguarda': acao.pausar_prazo_enquanto_aguarda,
                    'tipo_pausa_acao': acao.tipo_pausa_acao_id, 'prazo_dias': acao.prazo_dias,
                    'dias_aguardar': acao.dias_aguardar, 'mudar_status_caso_para': acao.mudar_status_caso_para,
                    # Adiciona dados da transição
                    'fase_destino_padrao': trans_padrao.fase_destino_id if trans_padrao else '',
                    'fase_destino_sim': trans_sim.fase_destino_id if trans_sim else '',
                    'fase_destino_nao': trans_nao.fase_destino_id if trans_nao else '',
                })
            
            fases_data.append({
                'temp_id': fase.id, 'nome': fase.nome,
                'pausar_prazo_automaticamente': fase.pausar_prazo_automaticamente,
                'tipo_pausa_padrao': fase.tipo_pausa_padrao_id,
                'retomar_prazo_ao_sair': fase.retomar_prazo_ao_sair,
                'cor_fase': fase.cor_fase, 'icone_fase': fase.icone_fase,
                'acoes': acoes_data
            })
        
        return JsonResponse({
            'success': True,
            'workflow': {
                'id': workflow.id, 'nome': workflow.nome, 'cliente': workflow.cliente_id,
                'produto': workflow.produto_id, 'fases': fases_data
            }
        })
    except Exception as e:
        print(f"Erro ao carregar workflow: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def deletar_workflow(request, pk):
    """
    Deleta um workflow.
    """
    workflow = get_object_or_404(Workflow, pk=pk)
    casos_count = Caso.objects.filter(fase_atual_wf__workflow=workflow).count()
    if casos_count > 0:
        messages.error(request, f'Não é possível deletar: existem {casos_count} caso(s) neste workflow.')
    else:
        nome = workflow.nome
        workflow.delete()
        messages.success(request, f'Workflow "{nome}" deletado com sucesso!')
    return redirect('workflow:lista_workflows')

@login_required
def duplicar_workflow(request, pk):
    """
    Duplica um workflow existente.
    """
    workflow_original = get_object_or_404(Workflow.objects.prefetch_related('fases__acoes', 'transicoes'), pk=pk)
    try:
        with transaction.atomic():
            novo_workflow = Workflow.objects.create(
                nome=f"{workflow_original.nome} (Cópia)",
                cliente=workflow_original.cliente,
                produto=workflow_original.produto
            )
            mapa_fases, mapa_acoes = {}, {}
            for fase_antiga in workflow_original.fases.all():
                fase_nova = Fase.objects.create(
                    workflow=novo_workflow, nome=fase_antiga.nome, ordem=fase_antiga.ordem,
                    pausar_prazo_automaticamente=fase_antiga.pausar_prazo_automaticamente,
                    tipo_pausa_padrao=fase_antiga.tipo_pausa_padrao,
                    retomar_prazo_ao_sair=fase_antiga.retomar_prazo_ao_sair,
                    cor_fase=fase_antiga.cor_fase, icone_fase=fase_antiga.icone_fase,
                    eh_fase_final=fase_antiga.eh_fase_final
                )
                mapa_fases[fase_antiga.id] = fase_nova
                for acao_antiga in fase_antiga.acoes.all():
                    acao_nova = Acao.objects.create(
                        fase=fase_nova, titulo=acao_antiga.titulo, descricao=acao_antiga.descricao,
                        tipo=acao_antiga.tipo, tipo_responsavel=acao_antiga.tipo_responsavel,
                        responsavel_padrao=acao_antiga.responsavel_padrao,
                        nome_responsavel_terceiro=acao_antiga.nome_responsavel_terceiro,
                        pausar_prazo_enquanto_aguarda=acao_antiga.pausar_prazo_enquanto_aguarda,
                        tipo_pausa_acao=acao_antiga.tipo_pausa_acao, prazo_dias=acao_antiga.prazo_dias,
                        dias_aguardar=acao_antiga.dias_aguardar,
                        mudar_status_caso_para=acao_antiga.mudar_status_caso_para
                    )
                    mapa_acoes[acao_antiga.id] = acao_nova
            
            for transicao_antiga in workflow_original.transicoes.all():
                fase_origem_nova = mapa_fases.get(transicao_antiga.fase_origem_id)
                fase_destino_nova = mapa_fases.get(transicao_antiga.fase_destino_id)
                acao_nova = mapa_acoes.get(transicao_antiga.acao_id)
                if fase_origem_nova and fase_destino_nova and acao_nova:
                    Transicao.objects.create(
                        workflow=novo_workflow, fase_origem=fase_origem_nova,
                        fase_destino=fase_destino_nova, acao=acao_nova,
                        condicao=transicao_antiga.condicao
                    )
        messages.success(request, f'Workflow duplicado com sucesso!')
        return redirect('workflow:workflow_builder', pk=novo_workflow.id)
    except Exception as e:
        messages.error(request, f'Erro ao duplicar workflow: {str(e)}')
        return redirect('workflow:lista_workflows')

# ==============================================================================
# FUNCOES AUXILIARES E EXECUCAO DE ACOES
# ==============================================================================

def transitar_fase(caso, nova_fase):
    fase_antiga = caso.fase_atual_wf
    if fase_antiga == nova_fase: return
    
    print(f"Transitando caso #{caso.id} de '{fase_antiga.nome if fase_antiga else 'Nenhuma'}' para '{nova_fase.nome}'")
    HistoricoFase.objects.filter(caso=caso, data_saida__isnull=True).update(data_saida=timezone.now())
    caso.fase_atual_wf = nova_fase
    caso.save(update_fields=['fase_atual_wf'])
    HistoricoFase.objects.create(caso=caso, fase=nova_fase)
    caso.acoes_pendentes.all().delete()

    for acao_definicao in nova_fase.acoes.all():
        responsavel_final = acao_definicao.responsavel_padrao or caso.advogado_responsavel
        dados_instancia = {
            'caso': caso, 'acao': acao_definicao,
            'responsavel': responsavel_final, 'status': 'PENDENTE'
        }
        if acao_definicao.prazo_dias > 0:
            dados_instancia['data_prazo'] = timezone.now().date() + timedelta(days=acao_definicao.prazo_dias)
        InstanciaAcao.objects.create(**dados_instancia)
    
    FluxoInterno.objects.create(
        caso=caso, tipo_evento='MUDANCA_FASE_WF',
        descricao=f"Caso transitou de '{fase_antiga.nome if fase_antiga else 'Nenhuma'}' para '{nova_fase.nome}'.",
        autor=None
    )

@require_POST
@login_required
def executar_acao(request, pk):
    instancia_acao = get_object_or_404(InstanciaAcao, pk=pk, status='PENDENTE')
    caso = instancia_acao.caso
    acao = instancia_acao.acao
    
    resposta = request.POST.get('resposta', '')
    comentario = request.POST.get('comentario', '')

    with transaction.atomic():
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
            transicao = Transicao.objects.get(workflow=caso.workflow, acao=acao, condicao=resposta)
            if transicao.fase_destino:
                transitar_fase(caso, transicao.fase_destino)
        except Transicao.DoesNotExist:
            print(f"Nenhuma transição encontrada. O caso permanece na fase '{caso.fase_atual_wf.nome}'.")
        
        descricao_log = f"Ação '{acao.titulo}' concluída."
        if comentario: descricao_log += f" Comentário: {comentario}"
        if resposta: descricao_log += f" Resposta: {resposta}"
        FluxoInterno.objects.create(caso=caso, tipo_evento='ACAO_WF_CONCLUIDA', descricao=descricao_log, autor=request.user)

    context = {
        'caso': caso,
        'acoes_pendentes': caso.acoes_pendentes.filter(status='PENDENTE'),
        'acoes_concluidas': caso.acoes_pendentes.filter(status='CONCLUIDA').order_by('-data_conclusao'),
    }
    return render(request, 'workflow/partials/painel_acoes.html', context)

@login_required
def carregar_painel_acoes(request, caso_id):
    caso = get_object_or_404(Caso, id=caso_id)
    context = {
        'caso': caso,
        'acoes_pendentes': caso.acoes_pendentes.filter(status='PENDENTE'),
        'acoes_concluidas': caso.acoes_pendentes.filter(status='CONCLUIDA').order_by('-data_conclusao'),
    }
    return render(request, 'workflow/partials/painel_acoes.html', context)

@login_required
def lista_todas_acoes(request):
    acoes_list = InstanciaAcao.objects.select_related('caso', 'caso__cliente', 'acao', 'responsavel').order_by('data_prazo')
    # ... (código de filtro continua o mesmo) ...
    context = {
        'acoes': acoes_list,
        'valores_filtro': request.GET,
        'todos_responsaveis': User.objects.all().order_by('username'),
        'status_choices': InstanciaAcao.STATUS_CHOICES,
    }
    return render(request, 'workflow/lista_acoes.html', context)

@login_required
def kanban_view(request):
    todas_fases = Fase.objects.all().order_by('workflow__nome', 'ordem')
    casos_no_workflow = Caso.objects.filter(status='ATIVO', fase_atual_wf__isnull=False).select_related('cliente', 'produto', 'advogado_responsavel', 'fase_atual_wf')
    casos_por_fase = {fase.id: [] for fase in todas_fases}
    for caso in casos_no_workflow:
        if caso.fase_atual_wf_id in casos_por_fase:
            casos_por_fase[caso.fase_atual_wf_id].append(caso)
    context = {'fases': todas_fases, 'casos_por_fase': casos_por_fase}
    return render(request, 'workflow/kanban.html', context)