# campos_custom/admin.py
from django.contrib import admin
from .models import CampoPersonalizado

@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ('nome_campo', 'produto', 'tipo_campo', 'obrigatorio', 'ordem')
    list_filter = ('produto', 'tipo_campo')
    search_fields = ('nome_campo',)
    list_editable = ('ordem',) # Permite editar a ordem diretamente na lista