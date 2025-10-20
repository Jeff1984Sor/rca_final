# gestao_casos/celery.py

import os
from celery import Celery

# Define o módulo de configurações padrão do Django para o Celery.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_casos.settings')

# Cria a instância da aplicação Celery
app = Celery('gestao_casos')

# O Celery vai buscar as suas configurações no ficheiro settings.py do Django.
# O namespace='CELERY' significa que todas as configurações do Celery no settings.py
# devem começar com o prefixo "CELERY_", por exemplo: CELERY_BROKER_URL
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega automaticamente os módulos de tarefas (tasks.py) de todos os apps registados.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')