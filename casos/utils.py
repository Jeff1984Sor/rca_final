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
    
    Retorna: (lista_de_chaves, lista_de_cabecalhos, mapa_tipos)
    mapa_tipos = {'personalizado_nome_variavel': 'TIPO_CAMPO', ...}
    """
    
    lista_chaves = []
    lista_cabecalhos = []
    mapa_tipos = {} # <-- NOVO DICIONÁRIO DE TIPOS
    
    # 1. Adiciona os campos fixos
    campos_fixos = get_lista_campos_fixos()
    for chave, cabecalho in campos_fixos:
        lista_chaves.append(chave)
        lista_cabecalhos.append(cabecalho)
        # (Opcional) Adicionar tipos fixos se necessário, ex:
        if 'data_' in chave:
             mapa_tipos[chave] = 'DATA'
            
    campos_personalizados_query = None

    # 2. Lógica Híbrida para buscar campos personalizados
    if cliente and produto:
        # Modo 1: Filtra pela estrutura C+P (Usado pela Importação)
        try:
            estrutura = EstruturaDeCampos.objects.get(cliente=cliente, produto=produto)
            campos_personalizados_query = estrutura.campos.all().order_by('estruturacampoordenado__order')
        except EstruturaDeCampos.DoesNotExist:
            campos_personalizados_query = CampoPersonalizado.objects.none()
    else:
        # Modo 2: MESTRE (Exportação) - Pega TODOS
        campos_personalizados_query = CampoPersonalizado.objects.all().order_by('nome_campo')

    # 3. Processa o queryset de campos personalizados
    if campos_personalizados_query:
        for campo in campos_personalizados_query:
            chave_personalizada = f'personalizado_{campo.nome_variavel}'
            cabecalho_personalizado = campo.nome_campo 
            
            if chave_personalizada not in lista_chaves:
                lista_chaves.append(chave_personalizada)
                lista_cabecalhos.append(cabecalho_personalizado)
                mapa_tipos[chave_personalizada] = campo.tipo_campo # <-- SALVA O TIPO
                
    # Retorna as 3 listas
    return (lista_chaves, lista_cabecalhos, mapa_tipos)