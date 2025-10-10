from django.contrib import admin
from django.urls import path
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls', namespace='core')),
    path('clientes/', include('clientes.urls', namespace='clientes')),
    
    # Garanta que esta linha exista para conectar ao app de casos
    path('casos/', include('casos.urls', namespace='casos')),
]
