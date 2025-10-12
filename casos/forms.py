from django import forms
from django.contrib.auth import get_user_model
from datetime import date

# UMA ÚNICA LINHA PARA TODOS OS MODELOS DO APP 'casos'
from .models import Acordo, Caso, Andamento, ModeloAndamento, Timesheet, Despesa

from campos_custom.models import CampoPersonalizado
User = get_user_model()

class CasoDinamicoForm(forms.Form):
    # Campos Padrão (permanecem os mesmos)
    status = forms.ChoiceField(choices=Caso.STATUS_CHOICES, required=True)
    data_entrada = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    data_encerramento = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    advogado_responsavel = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('first_name', 'last_name', 'username'),
        required=False,
        label="Advogado Responsável"
    )
    
    def __init__(self, *args, **kwargs):
        produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)

        if produto:
            if not produto.padrao_titulo:
                self.fields['titulo_manual'] = forms.CharField(
                    label="Título Manual", 
                    max_length=255, 
                    required=False,
                    widget=forms.TextInput(attrs={'placeholder': 'Descreva o caso resumidamente...'})
                )

            # --- LÓGICA DE BUSCA E LOOP CORRIGIDA ---

            # 1. Buscamos a relação através do modelo intermediário
            campos_info = produto.produtocampo_set.select_related('campo').order_by('ordem')
            
            # 2. Iteramos sobre o resultado correto ('campos_info')
            for produto_campo in campos_info:
                # 3. Pegamos o objeto CampoPersonalizado de dentro do modelo intermediário
                campo = produto_campo.campo
                
                field_name = f'campo_personalizado_{campo.id}'
                field_label = campo.nome_campo
                # 4. Pegamos 'obrigatorio' do modelo intermediário
                field_required = produto_campo.obrigatorio

                if campo.tipo_campo == 'TEXTO':
                    self.fields[field_name] = forms.CharField(label=field_label, required=field_required)
                
                elif campo.tipo_campo == 'NUMERO_INT':
                    self.fields[field_name] = forms.IntegerField(label=field_label, required=field_required)
                
                elif campo.tipo_campo == 'NUMERO_DEC':
                    self.fields[field_name] = forms.DecimalField(label=field_label, required=field_required)

                elif campo.tipo_campo == 'DATA':
                    self.fields[field_name] = forms.DateField(label=field_label, required=field_required, widget=forms.DateInput(attrs={'type': 'date'}))
                
                elif campo.tipo_campo == 'LISTA_UNICA':
                    opcoes = [('', '---------')] + [(opt, opt) for opt in campo.get_opcoes_como_lista]
                    self.fields[field_name] = forms.ChoiceField(label=field_label, required=field_required, choices=opcoes)

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