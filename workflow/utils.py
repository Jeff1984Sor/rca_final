# workflow/utils.py
from django.utils import timezone
from datetime import timedelta
from .models import HistoricoFase, InstanciaAcao
from casos.models import FluxoInterno

def transitar_fase(caso, nova_fase):
    """
    Função central para mover um caso para uma nova fase.
    Atualiza o caso, o histórico, o fluxo interno e cria as novas ações.
    """
    fase_antiga = caso.fase_atual_wf
    
    print(f"UTILS: Transitando caso #{caso.id} da fase '{fase_antiga.nome if fase_antiga else 'Nenhuma'}' para '{nova_fase.nome}'")

    # 1. Marca a data de saída da fase antiga no histórico
    HistoricoFase.objects.filter(caso=caso, data_saida__isnull=True).update(data_saida=timezone.now())
    
    # 2. Atualiza a fase atual no objeto Caso
    caso.fase_atual_wf = nova_fase
    caso.save(update_fields=['fase_atual_wf'])

    # 3. Cria o novo registro no histórico para a nova fase
    HistoricoFase.objects.create(caso=caso, fase=nova_fase)

    # 4. Apaga as ações pendentes da fase anterior
    caso.acoes_pendentes.filter(status='PENDENTE').delete()

    # 5. Cria as novas instâncias de ação para a nova fase
    for acao_definicao in nova_fase.acoes.all():
        # Define o responsável com a regra de prioridade
        responsavel_final = acao_definicao.responsavel_padrao or caso.advogado_responsavel

        dados_instancia = {
            'caso': caso,
            'acao': acao_definicao,
            'responsavel': responsavel_final,
            'status': 'PENDENTE'
        }
        
        # Calcula o prazo, se houver
        if acao_definicao.prazo_dias > 0:
            dados_instancia['data_prazo'] = timezone.now().date() + timedelta(days=acao_definicao.prazo_dias)
            
        InstanciaAcao.objects.create(**dados_instancia)
    
    # 6. Cria o log no Fluxo Interno
    FluxoInterno.objects.create(
        caso=caso,
        tipo_evento='MUDANCA_FASE_WF',
        descricao=f"Caso transitou da fase '{fase_antiga.nome if fase_antiga else 'Nenhuma'}' para '{nova_fase.nome}'.",
        autor=None # Ação do sistema
    )
    
    print(f"UTILS: Transição do caso #{caso.id} para '{nova_fase.nome}' concluída.")