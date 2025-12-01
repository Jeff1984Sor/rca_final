# equipamentos/urls.py

from django.urls import path
from .views import (
    EquipamentoListView,
    EquipamentoDetailView,
    EquipamentoCreateView,
    EquipamentoUpdateView,
    api_atualizar_hardware, # A função correta da API
)

app_name = 'equipamentos'

urlpatterns = [
    # Ex: /equipamentos/
    path('', EquipamentoListView.as_view(), name='equipamento_list'),
    
    # Ex: /equipamentos/novo/
    path('novo/', EquipamentoCreateView.as_view(), name='equipamento_create'),
    
    # Ex: /equipamentos/5/
    path('<int:pk>/', EquipamentoDetailView.as_view(), name='equipamento_detail'),
    
    # Ex: /equipamentos/5/editar/
    path('<int:pk>/editar/', EquipamentoUpdateView.as_view(), name='equipamento_update'),
    
    # Rota da API
    # O script python (agente) vai mandar os dados para este endereço:
    path('api/atualizar-hardware/', api_atualizar_hardware, name='api_atualizar_hardware'),
]