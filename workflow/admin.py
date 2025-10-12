from django.contrib import admin
import nested_admin # Importa a nova biblioteca
from .models import Workflow, Fase, Acao, Transicao

# --- INLINES ANINHADOS ---
# A estrutura será: Workflow > Fase > Acao > Transicao

class TransicaoInline(nested_admin.NestedTabularInline):
    """
    Nível 3: Permite definir as Transições (regras) DENTRO de cada Ação.
    """
    model = Transicao
    fk_name = 'acao'
    extra = 1
    verbose_name = "Transição (Se.. Então..)"
    verbose_name_plural = "Transições (Regras de Negócio para esta Ação)"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Esta função inteligente filtra o dropdown de "Fase de destino"
        # para mostrar apenas as fases do mesmo workflow.
        if db_field.name == "fase_destino":
            # Tenta encontrar o objeto pai (Fase) para pegar o workflow
            # A biblioteca nested_admin nos dá acesso aos pais
            if hasattr(self, 'parent_obj'):
                fase_origem = self.parent_obj.fase
                kwargs["queryset"] = Fase.objects.filter(workflow=fase_origem.workflow).exclude(pk=fase_origem.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AcaoInline(nested_admin.NestedStackedInline):
    model = Acao
    extra = 1
    inlines = [TransicaoInline]
    verbose_name_plural = "Ações a serem executadas nesta Fase"
    classes = ['collapse']
    
    # Opcional, mas bom para organização:
    fieldsets = (
        (None, {
            'fields': ('titulo', 'tipo', 'prazo_dias', 'responsavel_padrao')
        }),
        ('Efeitos Colaterais', {
            'classes': ('collapse',),
            'fields': ('mudar_status_caso_para',)
        }),
        ('Lógica de Aguardo', {
            'classes': ('collapse',),
            'fields': ('dias_aguardar',)
        })
    )
    
    # Para o campo de usuário não ser um dropdown gigante
    autocomplete_fields = ['responsavel_padrao']


class FaseInline(nested_admin.NestedStackedInline):
    """
    Nível 1: Permite definir as Fases DENTRO do Workflow.
    """
    model = Fase
    extra = 1
    inlines = [AcaoInline] # Aninha as Ações dentro da Fase
    sortable_field_name = "ordem" # Permite arrastar e soltar para reordenar as fases
    verbose_name_plural = "Fases do Workflow (arraste para reordenar)"


# --- ADMIN PRINCIPAL ---

@admin.register(Workflow)
class WorkflowAdmin(nested_admin.NestedModelAdmin): # Usa o NestedModelAdmin
    """
    A página principal e única para configurar um Workflow completo.
    """
    list_display = ('nome', 'cliente', 'produto')
    list_filter = ('cliente', 'produto')
    # O único inline que precisamos aqui é o de Fases, o resto é aninhado
    inlines = [FaseInline]

# Como agora tudo é gerenciado dentro do WorkflowAdmin, não precisamos mais
# das páginas de admin individuais para Fase, Ação e Transição.
# Se você as criou antes, pode removê-las ou comentá-las.
# Por exemplo:
# admin.site.unregister(Fase)
# admin.site.unregister(Acao)
# admin.site.unregister(Transicao)