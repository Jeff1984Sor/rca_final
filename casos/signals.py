# casos/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Caso
from .emails import enviar_email_novo_caso
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Caso
from pastas.models import EstruturaPasta
from integrations.sharepoint import SharePoint

@receiver(post_save, sender=Caso)
def caso_post_save(sender, instance, created, **kwargs):
    """
    Dispara após um Caso ser salvo. Se foi uma criação, envia o e-mail.
    """
    if created:  # 'created' é True apenas na primeira vez que o objeto é salvo
        print(f"Sinal recebido: Novo caso #{instance.id} criado. Preparando para enviar e-mail...")
        enviar_email_novo_caso(instance)

@receiver(post_save, sender=Caso)
def criar_pastas_sharepoint(sender, instance, created, **kwargs):
    """
    Esta função é chamada toda vez que um objeto 'Caso' é salvo.
    """
    # 1. Executa a lógica APENAS na primeira vez que o caso é criado
    if created:
        print(f"Sinal recebido: Novo caso #{instance.id} criado.")
        
        # 2. Busca a estrutura de pastas definida para este Cliente + Produto
        try:
            estrutura = EstruturaPasta.objects.get(
                cliente=instance.cliente,
                produto=instance.produto
            )
        except EstruturaPasta.DoesNotExist:
            # Se não houver estrutura definida, não faz nada e encerra a função
            print("Nenhuma estrutura de pastas encontrada para esta combinação. Nenhuma ação será tomada.")
            return

        # Se encontrou uma estrutura, continua...
        pastas_a_criar = estrutura.pastas.all()
        if not pastas_a_criar:
            print("Estrutura encontrada, mas sem pastas associadas. Nenhuma ação será tomada.")
            return

        try:
            # 3. Conecta ao SharePoint
            sp = SharePoint()
            
            # 4. Cria a pasta principal para o caso
            nome_pasta_caso = str(instance.id)
            folder_id = sp.criar_pasta_caso(nome_pasta_caso)
            
            # 5. Salva o ID da pasta principal no nosso modelo de Caso
            instance.sharepoint_folder_id = folder_id
            # Usamos update_fields para evitar disparar o sinal novamente em um loop infinito
            instance.save(update_fields=['sharepoint_folder_id'])
            
            # 6. Cria as subpastas
            for pasta in pastas_a_criar:
                sp.criar_subpasta(folder_id, pasta.nome)
            
            print("Processo de criação de pastas no SharePoint concluído com sucesso!")

        except Exception as e:
            # Se qualquer coisa der errado na comunicação com o SharePoint,
            # registramos o erro no console para depuração.
            print(f"ERRO ao criar pastas no SharePoint para o Caso #{instance.id}: {e}")