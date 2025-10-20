# gestao_casos/__init__.py

# Isto garante que a aplicação Celery seja carregada quando o Django iniciar.
from .celery import app as celery_app

__all__ = ('celery_app',)
