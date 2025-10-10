# clientes/models.py
from django.db import models

class Cliente(models.Model): # <-- VERIFIQUE SE O 'C' É MAIÚSCULO
    # Definindo as opções para o campo 'tipo'
    TIPO_CHOICES = [
        ('PF', 'Pessoa Física'),
        ('PJ', 'Pessoa Jurídica'),
    ]

    # Campos principais
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, blank=True, null=True)
    contato_empresa = models.CharField(max_length=100, blank=True, verbose_name="Contato (se for PJ)")

    # Endereço (campos separados e opcionais)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField(max_length=2, blank=True, verbose_name="UF")

    # Campos de controle
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome