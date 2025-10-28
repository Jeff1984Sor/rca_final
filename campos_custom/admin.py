# campos_custom/admin.py

from django.contrib import admin
# Importa os novos modelos (incluindo OpcoesListaPersonalizada)
from .models import (
    CampoPersonalizado, 
    EstruturaDeCampos, EstruturaCampoOrdenado,
    GrupoCampos, GrupoCampoOrdenado, 
    ValorCampoPersonalizado,
    # <<< ADICIONADO PARA GERENCIAR LISTAS CUSTOMIZADAS >>>
    OpcoesListaPersonalizada, 
    InstanciaGrupoValor # Garante que este também está importado se necessário
)
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
        # O campo 'opcoes_lista' foi removido do modelo CampoPersonalizado,
        # então removemos este fieldset quebrado.
        # ('Configuração para Listas', {
        #     'classes': ('collapse',),
        #     'fields': ('opcoes_lista',),
        # }),
    )

# ==========================================================
# 1. ADMIN PARA LISTAS DE OPÇÕES EXCLUSIVAS (NOVO)
# ==========================================================

# Permite ao Admin definir a lista de opções por Cliente/Produto
@admin.register(OpcoesListaPersonalizada)
class OpcoesListaPersonalizadaAdmin(admin.ModelAdmin):
    list_display = ('campo', 'cliente', 'produto', 'opcoes_lista')
    list_filter = ('cliente', 'produto', 'campo')
    search_fields = ('campo__nome_campo', 'opcoes_lista')
    autocomplete_fields = ['campo', 'cliente', 'produto']
    # Apenas campos do tipo LISTA devem aparecer no select 'campo'
    # Esta função garante que o select de 'campo' só mostre campos com tipo_campo='LISTA_UNICA' ou 'LISTA_MULTIPLA'
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "campo":
            from .models import CampoPersonalizado # Importa dentro da função para evitar ciclos
            kwargs["queryset"] = CampoPersonalizado.objects.filter(
                tipo_campo__in=['LISTA_UNICA', 'LISTA_MULTIPLA']
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ==========================================================
# 2. INLINES E ESTRUTURA PRINCIPAL (Nested Admin)
# ==========================================================

# --- INLINE NÍVEL 2 (Campos dentro do Grupo) ---
class GrupoCampoOrdenadoInline(nested_admin.NestedTabularInline):
    model = GrupoCampoOrdenado
    extra = 1
    autocomplete_fields = ['campo']
    sortable_field_name = "order"
    verbose_name = "Campo do Grupo"
    verbose_name_plural = "Campos do Grupo"
    fk_name = 'grupo'

# --- INLINE NÍVEL 1 (Grupo Repetível) ---
class GrupoCamposInline(nested_admin.NestedStackedInline):
    model = GrupoCampos
    extra = 0
    inlines = [GrupoCampoOrdenadoInline]
    verbose_name = "Grupo Repetível"
    verbose_name_plural = "Grupos Repetíveis (Ex: Vigências, Envolvidos)"
    fk_name = 'estrutura'

# --- INLINE NÍVEL 1 (B) - Campos Simples ---
class EstruturaCampoOrdenadoInline(nested_admin.NestedTabularInline):
    model = EstruturaCampoOrdenado
    extra = 1
    autocomplete_fields = ['campo']
    sortable_field_name = "order"
    verbose_name = "Campo Não-Repetível"
    verbose_name_plural = "Campos Não-Repetíveis (Simples)"
    fk_name = 'estrutura'

# --- ADMIN PRINCIPAL DA ESTRUTURA DE CAMPOS ---
@admin.register(EstruturaDeCampos)
class EstruturaDeCamposAdmin(nested_admin.NestedModelAdmin):
    list_display = ('__str__', 'cliente', 'produto')
    search_fields = ('cliente__nome', 'produto__nome')
    autocomplete_fields = ['cliente', 'produto']
    
    inlines = [
        EstruturaCampoOrdenadoInline,
        GrupoCamposInline
    ]

# --- ADMIN DE CONSULTA PARA VALORES ---
@admin.register(ValorCampoPersonalizado)
class ValorCampoAdmin(admin.ModelAdmin):
    list_display = ('get_caso_info', 'campo', 'valor')
    search_fields = (
        'caso__id',
        'instancia_grupo__caso__id',
        'campo__nome_campo', 
        'valor'
    )
    readonly_fields = ('caso', 'instancia_grupo', 'campo', 'valor')
    list_filter = ('campo',)
    
    @admin.display(description='Referência do Caso', ordering='caso__id')
    def get_caso_info(self, obj):
        if obj.caso:
            return f"Caso #{obj.caso.id} (Campo Direto)"
        if obj.instancia_grupo:
            return f"Caso #{obj.instancia_grupo.caso_id} (Grupo: {obj.instancia_grupo.grupo.nome_grupo})"
        return "Valor Órfão (ERRO)"