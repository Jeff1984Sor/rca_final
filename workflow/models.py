# workflow/models.py
from django.db import models
from django.conf import settings
from casos.models import Caso

class Workflow(models.Model):
    """
    O contêiner principal para um fluxo de trabalho.
    Associado a uma combinação única de Cliente e Produto.
    """
    nome = models.CharField(max_length=200, help_text="Ex: Workflow de Sinistro RCG para Tokio")
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "1. Workflows (Configuração)"
        unique_together = ('cliente', 'produto') # Só pode haver um workflow por Cliente+Produto

    def __str__(self):
        return self.nome

class Fase(models.Model):
    """
    Um estado ou etapa dentro de um Workflow.
    Ex: 'Análise Inicial', 'Aguardando Documentação', 'Em Negociação'
    """
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='fases')
    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField(help_text="Define a sequência das fases. A fase com ordem '1' é a inicial.")
    
    # Indica se esta é a fase final do workflow
    eh_fase_final = models.BooleanField(default=False, verbose_name="É Fase Final?")

    class Meta:
        verbose_name = "Fase"
        verbose_name_plural = "2. Fases do Workflow"
        ordering = ['workflow', 'ordem']
        unique_together = ('workflow', 'ordem') # Não pode haver duas 'fase 1' no mesmo workflow

    def __str__(self):
        return f"{self.workflow.nome} - Fase {self.ordem}: {self.nome}"

class Acao(models.Model):
    """
    Uma tarefa a ser executada pelo usuário em uma determinada Fase.
    """
    TIPO_ACAO_CHOICES = [
        ('SIMPLES', 'Ação Simples (Apenas confirmação)'),
        ('DECISAO_SN', 'Decisão (Sim/Não)'),
        ('AGUARDAR_DIAS', 'Aguardar (Dispara nova ação após X dias)'),
    ]
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='acoes')
    titulo = models.CharField(max_length=255, verbose_name="Título da Ação")
    tipo = models.CharField(max_length=20, choices=TIPO_ACAO_CHOICES, default='SIMPLES')

    prazo_dias = models.PositiveIntegerField(
        default=0, 
        verbose_name="Prazo (em dias)",
        help_text="0 para nenhum prazo. Contado a partir da criação da ação."
    )
    dias_aguardar = models.PositiveIntegerField(
        default=0,
        verbose_name="Dias para Aguardar",
        help_text="Use apenas para o tipo 'Aguardar'."
    )
    responsavel_padrao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Responsável Padrão",
        help_text="Se definido, esta ação será atribuída a este usuário por padrão."
    )

    # LÓGICA CORRIGIDA: Ele busca as opções DIRETAMENTE da classe Caso
    mudar_status_caso_para = models.CharField(
        max_length=20, 
        blank=True,
        # CORREÇÃO AQUI: Acessa o atributo da classe
        choices=[('', 'Não alterar')] + Caso.STATUS_CHOICES, 
        verbose_name="Ao concluir, mudar Status do Caso para"
    )

    class Meta:
        verbose_name = "Ação"
        verbose_name_plural = "3. Ações da Fase"
    
    def __str__(self):
        return self.titulo


class Transicao(models.Model):
    """
    A REGRA que conecta as Fases. "Se X acontecer, vá para Y".
    """
    fase_origem = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='transicoes_saida')
    fase_destino = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='transicoes_entrada')
    
    # A condição para esta transição acontecer
    acao = models.ForeignKey(Acao, on_delete=models.CASCADE, help_text="A ação que dispara esta transição.")
    condicao = models.CharField(
        max_length=10, 
        blank=True, 
        choices=[('', 'Sempre (para Ação Simples)'), ('SIM', 'Se a resposta for SIM'), ('NAO', 'Se a resposta for NÃO')],
        verbose_name="Condição para transição"
    )

    class Meta:
        verbose_name = "Transição"
        verbose_name_plural = "4. Transições entre Fases"

    def __str__(self):
        return f"De '{self.fase_origem.nome}' para '{self.fase_destino.nome}' via '{self.acao.titulo}'"

class HistoricoFase(models.Model):
    """
    Registra a passagem de um Caso por uma Fase (para a aba 'Workflow').
    """
    caso = models.ForeignKey('casos.Caso', on_delete=models.CASCADE, related_name='historico_fases')
    fase = models.ForeignKey(Fase, on_delete=models.PROTECT)
    data_entrada = models.DateTimeField(auto_now_add=True)
    data_saida = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Caso #{self.caso_id} em '{self.fase.nome}'"

class InstanciaAcao(models.Model):
    """
    Uma instância de uma Ação para um Caso específico (para a aba 'Ações').
    """
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CONCLUIDA', 'Concluída'),
    ]
    
    caso = models.ForeignKey('casos.Caso', on_delete=models.CASCADE, related_name='acoes_pendentes')
    acao = models.ForeignKey(Acao, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    
    # Quem e quando completou a ação
    data_conclusao = models.DateTimeField(null=True, blank=True)
    concluida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    resposta = models.CharField(max_length=10, blank=True, help_text="Ex: SIM, NAO") # Para ações de decisão

    data_prazo = models.DateField(null=True, blank=True, verbose_name="Prazo de Conclusão")
    
    comentario = models.TextField(blank=True, verbose_name="Comentário de Conclusão")
    
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acoes_responsaveis',
        verbose_name="Responsável pela Ação"
    )
    def __str__(self):
        return f"Ação '{self.acao.titulo}' para o Caso #{self.caso_id} - {self.status}"