from django import forms
from django.contrib.auth import get_user_model
from datetime import date
from django.contrib.auth import get_user_model
# UMA ÚNICA LINHA PARA TODOS OS MODELOS DO APP 'casos'
from .models import Acordo, Caso, Andamento, ModeloAndamento, Timesheet, Despesa
from campos_custom.models import ConfiguracaoCampoPersonalizado

User = get_user_model()

class CasoDinamicoForm(forms.Form):
    # Campos Padrão do Caso (não precisam mudar)
    status = forms.ChoiceField(choices=Caso.STATUS_CHOICES, required=True, label="Status do Caso")
    data_entrada = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True, label="Data de Entrada")
    data_encerramento = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label="Data de Encerramento")
    advogado_responsavel = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        required=False,
        label="Advogado Responsável"
    )
    
    def __init__(self, *args, **kwargs):
        # ==============================================================================
        # LÓGICA DE INICIALIZAÇÃO ATUALIZADA
        # Agora o formulário precisa receber o 'cliente' e o 'produto'
        # ==============================================================================
        cliente = kwargs.pop('cliente', None)
        produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)

        # Se o produto não tiver um padrão de título, adicionamos o campo de título manual
        if produto and not produto.padrao_titulo:
            self.fields['titulo_manual'] = forms.CharField(
                label="Título Manual", 
                max_length=255, 
                required=False,
                widget=forms.TextInput(attrs={'placeholder': 'Descreva o caso resumidamente...'})
            )

        # A mágica acontece aqui: só adicionamos campos se tivermos um cliente e um produto
        if cliente and produto:
            # 1. Buscamos as configurações de campos para esta combinação específica de Cliente + Produto
            configuracoes = ConfiguracaoCampoPersonalizado.objects.filter(
                cliente=cliente, 
                produto=produto
            ).select_related('campo').order_by('ordem')
            
            # 2. Iteramos sobre as configurações encontradas
            for config in configuracoes:
                # 3. Pegamos o objeto CampoPersonalizado de dentro da configuração
                campo = config.campo
                
                field_name = f'campo_personalizado_{campo.id}'
                field_label = campo.nome_campo
                # 4. Pegamos 'obrigatorio' da configuração
                field_required = config.obrigatorio

                # ==============================================================================
                # LÓGICA ATUALIZADA PARA CRIAR OS CAMPOS DO FORMULÁRIO
                # Incluindo os novos tipos 'MOEDA' e 'LISTA_USUARIOS'
                # ==============================================================================
                if campo.tipo_campo == 'TEXTO':
                    self.fields[field_name] = forms.CharField(label=field_label, required=field_required, widget=forms.TextInput(attrs={'class': 'form-control'}))
                
                elif campo.tipo_campo == 'NUMERO_INT':
                    self.fields[field_name] = forms.IntegerField(label=field_label, required=field_required, widget=forms.NumberInput(attrs={'class': 'form-control'}))
                
                elif campo.tipo_campo == 'NUMERO_DEC':
                    self.fields[field_name] = forms.DecimalField(label=field_label, required=field_required, widget=forms.NumberInput(attrs={'class': 'form-control'}))
                
                # --- NOVO TIPO: MOEDA ---
                elif campo.tipo_campo == 'MOEDA':
                    self.fields[field_name] = forms.DecimalField(
                        label=field_label, 
                        required=field_required, 
                        decimal_places=2,
                        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
                    )
                
                elif campo.tipo_campo == 'DATA':
                    self.fields[field_name] = forms.DateField(label=field_label, required=field_required, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
                
                # --- NOVO TIPO: LISTA DE USUÁRIOS ---
                elif campo.tipo_campo == 'LISTA_USUARIOS':
                    self.fields[field_name] = forms.ModelChoiceField(
                        label=field_label,
                        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
                        required=field_required,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )

                elif campo.tipo_campo == 'LISTA_UNICA':
                    opcoes = [('', '---------')] + [(opt, opt) for opt in campo.get_opcoes_como_lista]
                    self.fields[field_name] = forms.ChoiceField(label=field_label, required=field_required, choices=opcoes, widget=forms.Select(attrs={'class': 'form-select'}))
                
                elif campo.tipo_campo == 'LISTA_MULTIPLA':
                    opcoes = [(opt, opt) for opt in campo.get_opcoes_como_lista]
                    self.fields[field_name] = forms.MultipleChoiceField(label=field_label, required=field_required, choices=opcoes, widget=forms.SelectMultiple(attrs={'class': 'form-select'}))
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