from django.contrib import admin

# Register your models here.
# equipamentos/admin.py

from django.contrib import admin
from .models import Equipamento, TipoItem, CategoriaItem, Marca, StatusItem

# ==============================================================================
# Registrando os Modelos de Apoio (As "Listas")
# Isso permite que você adicione 'Tipos', 'Marcas', etc., pelo Admin.
# ==============================================================================

@admin.register(TipoItem)
class TipoItemAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(CategoriaItem)
class CategoriaItemAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

@admin.register(StatusItem)
class StatusItemAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


# ==============================================================================
# Configuração do Painel Principal de Equipamentos
# Aqui deixamos a tela de cadastro e listagem de equipamentos poderosa.
# ==============================================================================

@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    # Campos que aparecerão na lista principal de equipamentos
    list_display = (
        'nome_item', 
        'responsavel', 
        'status', 
        'tipo_item', 
        'marca',
        'etiqueta_servico_dell',
    )
    
    # Adiciona filtros na lateral direita para encontrar equipamentos facilmente
    list_filter = ('status', 'tipo_item', 'marca', 'responsavel', 'pago_por')
    
    # Habilita a barra de busca e define em quais campos ela deve procurar
    search_fields = (
        'nome_item', 
        'modelo', 
        'etiqueta_servico_dell', 
        'hostname', 
        'responsavel__username', # Permite buscar pelo username do responsável
        'responsavel__first_name',
        'responsavel__last_name',
    )
    
    # Mostra o email do responsável (apenas para leitura) no formulário
    readonly_fields = ('email_responsavel',)

    # Organiza os campos no formulário de adição/edição em seções lógicas
    fieldsets = (
        ('Identificação do Item', {
            'fields': ('nome_item', 'tipo_item', 'categoria_item', 'marca', 'modelo', 'etiqueta_servico_dell', 'hostname')
        }),
        ('Detalhes da Aquisição', {
            'classes': ('collapse',), # Começa a seção recolhida para não poluir a tela
            'fields': ('data_compra', 'loja_compra', 'valor_pago', 'pago_por')
        }),
        ('Uso e Responsabilidade', {
            'fields': ('status', 'responsavel', 'email_responsavel', 'telefone_usuario', 'anydesk')
        }),
    )

    # Função para exibir o email do responsável (que não está no modelo Equipamento)
    def email_responsavel(self, obj):
        if obj.responsavel and obj.responsavel.email:
            return obj.responsavel.email
        return "Nenhum responsável ou email cadastrado"
    email_responsavel.short_description = "Email do Responsável"