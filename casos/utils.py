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
    Retorna uma lista de tuplas: (nome_variavel, nome_exibicao)
    """
    
    # --------------------------------------------------------------------------
    # LISTA DE CAMPOS FIXOS (Ajuste essa lista conforme o que você quer na planilha!)
    # --------------------------------------------------------------------------
    campos_fixos = [
        # (NOME DA VARIÁVEL/CHAVE, NOME DE EXIBIÇÃO NA PLANILHA)
        ('id', 'ID do Caso'),
        ('titulo', 'Título do Caso'),
        ('data_entrada', 'Data de Entrada'),
        ('status', 'Status'),
        ('cliente__nome', 'Cliente'),          # Acessa o nome do Cliente via FK
        ('produto__nome', 'Produto'),          # Acessa o nome do Produto via FK
        ('advogado_responsavel__first_name', 'Advogado Responsável'), # Usa o first_name do usuário
        ('data_encerramento', 'Data de Encerramento'),
    ]
    
    return campos_fixos


def get_cabecalho_exportacao(cliente, produto):
    """
    Monta a lista completa de cabeçalhos (fixos + personalizados) e suas chaves.
    Recebe os objetos Cliente e Produto.
    Retorna: (lista_de_chaves, lista_de_cabecalhos)
    """
    
    # 1. Obter a Estrutura de Campos Personalizados
    # Prefetch o 'campos' para otimizar a query
    estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).prefetch_related('campos').first()
    
    # 2. Iniciar as Listas com Campos Fixos
    lista_chaves = []
    lista_cabecalhos = []
    
    # Adiciona os campos fixos
    campos_fixos = get_lista_campos_fixos()
    for chave, cabecalho in campos_fixos:
        lista_chaves.append(chave)
        lista_cabecalhos.append(cabecalho)
        
    # 3. Adicionar Campos Personalizados
    if estrutura:
        # Itera pelos campos da estrutura (já estão na ordem correta)
        for campo in estrutura.campos.all(): 
            
            # A chave interna (para busca) é o nome da variável, com prefixo.
            chave_personalizada = f'personalizado_{campo.nome_variavel}' 
            
            # O cabeçalho é o nome de exibição do campo
            cabecalho_personalizado = campo.nome_campo
            
            lista_chaves.append(chave_personalizada)
            lista_cabecalhos.append(cabecalho_personalizado)
            
    return (lista_chaves, lista_cabecalhos)