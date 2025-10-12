# campos_custom/admin.py
from django.contrib import admin
from .models import CampoPersonalizado, ProdutoCampo

@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    # Agora só mostramos os campos que realmente existem no modelo
    list_display = ('nome_campo', 'tipo_campo')
    list_filter = ('tipo_campo',)
    search_fields = ('nome_campo',)

# Opcional, mas útil para depuração: registrar o modelo intermediário
@admin.register(ProdutoCampo)
class ProdutoCampoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'campo', 'ordem', 'obrigatorio')
    list_filter = ('produto',)