# casos/admin.py
from django.contrib import admin
from .models import Caso, ModeloAndamento, Andamento, Timesheet, Acordo, Parcela

@admin.register(Caso)
class CasoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'produto', 'status', 'advogado_responsavel', 'data_entrada')
    list_filter = ('status', 'produto', 'advogado_responsavel')
    search_fields = ('titulo', 'cliente__nome') # Busca no nome do cliente relacionado
    autocomplete_fields = ['cliente', 'advogado_responsavel'] # Transforma em campos de busca inteligentes

@admin.register(ModeloAndamento)
class ModeloAndamentoAdmin(admin.ModelAdmin):
    list_display = ('titulo',)
    search_fields = ('titulo', 'descricao')

@admin.register(Andamento)
class AndamentoAdmin(admin.ModelAdmin):
    list_display = ('caso', 'data_andamento', 'autor', 'data_criacao')
    list_filter = ('autor', 'data_andamento')
    search_fields = ('descricao',)
    raw_id_fields = ('caso',) # Melhor para muitos casos

@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ('caso', 'data_execucao', 'tempo', 'advogado')
    list_filter = ('advogado', 'data_execucao')
    search_fields = ('descricao',)
    raw_id_fields = ('caso',) # Facilita a seleção do caso

@admin.register(Acordo)
class AcordoAdmin(admin.ModelAdmin):
    list_display = ('id', 'caso', 'valor_total', 'numero_parcelas', 'data_primeira_parcela')
    raw_id_fields = ('caso',)

@admin.register(Parcela)
class ParcelaAdmin(admin.ModelAdmin):
    list_display = ('acordo', 'numero_parcela', 'valor_parcela', 'data_vencimento', 'status')
    list_filter = ('status',)
    list_editable = ('status',) # Permite mudar o status diretamente na lista do admin