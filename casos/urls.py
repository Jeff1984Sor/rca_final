# casos/urls.py
from django.urls import path
from . import views

app_name = 'casos'

urlpatterns = [
    # Por enquanto, teremos apenas a URL para o primeiro passo da criação.
    # A lista de casos virá depois.
    path('', views.lista_casos, name='lista_casos'),
    path('novo/', views.selecionar_produto_cliente, name='selecionar_produto_cliente'),
    path('novo/<int:cliente_id>/<int:produto_id>/', views.criar_caso, name='criar_caso'),
]