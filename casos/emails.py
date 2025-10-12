# casos/emails.py

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string # Opcional, para e-mails HTML

def enviar_email_novo_caso(caso):
    """
    Envia um e-mail de notificação quando um novo caso é criado.
    """
    try:
        assunto = f"Novo Caso Cadastrado: #{caso.id} - {caso.titulo}"
        
        # Corpo do e-mail em texto simples
        mensagem = (
            f"Olá,\n\n"
            f"Um novo caso foi registrado no sistema com sucesso.\n\n"
            f"Detalhes do Caso:\n"
            f"- Número: {caso.id}\n"
            f"- Título: {caso.titulo}\n"
            f"- Cliente: {caso.cliente.nome}\n"
            f"- Produto: {caso.produto.nome}\n"
            f"- Data de Entrada: {caso.data_entrada.strftime('%d/%m/%Y')}\n\n"
            f"Atenciosamente,\n"
            f"Seu Sistema Jurídico"
        )

        email_remetente = settings.EMAIL_HOST_USER
        
        # Lista de destinatários. Mude para o e-mail que deve receber a notificação.
        lista_destinatarios = ['ti@rcostaadv.com.br'] 

        send_mail(
            assunto,
            mensagem,
            email_remetente,
            lista_destinatarios,
            fail_silently=False, # Se False, levanta um erro se o envio falhar
        )
        
        print(f"E-mail de notificação para o caso #{caso.id} enviado com sucesso!")
        return True

    except Exception as e:
        print(f"Erro ao enviar e-mail para o caso #{caso.id}: {e}")
        return False