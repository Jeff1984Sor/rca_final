# workflow/signals.py

import os
import requests
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver # Mantido caso você adicione outros signals com decorador
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

# Importa todos os modelos e serviços necessários
# Garanta que estes imports estão corretos
try:
    from casos.models import Caso, FluxoInterno
    from pastas.models import EstruturaPasta
    from integrations.sharepoint import SharePoint
    from .models import Workflow, Fase
    # Tenta importar a view; se não existir, define como None
    try:
        from .views import transitar_fase
    except ImportError:
        transitar_fase = None

except ImportError as e:
    initial_logger = logging.getLogger(__name__)
    initial_logger.critical(f"Erro CRÍTICO ao importar modelos/views em signals.py: {e}. Verifique caminhos/dependências.")
    raise ImportError(f"Não foi possível importar dependências em signals.py: {e}") from e

print("--- workflow.signals.py: File is being imported! ---") # Log de confirmação de importação

logger = logging.getLogger('casos_app') # Use o logger configurado


# ==================================
# Funções Auxiliares (Lógicas)
# ==================================

def enviar_sinal_para_n8n(instance):
    """ Envia dados do novo caso para o Webhook n8n. """
    log_prefix = f"[Signal n8n - Caso {instance.id}]"
    logger.debug(f"{log_prefix} Preparando para enviar sinal...")

    webhook_url = os.environ.get('N8N_WEBHOOK_URL')
    if not webhook_url:
        logger.warning(f"{log_prefix} Envio cancelado. Var N8N_WEBHOOK_URL não configurada.")
        return

    payload = {
        "id": instance.id,
        "titulo": instance.titulo,
        "status": instance.status,
        "status_display": instance.get_status_display(),
        "data_entrada": instance.data_entrada.isoformat() if instance.data_entrada else None,
        "cliente_id": instance.cliente_id, # Usar _id é mais seguro
        "cliente_nome": instance.cliente.nome if instance.cliente else None,
        "produto_id": instance.produto_id, # Usar _id
        "produto_nome": instance.produto.nome if instance.produto else None,
        "advogado_id": instance.advogado_responsavel_id if instance.advogado_responsavel else None,
        "advogado_nome": instance.advogado_responsavel.get_full_name() if instance.advogado_responsavel else None,
        "advogado_email": instance.advogado_responsavel.email if instance.advogado_responsavel else None,
    }

    try:
        logger.info(f"{log_prefix} Enviando dados para: {webhook_url}")
        response = requests.post(webhook_url, json=payload, timeout=15) # Timeout um pouco maior
        response.raise_for_status() # Levanta erro para status >= 400
        logger.info(f"{log_prefix} Sinal enviado com sucesso! Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"{log_prefix} ERRO ao enviar sinal: {e}", exc_info=True)


def criar_pastas_sharepoint_logica(instance):
    """ Verifica estrutura e cria pastas no SharePoint. """
    log_prefix = f"[Signal SP - Caso {instance.id}]"
    logger.debug(f"{log_prefix} Iniciando lógica de criação de pastas...")

    try:
        # Busca a estrutura de pastas para a combinação Cliente/Produto
        estrutura = EstruturaPasta.objects.get(cliente=instance.cliente, produto=instance.produto)
        pastas_a_criar = estrutura.pastas.all().order_by('nome') # Ordena para consistência
    except EstruturaPasta.DoesNotExist:
        logger.warning(f"{log_prefix} Nenhuma estrutura de pastas encontrada.")
        return # Não há o que fazer

    if not pastas_a_criar.exists():
        logger.warning(f"{log_prefix} Estrutura encontrada, mas sem pastas associadas.")
        return # Não há o que fazer

    try:
        logger.info(f"{log_prefix} Estrutura encontrada. Iniciando criação no SharePoint...")
        sp = SharePoint()
        # Usa o ID do caso como nome da pasta principal para garantir unicidade
        nome_pasta_caso = str(instance.id)
        # Cria a pasta principal do caso
        folder_id = sp.criar_pasta_caso(nome_pasta_caso)
        if not folder_id:
             logger.error(f"{log_prefix} Falha ao criar a pasta principal '{nome_pasta_caso}'. Abortando subpastas.")
             return # Aborta se a pasta principal falhar

        # Salva o ID no objeto 'instance' em memória (será salvo pelo chamador)
        instance.sharepoint_folder_id = folder_id
        logger.info(f"{log_prefix} Pasta principal '{nome_pasta_caso}' criada com ID: {folder_id}")

        # Cria as subpastas definidas na estrutura
        for pasta in pastas_a_criar:
            try:
                sp.criar_subpasta(folder_id, pasta.nome)
                logger.debug(f"{log_prefix} Subpasta '{pasta.nome}' criada.")
            except Exception as sub_e: # Captura erro ao criar subpasta específica
                 logger.error(f"{log_prefix} ERRO ao criar subpasta '{pasta.nome}': {sub_e}", exc_info=True)
                 # Decide se quer continuar com as outras ou parar (aqui continua)

        logger.info(f"{log_prefix} Criação de pastas concluída.")

    except Exception as e: # Captura erro geral (conexão SP, criar pasta principal)
        logger.error(f"{log_prefix} ERRO GERAL ao criar pastas no SharePoint: {e}", exc_info=True)
        # Limpa o folder_id se a criação falhou no meio
        instance.sharepoint_folder_id = None


def enviar_email_novo_caso(instance):
    """ Prepara e envia e-mail de notificação para destinatário fixo. """
    log_prefix = f"[Signal Email - Caso {instance.id}]"
    logger.debug(f"{log_prefix} Preparando para enviar e-mail...")

    destinatario_fixo = os.environ.get('EMAIL_DESTINATARIO_NOVOS_CASOS')
    if not destinatario_fixo:
        logger.warning(f"{log_prefix} Envio cancelado. Var 'EMAIL_DESTINATARIO_NOVOS_CASOS' não definida no .env.")
        return

    destinatarios = [destinatario_fixo]

    try:
        # Monta o link ABSOLUTO para o caso (necessário para e-mails)
        # Tenta obter o domínio do settings, senão usa um fallback
        domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000') # Adicione SITE_DOMAIN ao seu settings.py
        protocol = 'https://' if getattr(settings, 'USE_HTTPS', False) else 'http://' # Verifica se HTTPS está ativo
        path = reverse('casos:detalhe_caso', kwargs={'pk': instance.id})
        link_caso_completo = f"{protocol}{domain}{path}"

        context = {
            'caso': instance,
            'link_caso': link_caso_completo
        }

        # Renderiza o corpo HTML (garanta que o template existe)
        html_message = render_to_string('emails/notificacao_novo_caso.html', context)

        # Envio do E-mail
        send_mail(
            subject=f'Novo Caso Criado: #{instance.id} - {instance.titulo}',
            message='', # Plain text opcional
            from_email=settings.EMAIL_HOST_USER, # Garanta que está no settings/.env
            recipient_list=destinatarios,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"{log_prefix} Notificação enviada com sucesso para {destinatarios[0]}.")
    except Exception as e:
        logger.error(f"{log_prefix} ERRO AO ENVIAR E-MAIL: {e}", exc_info=True)


# ==================================
# Signal Handler Principal
# ==================================

# O decorador @receiver foi removido, a conexão é feita no apps.py
def gatilho_pos_criacao_caso(sender, instance, created, **kwargs):
    """
    Orquestrador principal disparado APENAS na criação (`created=True`) de um novo Caso.
    Executa Workflow, cria FluxoInterno, pastas no SharePoint e envia E-mail/Webhook.
    """
    # Log inicial para TODAS as chamadas post_save
    logger.debug(f"[Signal Handler] Recebido post_save para Caso ID {instance.id}. Flag 'created'={created}")
    print(f"!!! GATILHO DISPARADO para Caso ID {instance.id}, Created={created} !!!") # Print de confirmação

    if created:
        log_prefix = f"[Signal Handler - Caso {instance.id} - CREATED]"
        logger.info(f"{log_prefix} --- PROCESSANDO Gatilhos de CRIAÇÃO ---")

        # 1. LÓGICA DO WORKFLOW
        logger.debug(f"{log_prefix} Iniciando lógica de Workflow...")
        try:
            workflow = Workflow.objects.get(cliente=instance.cliente, produto=instance.produto)
            fase_inicial = workflow.fases.order_by('ordem').first()
            if fase_inicial and transitar_fase: # Verifica se a função foi importada
                 transitar_fase(instance, fase_inicial) # Assumindo que transitar_fase já salva o caso
                 logger.info(f"{log_prefix} Workflow transitado para fase inicial '{fase_inicial.nome}'.")
            elif not fase_inicial:
                 logger.warning(f"{log_prefix} Workflow '{workflow.nome}' não tem fase inicial definida (ordem=1?).")
            elif not transitar_fase:
                 logger.warning(f"{log_prefix} Função 'transitar_fase' não encontrada. Pulando transição.")
        except Workflow.DoesNotExist:
             logger.warning(f"{log_prefix} Nenhum workflow definido para esta combinação Cliente/Produto.")
        except Exception as e:
             logger.error(f"{log_prefix} Erro na lógica de Workflow: {e}", exc_info=True)

        # 2. Criação do Fluxo Interno (COM VERIFICAÇÃO DE IDEMPOTÊNCIA)
        logger.debug(f"{log_prefix} Verificando/Criando FluxoInterno 'CRIACAO_CASO'...")
        try:
            # Verifica se já existe para evitar duplicação pelo signal duplo do runserver
            if not FluxoInterno.objects.filter(caso=instance, tipo_evento='CRIACAO_CASO').exists():
                autor_evento = getattr(instance, '_criador', None) or instance.advogado_responsavel
                FluxoInterno.objects.create(
                    caso=instance,
                    tipo_evento='CRIACAO_CASO',
                    descricao=f"Caso criado com status '{instance.get_status_display()}'.",
                    autor=instance.advogado_responsavel # Pode ser None se não definido na criação
                )
                logger.info(f"{log_prefix} FluxoInterno 'CRIACAO_CASO' criado.")
            else:
                logger.warning(f"{log_prefix} FluxoInterno 'CRIACAO_CASO' já existe. Pulando criação duplicada.")
        except Exception as e:
            logger.error(f"{log_prefix} Erro ao criar/verificar FluxoInterno: {e}", exc_info=True)


        # 3. LÓGICA DO SHAREPOINT (COM VERIFICAÇÃO DE IDEMPOTÊNCIA)
        logger.debug(f"{log_prefix} Iniciando lógica do SharePoint...")
        try:
            # Recarrega a instância do banco para pegar o valor mais recente de sharepoint_folder_id
            # Usa try-except caso o objeto ainda não esteja totalmente salvo (raro, mas possível)
            try:
                instance.refresh_from_db(fields=['sharepoint_folder_id'])
            except Caso.DoesNotExist:
                 logger.warning(f"{log_prefix} Não foi possível recarregar o Caso do banco antes de checar SharePoint ID.")

            if instance.sharepoint_folder_id:
                 logger.warning(f"{log_prefix} SharePoint Folder ID ('{instance.sharepoint_folder_id}') já existe. Pulando criação de pastas.")
            else:
                # Só executa a criação se o ID não existir
                criar_pastas_sharepoint_logica(instance) # Esta função define instance.sharepoint_folder_id em memória
                # Salva o ID IMEDIATAMENTE após a criação pela função
                if instance.sharepoint_folder_id:
                     # Usa update() direto no banco para evitar disparar outro post_save desnecessário
                     Caso.objects.filter(pk=instance.pk).update(sharepoint_folder_id=instance.sharepoint_folder_id)
                     logger.info(f"{log_prefix} SharePoint Folder ID salvo no banco: {instance.sharepoint_folder_id}")
                else:
                     logger.warning(f"{log_prefix} Função criar_pastas_sharepoint_logica não retornou/definiu um folder_id.")

        except Exception as e:
             logger.error(f"{log_prefix} Erro GERAL na lógica do SharePoint: {e}", exc_info=True)


        # 4. LÓGICA DE E-MAIL
        logger.debug(f"{log_prefix} Iniciando lógica de E-mail...")
        try:
            enviar_email_novo_caso(instance)
            # Log de sucesso/falha já está dentro da função enviar_email_novo_caso
        except Exception as e:
             # O try/except dentro da função já loga o erro, mas podemos logar aqui também se quisermos
             logger.error(f"{log_prefix} Erro não capturado ao chamar enviar_email_novo_caso: {e}", exc_info=True)

        # 5. LÓGICA N8N (Webhook)
        logger.debug(f"{log_prefix} Iniciando lógica do n8n...")
        try:
            enviar_sinal_para_n8n(instance)
             # Log de sucesso/falha já está dentro da função enviar_sinal_para_n8n
        except Exception as e:
             logger.error(f"{log_prefix} Erro não capturado ao chamar enviar_sinal_para_n8n: {e}", exc_info=True)


        logger.info(f"{log_prefix} --- FIM dos Gatilhos de CRIAÇÃO ---")

    else: # Se created == False
        # Loga apenas se o nível for DEBUG para não poluir
        logger.debug(f"[Signal Handler] Sinal post_save para Caso ID {instance.id} ignorado (created=False).")

# --- Fim do Arquivo ---