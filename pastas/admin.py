# pastas/admin.py
from django.contrib import admin
from .models import Pasta, EstruturaPasta

@admin.register(Pasta)
class PastaAdmin(admin.ModelAdmin):
    """ Admin para a biblioteca de nomes de pastas. """
    list_display = ('nome',)
    search_fields = ('nome',)


@admin.register(EstruturaPasta)
class EstruturaPastaAdmin(admin.ModelAdmin):
    """ Admin para associar as pastas a um Cliente + Produto. """
    list_display = ('cliente', 'produto')
    list_filter = ('cliente', 'produto')
    # Melhora a interface de seleção do ManyToManyField
    filter_horizontal = ('pastas',)
    # Usa campos de busca para Cliente e Produto
    autocomplete_fields = ['cliente', 'produto']