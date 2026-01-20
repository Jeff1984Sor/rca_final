# campos_custom/models.py

from django.db import models
from django.core.exceptions import ValidationError
import re

# Importações de outros apps
from clientes.models import Cliente
from produtos.models import Produto
from casos.models import Caso 

# ==============================================================================
# 1. VALIDAÇÃO
# ==============================================================================
def validate_variable_name(value):
    """Garante que o nome da variável seja seguro para uso em lógica e templates."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
        raise ValidationError(
            'Nome da Variável inválido. Deve começar com uma letra ou underscore e '
            'conter apenas letras, números e underscores (sem espaços ou acentos).'
        )

# ==============================================================================
# 2. BIBLIOTECA DE CAMPOS
# ==============================================================================
class CampoPersonalizado(models.Model):
    nome_campo = models.CharField(max_length=100, verbose_name="Nome Visível (Rótulo)")
    nome_variavel = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Nome da Variável (para relatórios)",
        help_text="Ex: NumeroAviso, ValorCausa. Sem espaços ou caracteres especiais.",
        validators=[validate_variable_name]
    )

    TIPO_CAMPO_CHOICES = [
        ('TEXTO', 'Texto Curto (String)'), 
        ('TEXTO_LONGO', 'Texto Longo (Área de Texto)'), # NOVO
        ('NUMERO_INT', 'Número Inteiro'),
        ('NUMERO_DEC', 'Número Decimal'), 
        ('MOEDA', 'Moeda (R$)'),
        ('LISTA_USUARIOS', 'Lista de Usuários'), 
        ('LISTA_UNICA', 'Lista de Opções (Escolha Única)'),
        ('LISTA_MULTIPLA', 'Lista de Opções (Escolha Múltipla)'), 
        ('DATA', 'Data'),
        ('BOOLEANO', 'Sim/Não (Checkbox)'),
    ]
    tipo_campo = models.CharField(max_length=20, choices=TIPO_CAMPO_CHOICES, verbose_name="Tipo do Campo")
    
    # NOVO: Campo para definição de máscara no frontend
    mascara = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Máscara de Entrada",
        help_text="Ex: 000.000.000-00, (00) 0000-0000, SSS-0A00. Use '0' para números e 'S' para letras."
    )
    
    def __str__(self):
        return self.nome_campo

# ==============================================================================
# 3. OPÇÕES DE LISTA (Configurável por Cliente/Produto)
# ==============================================================================
class OpcoesListaPersonalizada(models.Model):
    campo = models.ForeignKey(
        'CampoPersonalizado', 
        on_delete=models.CASCADE,
        verbose_name="Campo de Lista",
        limit_choices_to={'tipo_campo__in': ['LISTA_UNICA', 'LISTA_MULTIPLA']} 
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    
    opcoes_lista = models.TextField(
        verbose_name="Opções de Lista", 
        help_text="Separadas por vírgula. Ex: Opção A, Opção B"
    )

    class Meta:
        verbose_name = "Opção de Lista Customizada"
        verbose_name_plural = "Opções de Lista Customizadas"
        unique_together = ('campo', 'cliente', 'produto') 

    def get_opcoes_como_lista(self):
        if self.opcoes_lista:
            return [opt.strip() for opt in self.opcoes_lista.split(',')]
        return []
    
    def __str__(self):
        return f"Lista: {self.campo.nome_campo} ({self.cliente.nome} / {self.produto.nome})"

# ==============================================================================
# 4. ESTRUTURA MESTRE (Define quais campos aparecem para cada combinação)
# ==============================================================================
class EstruturaDeCampos(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    
    campos = models.ManyToManyField(
        CampoPersonalizado,
        through='EstruturaCampoOrdenado', 
        verbose_name="Campos Personalizados Simples",
        blank=True
    )
    
    class Meta:
        verbose_name = "Estrutura de Campos"
        verbose_name_plural = "Estruturas de Campos"
        unique_together = ('cliente', 'produto')

    def __str__(self): 
        return f"Estrutura para {self.cliente.nome} - {self.produto.nome}"

class EstruturaCampoOrdenado(models.Model): 
    estrutura = models.ForeignKey(EstruturaDeCampos, on_delete=models.CASCADE, related_name='ordenamentos_simples')
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, db_index=True)
    obrigatorio = models.BooleanField(default=False, verbose_name="Obrigatório")

    class Meta:
        ordering = ['order']
        unique_together = ('estrutura', 'campo')

# ==============================================================================
# 5. GRUPOS REPETÍVEIS (Ex: Itens do Sinistro, Vigências)
# ==============================================================================
class GrupoCampos(models.Model):
    estrutura = models.ForeignKey(EstruturaDeCampos, on_delete=models.CASCADE, related_name="grupos_repetiveis")
    nome_grupo = models.CharField(max_length=100, verbose_name="Nome do Grupo") 
    campos = models.ManyToManyField(
        CampoPersonalizado,
        through='GrupoCampoOrdenado',
        verbose_name="Campos do Grupo",
        blank=True
    )

    class Meta:
        verbose_name = "Grupo de Campos Repetível"
        verbose_name_plural = "Grupos de Campos Repetíveis"

    def __str__(self): 
        return f"{self.nome_grupo} (Estrutura: {self.estrutura})"

class GrupoCampoOrdenado(models.Model):
    grupo = models.ForeignKey(GrupoCampos, on_delete=models.CASCADE, related_name='ordenamentos_grupo')
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['order']
        unique_together = ('grupo', 'campo')

# ==============================================================================
# 6. ARMAZENAMENTO DE VALORES (Onde os dados digitados são salvos)
# ==============================================================================
class InstanciaGrupoValor(models.Model):
    """Representa uma linha de um grupo repetível preenchida em um caso."""
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="grupos_de_valores")
    grupo = models.ForeignKey(GrupoCampos, on_delete=models.CASCADE, related_name="instancias")
    ordem_instancia = models.PositiveIntegerField(default=0, db_index=True) 

    class Meta:
        ordering = ['ordem_instancia']
    def __str__(self): 
        return f"{self.grupo.nome_grupo} [Inst {self.ordem_instancia}] - Caso #{self.caso.id}"

class ValorCampoPersonalizado(models.Model):
    """Armazena o valor bruto (string) de cada campo preenchido."""
    caso = models.ForeignKey(
        Caso, on_delete=models.CASCADE, related_name='valores_personalizados', 
        null=True, blank=True
    )
    instancia_grupo = models.ForeignKey(
        InstanciaGrupoValor, on_delete=models.CASCADE, related_name='valores',
        null=True, blank=True
    )
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    valor = models.TextField(blank=True, null=True)

    def __str__(self):
        id_caso = self.caso.id if self.caso else self.instancia_grupo.caso.id
        return f"Caso #{id_caso} | {self.campo.nome_campo}: {self.valor}"

    class Meta:
        unique_together = ('caso', 'campo')
        constraints = [
            models.UniqueConstraint(fields=['instancia_grupo', 'campo'], name='unique_valor_em_grupo')
        ]