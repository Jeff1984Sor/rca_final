# pastas/models.py
from django.db import models

class Pasta(models.Model):
    """
    Representa um nome de pasta genérico na nossa biblioteca.
    Ex: 'Documentos Pessoais', 'Provas', 'Laudos Técnicos'
    """
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Pasta")

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class EstruturaPasta(models.Model):
    """
    A associação. Define qual conjunto de pastas será usado para uma
    combinação específica de Cliente e Produto.
    """
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    
    # A relação Muitos-para-Muitos com a nossa biblioteca de Pastas
    pastas = models.ManyToManyField(Pasta, blank=True)

    class Meta:
        verbose_name = "Estrutura de Pasta"
        verbose_name_plural = "Estruturas de Pastas"
        # Garante que só exista uma estrutura por combinação Cliente + Produto
        unique_together = ('cliente', 'produto')

    def __str__(self):
        return f"Estrutura para {self.cliente.nome} - {self.produto.nome}"