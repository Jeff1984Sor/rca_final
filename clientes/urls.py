# clientes/urls.py
from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    # URL para a lista: /clientes/
    path('', views.lista_clientes, name='lista_clientes'),
    path('novo/', views.criar_cliente, name='criar_cliente'),
    path('editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('deletar/<int:pk>/', views.deletar_cliente, name='deletar_cliente'),
    path('exportar/excel/', views.exportar_clientes_excel, name='exportar_excel'),
    # URL para o formulário de criação: /clientes/novo/
    # path('novo/', views.criar_cliente, name='criar_cliente'), # Vamos criar essa view depois
]