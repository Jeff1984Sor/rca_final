# analyser/urls.py

from django.urls import path
from . import views

app_name = 'analyser'

urlpatterns = [
    # Modelos
    path('modelos/', views.listar_modelos, name='listar_modelos'),
    path('modelos/criar/', views.criar_modelo, name='criar_modelo'),
    path('modelos/<int:pk>/editar/', views.editar_modelo, name='editar_modelo'),
    path('modelos/<int:pk>/deletar/', views.deletar_modelo, name='deletar_modelo'),
    
    # AJAX
    path('ajax/campos-produto/', views.ajax_buscar_campos, name='ajax_campos_produto'),
    
    # Análise
    path('analisar/<int:caso_id>/', views.selecionar_arquivos, name='selecionar_arquivos'),
    path('resultado/<int:resultado_id>/', views.resultado_analise, name='resultado'),
    path('aplicar/<int:resultado_id>/', views.aplicar_ao_caso, name='aplicar_ao_caso'),

    path('analisar/<int:caso_id>/iniciar/', views.iniciar_analise, name='iniciar_analise'),
    path('caso/<int:caso_id>/carregar-arquivos/', views.carregar_arquivos_sharepoint, name='carregar_arquivos'),
]