from django import forms
from django.contrib.auth import get_user_model
from datetime import date
from .models import Acordo 
from .models import Caso, Andamento, ModeloAndamento, Timesheet
from campos_custom.models import CampoPersonalizado

User = get_user_model()


class CasoDinamicoForm(forms.Form):
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

            campos_personalizados = CampoPersonalizado.objects.filter(produto=produto).order_by('ordem')
            
            for campo in campos_personalizados:
                field_name = f'campo_personalizado_{campo.id}'
                field_label = campo.nome_campo
                field_required = campo.obrigatorio

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
    modelo_andamento = forms.ModelChoiceField(
        queryset=ModeloAndamento.objects.all(),
        required=False,
        label="Usar Modelo de Andamento",
        empty_label="-- Selecione um modelo para preencher a descrição --"
    )

    # Definimos o campo aqui fora para adicionar o 'initial'
    data_andamento = forms.DateField(
        label="Data do Andamento",
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=date.today
    )

    class Meta:
        model = Andamento
        # 'data_andamento' já foi definido, então não precisa estar aqui
        fields = ['descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reordenamos para garantir que 'modelo_andamento' apareça primeiro
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