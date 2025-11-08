# workflow/admin.py

from django.contrib import admin
import nested_admin
from .models import (
    Workflow, Fase, Acao, Transicao,
    HistoricoFase, InstanciaAcao, TipoPausa
)

# ==============================================================================
# TIPO DE PAUSA ADMIN
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
# WORKFLOW ADMIN (✅ ATUALIZADO)
# ==============================================================================

class TransicaoInline(nested_admin.NestedTabularInline):
    """Nível 3: Transições."""
    model = Transicao
    fk_name = 'acao'
    extra = 1
    verbose_name = "Transição"
    verbose_name_plural = "➜ Transições (Se.. Então..)"
    fields = ['fase_destino', 'condicao']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "fase_destino":
            if hasattr(self, 'parent_obj') and hasattr(self.parent_obj, 'fase'):
                fase_origem = self.parent_obj.fase
                if fase_origem and fase_origem.workflow:
                    kwargs["queryset"] = Fase.objects.filter(
                        workflow=fase_origem.workflow
                    ).exclude(pk=fase_origem.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AcaoInline(nested_admin.NestedStackedInline):
    """Nível 2: Ações."""
    model = Acao
    extra = 1
    inlines = [TransicaoInline]
    verbose_name_plural = "🎯 Ações desta Fase"
    classes = ['collapse']
    
    fieldsets = (
        ('📋 Informações Básicas', {
            'fields': ('titulo', 'descricao', 'tipo')
        }),
        ('👤 Responsabilidade', {
            'fields': (
                'tipo_responsavel',
                'responsavel_padrao',
                'nome_responsavel_terceiro'
            ),
            'description': 'Defina quem é responsável: interno (usuário do sistema) ou terceiro (cliente, perito, etc)'
        }),
        ('⏸️ Controle de Prazo', {
            'fields': (
                'pausar_prazo_enquanto_aguarda',
                'tipo_pausa_acao'
            ),
            'classes': ('collapse',),
            'description': '✅ Marque para pausar o prazo enquanto aguarda esta ação (útil para terceiros)'
        }),
        ('⏰ Prazos', {
            'fields': ('prazo_dias', 'dias_aguardar'),
            'classes': ('collapse',)
        }),
        ('⚙️ Efeitos Automáticos', {
            'fields': ('mudar_status_caso_para',),
            'classes': ('collapse',)
        }),
    )
    
    autocomplete_fields = ['responsavel_padrao']


class FaseInline(nested_admin.NestedStackedInline):
    """Nível 1: Fases."""
    model = Fase
    extra = 1
    inlines = [AcaoInline]
    sortable_field_name = "ordem"
    verbose_name_plural = "📍 Fases do Workflow (arraste para reordenar)"
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ordem', 'eh_fase_final')
        }),
        ('⏸️ Controle de Prazo Automático', {
            'fields': (
                'pausar_prazo_automaticamente',
                'tipo_pausa_padrao',
                'retomar_prazo_ao_sair'
            ),
            'classes': ('collapse',),
            'description': (
                '✅ Pausar Automaticamente: O prazo para quando o caso ENTRA nesta fase<br>'
                '✅ Retomar ao Sair: O prazo volta a contar quando o caso SAI desta fase'
            )
        }),
        ('🎨 Visual (Kanban/Dashboard)', {
            'fields': ('cor_fase', 'icone_fase'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Workflow)
class WorkflowAdmin(nested_admin.NestedModelAdmin):
    """Admin principal para Workflow."""
    list_display = ('nome', 'cliente', 'produto')
    list_filter = ('cliente', 'produto')
    search_fields = ('nome', 'cliente__nome', 'produto__nome')
    inlines = [FaseInline]
    
    fieldsets = (
        ('Configuração Básica', {
            'fields': ('nome', 'cliente', 'produto')
        }),
    )


# ==============================================================================
# HISTÓRICO (Apenas visualização - NÃO permite edição)
# ==============================================================================

@admin.register(HistoricoFase)
class HistoricoFaseAdmin(admin.ModelAdmin):
    """Visualização do histórico de fases."""
    list_display = ['caso', 'fase', 'data_entrada', 'data_saida']
    list_filter = ['fase', 'data_entrada']
    search_fields = ['caso__titulo']
    readonly_fields = ['caso', 'fase', 'data_entrada', 'data_saida']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# ==============================================================================
# ❌ INSTÂNCIA AÇÃO: NÃO REGISTRA NO ADMIN
# ==============================================================================
# InstanciaAcao é gerenciada automaticamente pelo sistema
# Não precisa aparecer no Admin, é criada via signals/views

# Se você tinha registrado antes, descomente para remover:
# try:
#     admin.site.unregister(InstanciaAcao)
# except admin.sites.NotRegistered:
#     pass