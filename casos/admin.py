# casos/admin.py
from django.contrib import admin
from django import forms
from django.contrib.auth import get_user_model
# Adicionei Tomador, TomadorEmail e TomadorTelefone nos imports
from .models import (
    Caso, ModeloAndamento, Andamento, Timesheet, Acordo, 
    Parcela, Despesa, FluxoInterno, RegraPrazo,
    Tomador, TomadorEmail, TomadorTelefone, ConfiguracaoTomador
)

# --- CONFIGURAÇÃO DO TOMADOR NO ADMIN ---
class TomadorEmailInline(admin.TabularInline):
    model = TomadorEmail
    extra = 1

class TomadorTelefoneInline(admin.TabularInline):
    model = TomadorTelefone
    extra = 1

@admin.register(Tomador)
class TomadorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj', 'data_criacao')
    search_fields = ('nome', 'cpf_cnpj')
    inlines = [TomadorEmailInline, TomadorTelefoneInline]

# --- FIM CONFIGURAÇÃO TOMADOR ---


class CasoAdminForm(forms.ModelForm):
    class Meta:
        model = Caso
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'advogado_responsavel' in self.fields:
            self.fields['advogado_responsavel'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})" if obj.get_full_name() else obj.username


@admin.register(Caso)
class CasoAdmin(admin.ModelAdmin):
    form = CasoAdminForm
    list_display = (
        'id', 
        'cliente', 
        'produto', 
        'status', 
        'exibir_advogado', # Agora vai funcionar
        'data_entrada',
        'prazo_final_calculado'
    )
    
    list_filter = ('status', 'produto', 'advogado_responsavel')
    search_fields = ('titulo', 'cliente__nome')
    autocomplete_fields = ['cliente', 'advogado_responsavel']

    # --- A FUNÇÃO PRECISA ESTAR AQUI DENTRO (INDENTADA) ---
    def exibir_advogado(self, obj):
        if obj.advogado_responsavel:
            return obj.advogado_responsavel.get_full_name() or obj.advogado_responsavel.username
        return "-"
    
    exibir_advogado.short_description = 'Advogado Responsável'
    exibir_advogado.admin_order_field = 'advogado_responsavel'
    # ------------------------------------------------------

@admin.register(ModeloAndamento)
class ModeloAndamentoAdmin(admin.ModelAdmin):
    list_display = ('titulo',)
    search_fields = ('titulo', 'descricao')

@admin.register(RegraPrazo)
class RegraPrazoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'produto', 'valor_minimo', 'valor_maximo', 'prazo_em_dias')
    list_filter = ('cliente', 'produto')
    search_fields = ('cliente__nome', 'produto__nome')

@admin.register(Andamento)
class AndamentoAdmin(admin.ModelAdmin):
    list_display = ('caso', 'data_andamento', 'autor', 'data_criacao')
    list_filter = ('autor', 'data_andamento')
    search_fields = ('descricao',)
    raw_id_fields = ('caso',)

@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ('caso', 'data_execucao', 'tempo', 'advogado')
    list_filter = ('advogado', 'data_execucao')
    search_fields = ('descricao',)
    raw_id_fields = ('caso',)

@admin.register(Acordo)
class AcordoAdmin(admin.ModelAdmin):
    list_display = ('id', 'caso', 'valor_total', 'numero_parcelas', 'data_primeira_parcela')
    raw_id_fields = ('caso',)

@admin.register(Parcela)
class ParcelaAdmin(admin.ModelAdmin):
    list_display = ('acordo', 'numero_parcela', 'valor_parcela', 'data_vencimento', 'status')
    list_filter = ('status',)
    list_editable = ('status',)

@admin.register(Despesa)
class DespesaAdmin(admin.ModelAdmin):
    list_display = ('caso', 'data_despesa', 'valor', 'advogado', 'descricao')
    list_filter = ('advogado', 'data_despesa')
    search_fields = ('descricao',)
    raw_id_fields = ('caso',)

@admin.register(FluxoInterno)
class FluxoInternoAdmin(admin.ModelAdmin):
    list_display = ('caso', 'tipo_evento', 'autor', 'data_evento')
    list_filter = ('tipo_evento', 'autor')
    raw_id_fields = ('caso',)

@admin.register(ConfiguracaoTomador)
class ConfiguracaoTomadorAdmin(admin.ModelAdmin):
    list_display = ('produto', 'cliente', 'habilitar_tomador')
    list_filter = ('produto', 'habilitar_tomador')
    search_fields = ('produto__nome', 'cliente__nome')
    autocomplete_fields = ['produto', 'cliente']