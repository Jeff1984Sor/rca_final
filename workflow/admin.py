# workflow/admin.py

from django.contrib import admin
from .models import (
    Workflow, Fase, Acao, Transicao,
    HistoricoFase, InstanciaAcao, TipoPausa
)

# ==============================================================================
# TIPO DE PAUSA ADMIN (Sem alterações)
# ==============================================================================

@admin.register(TipoPausa)
class TipoPausaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'ativo', 'cor', 'ordem']
    list_filter = ['ativo']
    search_fields = ['codigo', 'nome']
    list_editable = ['ativo', 'ordem']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'nome', 'descricao', 'ativo')
        }),
        ('Visual', {
            'fields': ('cor', 'icone', 'ordem'),
            'classes': ('collapse',)
        }),
    )


# ==============================================================================
# ADMINS PARA WORKFLOW E SEUS COMPONENTES (✅ ATUALIZADO E SIMPLIFICADO)
# ==============================================================================

class FaseInline(admin.TabularInline):
    """Inline para Fases dentro de um Workflow."""
    model = Fase
    extra = 1
    ordering = ('ordem',)
    fields = ('ordem', 'nome', 'eh_fase_final', 'cor_fase')


class TransicaoInline(admin.TabularInline):
    """Inline para Transições dentro de um Workflow."""
    model = Transicao
    extra = 1
    # O Django preenche 'workflow' automaticamente. Mostramos só o que importa.
    fields = ('fase_origem', 'acao', 'condicao', 'fase_destino')
    verbose_name_plural = "➜ Transições (Regras de Negócio)"
    
    # Adiciona campos de busca para facilitar a seleção
    autocomplete_fields = ['fase_origem', 'acao', 'fase_destino']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtra as Fases para mostrar apenas as do Workflow atual."""
        # Pega o ID do objeto Workflow que está sendo editado a partir da URL
        if 'object_id' in request.resolver_match.kwargs:
            workflow_id = request.resolver_match.kwargs['object_id']
            if db_field.name in ["fase_origem", "fase_destino"]:
                kwargs["queryset"] = Fase.objects.filter(workflow_id=workflow_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    """Admin principal para Workflow."""
    list_display = ('nome', 'cliente', 'produto')
    list_filter = ('cliente', 'produto')
    search_fields = ('nome', 'cliente__nome', 'produto__nome')
    
    # Agora usamos inlines normais, que são mais eficientes
    inlines = [
        FaseInline,
        TransicaoInline
    ]
    
    fieldsets = (
        ('Configuração Básica', {
            'fields': ('nome', 'cliente', 'produto')
        }),
    )

# ==============================================================================
# ADMINS INDIVIDUAIS PARA FASE E AÇÃO (Necessário para autocomplete)
# ==============================================================================

class AcaoInline(admin.StackedInline):
    """Inline para Ações dentro de uma Fase."""
    model = Acao
    extra = 1
    classes = ['collapse']
    
    fieldsets = (
        (None, {'fields': ('titulo', 'tipo')}),
        ('👤 Responsabilidade', {
            'fields': ('tipo_responsavel', 'responsavel_padrao', 'nome_responsavel_terceiro'),
            'classes': ('collapse',),
        }),
        ('⏸️ Controle de Prazo', {
            'fields': ('pausar_prazo_enquanto_aguarda', 'tipo_pausa_acao', 'prazo_dias'),
            'classes': ('collapse',),
        }),
        ('⚙️ Outras Configurações', {
            'fields': ('dias_aguardar', 'mudar_status_caso_para', 'descricao'),
            'classes': ('collapse',),
        }),
    )
    autocomplete_fields = ['responsavel_padrao']

@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    """Admin para edição detalhada de uma Fase."""
    list_display = ('nome', 'workflow', 'ordem', 'eh_fase_final')
    list_filter = ('workflow',)
    search_fields = ('nome', 'workflow__nome')
    inlines = [AcaoInline]


@admin.register(Acao)
class AcaoAdmin(admin.ModelAdmin):
    """Admin para edição detalhada de uma Ação."""
    list_display = ('titulo', 'fase', 'tipo', 'tipo_responsavel')
    list_filter = ('fase__workflow', 'tipo', 'tipo_responsavel')
    search_fields = ('titulo', 'fase__nome')


# ==============================================================================
# HISTÓRICO (Apenas visualização - Sem alterações)
# ==============================================================================

@admin.register(HistoricoFase)
class HistoricoFaseAdmin(admin.ModelAdmin):
    list_display = ['caso', 'fase', 'data_entrada', 'data_saida']
    list_filter = ['fase__workflow', 'fase', 'data_entrada']
    search_fields = ['caso__id']
    readonly_fields = ['caso', 'fase', 'data_entrada', 'data_saida']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# ------------------------------------------------------------------------------
# ❌ INSTÂNCIA AÇÃO: NÃO REGISTRAR NO ADMIN
# A gestão deste modelo é automática.
# ------------------------------------------------------------------------------