# campos_custom/models.py
from django.db import models
from produtos.models import Produto
from casos.models import Caso

# Modelo 1: A DEFINIÇÃO do campo personalizado
# Aqui nós criamos o "molde" do campo.
class CampoPersonalizado(models.Model):
    TIPO_CAMPO_CHOICES = [
        ('TEXTO', 'Texto Curto (String)'),
        ('NUMERO_INT', 'Número Inteiro'),
        ('NUMERO_DEC', 'Número Decimal'),
        ('LISTA_UNICA', 'Lista de Escolha Única'),
        ('LISTA_MULTIPLA', 'Lista de Escolha Múltipla'),
        ('DATA', 'Data'),
    ]

    # A qual produto este campo pertence?
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='campos_personalizados')
    
    nome_campo = models.CharField(max_length=100, verbose_name="Nome do Campo")
    tipo_campo = models.CharField(max_length=20, choices=TIPO_CAMPO_CHOICES, verbose_name="Tipo do Campo")
    
    # Se o campo for do tipo LISTA, aqui guardamos as opções, separadas por vírgula.
    # Ex: "Pendente, Aprovado, Rejeitado"
    opcoes_lista = models.TextField(
        blank=True,
        verbose_name="Opções (para campos de lista, separadas por vírgula)",
        help_text="Ex: Opção A, Opção B, Opção C"
    )
    
    obrigatorio = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0, help_text="Define a ordem de exibição no formulário.")

    class Meta:
        ordering = ['produto', 'ordem']
        unique_together = ('produto', 'nome_campo') # Não pode haver campos com o mesmo nome para o mesmo produto

    def __str__(self):
        return f"{self.nome_campo} ({self.produto.nome})"
    
    @property
    def get_opcoes_como_lista(self):
        """
        Pega a string de opções e a retorna como uma lista de strings limpas.
        """
        if self.opcoes_lista:
            # split(',') cria a lista
            # [opt.strip() for opt in ...] remove espaços em branco de cada opção
            return [opt.strip() for opt in self.opcoes_lista.split(',')]
        return []

# Modelo 2: O VALOR do campo personalizado
# Aqui nós guardamos a informação que o usuário digitou.
class ValorCampoPersonalizado(models.Model):
    # A qual caso este valor pertence?
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='valores_personalizados')
    
    # Qual é o campo que estamos preenchendo?
    campo = models.ForeignKey(CampoPersonalizado, on_delete=models.CASCADE)
    
    # O valor em si. Usamos um TextField pois ele é flexível para guardar texto, números, datas, etc.
    valor = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Caso #{self.caso.id}: {self.campo.nome_campo} = {self.valor}"