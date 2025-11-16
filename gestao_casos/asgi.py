# gestao_casos/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import analyser.routing # Vamos criar este arquivo a seguir

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestao_casos.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            analyser.routing.websocket_urlpatterns
        )
    ),
})