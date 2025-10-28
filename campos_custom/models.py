# campos_custom/models.py

from django.db import models
from casos.models import Caso # Garanta que este import esteja correto
from clientes.models import Cliente
from produtos.models import Produto
from django.core.exceptions import ValidationError
from django.urls import reverse # Se usado em algum método do modelo
import re


# ==============================================================================
# 1. VALIDAÇÃO
# ==============================================================================
# Função de validação para garantir que o nome da variável seja seguro
def validate_variable_name(value):
    # Garante que começa com letra e só contém letras, números e underscore
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', value):
        raise ValidationError(
            'Nome da Variável inválido. Deve começar com uma letra ou underscore e conter apenas letras, números e underscores (sem espaços ou caracteres especiais).'
        )


# ==============================================================================
# 2. DEFINIÇÃO DA BIBLIOTECA DE CAMPOS (CORRIGIDO: removeu opções de lista)
# ==============================================================================
class CampoPersonalizado(models.Model):
    
    # --- CAMPOS DO MODELO ---
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
        ('NUMERO_INT', 'Número Inteiro'),
        ('NUMERO_DEC', 'Número Decimal'), 
        ('MOEDA', 'Moeda (R$)'),
        ('LISTA_USUARIOS', 'Lista de Usuários'), 
        ('LISTA_UNICA', 'Lista de Opções (Escolha Única)'),
        ('LISTA_MULTIPLA', 'Lista de Opções (Escolha Múltipla)'), 
        ('DATA', 'Data'),
    ]
    tipo_campo = models.CharField(max_length=20, choices=TIPO_CAMPO_CHOICES, verbose_name="Tipo do Campo")
    
    # O campo opcoes_lista FOI REMOVIDO DAQUI
    
    def __str__(self):
        return self.nome_campo


# ==============================================================================
# 3. NOVO MODELO DE LISTA DE OPÇÕES (Lista Exclusiva por C+P)
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
    
    opcoes_lista = models.TextField(verbose_name="Opções de Lista", help_text="Separadas por vírgula. Ex: Opção A, Opção B")

    class Meta:
        verbose_name = "Opção de Lista Customizada"
        verbose_name_plural = "Opções de Lista Customizadas"
        unique_together = ('campo', 'cliente', 'produto') 

    def get_opcoes_como_lista(self):
        """Transforma o texto 'Opção A, Opção B' em uma lista ['Opção A', 'Opção B']."""
        if self.opcoes_lista:
            return [opt.strip() for opt in self.opcoes_lista.split(',')]
        return []
    
    def __str__(self):
        return f"Lista para {self.campo.nome_campo} ({self.cliente.nome} / {self.produto.nome})"


# ==============================================================================
# 4. ESTRUTURA DE CAMPOS (Define a estrutura mestre)
# ==============================================================================
class EstruturaDeCampos(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    
    # Campos que NÃO SE REPETEM (ex: Aviso)
    campos = models.ManyToManyField(
        CampoPersonalizado,
        through='EstruturaCampoOrdenado', 
        verbose_name="Campos Personalizados (Não Repetíveis)",
        blank=True
    )
    
    class Meta:
        verbose_name = "Estrutura de Campos"
        verbose_name_plural = "Estruturas de Campos"
        unique_together = ('cliente', 'produto')
    def __str__(self): return f"Estrutura para {self.cliente.nome} - {self.produto.nome}"

# Modelo 'Through' para ordenar os campos não repetíveis
class EstruturaCampoOrdenado(models.Model): 
    estrutura = models.ForeignKey(EstruturaDeCampos, on_delete=models.CASCADE, related_name='ordenamentos_simples')
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, db_index=True)

    obrigatorio = models.BooleanField(default=False, verbose_name="Obrigatório")
    # TODO: Se o campo era 'obrigatorio' no modelo antigo, você pode adicionar aqui
    # obrigatorio = models.BooleanField(default=False) 

    class Meta:
        ordering = ['order']
        unique_together = ('estrutura', 'campo')


# ==============================================================================
# 5. GRUPOS REPETÍVEIS
# ==============================================================================
class GrupoCampos(models.Model):
    estrutura = models.ForeignKey(EstruturaDeCampos, on_delete=models.CASCADE, related_name="grupos_repetiveis")
    nome_grupo = models.CharField(max_length=100, verbose_name="Nome do Grupo") 
    
    # Define os campos que compõem este grupo (ex: Data Início, Data Fim)
    campos = models.ManyToManyField(
        CampoPersonalizado,
        through='GrupoCampoOrdenado',
        verbose_name="Campos do Grupo",
        blank=True
    )

    class Meta:
        verbose_name = "Grupo de Campos Repetível"
        verbose_name_plural = "Grupos de Campos Repetíveis"
    def __str__(self): return f"{self.nome_grupo} (para {self.estrutura})"

# Modelo 'Through' para ordenar os campos DENTRO de um grupo
class GrupoCampoOrdenado(models.Model):
    grupo = models.ForeignKey(GrupoCampos, on_delete=models.CASCADE, related_name='ordenamentos_grupo')
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['order']
        unique_together = ('grupo', 'campo')


# ==============================================================================
# 6. INSTÂNCIA DO GRUPO e VALOR CAMPO PERSONALIZADO (NOVA ESTRUTURA)
# ==============================================================================
class InstanciaGrupoValor(models.Model):
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="grupos_de_valores")
    grupo = models.ForeignKey(GrupoCampos, on_delete=models.CASCADE, related_name="instancias")
    ordem_instancia = models.PositiveIntegerField(default=0, db_index=True) 

    class Meta:
        ordering = ['ordem_instancia']
    def __str__(self): return f"{self.grupo.nome_grupo} (Instância {self.ordem_instancia}) - Caso {self.caso.id}"


class ValorCampoPersonalizado(models.Model):
    # Ligação direta ao Caso (para campos NÃO repetíveis, como "Aviso")
    caso = models.ForeignKey(
        Caso, 
        on_delete=models.CASCADE, 
        related_name='valores_personalizados', 
        null=True, # << NULO se pertencer a um grupo
        blank=True
    )
    
    # Ligação à Instância do Grupo (para campos REPETÍVEIS, como "Data Início Vigência")
    instancia_grupo = models.ForeignKey(
        InstanciaGrupoValor, 
        on_delete=models.CASCADE, 
        related_name='valores',
        null=True, # << NULO se for um campo direto do caso
        blank=True
    )
    
    # O campo e o valor (não mudam)
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    valor = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.caso:
            return f"Caso #{self.caso.id}: {self.campo.nome_campo} = {self.valor}"
        elif self.instancia_grupo:
             return f"Grupo (Caso {self.instancia_grupo.caso.id}): {self.campo.nome_campo} = {self.valor}"
        return f"Valor Órfão: {self.campo.nome_campo}"

    class Meta:
        # Garante que um campo só exista uma vez por caso (se não for de grupo)
        unique_together = ('caso', 'campo')
        # Garante que um campo só exista uma vez por instância de grupo
        constraints = [
            models.UniqueConstraint(fields=['instancia_grupo', 'campo'], name='unique_valor_em_grupo')
        ]