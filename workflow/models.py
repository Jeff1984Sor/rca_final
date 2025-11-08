# workflow/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from casos.models import Caso
from datetime import date, timedelta

# ==============================================================================
# TIPO DE PAUSA (Motivos cadastráveis)
# ==============================================================================

class TipoPausa(models.Model):
    """Motivos de pausa cadastráveis no Admin."""
    codigo = models.CharField(
        "Código Único",
        max_length=50,
        unique=True,
        help_text="Ex: DOC_PENDENTE, VISTORIA, ANALISE_JURIDICA"
    )
    
    nome = models.CharField(
        "Nome do Motivo",
        max_length=200,
        help_text="Ex: 'Aguardando Documentação do Cliente'"
    )
    
    descricao = models.TextField("Descrição", blank=True)
    ativo = models.BooleanField("Ativo?", default=True)
    cor = models.CharField("Cor (Hexadecimal)", max_length=7, default='#ffc107')
    icone = models.CharField("Ícone Font Awesome", max_length=50, default='fa-pause-circle', blank=True)
    ordem = models.PositiveIntegerField("Ordem de Exibição", default=0)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tipo de Pausa"
        verbose_name_plural = "0. Tipos de Pausa"
        ordering = ['ordem', 'nome']
    
    def __str__(self):
        return self.nome


# ==============================================================================
# WORKFLOW
# ==============================================================================

class Workflow(models.Model):
    """O contêiner principal para um fluxo de trabalho."""
    nome = models.CharField(max_length=200, help_text="Ex: Workflow de Sinistro RCG para Tokio")
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "1. Workflows (Configuração)"
        unique_together = ('cliente', 'produto')

    def __str__(self):
        return self.nome


# ==============================================================================
# FASE (✅ ATUALIZADA COM CONTROLE DE PRAZO)
# ==============================================================================

class Fase(models.Model):
    """Um estado ou etapa dentro de um Workflow."""
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='fases')
    nome = models.CharField(max_length=100)
    ordem = models.PositiveIntegerField(help_text="Define a sequência das fases.")
    eh_fase_final = models.BooleanField(default=False, verbose_name="É Fase Final?")
    
    # ========================================
    # ✅ NOVOS CAMPOS: CONTROLE DE PRAZO
    # ========================================
    pausar_prazo_automaticamente = models.BooleanField(
        "Pausar Prazo ao Entrar nesta Fase?",
        default=False,
        help_text="✅ Se marcado, o prazo para automaticamente quando o caso entra nesta fase"
    )
    
    tipo_pausa_padrao = models.ForeignKey(
        TipoPausa,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Motivo da Pausa (Padrão)",
        help_text="Motivo que será usado quando pausar automaticamente"
    )
    
    retomar_prazo_ao_sair = models.BooleanField(
        "Retomar Prazo ao Sair desta Fase?",
        default=False,
        help_text="✅ Se marcado, o prazo volta a contar ao sair desta fase"
    )
    
    # ========================================
    # CAMPOS VISUAIS
    # ========================================
    cor_fase = models.CharField(
        "Cor da Fase (Hex)",
        max_length=7,
        default='#6c757d',
        help_text="Para Kanban. Ex: #28a745"
    )
    
    icone_fase = models.CharField(
        "Ícone Font Awesome",
        max_length=50,
        default='fa-circle',
        blank=True
    )

    class Meta:
        verbose_name = "Fase"
        verbose_name_plural = "2. Fases do Workflow"
        ordering = ['workflow', 'ordem']
        unique_together = ('workflow', 'ordem')

    def __str__(self):
        return f"{self.workflow.nome} - Fase {self.ordem}: {self.nome}"


# ==============================================================================
# AÇÃO (✅ ATUALIZADA COM RESPONSÁVEL TERCEIRO)
# ==============================================================================

class Acao(models.Model):
    """Uma tarefa a ser executada pelo usuário em uma determinada Fase."""
    TIPO_ACAO_CHOICES = [
        ('SIMPLES', 'Ação Simples (Apenas confirmação)'),
        ('DECISAO_SN', 'Decisão (Sim/Não)'),
        ('AGUARDAR_DIAS', 'Aguardar (Dispara nova ação após X dias)'),
    ]
    
    # ========================================
    # ✅ NOVO CAMPO: TIPO DE RESPONSÁVEL
    # ========================================
    TIPO_RESPONSAVEL_CHOICES = [
        ('INTERNO', 'Responsável Interno (Advogado/Regulador)'),
        ('TERCEIRO', 'Responsável Terceiro (Cliente/Fornecedor/Perito)'),
    ]
    
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='acoes')
    titulo = models.CharField(max_length=255, verbose_name="Título da Ação")
    descricao = models.TextField(blank=True, verbose_name="Descrição da Tarefa")
    tipo = models.CharField(max_length=20, choices=TIPO_ACAO_CHOICES, default='SIMPLES')
    
    # ========================================
    # ✅ RESPONSABILIDADE
    # ========================================
    tipo_responsavel = models.CharField(
        "Tipo de Responsável",
        max_length=20,
        choices=TIPO_RESPONSAVEL_CHOICES,
        default='INTERNO',
        help_text="Define quem é responsável por esta ação"
    )
    
    responsavel_padrao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Responsável Padrão (se interno)",
        help_text="Usuário do sistema que será atribuído automaticamente"
    )
    
    nome_responsavel_terceiro = models.CharField(
        "Nome do Responsável Terceiro",
        max_length=200,
        blank=True,
        help_text="Ex: 'Cliente', 'Perito João Silva', 'Seguradora XYZ'"
    )
    
    # ========================================
    # ✅ CONTROLE DE PRAZO NA AÇÃO
    # ========================================
    pausar_prazo_enquanto_aguarda = models.BooleanField(
        "Pausar Prazo Enquanto Aguarda esta Ação?",
        default=False,
        help_text="✅ Útil para ações de terceiros (aguardando cliente, perito, etc)"
    )
    
    tipo_pausa_acao = models.ForeignKey(
        TipoPausa,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acoes_com_pausa',
        verbose_name="Motivo da Pausa",
        help_text="Usado se 'Pausar Prazo' estiver marcado"
    )

    prazo_dias = models.PositiveIntegerField(
        default=0,
        verbose_name="Prazo (em dias)",
        help_text="0 = sem prazo"
    )
    
    dias_aguardar = models.PositiveIntegerField(
        default=0,
        verbose_name="Dias para Aguardar"
    )

    mudar_status_caso_para = models.CharField(
        max_length=20,
        blank=True,
        choices=[('', 'Não alterar')] + Caso.STATUS_CHOICES,
        verbose_name="Ao concluir, mudar Status do Caso para"
    )

    class Meta:
        verbose_name = "Ação"
        verbose_name_plural = "3. Ações da Fase"
    
    def __str__(self):
        return self.titulo


# ==============================================================================
# TRANSIÇÃO (Mantém como está)
# ==============================================================================

class Transicao(models.Model):
    """A REGRA que conecta as Fases."""
    fase_origem = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='transicoes_saida')
    fase_destino = models.ForeignKey(Fase, on_delete=models.CASCADE, related_name='transicoes_entrada')
    acao = models.ForeignKey(Acao, on_delete=models.CASCADE)
    condicao = models.CharField(
        max_length=10,
        blank=True,
        choices=[('', 'Sempre'), ('SIM', 'Se SIM'), ('NAO', 'Se NÃO')],
        verbose_name="Condição"
    )

    class Meta:
        verbose_name = "Transição"
        verbose_name_plural = "4. Transições entre Fases"

    def __str__(self):
        return f"De '{self.fase_origem.nome}' para '{self.fase_destino.nome}'"


# ==============================================================================
# HISTÓRICO DE FASE (Mantém como está)
# ==============================================================================

class HistoricoFase(models.Model):
    """Registra a passagem de um Caso por uma Fase."""
    caso = models.ForeignKey('casos.Caso', on_delete=models.CASCADE, related_name='historico_fases')
    fase = models.ForeignKey(Fase, on_delete=models.PROTECT)
    data_entrada = models.DateTimeField(auto_now_add=True)
    data_saida = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Histórico de Fase"
        verbose_name_plural = "8. Histórico de Fases"
        ordering = ['-data_entrada']

    def __str__(self):
        return f"Caso #{self.caso_id} em '{self.fase.nome}'"


# ==============================================================================
# INSTÂNCIA DE AÇÃO (Mantém, mas NÃO vai no Admin)
# ==============================================================================

class InstanciaAcao(models.Model):
    """Uma instância de uma Ação para um Caso específico."""
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CONCLUIDA', 'Concluída'),
    ]
    
    caso = models.ForeignKey('casos.Caso', on_delete=models.CASCADE, related_name='acoes_pendentes')
    acao = models.ForeignKey(Acao, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_conclusao = models.DateTimeField(null=True, blank=True)
    concluida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acoes_concluidas'
    )
    resposta = models.CharField(max_length=10, blank=True)
    data_prazo = models.DateField(null=True, blank=True, verbose_name="Prazo")
    comentario = models.TextField(blank=True, verbose_name="Comentário")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='acoes_responsaveis',
        verbose_name="Responsável"
    )
    
    class Meta:
        verbose_name = "Instância de Ação"
        verbose_name_plural = "9. Instâncias de Ações"
        ordering = ['-id']
    
    def __str__(self):
        return f"{self.acao.titulo} - Caso #{self.caso_id}"