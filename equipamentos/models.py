from django.db import models
from django.conf import settings 

# ==============================================================================
# Modelos de Apoio
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
# ==============================================================================

class Equipamento(models.Model):
    
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
    
    # Campo CRÍTICO: É por aqui que o script vai identificar o PC
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

    # ==========================================================================
    # NOVOS CAMPOS: Auditoria Automática (Hardware e Software)
    # Estes campos serão preenchidos pelo script Python (agente)
    # ==========================================================================
    sistema_operacional = models.CharField("SO Instalado", max_length=150, blank=True, null=True)
    processador = models.CharField("Processador (CPU)", max_length=150, blank=True, null=True)
    memoria_ram = models.CharField("Memória RAM", max_length=100, blank=True, null=True)
    espaco_disco = models.CharField("Espaço em Disco", max_length=100, blank=True, null=True)
    
    # TextField permite texto ilimitado (ideal para lista longa de softwares)
    softwares_instalados = models.TextField("Softwares Instalados", blank=True, null=True, help_text="Lista gerada automaticamente")
    
    # Para sabermos quando foi a última vez que o script rodou
    ultima_auditoria = models.DateTimeField("Data da Última Leitura", blank=True, null=True)

    def __str__(self):
        return f"{self.nome_item} ({self.modelo or 'Sem modelo'})"

    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        ordering = ['nome_item']