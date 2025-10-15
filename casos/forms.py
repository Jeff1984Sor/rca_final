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
    # Campos Padrão do Caso (não mudam)
    status = forms.ChoiceField(choices=Caso.STATUS_CHOICES, required=True, label="Status do Caso")
    data_entrada = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True, label="Data de Entrada")
    data_encerramento = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label="Data de Encerramento")
    advogado_responsavel = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        required=False,
        label="Advogado Responsável"
    )
    class Meta:
        model = Caso
        # Campos que o ModelForm vai cuidar AUTOMATICAMENTE
        fields = ['status', 'data_entrada', 'data_encerramento', 'advogado_responsavel', 'titulo']
        widgets = {
            'data_entrada': forms.DateInput(attrs={'type': 'date'}),
            'data_encerramento': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        # ==============================================================================
        # ESPIÃO DOS DADOS INICIAIS (AQUI ESTÁ A CHAVE)
        # ==============================================================================
        print(f"\n--- DADOS INICIAIS RECEBIDOS PELA VIEW: {kwargs.get('initial')} ---")
        # ==============================================================================
        
        cliente = kwargs.pop('cliente', None)
        produto = kwargs.pop('produto', None)

        initial_data = kwargs.get('initial', {})

        super().__init__(*args, **kwargs)

        if 'data_entrada' in initial_data:
            self.fields['data_entrada'].initial = initial_data['data_entrada']

        print("\n--- INICIANDO DIAGNÓSTICO DO CasoDinamicoForm ---")
        if cliente:
            print(f"1. RECEBIDO: Cliente ID={cliente.id}, Nome='{cliente}'")
        else:
            print("1. [ALERTA] Nenhum objeto 'cliente' foi recebido pela view.")

        if produto:
            print(f"2. RECEBIDO: Produto ID={produto.id}, Nome='{produto}'")
        else:
            print("2. [ALERTA] Nenhum objeto 'produto' foi recebido pela view.")

        if produto and not produto.padrao_titulo:
            self.fields['titulo_manual'] = forms.CharField(
                label="Título Manual", 
                max_length=255, 
                required=False,
                widget=forms.TextInput(attrs={'placeholder': 'Descreva o caso resumidamente...'})
            )

        if cliente and produto:
            print(f"3. BUSCANDO: EstruturaDeCampos para Cliente ID={cliente.id} E Produto ID={produto.id}")
            estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
            
            if estrutura:
                print(f"4. [SUCESSO] Estrutura encontrada! ID={estrutura.id}")
                campos_da_estrutura = list(estrutura.campos.all())
                print(f"5. CAMPOS NA ESTRUTURA: {[campo.nome_campo for campo in campos_da_estrutura]}")
                
                for i, campo in enumerate(campos_da_estrutura):
                    print(f"   -> Processando campo {i+1}/{len(campos_da_estrutura)}: '{campo.nome_campo}' (ID: {campo.id})")
                    field_name = f'campo_personalizado_{campo.id}'
                    # ... (resto da sua lógica de criação de campos) ...

            else:
                print("4. [FALHA] Nenhuma 'EstruturaDeCampos' encontrada para esta combinação de Cliente e Produto.")
            
            print("--- FIM DO DIAGNÓSTICO ---\n")
        else:
            print("3. [PULANDO] Busca de campos personalizados não realizada por falta de Cliente ou Produto.")
            print("--- FIM DO DIAGNÓSTICO ---\n")
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