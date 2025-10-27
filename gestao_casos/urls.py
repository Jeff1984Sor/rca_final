# gestao_casos/urls.py (VERSÃO CORRIGIDA E FINAL)

from django.contrib import admin
from django.urls import path, include
# Importa as views que acabamos de garantir que existem
from core.views import CustomLoginView, logout_view
from casos.urls import urlpatterns_api as casos_api_urls
from rest_framework.authtoken import views as authtoken_views
from django.contrib.auth import views as auth_views
from . import views
from casos.views import importar_casos_view

urlpatterns = [
    # 1. Rotas de Admin e Bibliotecas
    path('admin/', admin.site.urls),
    path('casos/', include('casos.urls')),
    path('api/v1/', include(casos_api_urls)),
    path('api-token-auth/', authtoken_views.obtain_auth_token),
    path('trocar-senha/ok/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    path('reset-senha/', include('django.contrib.auth.urls')), 
    


    # 2. Rotas de Autenticação
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('trocar-senha/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    
    # 3. Rotas dos Seus Aplicativos
    path('', include('core.urls', namespace='core')),
    path('clientes/', include('clientes.urls', namespace='clientes')),
    path('casos/', include('casos.urls', namespace='casos')),
    path('pastas/', include('pastas.urls', namespace='pastas')),
    path('workflow/', include('workflow.urls', namespace='workflow')),
    path('equipamentos/', include('equipamentos.urls', namespace='equipamentos')),
    path('campos-custom/', include('campos_custom.urls', namespace='campos_custom')),
    path('exportar/', include('casos.urls')),
    path('importar/', importar_casos_view, name='importar_casos_view'),
    ]