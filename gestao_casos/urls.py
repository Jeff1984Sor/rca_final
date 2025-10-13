from django.contrib import admin
from django.urls import path, include
from core.views import CustomLoginView, logout_view

urlpatterns = [
    # Rotas Padrão
    path('admin/', admin.site.urls),
    #path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/logout/', logout_view, name='logout'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls', namespace='core')),
    path('clientes/', include('clientes.urls', namespace='clientes')),
    path('casos/', include('casos.urls', namespace='casos')),
    path('pastas/', include('pastas.urls', namespace='pastas')),
    path('workflow/', include('workflow.urls', namespace='workflow')),
]