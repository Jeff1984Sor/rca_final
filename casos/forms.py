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
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'), 
        input_formats=['%Y-%m-%d'],
        required=True, 
        label="Data de Entrada"
    )
    data_encerramento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
        required=False, 
        label="Data de Encerramento"
    )
    advogado_responsavel = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        required=False,
        label="Advogado Responsável"
    )
    
    # ==============================================================================
    # 2. O CORAÇÃO DA MÁGICA: O __init__ COM O MEGA LOG
    # ==============================================================================
    def __init__(self, *args, **kwargs):
        # ==============================================================================
        # MEGA LOG DE DIAGNÓSTICO
        # ==============================================================================
        print("\n" + "="*60)
        print("--- INICIANDO DIAGNÓSTICO COMPLETO DO CasoDinamicoForm ---")
        
        # Espião 1: Verificamos os dados iniciais que a view enviou
        initial_data_from_view = kwargs.get('initial', {})
        print("\n[ESPIÃO 1: DADOS INICIAIS RECEBIDOS DA VIEW]")
        if initial_data_from_view:
            print("  - Status:", initial_data_from_view.get('status'))
            print("  - Data de Entrada:", initial_data_from_view.get('data_entrada'))
            print("  - Campos Personalizados encontrados:", {k: v for k, v in initial_data_from_view.items() if k.startswith('campo_personalizado_')})
        else:
            print("  - [AVISO] Nenhum dicionário 'initial' foi recebido. O formulário estará em branco.")
        
        # ==============================================================================

        # Separação dos nossos parâmetros customizados
        cliente = kwargs.pop('cliente', None)
        produto = kwargs.pop('produto', None)
        
        # Inicializa o formulário pai. Isso processa os 'initial data'.
        super().__init__(*args, **kwargs)
        
        # ==============================================================================
        # Espião 2: Verificamos os dados após a inicialização do Django
        print("\n[ESPIÃO 2: DADOS APÓS super().__init__()]")
        print("  - Valor inicial de 'data_entrada' no formulário:", self.fields['data_entrada'].initial)
        print("  - Dicionário `self.initial` completo:", self.initial)
        # ==============================================================================

        # Adiciona os campos dinâmicos
        if produto and not produto.padrao_titulo:
            self.fields['titulo_manual'] = forms.CharField(
                label="Título Manual", 
                required=False,
                widget=forms.TextInput(attrs={'placeholder': 'Descreva o caso resumidamente...'})
            )

        if cliente and produto:
            print("\n[ESPIÃO 3: LÓGICA DE CAMPOS DINÂMICOS]")
            print(f"  - Buscando Estrutura para Cliente ID={cliente.id} e Produto ID={produto.id}")
            estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
            if estrutura:
                print(f"  - [SUCESSO] Estrutura encontrada (ID={estrutura.id}). Processando campos...")
                for campo in estrutura.campos.all().order_by('estruturacampoordenado__order'):
                    field_name = f'campo_personalizado_{campo.id}'
                    # ... sua lógica de criação de campos aqui ...
                    if campo.tipo_campo == 'TEXTO': self.fields[field_name] = forms.CharField(label=campo.nome_campo, required=False)
                    elif campo.tipo_campo == 'DATA': self.fields[field_name] = forms.DateField(label=campo.nome_campo, required=False, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'), input_formats=['%Y-%m-%d'])
                    # ... adicione os outros elifs ...

                    # A LÓGICA DE PREENCHIMENTO
                    initial_value = self.initial.get(field_name)
                    if initial_value is not None:
                        self.fields[field_name].initial = initial_value
                        print(f"    -> Campo '{campo.nome_campo}' criado e preenchido com valor inicial: '{initial_value}'")
                    else:
                        print(f"    -> Campo '{campo.nome_campo}' criado (sem valor inicial).")
            else:
                print("  - [FALHA] Nenhuma estrutura encontrada para esta combinação.")
        else:
            print("\n[ESPIÃO 3: LÓGICA DE CAMPOS DINÂMICOS] -> PULADO (Faltou cliente ou produto).")

        print("--- FIM DO DIAGNÓSTICO ---")
        print("="*60 + "\n")
        
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