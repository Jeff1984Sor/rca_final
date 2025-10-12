from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Rotas Padrão
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls', namespace='core')),
    path('clientes/', include('clientes.urls', namespace='clientes')),
    path('casos/', include('casos.urls', namespace='casos')),
    path('pastas/', include('pastas.urls', namespace='pastas')),
    path('workflow/', include('workflow.urls', namespace='workflow')),
]