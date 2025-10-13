# campos_custom/admin.py

from django.contrib import admin
from .models import CampoPersonalizado, ConfiguracaoCampoPersonalizado, ValorCampoPersonalizado

# ==============================================================================
# ADMIN PARA A BIBLIOTECA DE CAMPOS
# Permite criar e gerenciar os campos que podem ser usados.
# ==============================================================================
@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ('nome_campo', 'tipo_campo')
    list_filter = ('tipo_campo',)
    search_fields = ('nome_campo',)
    ordering = ('nome_campo',)


# ==============================================================================
# ADMIN PARA A CONFIGURAÇÃO (A PARTE MAIS IMPORTANTE)
# É aqui que você vai associar Cliente + Produto -> Campo da Biblioteca
# ==============================================================================
@admin.register(ConfiguracaoCampoPersonalizado)
class ConfiguracaoCampoAdmin(admin.ModelAdmin):

    change_list_template = "admin/campos_custom/configuracaocampopersonalizado/change_list.html"
    
    # Mostra as colunas principais na lista
    list_display = ('cliente', 'produto', 'campo', 'ordem', 'obrigatorio')
    
    # Adiciona filtros poderosos na lateral
    list_filter = ('cliente', 'produto')
    
    # Define os campos que a barra de busca vai pesquisar
    search_fields = ('cliente__nome_razao_social', 'produto__nome', 'campo__nome_campo')
    
    # Melhora drasticamente a usabilidade ao selecionar Cliente, Produto e Campo,
    # transformando o select em um campo de busca.
    autocomplete_fields = ['cliente', 'produto', 'campo']
    
    # Organiza a ordem da lista
    ordering = ('cliente', 'produto', 'ordem')


# ==============================================================================
# ADMIN PARA OS VALORES PREENCHIDOS (Geralmente para consulta)
# É útil para ver os dados que os usuários preencheram nos casos.
# ==============================================================================
@admin.register(ValorCampoPersonalizado)
class ValorCampoAdmin(admin.ModelAdmin):
    list_display = ('get_caso_id', 'get_cliente_do_caso', 'campo', 'valor')
    search_fields = ('caso__id', 'campo__nome_campo', 'valor')
    
    # Deixamos os campos como somente leitura, pois a edição deve ser feita na tela do Caso.
    readonly_fields = ('caso', 'campo', 'valor')

    # Funções para exibir informações do caso relacionado na lista
    @admin.display(description='ID do Caso', ordering='caso__id')
    def get_caso_id(self, obj):
        return obj.caso.id

    @admin.display(description='Cliente do Caso', ordering='caso__cliente__nome_razao_social')
    def get_cliente_do_caso(self, obj):
        if obj.caso and obj.caso.cliente:
            return obj.caso.cliente.nome_razao_social
        return "N/A"