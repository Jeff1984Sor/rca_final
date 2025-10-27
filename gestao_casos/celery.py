# gestao_casos/celery.py
import os
from celery import Celery

# Define o módulo de settings padrão do Django para o 'celery'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_casos.settings') # AJUSTE o nome do seu projeto

# Cria a instância do Celery
app = Celery('gestao_casos') # AJUSTE o nome do seu projeto

# Usa string aqui para que o worker não precise serializar
# o objeto de configuração diretamente.
# - namespace='CELERY' significa todas as configs Celery no settings.py
#   devem ter um prefixo `CELERY_` (ex: CELERY_BROKER_URL).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega automaticamente tasks de todos os 'tasks.py' nos INSTALLED_APPS.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')