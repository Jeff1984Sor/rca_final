from django.contrib import admin
from django.urls import path
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls', namespace='core')),

    # Os outros apps continuam em seus próprios caminhos
    path('clientes/', include('clientes.urls', namespace='clientes')),
    # path('equipamentos/', include('equipamentos.urls', namespace='equipamentos')), # Futuro
    # path('casos/', include('casos.urls', namespace='casos')),                   # Futuro
]
