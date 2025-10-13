# campos_custom/models.py

from django.db import models
from casos.models import Caso
# Importar os modelos de Cliente e Produto para criar os relacionamentos
from clientes.models import Cliente
from produtos.models import Produto

# ==============================================================================
# MODELO DA BIBLIOTECA DE CAMPOS (NÃO PRECISA MUDAR)
# ==============================================================================
class CampoPersonalizado(models.Model):
    TIPO_CAMPO_CHOICES = [
        ('TEXTO', 'Texto Curto (String)'),
        ('NUMERO_INT', 'Número Inteiro'),
        ('NUMERO_DEC', 'Número Decimal'),
        ('LISTA_UNICA', 'Lista de Escolha Única'),
        ('LISTA_MULTIPLA', 'Lista de Escolha Múltipla'),
        ('DATA', 'Data'),
    ]
    nome_campo = models.CharField(max_length=100, unique=True, verbose_name="Nome do Campo na Biblioteca")
    tipo_campo = models.CharField(max_length=20, choices=TIPO_CAMPO_CHOICES, verbose_name="Tipo do Campo")
    opcoes_lista = models.TextField(
        blank=True,
        verbose_name="Opções (para campos de lista, separadas por vírgula)",
        help_text="Ex: Opção A, Opção B, Opção C"
    )
    
    def __str__(self):
        return self.nome_campo

    @property
    def get_opcoes_como_lista(self):
        if self.opcoes_lista:
            return [opt.strip() for opt in self.opcoes_lista.split(',')]
        return []

# ==============================================================================
# MODELO DE CONFIGURAÇÃO (AQUI ESTÁ A GRANDE MUDANÇA)
# Antigo 'ProdutoCampo', agora vincula Cliente + Produto + Campo
# ==============================================================================
class ConfiguracaoCampoPersonalizado(models.Model):
    # <<< NOVA CHAVE ESTRANGEIRA PARA CLIENTE >>>
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, verbose_name="Produto")
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE, verbose_name="Campo da Biblioteca")
    obrigatorio = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Configuração de Campo Personalizado"
        verbose_name_plural = "Configurações de Campos Personalizados"
        ordering = ['cliente', 'produto', 'ordem']
        # <<< UNIQUE_TOGETHER ATUALIZADO PARA INCLUIR O CLIENTE >>>
        unique_together = ('cliente', 'produto', 'campo')

    def __str__(self):
        return f"{self.cliente.nome} | {self.produto.nome} -> {self.campo.nome_campo}"

# ==============================================================================
# MODELO DE VALORES (NÃO PRECISA MUDAR)
# Ele continua vinculado ao 'Caso', e o 'Caso' já tem o cliente e o produto.
# ==============================================================================
class ValorCampoPersonalizado(models.Model):
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='valores_personalizados')
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    valor = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Caso #{self.caso.id}: {self.campo.nome_campo} = {self.valor}"