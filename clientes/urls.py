# clientes/urls.py
from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    # URL para a lista: /clientes/
    path('', views.lista_clientes, name='lista_clientes'),
    # URL para o formulário de criação: /clientes/novo/
    # path('novo/', views.criar_cliente, name='criar_cliente'), # Vamos criar essa view depois
]