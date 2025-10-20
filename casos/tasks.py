# casos/tasks.py

from celery import shared_task
from .models import Caso
import os
import requests
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from pastas.models import EstruturaPasta
from integrations.sharepoint import SharePoint

# ==============================================================================
# LÓGICA DAS TAREFAS EM SEGUNDO PLANO
# Estas funções serão executadas pelo Celery Worker, não pelo servidor web.
# ==============================================================================

@shared_task
def criar_pastas_sharepoint_task(caso_id):
    """
    Tarefa Celery para criar a estrutura de pastas no SharePoint.
    """
    try:
        caso = Caso.objects.get(id=caso_id)
        print(f"TASK SharePoint: A iniciar para o caso #{caso.id}...")
        
        estrutura = EstruturaPasta.objects.get(cliente=caso.cliente, produto=caso.produto)
        pastas_a_criar = estrutura.pastas.all()

        if not pastas_a_criar:
            print(f"TASK SharePoint: Estrutura encontrada para o caso #{caso.id}, mas sem pastas associadas.")
            return

        sp = SharePoint()
        nome_pasta_caso = str(caso.id)
        folder_id = sp.criar_pasta_caso(nome_pasta_caso)
        
        # Salva o ID no objeto 'caso'
        caso.sharepoint_folder_id = folder_id
        caso.save(update_fields=['sharepoint_folder_id']) # Salva diretamente na BD
        
        for pasta in pastas_a_criar:
            sp.criar_subpasta(folder_id, pasta.nome)
        
        print(f"TASK SharePoint: Pastas para o caso #{caso.id} criadas com sucesso.")
        return f"Pastas para o caso {caso_id} criadas com sucesso."
    except Caso.DoesNotExist:
        print(f"ERRO na TASK SharePoint: Caso com ID {caso_id} não encontrado.")
        return f"Caso com ID {caso_id} não encontrado."
    except EstruturaPasta.DoesNotExist:
        print(f"TASK SharePoint: Nenhuma estrutura de pastas encontrada para o caso #{caso_id}.")
        return f"Nenhuma estrutura de pastas para o caso {caso_id}."
    except Exception as e:
        print(f"ERRO na TASK SharePoint para o Caso #{caso_id}: {e}")
        # Re-raise the exception to mark the task as failed
        raise e


@shared_task
def enviar_sinal_para_n8n_task(caso_id):
    """
    Tarefa Celery para enviar os dados do novo caso para o Webhook do n8n.
    """
    try:
        caso = Caso.objects.get(id=caso_id)
        print(f"TASK n8n Webhook: A preparar para o caso #{caso.id}...")

        webhook_url = os.environ.get('N8N_WEBHOOK_URL')
        if not webhook_url:
            print("AVISO na TASK n8n: N8N_WEBHOOK_URL não configurada.")
            return "N8N_WEBHOOK_URL não configurada."

        payload = {
            "id": caso.id,
            "titulo": caso.titulo,
            # ... (adicione todos os outros campos do payload que já tinha)
        }

        response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        print(f"TASK n8n Webhook: Sinal enviado com sucesso! Status: {response.status_code}")
        return f"Webhook para o caso {caso_id} enviado com sucesso."
    except Caso.DoesNotExist:
        print(f"ERRO na TASK n8n: Caso com ID {caso_id} não encontrado.")
        return f"Caso com ID {caso_id} não encontrado."
    except requests.exceptions.RequestException as e:
        print(f"ERRO na TASK n8n para o caso #{caso_id}: {e}")
        raise e


@shared_task
def enviar_email_novo_caso_task(caso_id):
    """
    Tarefa Celery para preparar e enviar um e-mail de notificação.
    """
    try:
        caso = Caso.objects.get(id=caso_id)
        print(f"TASK E-mail: A preparar para o caso #{caso.id}...")

        destinatario_fixo = os.environ.get('EMAIL_DESTINATARIO_NOVOS_CASOS')
        if not destinatario_fixo:
            print("AVISO na TASK E-mail: EMAIL_DESTINATARIO_NOVOS_CASOS não definida.")
            return "Variável de e-mail não definida."

        link_caso = reverse('casos:detalhe_caso', kwargs={'pk': caso.id})
        context = {
            'caso': caso,
            'link_caso': f"https://gesta-rca.onrender.com{link_caso}"
        }
        html_message = render_to_string('emails/notificacao_novo_caso.html', context)
        
        send_mail(
            subject=f'Novo Caso Criado: #{caso.id} - {caso.titulo}',
            message='',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[destinatario_fixo],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"TASK E-mail: Notificação para o caso #{caso.id} enviada com sucesso!")
        return f"E-mail para o caso {caso_id} enviado."
    except Caso.DoesNotExist:
        print(f"ERRO na TASK E-mail: Caso com ID {caso_id} não encontrado.")
        return f"Caso com ID {caso_id} não encontrado."
    except Exception as e:
        print(f"ERRO na TASK E-mail para o caso #{caso.id}: {e}")
        raise e