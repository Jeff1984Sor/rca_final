# casos/models.py
from django.db import models
from django.conf import settings # Para pegar o modelo de usuário do Django
from clientes.models import Cliente
from django.urls import reverse
from produtos.models import Produto
from django.conf import settings
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from decimal import Decimal, InvalidOperation

# ==============================================================================
# 1. MODELOS DE TOMADOR (ATUALIZADO)
# ==============================================================================

class Tomador(models.Model):
    # REMOVIDO: cliente = models.ForeignKey(...) -> Agora independente
    
    TIPO_PESSOA_CHOICES = [
        ('PF', 'Pessoa Fisica'),
        ('PJ', 'Pessoa Juridica'),
    ]

    nome = models.CharField(max_length=255, verbose_name="Nome do Tomador")
    tipo = models.CharField(max_length=2, choices=TIPO_PESSOA_CHOICES, verbose_name="Tipo", default="PF")
    cpf = models.CharField(max_length=14, verbose_name="CPF", blank=True, null=True)
    cnpj = models.CharField(max_length=18, verbose_name="CNPJ", blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = "Tomador"
        verbose_name_plural = "Tomadores"
        # REMOVIDO: unique_together = ('cliente', 'nome') -> Pois não tem mais cliente

    def __str__(self):
        return self.nome

class TomadorEmail(models.Model):
    """Tabela auxiliar para múltiplos e-mails por tomador"""
    tomador = models.ForeignKey(Tomador, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField(verbose_name="E-mail")

    def __str__(self):
        return self.email

class TomadorTelefone(models.Model):
    """Tabela auxiliar para múltiplos telefones por tomador"""
    tomador = models.ForeignKey(Tomador, on_delete=models.CASCADE, related_name='telefones')
    telefone = models.CharField(max_length=20, verbose_name="Telefone")

    def __str__(self):
        return self.telefone

# ==============================================================================
# 1B. MODELOS DE SEGURADO
# ==============================================================================

class Segurado(models.Model):
    TIPO_PESSOA_CHOICES = [
        ('PF', 'Pessoa Fisica'),
        ('PJ', 'Pessoa Juridica'),
    ]

    nome = models.CharField(max_length=255, verbose_name="Nome do Segurado")
    tipo = models.CharField(max_length=2, choices=TIPO_PESSOA_CHOICES, verbose_name="Tipo", default="PF")
    cpf = models.CharField(max_length=14, verbose_name="CPF", blank=True, null=True)
    cnpj = models.CharField(max_length=18, verbose_name="CNPJ", blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = "Segurado"
        verbose_name_plural = "Segurados"

    def __str__(self):
        return self.nome

class SeguradoEmail(models.Model):
    """Tabela auxiliar para multiplos e-mails por segurado"""
    segurado = models.ForeignKey(Segurado, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField(verbose_name="E-mail")

    def __str__(self):
        return self.email

class SeguradoTelefone(models.Model):
    """Tabela auxiliar para multiplos telefones por segurado"""
    TIPO_CHOICES = [
        ('COMERCIAL', 'Comercial'),
        ('RESIDENCIAL', 'Residencial'),
        ('CELULAR', 'Celular'),
    ]

    segurado = models.ForeignKey(Segurado, on_delete=models.CASCADE, related_name='telefones')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='CELULAR', verbose_name="Tipo")
    telefone = models.CharField(max_length=20, verbose_name="Telefone")

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.telefone}"

# ==============================================================================
# 2. MODELO DE CASO (ATUALIZADO)
# ==============================================================================

class Caso(models.Model):
    # Definindo as opções para o campo 'status'
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('ENCERRADO', 'Encerrado')        
    ]

    # --- CAMPOS PADRÃO OBRIGATÓRIOS ---
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='casos')
    
    produto = models.ForeignKey('produtos.Produto', on_delete=models.PROTECT, related_name='casos')

    segurado = models.ForeignKey(
        Segurado,
        on_delete=models.PROTECT,
        related_name='casos',
        verbose_name="Segurado",
        null=True,
        blank=True
    )
    # ---------------------------

    # --- NOVO CAMPO: TOMADOR ---
    tomador = models.ForeignKey(
        Tomador, 
        on_delete=models.PROTECT, 
        related_name='casos',
        verbose_name="Tomador",
        null=True,  # Obrigatório ser null para casos antigos
        blank=True
    )
    # ---------------------------

    data_entrada = models.DateField(verbose_name="Data de Entrada RCA")
 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVO')
    sharepoint_folder_id = models.CharField(max_length=255, blank=True, null=True, editable=False)
    resumo = models.TextField(
        verbose_name="Resumo do Caso",
        blank=True, 
        null=True,
        help_text="Um resumo executivo do caso, que pode ser gerado pela IA ou inserido manualmente."
    )
    # --- CAMPOS PADRÃO OPCIONAIS ---
    titulo = models.CharField(max_length=255, blank=True)
    data_encerramento = models.DateField(verbose_name="Data de Encerramento", blank=True, null=True)
    
    # Relacionamento com o usuário do sistema (Advogado Responsável)
    advogado_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Advogado Responsável",
        related_name='casos_responsaveis'
    )
    
    fase_atual_wf = models.ForeignKey(
        'workflow.Fase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Fase Atual do Workflow"
    )
    # Campo de controle
    data_criacao = models.DateTimeField(auto_now_add=True)

    valor_apurado = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Valor Apurado",
        null=True, blank=True
    )

    def get_absolute_url(self):
        return reverse('casos:detalhe_caso', kwargs={'pk': self.pk})

    def __str__(self):
        return f"Caso #{self.id} - {self.cliente.nome} ({self.produto.nome})"
    
    @property
    def valor_apurado_custom(self):
        """
        Busca o objeto ValorCampoPersonalizado para 'valor_apurado'.
        !! IMPORTANTE: Altere 'valor_apurado' se o seu nome_variavel for outro !!
        """
        try:
            return self.valores_personalizados.get(campo__nome_variavel='valor_apurado', instancia_grupo__isnull=True)
        except self.valores_personalizados.model.DoesNotExist:
            return None
        
    @property
    def prazo_final_calculado(self):
        from .models import RegraPrazo # Evita importação circular
        try:
            regra = None
            if self.valor_apurado is not None:
                # LÓGICA NORMAL: Se o valor foi preenchido
                regra = RegraPrazo.objects.get(
                    cliente=self.cliente, produto=self.produto,
                    valor_minimo__lte=self.valor_apurado,
                    valor_maximo__gte=self.valor_apurado
                )
            else:
                # LÓGICA PADRÃO: Se o valor está vazio, pega a primeira faixa
                regra = RegraPrazo.objects.filter(
                    cliente=self.cliente, produto=self.produto
                ).order_by('valor_minimo').first()
            if self.status == 'ENCERRADO':
                return None

            if regra and self.data_entrada:
                return self.data_entrada + timedelta(days=regra.prazo_em_dias)
        except RegraPrazo.DoesNotExist:
            return None
        return None
        
class RegraPrazo(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, verbose_name="Cliente")
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE, verbose_name="Produto")
    valor_minimo = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="Valor Mínimo Apurado")
    valor_maximo = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="Valor Máximo Apurado")
    prazo_em_dias = models.PositiveIntegerField(verbose_name="Prazo (em dias)")

    class Meta:
        verbose_name = "Regra de Prazo"
        verbose_name_plural = "Regras de Prazos"
        unique_together = ('cliente', 'produto', 'valor_minimo', 'valor_maximo')
        app_label = 'casos'

    def __str__(self):
        return (f"Regra: {self.cliente.nome} / {self.produto.nome} "
                f"(R${self.valor_minimo} a R${self.valor_maximo}): {self.prazo_em_dias} dias")

class ModeloAndamento(models.Model):

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(verbose_name="Descrição Padrão")

    def __str__(self):
        return self.titulo

class Andamento(models.Model):
    """
    Registra um evento ou atualização em um caso específico.
    """
    # Relacionamento: Cada andamento pertence a um único Caso.
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='andamentos')
    
    data_andamento = models.DateField(verbose_name="Data do Andamento")
    descricao = models.TextField(verbose_name="Descrição")

    # Campos de auditoria: preenchidos automaticamente
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Se o usuário for deletado, o autor fica nulo
        null=True,
        editable=False, # Não pode ser editado pelo usuário no formulário
        verbose_name="Criado por"
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    class Meta:
        ordering = ['-data_andamento', '-data_criacao'] # Mostra os mais recentes primeiro

    def __str__(self):
        return f"Andamento em {self.data_andamento} para o Caso #{self.caso.id}"
    

class Timesheet(models.Model):
    """
    Registra uma entrada de tempo trabalhado em um caso.
    """
    # Relacionamento: Cada entrada de tempo pertence a um único Caso.
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='timesheets')
    
    data_execucao = models.DateField(verbose_name="Data da Execução")
    
    # DurationField é o tipo perfeito para armazenar "tempo decorrido" (HH:MM:SS)
    tempo = models.DurationField(verbose_name="Tempo Gasto (HH:MM)")
    
    advogado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Advogado"
    )
    
    descricao = models.TextField(verbose_name="Descrição do Trabalho Realizado")
    
    # Campo de auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_execucao'] # Mais recentes primeiro

    def __str__(self):
        return f"Timesheet de {self.advogado} para o Caso #{self.caso.id} em {self.data_execucao}"

class Acordo(models.Model):
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='acordos')
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Total do Acordo")
    numero_parcelas = models.PositiveIntegerField(default=1, verbose_name="Número de Parcelas")
    
    # Data da 1ª parcela, as outras serão calculadas
    data_primeira_parcela = models.DateField(verbose_name="Data da 1ª Parcela")

    advogado_acordo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Advogado do Acordo"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Acordo de R$ {self.valor_total} para o Caso #{self.caso.id}"

class Parcela(models.Model):
    STATUS_PAGAMENTO_CHOICES = [
        ('EMITIDA', 'Emitida'),
        ('QUITADA', 'Quitada'),
    ]

    acordo = models.ForeignKey(Acordo, on_delete=models.CASCADE, related_name='parcelas')
    numero_parcela = models.PositiveIntegerField(verbose_name="Nº da Parcela")
    valor_parcela = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor da Parcela")
    data_vencimento = models.DateField(verbose_name="Data de Vencimento")
    data_pagamento = models.DateField(
        verbose_name="Data de Pagamento",
        null=True, # Permite que o campo seja nulo
        blank=True # Permite que seja vazio
    )
    
    status = models.CharField(
        max_length=10,
        choices=STATUS_PAGAMENTO_CHOICES,
        default='EMITIDA',
        verbose_name="Status do Pagamento"
    )

    class Meta:
        ordering = ['data_vencimento']
        unique_together = ('acordo', 'numero_parcela') # Não pode haver duas "parcela 1" para o mesmo acordo

    def __str__(self):
        return f"Parcela {self.numero_parcela}/{self.acordo.numero_parcelas} - Venc: {self.data_vencimento}"
    

class Despesa(models.Model):
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='despesas')
    data_despesa = models.DateField(verbose_name="Data da Despesa")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor da Despesa")
    descricao = models.CharField(max_length=255, verbose_name="Descrição da Despesa")
    
    advogado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Advogado"
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_despesa']

    def __str__(self):
        return f"Despesa de R$ {self.valor} para o Caso #{self.caso.id}"
    
class FluxoInterno(models.Model):
    TIPO_EVENTO_CHOICES = [
        ('CRIACAO_CASO', 'Criação do Caso'),
        ('MUDANCA_FASE_WF', 'Mudança de Fase do Workflow'),
        ('ACAO_WF_CONCLUIDA', 'Ação de Workflow Concluída'),
        ('ANDAMENTO', 'Andamento Adicionado'),
        ('TIMESHEET', 'Timesheet Lançado'),
        ('ACORDO', 'Acordo Criado'),
        ('DESPESA', 'Despesa Lançada'),
        ('EMAIL', 'E-mail Enviado'),
        ('ANEXO', 'Anexo Adicionado'),
    ]

    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='fluxo_interno')
    
    # O que aconteceu?
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO_CHOICES, verbose_name="Tipo do Evento")
    
    # Descrição detalhada do evento
    descricao = models.TextField(verbose_name="Descrição")

    # Quem fez a ação?
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Autor da Ação"
    )
    
    # Quando aconteceu?
    data_evento = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_evento'] # Mais recentes primeiro
        verbose_name = "Evento do Fluxo Interno"
        verbose_name_plural = "Eventos do Fluxo Interno"

    def __str__(self):
        return f"{self.get_tipo_evento_display()} no Caso #{self.caso.id} em {self.data_evento.strftime('%d/%m/%Y')}"
class ConfiguracaoTomador(models.Model):
    produto = models.ForeignKey(
        'produtos.Produto', 
        on_delete=models.CASCADE, 
        verbose_name="Produto"
    )
    
    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.CASCADE, 
        verbose_name="Cliente Específico",
        null=True, 
        blank=True,
        help_text="Deixe em branco se quiser aplicar a TODOS os clientes deste produto."
    )
    
    habilitar_tomador = models.BooleanField(
        default=True, 
        verbose_name="Habilitar Campo Tomador"
    )

    class Meta:
        verbose_name = "Parametrização de Tomador"
        verbose_name_plural = "Parametrizações de Tomador"
        unique_together = ('produto', 'cliente') # Evita regras duplicadas

    def __str__(self):
        if self.cliente:
            return f"{self.produto.nome} - {self.cliente.nome}"
        return f"{self.produto.nome} - (Todos os Clientes)"
