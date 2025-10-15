from django import forms
from django.contrib.auth import get_user_model
from datetime import date
from django.contrib.auth import get_user_model
# UMA ÚNICA LINHA PARA TODOS OS MODELOS DO APP 'casos'
from .models import Acordo, Caso, Andamento, ModeloAndamento, Timesheet, Despesa
from campos_custom.models import ConfiguracaoCampoPersonalizado
from campos_custom.models import EstruturaDeCampos

User = get_user_model()

# casos/forms.py

class CasoDinamicoForm(forms.Form):
    # ==============================================================================
    # 1. CAMPOS PADRÃO (FIXOS)
    # Com a correção de formato para o widget de data.
    # ==============================================================================
    status = forms.ChoiceField(choices=Caso.STATUS_CHOICES, required=True, label="Status do Caso")
    data_entrada = forms.DateField(
        # Usamos um widget de texto normal, mas com um placeholder amigável
        widget=forms.DateInput(attrs={'type': 'text', 'placeholder': 'DD/MM/AAAA'}),
        # Informamos ao Django os formatos que aceitamos na entrada
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=True, 
        label="Data de Entrada"
    )
    data_encerramento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'text', 'placeholder': 'DD/MM/AAAA'}),
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=False, 
        label="Data de Encerramento"
    )
    
    advogado_responsavel = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        required=False,
        label="Advogado Responsável"
    )
    
    # ==============================================================================
    # 2. O __init__ COMPLETO E CORRIGIDO
    # ==============================================================================
    def __init__(self, *args, **kwargs):
        # Primeiro, separamos nossos parâmetros customizados (cliente e produto)
        cliente = kwargs.pop('cliente', None)
        produto = kwargs.pop('produto', None)
        
        # A inicialização do Django vem primeiro, SEMPRE.
        # Isso processa 'initial' e preenche os campos padrão.
        super().__init__(*args, **kwargs)

        # Agora, com o formulário base inicializado, adicionamos os campos dinâmicos.
        
        # Adiciona o campo de título manual, se necessário
        if produto and not produto.padrao_titulo:
            self.fields['titulo_manual'] = forms.CharField(
                label="Título Manual", 
                required=False,
                widget=forms.TextInput(attrs={'placeholder': 'Descreva o caso resumidamente...'})
            )
            # Preenche o valor inicial se ele existir
            if self.initial.get('titulo_manual'):
                self.fields['titulo_manual'].initial = self.initial.get('titulo_manual')

        # Busca e cria os campos personalizados baseados na combinação Cliente + Produto
        if cliente and produto:
            estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
            if estrutura:
                # Usamos a ordenação que definimos no Admin
                for campo in estrutura.campos.all().order_by('estruturacampoordenado__order'):
                    field_name = f'campo_personalizado_{campo.id}'
                    field_label = campo.nome_campo
                    field_required = False # O campo 'obrigatorio' foi removido, então todos são opcionais

                    # ==============================================================================
                    # LÓGICA COMPLETA PARA CRIAR CADA TIPO DE CAMPO
                    # ==============================================================================
                    if campo.tipo_campo == 'TEXTO':
                        self.fields[field_name] = forms.CharField(label=field_label, required=field_required)
                    
                    elif campo.tipo_campo == 'NUMERO_INT':
                        self.fields[field_name] = forms.IntegerField(label=field_label, required=field_required)
                    
                    elif campo.tipo_campo == 'NUMERO_DEC':
                        self.fields[field_name] = forms.DecimalField(label=field_label, required=field_required)
                    
                    elif campo.tipo_campo == 'MOEDA':
                        self.fields[field_name] = forms.DecimalField(label=field_label, required=field_required, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01'}))
                    
                    elif campo.tipo_campo == 'DATA':
                        self.fields[field_name] = forms.DateField(
                            label=field_label, 
                            required=field_required, 
                            widget=forms.DateInput(attrs={'type': 'text', 'placeholder': 'DD/MM/AAAA'}),
                            input_formats=['%d/%m/%Y', '%Y-%m-%d']
                    )
                    
                    elif campo.tipo_campo == 'LISTA_USUARIOS':
                        self.fields[field_name] = forms.ModelChoiceField(label=field_label, queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name'), required=field_required)
                    
                    elif campo.tipo_campo == 'LISTA_UNICA':
                        opcoes = [('', '---------')] + [(opt, opt) for opt in campo.get_opcoes_como_lista]
                        self.fields[field_name] = forms.ChoiceField(label=field_label, required=field_required, choices=opcoes)
                    
                    elif campo.tipo_campo == 'LISTA_MULTIPLA':
                        opcoes = [(opt, opt) for opt in campo.get_opcoes_como_lista]
                        self.fields[field_name] = forms.MultipleChoiceField(label=field_label, required=field_required, choices=opcoes, widget=forms.CheckboxSelectMultiple)

                    # AQUI ESTÁ A CORREÇÃO PARA OS CAMPOS PERSONALIZADOS:
                    # Após criar CADA campo, nós o preenchemos se houver um valor inicial para ele.
                    if self.initial.get(field_name):
                        # Para ModelChoiceField, o valor inicial precisa ser o ID.
                        if campo.tipo_campo == 'LISTA_USUARIOS':
                            try:
                                self.fields[field_name].initial = int(self.initial.get(field_name))
                            except (ValueError, TypeError):
                                pass # Ignora se o valor inicial não for um ID de usuário válido
                        else:
                            self.fields[field_name].initial = self.initial.get(field_name)


class AndamentoForm(forms.ModelForm):
    # Campo "virtual" para selecionar um modelo pré-definido
    modelo_andamento = forms.ModelChoiceField(
        queryset=ModeloAndamento.objects.all(),
        required=False,
        label="Usar Modelo de Andamento",
        empty_label="-- Selecione um modelo --"
    )

    class Meta:
        model = Andamento
        # 1. TODOS os campos do modelo que queremos no form estão aqui
        fields = ['data_andamento', 'descricao']
        widgets = {
            'data_andamento': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 2. MODIFICAMOS o campo que o ModelForm já criou
        self.fields['data_andamento'].initial = date.today
        self.fields['data_andamento'].label = "Data do Andamento"

        # 3. Reordenamos os campos para colocar o 'modelo_andamento' no topo
        self.order_fields(['modelo_andamento', 'data_andamento', 'descricao'])

class TimesheetForm(forms.ModelForm):
    # Definimos o campo aqui fora para ter mais controle
    data_execucao = forms.DateField(
        label="Data da Execução",
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=date.today
    )

    class Meta:
        model = Timesheet
        # IMPORTANTE: Incluímos 'data_execucao' na lista de fields
        fields = ['data_execucao', 'tempo', 'advogado', 'descricao']
        widgets = {
            'tempo': forms.TextInput(
                attrs={'placeholder': 'HH:MM', 'pattern': '[0-9]{2}:[0-5][0-9]'}
            ),
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['advogado'].initial = user
        
        # A ordem dos campos é garantida pela sua definição na classe
        # self.order_fields() não é mais necessário aqui

class AcordoForm(forms.ModelForm):
    class Meta:
        model = Acordo
        # Campos que o usuário vai preencher
        fields = ['valor_total', 'numero_parcelas', 'data_primeira_parcela', 'advogado_acordo']
        widgets = {
            'data_primeira_parcela': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Pega o usuário logado que passaremos da view
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Sugere o usuário logado como valor inicial para o campo 'advogado'
        if user:
            self.fields['advogado_acordo'].initial = user

class DespesaForm(forms.ModelForm):
    data_despesa = forms.DateField(
        label="Data da Despesa",
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=date.today
    )

    class Meta:
        model = Despesa
        fields = ['data_despesa', 'descricao', 'valor', 'advogado']
        widgets = {
            'descricao': forms.TextInput(attrs={'placeholder': 'Ex: Cópia, Autenticação, Deslocamento'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['advogado'].initial = user
        
        self.order_fields(['data_despesa', 'descricao', 'valor', 'advogado'])