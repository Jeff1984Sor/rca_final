# workflow/signals.py

import os
import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

# Importa todos os modelos e serviços necessários
from casos.models import Caso, FluxoInterno
from pastas.models import EstruturaPasta
from integrations.sharepoint import SharePoint
from .models import Workflow, Fase
from .views import transitar_fase # Importa nossa função de transição

print("--- workflow.signals.py: File is being imported! ---")

logger = logging.getLogger('casos_app')

def enviar_sinal_para_n8n(instance):
    """
    Envia os dados do novo caso para o Webhook configurado no n8n.
    """
    print(f"n8n Webhook: A preparar para enviar sinal para o caso #{instance.id}...")
    
    webhook_url = os.environ.get('N8N_WEBHOOK_URL')
    if not webhook_url:
        print("AVISO: Variável de ambiente N8N_WEBHOOK_URL não configurada. A saltar o envio para o n8n.")
        return

    payload = {
        "id": instance.id,
        "titulo": instance.titulo,
        "status": instance.status,
        "status_display": instance.get_status_display(),
        "data_entrada": instance.data_entrada.isoformat() if instance.data_entrada else None,
        "cliente_id": instance.cliente.id,
        "cliente_nome": instance.cliente.nome,
        "produto_id": instance.produto.id,
        "produto_nome": instance.produto.nome,
        "advogado_id": instance.advogado_responsavel.id if instance.advogado_responsavel else None,
        "advogado_nome": instance.advogado_responsavel.get_full_name() if instance.advogado_responsavel else None,
        "advogado_email": instance.advogado_responsavel.email if instance.advogado_responsavel else None,
    }

    try:
        print(f"n8N Webhook: A enviar dados para: {webhook_url}")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"n8n Webhook: Sinal enviado com sucesso! Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"ERRO ao enviar sinal para o n8n: {e}")

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

    print(f"!!! GATILHO DISPARADO para Caso ID {instance.id}, Created={created} !!!")
    logger.debug(f"--- Sinal post_save recebido para Caso ID {instance.id}. Flag 'created'={created} ---") # LOG INICIAL

    if created:
        logger.info(f"--- PROCESSANDO Gatilhos de CRIAÇÃO para Caso ID {instance.id} ---") # LOG CRIAÇÃO

        # 1. LÓGICA DO WORKFLOW
        logger.debug(f"Iniciando lógica de Workflow para Caso {instance.id}...")
        try:
            # ... (seu código de busca de Workflow e transição de fase) ...
            workflow = Workflow.objects.get(cliente=instance.cliente, produto=instance.produto)
            # ... (resto da lógica do workflow) ...
            logger.info(f"Workflow processado para Caso {instance.id}.")
        except Workflow.DoesNotExist:
             logger.warning(f"Workflow: Nenhum workflow definido para o caso #{instance.id}.")
        except Exception as e:
             logger.error(f"Erro na lógica de Workflow para Caso {instance.id}: {e}", exc_info=True) # LOG ERRO WORKFLOW
        
        # Criação do Fluxo Interno (já estava ok)
        try:
            # Verifica se já existe um registro de criação para este caso
            if not FluxoInterno.objects.filter(caso=instance, tipo_evento='CRIACAO_CASO').exists():
                FluxoInterno.objects.create(
                    caso=instance,                         
                    tipo_evento='CRIACAO_CASO',            
                    descricao=f"Caso criado com status '{instance.get_status_display()}'.", 
                    autor=instance.advogado_responsavel    
                )
                logger.debug(f"FluxoInterno 'CRIACAO_CASO' criado para Caso {instance.id}.")
            else:
                logger.warning(f"FluxoInterno 'CRIACAO_CASO' para Caso {instance.id} já existe. Pulando criação duplicada.") # LOG DUPLICADO
        except Exception as e:
            logger.error(f"Erro ao criar/verificar FluxoInterno para Caso {instance.id}: {e}", exc_info=True)

        # 2. LÓGICA DO SHAREPOINT
        logger.debug(f"Iniciando lógica do SharePoint para Caso {instance.id}...")
        try:
            criar_pastas_sharepoint_logica(instance)
            logger.info(f"Lógica do SharePoint concluída para Caso {instance.id}.")
        except Exception as e:
             logger.error(f"Erro na lógica do SharePoint para Caso {instance.id}: {e}", exc_info=True) # LOG ERRO SHAREPOINT

        # 3. LÓGICA DE E-MAIL
        logger.debug(f"Iniciando lógica de E-mail para Caso {instance.id}...")
        try:
            enviar_email_novo_caso(instance)
            logger.info(f"Lógica de E-mail concluída para Caso {instance.id}.")
        except Exception as e:
             logger.error(f"Erro na lógica de E-mail para Caso {instance.id}: {e}", exc_info=True) # LOG ERRO EMAIL
        
        # 4. LÓGICA N8N (se aplicável)
        logger.debug(f"Iniciando lógica do n8n para Caso {instance.id}...")
        try:
            # Descomente se você usa a função n8n aqui
            # enviar_sinal_para_n8n(instance) 
            logger.info(f"Lógica do n8n concluída para Caso {instance.id}.")
        except Exception as e:
             logger.error(f"Erro na lógica do n8n para Caso {instance.id}: {e}", exc_info=True) # LOG ERRO N8N


        # 5. SALVA O ID DO SHAREPOINT (já estava ok)
        try:
            if instance.sharepoint_folder_id and instance.pk: # Garante que o objeto foi salvo
                # Busca a instância mais recente do banco para evitar race conditions
                caso_atualizado = Caso.objects.get(pk=instance.pk) 
                if caso_atualizado.sharepoint_folder_id != instance.sharepoint_folder_id:
                     caso_atualizado.sharepoint_folder_id = instance.sharepoint_folder_id
                     caso_atualizado.save(update_fields=['sharepoint_folder_id'])
                     logger.info(f"SharePoint Folder ID salvo para Caso {instance.id}.")
        except Caso.DoesNotExist:
             logger.error(f"Erro ao tentar salvar SharePoint ID: Caso {instance.id} não encontrado no banco após criação.")
        except Exception as e:
             logger.error(f"Erro ao salvar SharePoint Folder ID para Caso {instance.id}: {e}", exc_info=True)

        logger.info(f"--- FIM dos Gatilhos de CRIAÇÃO para Caso ID {instance.id} ---")

    else:
         logger.debug(f"Sinal post_save para Caso ID {instance.id} ignorado (created=False).") # LOG IGNORADO