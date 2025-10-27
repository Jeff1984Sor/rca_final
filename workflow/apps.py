# Arquivo: workflow/apps.py

from django.apps import AppConfig
from django.db.models.signals import post_save # Importe o sinal aqui

class WorkflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workflow'

    def ready(self):
        print("--- WorkflowConfig: ready() method is being called! ---") 
        
        # 1. Importe o MODELO que envia o sinal
        from casos.models import Caso 
        
        # 2. Importe a FUNÇÃO que vai receber o sinal
        from .signals import gatilho_pos_criacao_caso 
        
        # 3. CONECTE explicitamente
        post_save.connect(gatilho_pos_criacao_caso, sender=Caso, dispatch_uid="gatilho_pos_criacao_caso_workflow")
        
        print("--- Signal post_save connected explicitly for Caso model ---") # Confirmação da conexão
        
        # A linha 'import workflow.signals' não é mais estritamente necessária aqui, 
        # mas pode deixar se outros signals estiverem lá.
        # import workflow.signals