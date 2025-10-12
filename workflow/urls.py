# workflow/urls.py
from django.urls import path
from . import views

app_name = 'workflow'

urlpatterns = [
    path('acao/<int:pk>/executar/', views.executar_acao, name='executar_acao'),
    path('caso/<int:caso_id>/painel/', views.carregar_painel_acoes, name='carregar_painel_acoes'),
    path('acoes/', views.lista_todas_acoes, name='lista_todas_acoes'),
    path('kanban/', views.kanban_view, name='kanban'),
]