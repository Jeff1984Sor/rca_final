"""
WSGI config for gestao_casos project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import dotenv
from django.core.wsgi import get_wsgi_application

def main():
    dotenv.read_dotenv() # Adicione esta linha para carregar as variáveis
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_casos.settings')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_casos.settings')

application = get_wsgi_application()
