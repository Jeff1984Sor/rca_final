# campos_custom/admin.py

from django.contrib import admin
import nested_admin

from .models import (
    CampoPersonalizado, 
    EstruturaDeCampos, 
    EstruturaCampoOrdenado,
    GrupoCampos, 
    GrupoCampoOrdenado, 
    ValorCampoPersonalizado,
    OpcoesListaPersonalizada, 
    InstanciaGrupoValor 
)

# ==========================================================
# 1. ADMIN DA BIBLIOTECA DE CAMPOS
# ==========================================================

@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    # Adicionado 'mascara' no display e na edição
    list_display = ('nome_campo', 'nome_variavel', 'tipo_campo', 'mascara')
    search_fields = ('nome_campo', 'nome_variavel')
    ordering = ('nome_campo',)
    list_filter = ('tipo_campo',)
    
    fieldsets = (
        (None, {
            'fields': ('nome_campo', 'nome_variavel', 'tipo_campo', 'mascara')
        }),
    )

# ==========================================================
# 2. INLINES PARA ESTRUTURA MESTRE (NESTED ADMIN)
# ==========================================================

# Nível 2: Campos dentro de um Grupo Repetível
class GrupoCampoOrdenadoInline(nested_admin.NestedTabularInline):
    model = GrupoCampoOrdenado
    extra = 1
    autocomplete_fields = ['campo']
    sortable_field_name = "order"
    verbose_name = "Campo do Grupo"
    verbose_name_plural = "Campos do Grupo"
    fk_name = 'grupo'

# Nível 1 (A): O Grupo em si
class GrupoCamposInline(nested_admin.NestedStackedInline):
    model = GrupoCampos
    extra = 0
    inlines = [GrupoCampoOrdenadoInline]
    verbose_name = "Grupo Repetível"
    verbose_name_plural = "Grupos Repetíveis (Ex: Itens do Sinistro, Envolvidos)"
    fk_name = 'estrutura'

# Nível 1 (B): Campos Simples (Não-repetíveis)
class EstruturaCampoOrdenadoInline(nested_admin.NestedTabularInline):
    model = EstruturaCampoOrdenado
    extra = 1
    autocomplete_fields = ['campo']
    sortable_field_name = "order"
    verbose_name = "Campo Simples"
    verbose_name_plural = "Campos Simples (Não-Repetíveis)"
    fk_name = 'estrutura'

# ==========================================================
# 3. ADMIN DA ESTRUTURA DE CAMPOS (TELA MESTRE)
# ==========================================================

@admin.register(EstruturaDeCampos)
class EstruturaDeCamposAdmin(nested_admin.NestedModelAdmin):
    list_display = ('__str__', 'cliente', 'produto')
    search_fields = ('cliente__nome', 'produto__nome')
    autocomplete_fields = ['cliente', 'produto']
    
    inlines = [
        EstruturaCampoOrdenadoInline,
        GrupoCamposInline
    ]

# ==========================================================
# 4. ADMIN DE LISTAS E VALORES
# ==========================================================

@admin.register(OpcoesListaPersonalizada)
class OpcoesListaPersonalizadaAdmin(admin.ModelAdmin):
    list_display = ('campo', 'cliente', 'produto', 'opcoes_lista')
    list_filter = ('cliente', 'produto', 'campo')
    search_fields = ('campo__nome_campo', 'opcoes_lista')
    autocomplete_fields = ['campo', 'cliente', 'produto']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtra para mostrar apenas campos que são do tipo LISTA no dropdown"""
        if db_field.name == "campo":
            kwargs["queryset"] = CampoPersonalizado.objects.filter(
                tipo_campo__in=['LISTA_UNICA', 'LISTA_MULTIPLA']
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(ValorCampoPersonalizado)
class ValorCampoAdmin(admin.ModelAdmin):
    list_display = ('get_caso_id', 'campo', 'valor', 'instancia_grupo')
    list_filter = ('campo', 'caso__cliente')
    search_fields = ('valor', 'caso__id', 'campo__nome_campo')
    readonly_fields = ('campo', 'caso', 'instancia_grupo')

    def get_caso_id(self, obj):
        if obj.caso:
            return f"Caso #{obj.caso.id}"
        return f"Caso #{obj.instancia_grupo.caso.id} (Grupo)"
    get_caso_id.short_description = 'Vínculo'

@admin.register(InstanciaGrupoValor)
class InstanciaGrupoValorAdmin(admin.ModelAdmin):
    list_display = ('caso', 'grupo', 'ordem_instancia')
    list_filter = ('grupo', 'caso__cliente')