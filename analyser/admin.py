# analyser/admin.py

from django.contrib import admin
from .models import ModeloAnalise, ResultadoAnalise, LogAnalise

@admin.register(ModeloAnalise)
class ModeloAnaliseAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cliente', 'produto', 'ativo', 'data_criacao']
    list_filter = ['ativo', 'cliente', 'produto']
    search_fields = ['nome', 'descricao']

@admin.register(ResultadoAnalise)
class ResultadoAnaliseAdmin(admin.ModelAdmin):
    list_display = ['id', 'caso', 'status', 'aplicado_ao_caso', 'data_criacao']
    list_filter = ['status', 'aplicado_ao_caso', 'data_criacao']
    readonly_fields = ['criado_por', 'data_criacao', 'tempo_processamento']

@admin.register(LogAnalise)
class LogAnaliseAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'resultado', 'nivel', 'mensagem']
    list_filter = ['nivel', 'timestamp']
    readonly_fields = ['timestamp']