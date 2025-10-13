# campos_custom/models.py

from django.db import models
from casos.models import Caso
# Importar os modelos de Cliente e Produto para criar os relacionamentos
from clientes.models import Cliente
from produtos.models import Produto
from django.core.exceptions import ValidationError
import re

# ==============================================================================
# MODELO DA BIBLIOTECA DE CAMPOS (NÃO PRECISA MUDAR)
# ==============================================================================
class CampoPersonalizado(models.Model):
    # Função de validação para garantir que o nome da variável seja seguro
    def validate_variable_name(value):
        # Garante que começa com letra e só contém letras, números e underscore
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
            raise ValidationError(
                'Nome da Variável inválido. Deve começar com uma letra ou underscore e conter apenas letras, números e underscores (sem espaços ou caracteres especiais).'
            )

    # --- CAMPOS DO MODELO ---
    nome_campo = models.CharField(max_length=100, verbose_name="Nome Visível (Rótulo)")
    
    # ==============================================================================
    #  NOVO CAMPO ADICIONADO AQUI
    # ==============================================================================
    nome_variavel = models.CharField(
        max_length=50, 
        unique=True, # Garante que cada variável seja única no sistema
        verbose_name="Nome da Variável (para relatórios)",
        help_text="Ex: NumeroAviso, ValorCausa, DataSentenca. Sem espaços ou caracteres especiais.",
        validators=[validate_variable_name]
    )
    # ==============================================================================

    TIPO_CAMPO_CHOICES = [
        ('TEXTO', 'Texto Curto (String)'), ('NUMERO_INT', 'Número Inteiro'),
        ('NUMERO_DEC', 'Número Decimal'), ('MOEDA', 'Moeda (R$)'),
        ('LISTA_USUARIOS', 'Lista de Usuários'), ('LISTA_UNICA', 'Lista de Opções (Escolha Única)'),
        ('LISTA_MULTIPLA', 'Lista de Opções (Escolha Múltipla)'), ('DATA', 'Data'),
    ]
    tipo_campo = models.CharField(max_length=20, choices=TIPO_CAMPO_CHOICES, verbose_name="Tipo do Campo")
    opcoes_lista = models.TextField(blank=True, verbose_name="Opções (para Lista de Opções)", help_text="Separadas por vírgula. Ex: Opção A, Opção B")
    
    def __str__(self):
        return self.nome_campo



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
    

class EstruturaDeCampos(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, verbose_name="Produto")
    campos = models.ManyToManyField(
        CampoPersonalizado,
        verbose_name="Campos Personalizados",
        blank=True
    )

    class Meta:
        verbose_name = "Estrutura de Campos"
        verbose_name_plural = "Estruturas de Campos"
        unique_together = ('cliente', 'produto')

    def __str__(self):
        return f"Estrutura para {self.cliente.nome} - {self.produto.nome}"