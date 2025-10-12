# workflow/apps.py
from django.apps import AppConfig

class WorkflowConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workflow'

    # ADICIONE ESTE MÉTODO
    def ready(self):
        import workflow.signals