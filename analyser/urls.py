# analyser/urls.py

from django.urls import path
from . import views

app_name = 'analyser'

urlpatterns = [
    # Seleção de arquivos e início de análise
    path('analisar/<int:caso_id>/', views.selecionar_arquivos, name='selecionar_arquivos'),
    path('analisar/<int:caso_id>/arquivos/', views.carregar_arquivos_navegacao, name='carregar_arquivos_navegacao'),
    path('analisar/<int:caso_id>/iniciar/', views.iniciar_analise, name='iniciar_analise'),
    
    # Resultado e logs
    path('resultado/<int:resultado_id>/', views.resultado_analise, name='resultado_analise'),
    path('resultado/<int:resultado_id>/logs/', views.carregar_logs, name='carregar_logs'),
    
    # Aplicar ao caso
    path('resultado/<int:resultado_id>/aplicar/', views.aplicar_ao_caso, name='aplicar_ao_caso'),
    
    # Gerenciamento de modelos
    path('modelos/', views.listar_modelos, name='listar_modelos'),
    path('modelos/criar/', views.criar_modelo, name='criar_modelo'),
    path('modelos/<int:pk>/editar/', views.editar_modelo, name='editar_modelo'),
    path('modelos/<int:pk>/deletar/', views.deletar_modelo, name='deletar_modelo'),
    
    # AJAX
    path('ajax/campos/', views.ajax_buscar_campos, name='ajax_buscar_campos'),
    path('debug/pasta/<int:caso_id>/', views.debug_pasta_caso, name='debug_pasta_caso'),
]