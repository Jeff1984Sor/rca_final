# equipamentos/models.py

from django.db import models
from django.conf import settings # Para referenciar o modelo de usuário do seu projeto de forma segura

# ==============================================================================
# Modelos de Apoio (As "Listas" que você pediu)
# Eles servem para popular os campos de escolha no cadastro de Equipamento.
# Você poderá adicionar/editar/remover itens em cada um deles pelo painel Admin.
# ==============================================================================

class TipoItem(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Tipo")

    class Meta:
        verbose_name = "Tipo de Item"
        verbose_name_plural = "Tipos de Itens"
        ordering = ['nome']

    def __str__(self):
        return self.nome

class CategoriaItem(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Categoria")
    
    class Meta:
        verbose_name = "Categoria do Item"
        verbose_name_plural = "Categorias dos Itens"
        ordering = ['nome']

    def __str__(self):
        return self.nome

class Marca(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Marca")

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ['nome']

    def __str__(self):
        return self.nome

class StatusItem(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Status")
    
    class Meta:
        verbose_name = "Status do Item"
        verbose_name_plural = "Status dos Itens"
        ordering = ['nome']

    def __str__(self):
        return self.nome


# ==============================================================================
# O Modelo Principal: Equipamento
# Aqui está o cadastro de ativos que você pediu, com todos os campos.
# ==============================================================================

class Equipamento(models.Model):
    
    # Opções para o campo "Pago por" (esta é uma lista mais fixa)
    OPCOES_PAGO_POR = [
        ('EMPRESA', 'Empresa'),
        ('SOCIO', 'Sócio'),
        ('REEMBOLSO', 'Reembolso'),
        ('PESSOAL', 'Pessoal'),
    ]

    # --- Identificação do Item ---
    nome_item = models.CharField(max_length=200, verbose_name="Nome do Item")
    tipo_item = models.ForeignKey(TipoItem, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tipo do Item")
    categoria_item = models.ForeignKey(CategoriaItem, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoria do Item")
    marca = models.ForeignKey(Marca, on_delete=models.SET_NULL, null=True, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    etiqueta_servico_dell = models.CharField("Etiqueta de Serviço Dell (S/N)", max_length=50, blank=True)
    hostname = models.CharField("Hostname (Nome na Rede)", max_length=100, blank=True)

    # --- Detalhes da Aquisição ---
    data_compra = models.DateField("Data da Compra", null=True, blank=True)
    loja_compra = models.CharField("Loja da Compra", max_length=100, blank=True)
    valor_pago = models.DecimalField("Valor Pago (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    pago_por = models.CharField("Pago por", max_length=10, choices=OPCOES_PAGO_POR, blank=True)

    # --- Informações de Uso e Responsabilidade ---
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Responsável pelo Item"
    )
    telefone_usuario = models.CharField("Telefone do Usuário", max_length=20, blank=True, help_text="Telefone de contato direto do responsável.")
    anydesk = models.CharField("AnyDesk", max_length=50, blank=True)
    status = models.ForeignKey(StatusItem, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Status do Item")
    
    # Nota sobre "Email de contato do Responsável":
    # Este campo não é necessário! Ao escolher um 'responsavel', o Django já sabe
    # o email dele. Podemos acessá-lo com `equipamento.responsavel.email`.
    # Isso evita dados duplicados e inconsistentes.

    def __str__(self):
        return f"{self.nome_item} ({self.modelo or 'Sem modelo'})"

    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        ordering = ['nome_item']