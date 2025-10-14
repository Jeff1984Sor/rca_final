# campos_custom/admin.py

from django.contrib import admin
from .models import CampoPersonalizado, EstruturaDeCampos, EstruturaCampoOrdenado, ValorCampoPersonalizado
from ordered_model.admin import OrderedTabularInline, OrderedModelAdmin

# ==============================================================================
# ADMIN PARA A BIBLIOTECA DE CAMPOS
# Essencial ter o search_fields para o autocomplete funcionar.
# ==============================================================================
@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ('nome_campo', 'nome_variavel', 'tipo_campo')
    search_fields = ('nome_campo', 'nome_variavel')
    ordering = ('nome_campo',)
    list_filter = ('tipo_campo',)
    
    fieldsets = (
        (None, {
            'fields': ('nome_campo', 'nome_variavel', 'tipo_campo')
        }),
        ('Configuração para Listas', {
            'classes': ('collapse',),
            'fields': ('opcoes_lista',),
        }),
    )

# ==============================================================================
# INLINE PARA OS CAMPOS ORDENADOS
# Esta é a parte que vai aparecer DENTRO da página da Estrutura de Campos.
# Ela usa a classe da biblioteca 'ordered_model'.
# ==============================================================================
class EstruturaCampoOrdenadoInline(OrderedTabularInline):
    model = EstruturaCampoOrdenado
    # 'move_up_down_links' é o campo "mágico" da biblioteca que cria as setinhas.
    fields = ('campo', 'move_up_down_links',)
    readonly_fields = ('move_up_down_links',)
    extra = 1 # Quantos campos vazios mostrar por padrão
    autocomplete_fields = ['campo']
    ordering = ('order',) # Garante que os campos apareçam na ordem correta

# ==============================================================================
# ADMIN PRINCIPAL PARA A ESTRUTURA DE CAMPOS
# Esta é a tela onde você vai configurar a relação Cliente + Produto -> Campos
# ==============================================================================
@admin.register(EstruturaDeCampos)
class EstruturaDeCamposAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'produto')
    search_fields = ('cliente__nome_razao_social', 'produto__nome')
    autocomplete_fields = ['cliente', 'produto']
    
    # Aninhamos o inline de campos ordenados aqui dentro.
    inlines = [EstruturaCampoOrdenadoInline]


# ==============================================================================
# ADMIN PARA CONSULTA DOS VALORES PREENCHIDOS
# ==============================================================================
@admin.register(ValorCampoPersonalizado)
class ValorCampoAdmin(admin.ModelAdmin):
    list_display = ('get_caso_id', 'get_cliente_do_caso', 'campo', 'valor')
    search_fields = ('caso__id', 'campo__nome_campo', 'valor')
    readonly_fields = ('caso', 'campo', 'valor')
    list_filter = ('campo',)
    
    @admin.display(description='ID do Caso', ordering='caso__id')
    def get_caso_id(self, obj):
        return obj.caso.id
        
    @admin.display(description='Cliente do Caso', ordering='caso__cliente__nome_razao_social')
    def get_cliente_do_caso(self, obj):
        if obj.caso and obj.caso.cliente:
            return obj.caso.cliente.nome_razao_social
        return "N/A"