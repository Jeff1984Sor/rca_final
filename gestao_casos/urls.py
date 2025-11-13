# gestao_casos/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.authtoken import views as authtoken_views

# Importa suas views customizadas
from core.views import CustomLoginView, logout_view
from casos.views import importar_casos_view

urlpatterns = [
    # ==========================================================
    # 1. ADMIN E ROTAS DE API
    # ==========================================================
    path('admin/', admin.site.urls),
    path('api-token-auth/', authtoken_views.obtain_auth_token),
    
    # ==========================================================
    # 2. AUTENTICAÇÃO (Tudo centralizado aqui)
    # ==========================================================
    # Sobrescreve as URLs de login/logout com as suas views customizadas
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    
    # Inclui TODAS as outras URLs de autenticação padrão do Django
    # (troca de senha, reset de senha, etc.) sob o prefixo 'accounts/'
    path('accounts/', include('django.contrib.auth.urls')),
    
    # ==========================================================
    # 3. APLICAÇÕES PRINCIPAIS
    # ==========================================================
    # A URL raiz (homepage) é gerenciada pelo app 'core'
    path('', include('core.urls', namespace='core')),
    
    # URLs específicas dos seus apps, cada uma com seu namespace
    path('casos/', include('casos.urls', namespace='casos')),
    path('clientes/', include('clientes.urls', namespace='clientes')),
    path('pastas/', include('pastas.urls', namespace='pastas')),
    path('workflow/', include('workflow.urls', namespace='workflow')), # <-- Namespace adicionado
    path('equipamentos/', include('equipamentos.urls', namespace='equipamentos')),
    path('campos-custom/', include('campos_custom.urls', namespace='campos_custom')),
    path('analyser/', include('analyser.urls')),
    
    # ==========================================================
    # 4. ROTAS ESPECÍFICAS (Importação, etc.)
    # ==========================================================
    path('importar/', importar_casos_view, name='importar_casos_view'),
]