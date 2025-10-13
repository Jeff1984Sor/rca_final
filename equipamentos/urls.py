# equipamentos/urls.py

from django.urls import path
from .views import (
    EquipamentoListView,
    EquipamentoDetailView,
    EquipamentoCreateView,
    EquipamentoUpdateView,
)

app_name = 'equipamentos'

urlpatterns = [
    # Ex: /equipamentos/
    path('', EquipamentoListView.as_view(), name='equipamento_list'),
    
    # Ex: /equipamentos/novo/
    path('novo/', EquipamentoCreateView.as_view(), name='equipamento_create'),
    
    # Ex: /equipamentos/5/ (para ver detalhes do equipamento com ID 5)
    path('<int:pk>/', EquipamentoDetailView.as_view(), name='equipamento_detail'),
    
    # Ex: /equipamentos/5/editar/ (para editar o equipamento com ID 5)
    path('<int:pk>/editar/', EquipamentoUpdateView.as_view(), name='equipamento_update'),
]