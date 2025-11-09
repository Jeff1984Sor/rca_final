# workflow/urls.py
from django.urls import path
from . import views

app_name = 'workflow'

urlpatterns = [
    # ==========================================================
    # 1. VIEWS PRINCIPAIS E LISTAGENS
    # ==========================================================
    # Lista de todos os workflows (Página principal do app)
    path('', views.lista_workflows, name='lista_workflows'),
    # Lista de todas as ações pendentes no sistema
    path('acoes/', views.lista_todas_acoes, name='lista_todas_acoes'),
    # Visão Kanban
    path('kanban/', views.kanban_view, name='kanban'),

    # ==========================================================
    # 2. WORKFLOW BUILDER (Criação e Edição)
    # ==========================================================
    # Página para criar um NOVO workflow
    path('builder/', views.workflow_builder, name='workflow_builder'),
    # Página para EDITAR um workflow existente
    path('builder/<int:pk>/', views.workflow_builder, name='workflow_builder_edit'),

    # ==========================================================
    # 3. AÇÕES SOBRE UM WORKFLOW ESPECÍFICO (via AJAX ou POST)
    # ==========================================================
    # Endpoint para salvar o workflow (via JSON/AJAX)
    path('salvar/', views.salvar_workflow_json, name='salvar_workflow_json'),
    # Endpoint para carregar os dados de um workflow (via JSON/AJAX)
    path('carregar/<int:pk>/', views.carregar_workflow_json, name='carregar_workflow_json'),
    # Ação para deletar um workflow
    path('deletar/<int:pk>/', views.deletar_workflow, name='deletar_workflow'),
    # Ação para duplicar um workflow
    path('duplicar/<int:pk>/', views.duplicar_workflow, name='duplicar_workflow'),
    
    # ==========================================================
    # 4. AÇÕES RELACIONADAS A CASOS (Execução do Workflow)
    # ==========================================================
    # Executa uma ação específica de uma instância
    path('instancia-acao/<int:pk>/executar/', views.executar_acao, name='executar_acao'),
    # Carrega o painel de ações de um caso (HTMX)
    path('caso/<int:caso_id>/painel-acoes/', views.carregar_painel_acoes, name='carregar_painel_acoes'),
]