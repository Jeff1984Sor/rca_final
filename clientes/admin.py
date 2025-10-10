# clientes/admin.py

from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    """
    Configurações personalizadas para o modelo Cliente no site de administração.
    """
    # Campos a serem exibidos na lista de clientes
    list_display = ('nome', 'tipo', 'cidade', 'uf', 'data_criacao')

    # Campos que podem ser usados para filtrar os resultados na barra lateral
    list_filter = ('tipo', 'uf', 'cidade')

    # Campo de busca para procurar clientes
    search_fields = ('nome', 'contato_empresa', 'cidade')

    # Organiza os campos no formulário de edição/criação em seções
    fieldsets = (
        ('Informações Principais', {
            'fields': ('nome', 'tipo', 'contato_empresa')
        }),
        ('Endereço', {
            'fields': ('logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf'),
            'classes': ('collapse',) # Começa a seção de endereço recolhida
        }),
    )

    # Ordena a lista por data de criação, do mais novo para o mais antigo
    ordering = ('-data_criacao',)