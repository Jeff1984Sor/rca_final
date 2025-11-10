# casos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# --- LÓGICA DA API ---
# 1. O roteador é definido
router = DefaultRouter()
router.register(r'casos', views.CasoAPIViewSet, basename='caso-api')

# 2. Crie a lista 'urlpatterns_api' (ISTO ESTÁ FALTANDO)
# O seu gestao_casos/urls.py está procurando por ESTA variável.
urlpatterns_api = [
    path('', include(router.urls)),
]


# --- LÓGICA DAS VIEWS NORMAIS ---
# 3. Defina as 'urlpatterns' normais (SEM as urls do router)
app_name = 'casos'
urlpatterns = [
    # A linha 'path('', include(router.urls)),' foi REMOVIDA daqui.
    path('lista/', views.lista_casos, name='lista_casos'),
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
    path('parcela/<int:pk>/quitar/', views.quitar_parcela, name='quitar_parcela'),
    path('acordo/editar/<int:pk>/', views.editar_acordo, name='editar_acordo'),
    path('despesa/editar/<int:pk>/', views.editar_despesa, name='editar_despesa'),
    path('pasta/<str:folder_id>/conteudo/', views.carregar_conteudo_pasta, name='carregar_conteudo_pasta'),
    path('pasta/<str:folder_id>/upload/', views.upload_arquivo_sharepoint, name='upload_arquivo'),
    path('anexo/preview/<str:item_id>/', views.preview_anexo, name='preview_anexo'),
    path('pasta/<str:parent_folder_id>/criar/', views.criar_pasta_sharepoint, name='criar_pasta'),
    path('anexo/excluir/<str:item_id>/', views.excluir_anexo_sharepoint, name='excluir_anexo'),
    path('selecionar/', views.selecionar_filtros_exportacao, name='selecionar_filtros_exportacao'),
    path('exportar/selecionar/', views.selecionar_filtros_exportacao, name='selecionar_filtros_exportacao'),
    path('exportar/<int:cliente_id>/<int:produto_id>/', views.exportar_casos_dinamico, name='exportar_casos_dinamico'),
    path('importar/', views.importar_casos_view, name='importar_casos_view'),
    path('visao-prazos/', views.visao_casos_prazo, name='visao_casos_prazo'),
    path('caso/<int:pk>/editar-info-basicas/', views.editar_info_basicas, name='editar_info_basicas'),
    path('caso/<int:pk>/editar-dados-adicionais/', views.editar_dados_adicionais, name='editar_dados_adicionais'),

]