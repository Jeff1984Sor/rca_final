# produtos/admin.py
from django.contrib import admin
from .models import Produto

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'padrao_titulo', 'data_criacao')
    search_fields = ('nome',)
    
    # Organiza os campos para clareza
    fieldsets = (
        (None, {
            'fields': ('nome',)
        }),
        ('Personalização de Casos', {
            'fields': ('padrao_titulo',),
            'description': "Defina aqui como o título dos casos deste produto será montado."
        }),
    )