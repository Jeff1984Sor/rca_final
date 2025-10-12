from django.db.models.signals import post_save
from django.dispatch import receiver

# Importa todos os modelos e serviços necessários
from casos.models import Caso, FluxoInterno
from pastas.models import EstruturaPasta
from integrations.sharepoint import SharePoint
from .models import Workflow, Fase
from .views import transitar_fase # Importa nossa função de transição

# --- FUNÇÃO DE LÓGICA DO SHAREPOINT ---
def criar_pastas_sharepoint_logica(instance):
    """
    Verifica a estrutura e cria as pastas no SharePoint para um novo caso.
    """
    try:
        estrutura = EstruturaPasta.objects.get(cliente=instance.cliente, produto=instance.produto)
    except EstruturaPasta.DoesNotExist:
        print(f"SharePoint: Nenhuma estrutura de pastas encontrada para o caso #{instance.id}.")
        return

    pastas_a_criar = estrutura.pastas.all()
    if not pastas_a_criar:
        print(f"SharePoint: Estrutura encontrada para o caso #{instance.id}, mas sem pastas associadas.")
        return

    try:
        print(f"SharePoint: Iniciando criação de pastas para o caso #{instance.id}...")
        sp = SharePoint()
        nome_pasta_caso = str(instance.id)
        folder_id = sp.criar_pasta_caso(nome_pasta_caso)
        
        # Salva o ID no objeto 'instance' que está em memória
        instance.sharepoint_folder_id = folder_id
        
        for pasta in pastas_a_criar:
            sp.criar_subpasta(folder_id, pasta.nome)
        
        print(f"SharePoint: Pastas para o caso #{instance.id} criadas com sucesso.")
    except Exception as e:
        print(f"ERRO ao criar pastas no SharePoint para o Caso #{instance.id}: {e}")

# --- FUNÇÃO DE LÓGICA DE E-MAIL (Exemplo) ---
def enviar_email_novo_caso(instance):
    print(f"E-mail: Preparando para enviar e-mail para o caso #{instance.id}...")
    # Coloque aqui o seu código que envia o e-mail
    print(f"E-mail: Notificação para o caso #{instance.id} enviada com sucesso!")


# --- SINAL ÚNICO E UNIFICADO ---
@receiver(post_save, sender=Caso)
def gatilho_pos_criacao_caso(sender, instance, created, **kwargs):
    """
    Orquestrador principal que é disparado APENAS na criação de um novo Caso.
    """
    if created:
        print(f"--- SINAL ÚNICO DISPARADO PARA NOVO CASO #{instance.id} ---")

        # 1. LÓGICA DO WORKFLOW
        if instance.status == 'ATIVO':
            try:
                workflow = Workflow.objects.get(cliente=instance.cliente, produto=instance.produto)
                fase_inicial = workflow.fases.order_by('ordem').first()
                if fase_inicial:
                    transitar_fase(instance, fase_inicial)
                else:
                    print(f"Workflow: '{workflow.nome}' não tem uma fase inicial (ordem=1).")
            except Workflow.DoesNotExist:
                print(f"Workflow: Nenhum workflow definido para o caso #{instance.id}.")
        
        FluxoInterno.objects.create(
            caso=instance,
            tipo_evento='CRIACAO_CASO',
            descricao=f"Caso criado com status '{instance.get_status_display()}'.",
            # O autor da criação é, por padrão, o advogado responsável, se houver
            autor=instance.advogado_responsavel 
        )

        # 2. LÓGICA DO SHAREPOINT
        criar_pastas_sharepoint_logica(instance)
        
        # 3. LÓGICA DE E-MAIL
        enviar_email_novo_caso(instance)

        # 4. SALVA O ID DO SHAREPOINT DE UMA VEZ
        # Como a função do SharePoint modifica o 'instance', precisamos salvar essa alteração.
        if instance.sharepoint_folder_id:
            instance.save(update_fields=['sharepoint_folder_id'])