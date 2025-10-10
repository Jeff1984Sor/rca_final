# produtos/models.py
from django.db import models

class Produto(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome