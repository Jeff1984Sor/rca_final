from django.contrib import admin
from django.urls import path
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),

    # A raiz do site agora aponta para o app 'core'
    path('', include('core.urls', namespace='core')),

    # Os outros apps continuam em seus próprios caminhos
    path('clientes/', include('clientes.urls', namespace='clientes')),
    # path('equipamentos/', include('equipamentos.urls', namespace='equipamentos')), # Futuro
    # path('casos/', include('casos.urls', namespace='casos')),                   # Futuro
]
