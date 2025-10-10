# casos/models.py
from django.db import models
from django.conf import settings # Para pegar o modelo de usuário do Django
from clientes.models import Cliente
from produtos.models import Produto

class Caso(models.Model):
    # Definindo as opções para o campo 'status'
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('ENCERRADO', 'Encerrado'),
    ]

    # --- CAMPOS PADRÃO OBRIGATÓRIOS ---
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='casos')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='casos')
    data_entrada = models.DateField(verbose_name="Data de Entrada RCA")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVO')

    # --- CAMPOS PADRÃO OPCIONAIS ---
    titulo = models.CharField(max_length=255, blank=True)
    data_encerramento = models.DateField(verbose_name="Data de Encerramento", blank=True, null=True)
    
    # Relacionamento com o usuário do sistema (Advogado Responsável)
    advogado_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='casos_responsaveis'
    )
    
    # Campo de controle
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Caso #{self.id} - {self.cliente.nome} ({self.produto.nome})"