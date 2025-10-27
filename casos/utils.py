# Arquivo: casos/utils.py

# Importações necessárias
from django.shortcuts import get_object_or_404
# Ajuste as importações de modelos conforme a localização real dos seus apps
from .models import Caso 
from campos_custom.models import EstruturaDeCampos, CampoPersonalizado
from clientes.models import Cliente
from produtos.models import Produto


def get_lista_campos_fixos():
    """
    Define a lista de campos fixos do modelo Caso que devem ser exportados.
    (Esta função permanece a mesma de antes)
    """
    campos_fixos = [
        # (NOME DA VARIÁVEL/CHAVE, NOME DE EXIBIÇÃO NA PLANILHA)
        ('id', 'ID do Caso'),
        ('titulo', 'Título do Caso'),
        ('data_entrada', 'Data de Entrada'),
        ('status', 'Status'),
        ('cliente__nome', 'Cliente'),          
        ('produto__nome', 'Produto'),          
        ('advogado_responsavel__first_name', 'Advogado Responsável'), 
        ('data_encerramento', 'Data de Encerramento'),
    ]
    return campos_fixos

def get_cabecalho_exportacao(cliente=None, produto=None):
    """
    Monta a lista completa de cabeçalhos (fixos + personalizados) e suas chaves.

    - Se Cliente e Produto são fornecidos (ex: Importação), filtra campos por estrutura.
    - Se NÃO são fornecidos (ex: Exportação Mestra), retorna TODOS os campos.
    """
    
    lista_chaves = []
    lista_cabecalhos = []
    
    # 1. Adiciona os campos fixos (sempre)
    campos_fixos = get_lista_campos_fixos()
    for chave, cabecalho in campos_fixos:
        lista_chaves.append(chave)
        lista_cabecalhos.append(cabecalho)
    
    campos_personalizados_query = None

    # 2. Lógica Híbrida para buscar campos personalizados
    if cliente and produto:
        # MODO 1: Filtra pela estrutura C+P (Usado pela Importação)
        try:
            # Pega a estrutura e os campos ordenados
            estrutura = EstruturaDeCampos.objects.get(cliente=cliente, produto=produto)
            campos_personalizados_query = estrutura.campos.all().order_by('estruturacampoordenado__order') # Usa a ordem definida
        except EstruturaDeCampos.DoesNotExist:
            campos_personalizados_query = CampoPersonalizado.objects.none() # Retorna vazio
    else:
        # MODO 2: MESTRE (Opção 2 que você pediu) - Pega TODOS
        # Busca todos os campos personalizados cadastrados no banco
        campos_personalizados_query = CampoPersonalizado.objects.all().order_by('nome_campo')

    # 3. Processa o queryset de campos personalizados
    if campos_personalizados_query:
        for campo in campos_personalizados_query:
            # Chave interna (para busca no dict)
            chave_personalizada = f'personalizado_{campo.nome_variavel}'
            # Cabeçalho (o nome visível)
            cabecalho_personalizado = campo.nome_campo # Usando o nome correto que descobrimos
            
            if chave_personalizada not in lista_chaves:
                lista_chaves.append(chave_personalizada)
                lista_cabecalhos.append(cabecalho_personalizado)
                
    return (lista_chaves, lista_cabecalhos)