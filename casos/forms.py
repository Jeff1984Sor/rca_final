# casos/forms.py

from django import forms
from django.forms import formset_factory, modelformset_factory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms.widgets import HiddenInput

# Importa os NOVOS modelos de campos_custom
from campos_custom.models import (
    EstruturaDeCampos, 
    GrupoCampos, 
    CampoPersonalizado,
    InstanciaGrupoValor, # Usado para salvar
    ValorCampoPersonalizado,
     OpcoesListaPersonalizada # Usado para salvar
)
# Importa os modelos de Caso e Cliente/Produto
from .models import Caso, Andamento, Timesheet, Acordo, Despesa
from clientes.models import Cliente
from produtos.models import Produto

User = get_user_model()

# ==============================================================================
# FORMULÁRIO DINÂMICO DE CASO (ATUALIZADO PARA GRUPOS)
# ==============================================================================


class CasoDinamicoForm(forms.ModelForm):
    """
    Formulário principal para criar/editar um Caso,
    incluindo campos fixos e personalizados simples.
    """
    class Meta:
        model = Caso
        fields = ['data_entrada', 'data_encerramento', 'status', 'advogado_responsavel']
        widgets = {
            'data_entrada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),            
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),

        }

    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)

        # ✅ Garante valores iniciais para edição
        if self.instance and self.instance.pk:
            self.fields['data_entrada'].initial = self.instance.data_entrada
            self.fields['data_encerramento'].initial = self.instance.data_encerramento

            # Se cliente/produto não foram passados, pega da instância
            if not self.cliente:
                self.cliente = self.instance.cliente
            if not self.produto:
                self.produto = self.instance.produto

        # Se não houver cliente/produto, não adiciona campos dinâmicos
        if not self.cliente or not self.produto:
            return

        # Busca estrutura de campos
        try:
            self.estrutura = EstruturaDeCampos.objects.prefetch_related(
                'campos', 'grupos_repetiveis__campos'
            ).get(cliente=self.cliente, produto=self.produto)
        except EstruturaDeCampos.DoesNotExist:
            self.estrutura = None
            return

        # ✅ Adiciona campos personalizados simples
        campos_simples_ordenados = self.estrutura.ordenamentos_simples.select_related('campo')
        for config_campo in campos_simples_ordenados:
            campo = config_campo.campo
            is_required = config_campo.obrigatorio
            field_name = f'campo_personalizado_{campo.id}'

            self.fields[field_name] = build_form_field(
                campo, is_required=is_required, cliente=self.cliente, produto=self.produto
            )
            self.fields[field_name].label = campo.nome_campo

            # ✅ Se estiver editando, carrega valor salvo
            if self.instance.pk:
                valor_salvo = self.instance.valores_personalizados.filter(campo=campo).first()
                if valor_salvo:
                    self.fields[field_name].initial = valor_salvo.valor

        # ✅ Campo de título manual (se não houver padrão)
        if not self.produto.padrao_titulo:
            self.fields['titulo_manual'] = forms.CharField(
                label="Título Manual do Caso",
                required=True,
                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o título do caso'})
            )

    # ✅ Métodos auxiliares para template
    def campos_fixos(self):
        return [self[field_name] for field_name in self.Meta.fields]

    def campos_personalizados_simples(self):
        if self.estrutura:
            ids = self.estrutura.ordenamentos_simples.values_list('campo__id', flat=True)
            return [self[f'campo_personalizado_{campo_id}'] for campo_id in ids if f'campo_personalizado_{campo_id}' in self.fields]
        return []

    def grupos_repetiveis(self):
        return self.estrutura.grupos_repetiveis.all() if self.estrutura else []

class BaseGrupoForm(forms.Form):
    """
    Classe base usada pelo formset_factory para criar formulários para grupos repetíveis.
    Os campos são adicionados dinamicamente no __init__.
    """
    def __init__(self, *args, grupo_campos=None, cliente=None, produto=None, **kwargs):
        super().__init__(*args, **kwargs)
        ORDEM = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput() # <<< OBRIGA O CAMPO A SER OCULTO
    )
        
        if grupo_campos:
            # CORREÇÃO AQUI: Usar o nome do modelo through (grupocampoordenado) e o campo 'order'
            # O nome do relacionamento é 'grupocampoordenado' (em minúsculo)
            campos_ordenados = grupo_campos.campos.all().order_by('grupocampoordenado__order') # <<< CORREÇÃO

            for campo in grupo_campos.campos.all().order_by('grupocampoordenado__order'): # <<< CORREÇÃO
                
                # Para carregar as opções customizadas (que o init principal não faz)
                cliente = kwargs.get('cliente')
                produto = kwargs.get('produto')
                
                # Constrói o campo dinâmico
                field_instance = build_form_field(campo, is_required=False, cliente=cliente, produto=produto)
                
                # Garante que o nome do campo no formulário use o ID
                field_name = f'campo_personalizado_{campo.id}' # Usa o nome final que a view espera
                self.fields[field_name] = field_instance
        if 'ORDER' in self.fields:
            self.fields['ORDER'].required = False # Não obrigatório (embora não devesse ser)
            self.fields['ORDER'].widget = HiddenInput()
            self.fields['ORDER'].initial = 0 # Valor inicial (geralmente preenchido pelo formset)
    
class Meta:
        exclude = ['ORDER']


# ==============================================================================
# FORMULÁRIOS DE GRUPO (PARA OS FORMSETS)
# ==============================================================================
class ValorCampoPersonalizadoForm(forms.ModelForm):
    """
    Formulário base para editar um ValorCampoPersonalizado dentro de um grupo repetível.
    """
    class Meta:
        model = ValorCampoPersonalizado
        fields = ['valor']
    
    # Vamos adicionar o campo 'nome_campo' (o rótulo) e o campo 'tipo_campo' 
    # para usar no __init__ do formset mais tarde.
    
    # O campo real será adicionado dinamicamente no construtor do formset.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O valor do campo 'valor' será sobrescrito pelo campo dinâmico real (Data Input, etc.)

# ==============================================================================
# FUNÇÃO AUXILIAR PARA CONSTRUIR CAMPOS
# ==============================================================================

def build_form_field(campo_obj: CampoPersonalizado, is_required=False, cliente=None, produto=None) -> forms.Field:
    """
    Cria o campo de formulário Django apropriado com base no 'tipo_campo'.
    Busca opções customizadas se o tipo for LISTA.
    """
    tipo = campo_obj.tipo_campo
    label = campo_obj.nome_campo
    
    # Adiciona classe form-control/form-select por padrão
    attrs = {'class': 'form-control'} 
    
    # 1. Lógica de Busca de Opções Customizadas (para Listas)
    choices = None
    if tipo in ['LISTA_UNICA', 'LISTA_MULTIPLA'] and cliente and produto:
        # Busca a lista de opções exclusiva para esta combinação C+P
        opcoes_customizadas = OpcoesListaPersonalizada.objects.filter(
            campo=campo_obj,
            cliente=cliente,
            produto=produto
        ).first()
        
        if opcoes_customizadas:
            opcoes = opcoes_customizadas.get_opcoes_como_lista()
            choices = [(o, o) for o in opcoes]

    # 2. Definição do Campo
    if tipo == 'DATA':
        return forms.DateField(
            label=label, 
            required=is_required, 
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        )
    elif tipo == 'NUMERO_INT':
        return forms.IntegerField(label=label, required=is_required, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    elif tipo == 'NUMERO_DEC' or tipo == 'MOEDA':
        return forms.DecimalField(label=label, required=is_required, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    
    # 3. Tipos de Lista
    elif tipo == 'LISTA_UNICA':
        # Se achou opções, usa, senão, o campo ficará vazio (ou você pode levantar um erro)
        if choices:
            choices.insert(0, ('', '---------')) # Adiciona a opção vazia
            return forms.ChoiceField(
                label=label, 
                required=is_required, 
                choices=choices, 
                widget=forms.Select(attrs={'class': 'form-select'})
            )
        else:
             # Se não houver opções customizadas, retorna um campo de texto simples para evitar erro
             return forms.CharField(label=label, required=is_required, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nenhuma opção de lista definida.'}))

    elif tipo == 'LISTA_MULTIPLA':
        if choices:
            return forms.MultipleChoiceField(
                label=label, 
                required=is_required, 
                choices=choices, 
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
            )
        else:
            return forms.CharField(label=label, required=is_required, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nenhuma opção de lista definida.'}))
    
    # Padrão é TEXTO
    else: 
        return forms.CharField(
            label=label, 
            required=is_required, 
            widget=forms.TextInput(attrs={'class': 'form-control'})
        )

# ==============================================================================
# OUTROS FORMULÁRIOS (Sem mudanças)
# ==============================================================================

class AndamentoForm(forms.ModelForm):
    class Meta:
        model = Andamento
        fields = ['data_andamento', 'descricao'] # <-- CORRIGIDO
        # (Adicione seus widgets aqui, se necessário)
        widgets = {
            'data_andamento': forms.DateInput(attrs={'type': 'date'}),
        }

class TimesheetForm(forms.ModelForm):
    # (Seu código original)
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['advogado'].initial = user
            self.fields['advogado'].queryset = User.objects.filter(id=user.id) # Exemplo

    class Meta:
        model = Timesheet
        fields = ['data_execucao', 'tempo', 'advogado', 'descricao']
        # (Seu código original de widgets)

class AcordoForm(forms.ModelForm):
    # (Seu código original)
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['advogado_acordo'].initial = user
            self.fields['advogado_acordo'].queryset = User.objects.filter(id=user.id) # Exemplo
            
    class Meta:
        model = Acordo
        fields = ['valor_total', 'numero_parcelas', 'data_primeira_parcela', 'advogado_acordo']
        # (Seu código original de widgets)

class DespesaForm(forms.ModelForm):
    # (Seu código original)
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['advogado'].initial = user
            self.fields['advogado'].queryset = User.objects.filter(id=user.id) # Exemplo
            
    class Meta:
        model = Despesa
        fields = ['data_despesa', 'descricao', 'valor', 'advogado']
        # (Seu código original de widgets)