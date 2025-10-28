# Arquivo: casos/utils.py

# Importações necessárias
from django.shortcuts import get_object_or_404
# Ajuste as importações de modelos conforme a localização real dos seus apps
from .models import Caso 
from campos_custom.models import EstruturaDeCampos, CampoPersonalizado
from clientes.models import Cliente
from produtos.models import Produto

from django import forms



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



def build_form_field(campo, is_required=False, cliente=None, produto=None):
    """
    Constrói dinamicamente um campo de formulário baseado no tipo do campo personalizado.
    """
    tipo = campo.tipo_campo

    if tipo == 'TEXTO':
        return forms.CharField(
            required=is_required,
            widget=forms.TextInput(attrs={'class': 'form-control'})
        )

    elif tipo == 'NUMERO_INT':
        return forms.IntegerField(
            required=is_required,
            widget=forms.NumberInput(attrs={'class': 'form-control'})
        )

    elif tipo == 'NUMERO_DEC':
        return forms.DecimalField(
            required=is_required,
            widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        )

    elif tipo == 'MOEDA':
        return forms.DecimalField(
            required=is_required,
            widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        )

    elif tipo == 'DATA':
        return forms.DateField(
            required=is_required,
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            input_formats=['%Y-%m-%d']
        )

    elif tipo in ['LISTA_UNICA', 'LISTA_MULTIPLA']:
        from campos_custom.models import OpcoesListaPersonalizada
        opcoes_obj = OpcoesListaPersonalizada.objects.filter(campo=campo, cliente=cliente, produto=produto).first()
        choices = [(opt.strip(), opt.strip()) for opt in opcoes_obj.get_opcoes_como_lista()] if opcoes_obj else []

        if tipo == 'LISTA_UNICA':
            return forms.ChoiceField(
                choices=[('', '--- Selecione ---')] + choices,
                required=is_required,
                widget=forms.Select(attrs={'class': 'form-select'})
            )
        else:
            return forms.MultipleChoiceField(
                choices=choices,
                required=is_required,
                widget=forms.SelectMultiple(attrs={'class': 'form-select'})
            )

    return forms.CharField(required=is_required, widget=forms.TextInput(attrs={'class': 'form-control'}))
