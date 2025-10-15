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
def enviar_email_novo_caso(instance, request=None):
    """
    Prepara e envia um e-mail de notificação sobre um novo caso.
    """
    print(f"E-mail: Preparando para enviar e-mail para o caso #{instance.id}...")

    # Define o destinatário. A lógica pode ser mais complexa (ex: um grupo)
    # Por enquanto, vamos enviar para o advogado responsável, se houver.
    if not instance.advogado_responsavel or not instance.advogado_responsavel.email:
        print(f"E-mail: Envio cancelado. Nenhum advogado responsável ou email definido para o caso #{instance.id}.")
        return

    destinatario = [instance.advogado_responsavel.email]
    
    # Monta o link completo para o caso
    # Precisamos do 'request' para construir a URL absoluta (http://...)
    # Se não tivermos o request, criamos um link relativo.
    if request:
        link_caso = request.build_absolute_uri(
            reverse('casos:detalhe_caso', kwargs={'pk': instance.id})
        )
    else:
        link_caso = reverse('casos:detalhe_caso', kwargs={'pk': instance.id})

    # Monta o contexto para o template do e-mail
    context = {
        'caso': instance,
        'link_caso': link_caso,
    }
    
    # Renderiza o corpo do e-mail a partir do template HTML
    html_message = render_to_string('emails/notificacao_novo_caso.html', context)
    
    try:
        send_mail(
            subject=f'Novo Caso Criado: #{instance.id} - {instance.titulo}',
            message='', # A mensagem de texto é opcional, pois estamos enviando HTML
            from_email=settings.EMAIL_HOST_USER, # Remetente (configurado no settings.py)
            recipient_list=destinatario,
            html_message=html_message, # O corpo do e-mail em HTML
            fail_silently=False, # Se der erro, levanta uma exceção
        )
        print(f"E-mail: Notificação para o caso #{instance.id} enviada com sucesso para {destinatario[0]}!")
    except Exception as e:
        print(f"!!!!!! ERRO AO ENVIAR E-MAIL para o caso #{instance.id}: {e} !!!!!!")


# --- SINAL ÚNICO E UNIFICADO ---


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