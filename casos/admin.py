# casos/admin.py
from django.contrib import admin
from .models import Caso

@admin.register(Caso)
class CasoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'produto', 'status', 'advogado_responsavel', 'data_entrada')
    list_filter = ('status', 'produto', 'advogado_responsavel')
    search_fields = ('titulo', 'cliente__nome') # Busca no nome do cliente relacionado
    autocomplete_fields = ['cliente', 'advogado_responsavel'] # Transforma em campos de busca inteligentes