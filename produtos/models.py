# produtos/models.py
from django.db import models

class Produto(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    padrao_titulo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Padrão do Título do Caso",
        help_text="Crie um padrão para o título. Use {NomeDoCampo} para inserir valores. Ex: Aviso {NumeroAviso} - Segurado {NomeSegurado}"
    )
    campos_personalizados = models.ManyToManyField(
        'campos_custom.CampoPersonalizado', # <<< ALTERAÇÃO AQUI
        through='campos_custom.ProdutoCampo',
        related_name='produtos',
        blank=True,
        verbose_name="Campos Personalizados"
    )

    def __str__(self):
        return self.nome