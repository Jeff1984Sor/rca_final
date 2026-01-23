# casos/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'casos'

# --- LÓGICA DA API ---
router = DefaultRouter()
router.register(r'casos', views.CasoAPIViewSet, basename='caso-api')

urlpatterns_api = [
    path('', include(router.urls)),
]

# --- LÓGICA DAS VIEWS NORMAIS ---
urlpatterns = [
    # --- CASOS ---
    path('lista/', views.lista_casos, name='lista_casos'),
    path('novo/', views.selecionar_produto_cliente, name='selecionar_produto_cliente'),
    path('novo/<int:cliente_id>/<int:produto_id>/', views.criar_caso, name='criar_caso'),
    path('<int:pk>/', views.detalhe_caso, name='detalhe_caso'),
    path('editar/<int:pk>/', views.editar_caso, name='editar_caso'),
    
    # --- TOMADORES (CRUD) ---
    path('tomadores/', views.TomadorListView.as_view(), name='lista_tomadores'),
    path('tomadores/novo/', views.TomadorCreateView.as_view(), name='criar_tomador'),
    path('tomadores/<int:pk>/editar/', views.TomadorUpdateView.as_view(), name='editar_tomador'),
    path('tomadores/<int:pk>/deletar/', views.TomadorDeleteView.as_view(), name='deletar_tomador'),

    # --- SEGURADOS (CRUD) ---
    path('segurados/', views.SeguradoListView.as_view(), name='lista_segurados'),
    path('segurados/novo/', views.SeguradoCreateView.as_view(), name='criar_segurado'),
    path('segurados/<int:pk>/', views.SeguradoDetailView.as_view(), name='detalhe_segurado'),
    path('segurados/<int:pk>/editar/', views.SeguradoUpdateView.as_view(), name='editar_segurado'),
    path('segurados/<int:pk>/deletar/', views.SeguradoDeleteView.as_view(), name='deletar_segurado'),

    # --- CORRETORES (CRUD) ---
    path('corretores/', views.CorretorListView.as_view(), name='lista_corretores'),
    path('corretores/novo/', views.CorretorCreateView.as_view(), name='criar_corretor'),
    path('corretores/<int:pk>/', views.CorretorDetailView.as_view(), name='detalhe_corretor'),
    path('corretores/<int:pk>/editar/', views.CorretorUpdateView.as_view(), name='editar_corretor'),
    path('corretores/<int:pk>/deletar/', views.CorretorDeleteView.as_view(), name='deletar_corretor'),

    # --- AJAX ---
    path('ajax/criar-tomador/', views.criar_tomador_ajax, name='ajax_criar_tomador'),
    path('ajax/criar-segurado/', views.criar_segurado_ajax, name='ajax_criar_segurado'),
    path('ajax/criar-corretor/', views.criar_corretor_ajax, name='ajax_criar_corretor'),
    path('ajax/segurado/<int:pk>/detalhes/', views.obter_detalhes_segurado, name='ajax_segurado_detalhes'),
    path('ajax/corretor/<int:pk>/detalhes/', views.obter_detalhes_corretor, name='ajax_corretor_detalhes'),

    # --- MODAIS HTMX ---
    path('caso/<int:pk>/editar-info-basicas/', views.editar_info_basicas, name='editar_info_basicas'),
    path('caso/<int:pk>/editar-dados-adicionais/', views.editar_dados_adicionais, name='editar_dados_adicionais'),
    
    # --- AÇÕES ESPECÍFICAS ---
    path('timesheet/editar/<int:pk>/', views.editar_timesheet, name='editar_timesheet'),
    path('timesheet/deletar/<int:pk>/', views.deletar_timesheet, name='deletar_timesheet'),
    path('parcela/<int:pk>/quitar/', views.quitar_parcela, name='quitar_parcela'),
    path('parcela/<int:pk>/pagar/', views.pagar_parcela, name='pagar_parcela'),
    path('parcela/<int:pk>/comprovante/', views.upload_comprovante_parcela, name='upload_comprovante_parcela'),
    path('parcela/<int:pk>/comprovante/ver/', views.baixar_comprovante_parcela, name='baixar_comprovante_parcela'),
    path('acordo/editar/<int:pk>/', views.editar_acordo, name='editar_acordo'),
    path('despesa/editar/<int:pk>/', views.editar_despesa, name='editar_despesa'),

    # --- SHAREPOINT / ARQUIVOS ---
    path('pasta/criar-raiz/', views.criar_pasta_raiz_sharepoint, name='criar_pasta_raiz_sharepoint'),
    path('<int:pk>/pasta/criar/', views.criar_pasta_para_caso, name='criar_pasta_para_caso'),
    path('<int:pk>/anexos/painel/', views.carregar_painel_anexos, name='carregar_painel_anexos'),
    path('<int:caso_pk>/anexos/upload/', views.upload_arquivo_sharepoint, name='upload_arquivo_sharepoint'),
    path('<int:caso_pk>/anexos/baixar/<str:arquivo_id>/', views.baixar_arquivo_sharepoint, name='baixar_arquivo_sharepoint'),
    path('<int:caso_pk>/anexos/deletar/', views.deletar_arquivo_sharepoint, name='deletar_arquivo_sharepoint'),
    path('<int:caso_pk>/anexos/criar-pasta/', views.criar_pasta_sharepoint, name='criar_pasta_sharepoint'),
    path('pasta/<str:folder_id>/conteudo/', views.carregar_conteudo_pasta, name='carregar_conteudo_pasta'),
    path('anexo/preview/<str:item_id>/', views.preview_anexo, name='preview_anexo'),
    path('anexo/excluir/<str:item_id>/', views.excluir_anexo_sharepoint, name='excluir_anexo_sharepoint'),
    path('<int:pk>/anexos/recriar-pastas/', views.recriar_pastas_sharepoint, name='recriar_pastas_sharepoint'),

    # --- ANALYSER ---
    path('<int:pk>/analyser/painel/', views.carregar_painel_analyser, name='carregar_painel_analyser'),
    path('<int:pk>/analyser/arquivos/', views.listar_arquivos_para_analise, name='listar_arquivos_para_analise'),
    path('<int:pk>/analyser/navegador/', views.analyser_navegador, name='analyser_navegador'),
    path('<int:pk>/analyser/navegador/<str:folder_id>/', views.analyser_navegador_pasta, name='analyser_navegador_pasta'),

    # --- EXPORTAÇÃO / IMPORTAÇÃO ---
    path('exportar/selecao/', views.selecionar_filtros_exportacao, name='selecionar_filtros_exportacao'),
    path('exportar/dinamico/<int:cliente_id>/<int:produto_id>/', views.exportar_casos_dinamico, name='exportar_casos_dinamico'),
    
    # ✅ CORREÇÃO AQUI: O nome agora é 'exportar_excel' para bater com seu HTML
    path('exportar/', views.exportar_casos_excel, name='exportar_excel'),
    
    path('<int:pk>/exportar/andamentos/', views.exportar_andamentos_excel, name='exportar_andamentos_excel'),
    path('<int:pk>/exportar/timesheet/', views.exportar_timesheet_excel, name='exportar_timesheet_excel'),
    path('<int:pk>/exportar/timesheet/pdf/', views.exportar_timesheet_pdf, name='exportar_timesheet_pdf'),
    path('importar/', views.importar_casos_view, name='importar_casos_view'),

    # --- VISÕES ---
    path('visao/prazos/', views.visao_casos_prazo, name='visao_casos_prazo'),
    path('ajax/tomador/<int:pk>/detalhes/', views.obter_detalhes_tomador, name='ajax_tomador_detalhes'),
    path('tomadores/exportar/excel/', views.exportar_tomadores_excel, name='exportar_tomadores_excel'),
    path('tomadores/exportar/pdf/', views.exportar_tomadores_pdf, name='exportar_tomadores_pdf'),
    path('segurados/exportar/excel/', views.exportar_segurados_excel, name='exportar_segurados_excel'),
    path('corretores/exportar/excel/', views.exportar_corretores_excel, name='exportar_corretores_excel'),
    path('caso/<int:pk>/trocar-tomador/', views.trocar_tomador_do_caso, name='trocar_tomador_do_caso'),
    
    # API
    path('', include(router.urls)),
]
