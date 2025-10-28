# campos_custom/admin.py

from django.contrib import admin
# Importa os novos modelos
from .models import (
    CampoPersonalizado, 
    EstruturaDeCampos, EstruturaCampoOrdenado,
    GrupoCampos, GrupoCampoOrdenado, 
    ValorCampoPersonalizado,
    # <<< CORRETO >>>
    OpcoesListaPersonalizada, 
    InstanciaGrupoValor 
)
import nested_admin

# ... (restante dos imports) ...

# --- ADMIN DA BIBLIOTECA DE CAMPOS ---
# ... (CampoPersonalizadoAdmin) ...

# ==========================================================
# 1. ADMIN DE LISTAS (OpcoesListaPersonalizada)
# ==========================================================

# A OpçõesListaPersonalizadaAdmin já é o local onde se define as opções de lista
# por Cliente/Produto. Você não precisa de um Inline para ela.
# Se você quer adicionar as LISTAS na tela do CAMPO PERSONALIZADO,
# a lógica deve ser diferente.

# Vamos assumir que o erro está no Inline que foi copiado por engano:

# --- INLINE NÍVEL 2 (Campos dentro do Grupo) ---
# ESTE INLINE ESTÁ LIGADO A OUTRO MODELO E JÁ DEVE ESTAR CORRETO.
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
    # ... (Seu código) ...
    pass
    
# --- CORRIGIR O BLOCO QUE CAUSOU O ERRO ---
# O modelo 'OpcaoCampoPersonalizado' não existe. Removemos o bloco inline
# que causou o erro e garantimos que o CampoPersonalizadoAdmin não o use.

# O CampoPersonalizadoAdmin DEVE SER SIMPLIFICADO:
@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ('nome_campo', 'nome_variavel', 'tipo_campo')
    search_fields = ('nome_campo', 'nome_variavel')
    ordering = ('nome_campo',)
    list_filter = ('tipo_campo',)
    
    # REMOVE A REFERÊNCIA AO INLINE INEXISTENTE
    # inlines = [OpcaoCampoPersonalizadoInline] 
    
    fieldsets = (
        (None, {
            'fields': ('nome_campo', 'nome_variavel', 'tipo_campo')
        }),
    )

# --- REGISTRO DO MODELO CORRETO DE LISTAS ---
@admin.register(OpcoesListaPersonalizada)
class OpcoesListaPersonalizadaAdmin(admin.ModelAdmin):
    list_display = ('campo', 'cliente', 'produto', 'opcoes_lista')
    list_filter = ('cliente', 'produto', 'campo')
    search_fields = ('campo__nome_campo', 'opcoes_lista')
    autocomplete_fields = ['campo', 'cliente', 'produto']
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "campo":
            from .models import CampoPersonalizado
            kwargs["queryset"] = CampoPersonalizado.objects.filter(
                tipo_campo__in=['LISTA_UNICA', 'LISTA_MULTIPLA']
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)