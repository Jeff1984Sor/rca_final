# analyser/models.py

from django.db import models
from django.contrib.auth.models import User
from casos.models import Caso
from clientes.models import Cliente
from produtos.models import Produto
from campos_custom.models import CampoPersonalizado, EstruturaDeCampos, EstruturaCampoOrdenado  # ✅

class ModeloAnalise(models.Model):
    """Modelo de análise com mapeamento de campos."""
    
    nome = models.CharField(max_length=200, verbose_name="Nome do Modelo")
    descricao = models.TextField(verbose_name="Descrição", blank=True, null=True)
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='modelos_analise',
        verbose_name="Cliente"
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='modelos_analise',
        verbose_name="Produto"
    )
    
    descricoes_campos = models.JSONField(
        verbose_name="Descrições dos Campos",
        help_text="Dicionário com descrições de como encontrar cada campo",
        default=dict,
        blank=True
    )
    
    instrucoes_gerais = models.TextField(
        verbose_name="Instruções Gerais",
        default="""Você é um assistente especializado em análise de documentos jurídicos.
Seja preciso e atencioso. Se não encontrar uma informação, retorne "Não encontrado".""",
        blank=True
    )
    
    gerar_resumo = models.BooleanField(default=True, verbose_name="Gerar Resumo do Caso")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modelos_analise_criados'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Modelo de Análise"
        verbose_name_plural = "Modelos de Análise"
        ordering = ['cliente', 'produto', 'nome']
        unique_together = ['cliente', 'produto', 'nome']
    
    def __str__(self):
        return f"{self.nome} - {self.cliente.nome} / {self.produto.nome}"
    
    def get_campos_para_extrair(self):
        """Retorna todos os campos (padrão + personalizados)."""
        campos = []
        
        # ✅ Campos padrão do Caso
        campos_padrao = [
            {'nome': 'titulo', 'tipo': 'TEXTO', 'label': 'Título do Caso'},
            {'nome': 'data_entrada', 'tipo': 'DATA', 'label': 'Data de Entrada'},
            {'nome': 'valor_apurado', 'tipo': 'MOEDA', 'label': 'Valor Apurado'},
        ]
        
        for cp in campos_padrao:
            campos.append({
                'nome': cp['nome'],
                'label': cp['label'],
                'tipo': cp['tipo'],
                'descricao': self.descricoes_campos.get(cp['nome'], ''),
                'is_padrao': True
            })
        
        # ✅ Busca a estrutura de campos do Cliente + Produto
        try:
            estrutura = EstruturaDeCampos.objects.get(
                cliente=self.cliente,
                produto=self.produto
            )
            
            # Pega campos ordenados da estrutura (campos NÃO repetíveis)
            campos_ordenados = EstruturaCampoOrdenado.objects.filter(
                estrutura=estrutura
            ).select_related('campo').order_by('order')
            
            for campo_ord in campos_ordenados:
                campo = campo_ord.campo
                campos.append({
                    'nome': f'campo_{campo.id}',
                    'label': campo.nome_campo,
                    'tipo': campo.tipo_campo,
                    'nome_variavel': campo.nome_variavel,
                    'descricao': self.descricoes_campos.get(f'campo_{campo.id}', ''),
                    'is_padrao': False,
                    'campo_id': campo.id,
                    'obrigatorio': campo_ord.obrigatorio
                })
                
        except EstruturaDeCampos.DoesNotExist:
            # Se não tem estrutura, retorna só campos padrão
            pass
        
        return campos


class ResultadoAnalise(models.Model):
    """Resultado de uma análise."""
    
    STATUS_CHOICES = [
        ('PROCESSANDO', 'Processando'),
        ('CONCLUIDO', 'Concluído'),
        ('ERRO', 'Erro'),
    ]
    
    caso = models.ForeignKey(
        Caso,
        on_delete=models.CASCADE,
        related_name='analises',
        verbose_name="Caso"
    )
    modelo_usado = models.ForeignKey(
        ModeloAnalise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resultados',
        verbose_name="Modelo Usado"
    )
    
    arquivos_analisados = models.JSONField(
        verbose_name="Arquivos Analisados",
        default=list
    )
    
    dados_extraidos = models.JSONField(
        verbose_name="Dados Extraídos",
        default=dict
    )
    
    resumo_caso = models.TextField(
        verbose_name="Resumo do Caso",
        blank=True,
        null=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PROCESSANDO',
        verbose_name="Status"
    )
    mensagem_erro = models.TextField(blank=True, null=True, verbose_name="Mensagem de Erro")
    
    aplicado_ao_caso = models.BooleanField(default=False, verbose_name="Aplicado ao Caso")
    data_aplicacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Aplicação")
    aplicado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analises_aplicadas',
        verbose_name="Aplicado Por"
    )
    
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analises_criadas',
        verbose_name="Criado Por"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    tempo_processamento = models.DurationField(null=True, blank=True, verbose_name="Tempo de Processamento")
    
    class Meta:
        verbose_name = "Resultado de Análise"
        verbose_name_plural = "Resultados de Análises"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"Análise #{self.id} - Caso {self.caso.id} - {self.get_status_display()}"


class LogAnalise(models.Model):
    """Log detalhado do processo de análise."""
    
    resultado = models.ForeignKey(
        ResultadoAnalise,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name="Resultado"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    nivel = models.CharField(
        max_length=20,
        choices=[
            ('INFO', 'Informação'),
            ('WARNING', 'Aviso'),
            ('ERROR', 'Erro'),
            ('SUCCESS', 'Sucesso'),
        ],
        default='INFO'
    )
    mensagem = models.TextField(verbose_name="Mensagem")
    detalhes = models.JSONField(blank=True, null=True, verbose_name="Detalhes")
    
    class Meta:
        verbose_name = "Log de Análise"
        verbose_name_plural = "Logs de Análises"
        ordering = ['timestamp']
    
    def __str__(self):
        return f"[{self.nivel}] {self.timestamp.strftime('%H:%M:%S')} - {self.mensagem[:50]}"