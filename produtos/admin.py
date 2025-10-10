# produtos/admin.py
from django.contrib import admin
from .models import Produto

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data_criacao')
    search_fields = ('nome',)