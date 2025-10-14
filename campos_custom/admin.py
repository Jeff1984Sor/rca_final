# campos_custom/admin.py

from django.contrib import admin
from .models import CampoPersonalizado, EstruturaDeCampos, EstruturaCampoOrdenado, ValorCampoPersonalizado
import nested_admin

# --- ADMIN DA BIBLIOTECA DE CAMPOS ---
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

# --- INLINE PARA A ORDENAÇÃO USANDO nested_admin ---
class EstruturaCampoOrdenadoInline(nested_admin.NestedTabularInline):
    model = EstruturaCampoOrdenado
    extra = 1
    autocomplete_fields = ['campo']
    # Esta linha ativa o "arrasta e solta" do nested_admin, que vai
    # preencher o campo 'order' que criamos no models.py.
    sortable_field_name = "order"

# --- ADMIN PRINCIPAL DA ESTRUTURA DE CAMPOS ---
@admin.register(EstruturaDeCampos)
class EstruturaDeCamposAdmin(nested_admin.NestedModelAdmin):
    list_display = ('cliente', 'produto')
    search_fields = ('cliente__nome', 'produto__nome') # Corrigido para 'nome'
    autocomplete_fields = ['cliente', 'produto']
    inlines = [EstruturaCampoOrdenadoInline]

# --- ADMIN DE CONSULTA PARA VALORES ---
@admin.register(ValorCampoPersonalizado)
class ValorCampoAdmin(admin.ModelAdmin):
    list_display = ('get_caso_id', 'get_cliente_do_caso', 'campo', 'valor')
    search_fields = ('caso__id', 'campo__nome_campo', 'valor')
    readonly_fields = ('caso', 'campo', 'valor')
    list_filter = ('campo',)
    
    @admin.display(description='ID do Caso', ordering='caso__id')
    def get_caso_id(self, obj):
        return obj.caso.id
        
    @admin.display(description='Cliente do Caso', ordering='caso__cliente__nome')
    def get_cliente_do_caso(self, obj):
        if obj.caso and obj.caso.cliente:
            return obj.caso.cliente.nome
        return "N/A"