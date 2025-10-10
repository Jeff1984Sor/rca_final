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
    path('<int:pk>/', views.detalhe_caso, name='detalhe_caso'),
    path('editar/<int:pk>/', views.editar_caso, name='editar_caso'),
    path('exportar/excel/', views.exportar_casos_excel, name='exportar_excel'),
    path('<int:pk>/exportar/andamentos/', views.exportar_andamentos_excel, name='exportar_andamentos_excel'),
    path('<int:pk>/exportar/timesheet/', views.exportar_timesheet_excel, name='exportar_timesheet_excel'),
    path('<int:pk>/exportar/timesheet/pdf/', views.exportar_timesheet_pdf, name='exportar_timesheet_pdf'),
    path('timesheet/editar/<int:pk>/', views.editar_timesheet, name='editar_timesheet'),
    path('timesheet/deletar/<int:pk>/', views.deletar_timesheet, name='deletar_timesheet'),

]