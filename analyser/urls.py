# analyser/urls.py

from django.urls import path
from . import views

app_name = 'analyser'

urlpatterns = [path('modelos/', views.listar_modelos, name='listar_modelos'),
    
    # ✅ CORRIGIDO: Ambas as rotas agora apontam para a mesma view
    path('modelos/criar/', views.criar_ou_editar_modelo, name='criar_modelo'),
    path('modelos/<int:pk>/editar/', views.criar_ou_editar_modelo, name='editar_modelo'),
    
    path('modelos/<int:pk>/deletar/', views.deletar_modelo, name='deletar_modelo'),
    
    path('analisar/<int:caso_id>/', views.selecionar_arquivos, name='selecionar_arquivos'),
    path('analisar/<int:caso_id>/iniciar/', views.iniciar_analise, name='iniciar_analise'),
    
    path('resultado/<int:resultado_id>/', views.resultado_analise, name='resultado_analise'),
    path('resultado/<int:resultado_id>/aplicar/', views.aplicar_ao_caso, name='aplicar_ao_caso'),
    
    path('ajax/buscar-campos/', views.ajax_buscar_campos, name='ajax_buscar_campos'),
    path('caso/<int:caso_id>/carregar-arquivos/', views.carregar_arquivos_sharepoint, name='carregar_arquivos'),

]