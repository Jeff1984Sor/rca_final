# workflow/signals.py

import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

# Importa todos os modelos e serviços necessários
from casos.models import Caso, FluxoInterno
from pastas.models import EstruturaPasta
from integrations.sharepoint import SharePoint
from .models import Workflow, Fase
from .views import transitar_fase # Importa nossa função de transição

# ==============================================================================
# FUNÇÃO DE LÓGICA DO SHAREPOINT (NÃO MUDA)
# ==============================================================================
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

# ==============================================================================
# FUNÇÃO DE LÓGICA DE E-MAIL (CORRIGIDA PARA DESTINATÁRIO FIXO)
# ==============================================================================
def enviar_email_novo_caso(instance, request=None):
    """
    Prepara e envia um e-mail de notificação sobre um novo caso para um destinatário fixo.
    """
    print(f"E-mail: Preparando para enviar e-mail para o caso #{instance.id}...")

    # 1. Pega o destinatário fixo da variável de ambiente.
    destinatario_fixo = os.environ.get('EMAIL_DESTINATARIO_NOVOS_CASOS')

    # 2. Verifica se a variável foi configurada. Se não, cancela o envio.
    if not destinatario_fixo:
        print("!!!!!! E-mail: Envio cancelado. A variável de ambiente 'EMAIL_DESTINATARIO_NOVOS_CASOS' não foi definida. !!!!!!")
        return

    destinatarios = [destinatario_fixo]
    
    # Monta o link para o caso.
    # Como o signal não tem acesso ao 'request', a URL será relativa (ex: /casos/1/).
    # O seu provedor de e-mail (Outlook, Gmail) geralmente transforma isso em um link clicável.
    link_caso = reverse('casos:detalhe_caso', kwargs={'pk': instance.id})

    # Monta o contexto para o template do e-mail
    context = {
        'caso': instance,
        'link_caso': f"https://gesta-rca.onrender.com{link_caso}" # Constrói a URL completa manualmente
    }
    
    # Renderiza o corpo do e-mail a partir do template HTML
    html_message = render_to_string('emails/notificacao_novo_caso.html', context)
    
    try:
        send_mail(
            subject=f'Novo Caso Criado no Sistema: #{instance.id} - {instance.titulo}',
            message='', # A mensagem de texto é opcional, pois estamos enviando HTML
            from_email=settings.EMAIL_HOST_USER, # Remetente (configurado no settings.py)
            recipient_list=destinatarios,
            html_message=html_message, # O corpo do e-mail em HTML
            fail_silently=False, # Se der erro, levanta uma exceção (visível nos logs)
        )
        print(f"E-mail: Notificação para o caso #{instance.id} enviada com sucesso para {destinatarios[0]}!")
    except Exception as e:
        print(f"!!!!!! ERRO AO ENVIAR E-MAIL para o caso #{instance.id}: {e} !!!!!!")


# ==============================================================================
# SINAL ÚNICO E UNIFICADO (NÃO MUDA)
# ==============================================================================
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