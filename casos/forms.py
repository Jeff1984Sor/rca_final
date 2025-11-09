# casos/forms.py

from django import forms
from django.forms import formset_factory, modelformset_factory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms.widgets import HiddenInput

# Importa os modelos
from campos_custom.models import (
    EstruturaDeCampos, 
    GrupoCampos, 
    CampoPersonalizado,
    InstanciaGrupoValor,
    ValorCampoPersonalizado,
    OpcoesListaPersonalizada
)
from .models import Caso, Andamento, Timesheet, Acordo, Despesa
from clientes.models import Cliente
from produtos.models import Produto
from datetime import timedelta
import re

User = get_user_model()

# ==============================================================================
# FUNÇÃO AUXILIAR (SEM MUDANÇAS)
# ==============================================================================

def build_form_field(campo_obj: CampoPersonalizado, is_required=False, cliente=None, produto=None) -> forms.Field:
    """
    ✅ FUNÇÃO CORRIGIDA
    Cria o campo de formulário Django apropriado com base no 'tipo_campo'.
    Busca opções customizadas se o tipo for LISTA.
    """
    tipo = campo_obj.tipo_campo
    label = campo_obj.nome_campo
    
    # Classe CSS padrão
    attrs = {'class': 'form-control'}
    
    if tipo in ['LISTA_UNICA', 'LISTA_MULTIPLA']:
        try:
            opcoes_obj = OpcoesListaPersonalizada.objects.get(
                campo=campo_obj,
                cliente=cliente,
                produto=produto
            )
            opcoes = opcoes_obj.get_opcoes_como_lista()
            choices = [(opt.strip(), opt.strip()) for opt in opcoes]
        
        except OpcoesListaPersonalizada.DoesNotExist:
            choices = []
            help_text = (
                f"⚠️ Opções não configuradas! "
                f"Configure em: Admin > Opções de Lista > "
                f"Campo '{campo_obj.nome_campo}' + Cliente '{cliente.nome if cliente else '?'}' + "
                f"Produto '{produto.nome if produto else '?'}'"
            )
        else:
            help_text = None
        
        if tipo == 'LISTA_UNICA':
            return forms.ChoiceField(
                label=label,
                required=is_required,
                choices=[('', '--- Selecione ---')] + choices,
                widget=forms.Select(attrs={'class': 'form-select'}),
                help_text=help_text if not choices else None
            )
        
        else:  # LISTA_MULTIPLA
            return forms.MultipleChoiceField(
                label=label,
                required=is_required,
                choices=choices,
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                help_text=help_text if not choices else None
            )
    
    elif tipo == 'DATA':
        return forms.DateField(
            label=label,
            required=is_required,
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        )
    
    elif tipo == 'NUMERO_INT':
        return forms.IntegerField(
            label=label,
            required=is_required,
            widget=forms.NumberInput(attrs={'class': 'form-control'})
        )
    
    elif tipo == 'NUMERO_DEC' or tipo == 'MOEDA':
        return forms.DecimalField(
            label=label,
            required=is_required,
            decimal_places=2,
            widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        )
    
    elif tipo == 'LISTA_USUARIOS':
        return forms.ModelChoiceField(
            queryset=User.objects.all(),
            label=label,
            required=is_required,
            widget=forms.Select(attrs={'class': 'form-select'})
        )
    
    else: # TEXTO
        return forms.CharField(
            label=label,
            required=is_required,
            widget=forms.TextInput(attrs={'class': 'form-control'})
        )


# ==============================================================================
# FORMULÁRIO DINÂMICO DE CASO (COM A CORREÇÃO FINAL)
# ==============================================================================

class CasoDinamicoForm(forms.ModelForm):
    """
    Formulário principal para criar/editar um Caso,
    incluindo campos fixos e personalizados simples.
    """
    class Meta:
        model = Caso
        fields = ['data_entrada', 'valor_apurado','data_encerramento', 'status', 'advogado_responsavel']
        widgets = {
            'data_entrada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valor_apurado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
        }

 # /casos/forms.py -> Dentro da classe CasoDinamicoForm

    # ... (Sua classe Meta continua aqui, sem mudanças) ...

    # ==============================================================================
    # MÉTODO __init__ (COM A CORREÇÃO FINAL)
    # ==============================================================================
    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)

        # --- USA NOMES DE VARIÁVEIS INTERNAS (com underscore) ---
        self._campos_fixos_list = [self[field_name] for field_name in self.Meta.fields]
        self._campos_personalizados_simples_list = []
        self.campo_valor_apurado = None

        # Lógica para edição
        if self.instance and self.instance.pk:
            if not self.cliente: self.cliente = self.instance.cliente
            if not self.produto: self.produto = self.instance.produto

        if not self.cliente or not self.produto:
            return

        try:
            self.estrutura = EstruturaDeCampos.objects.prefetch_related(
                'ordenamentos_simples__campo'
            ).get(cliente=self.cliente, produto=self.produto)
        except EstruturaDeCampos.DoesNotExist:
            self.estrutura = None
            return

        # --- LÓGICA DE CRIAÇÃO E SEPARAÇÃO DOS CAMPOS ---
        for config_campo in self.estrutura.ordenamentos_simples.select_related('campo').order_by('order'):
            campo = config_campo.campo
            is_required = config_campo.obrigatorio
            field_name = f'campo_personalizado_{campo.id}'

            self.fields[field_name] = build_form_field(
                campo, is_required=is_required, cliente=self.cliente, produto=self.produto
            )

            if self.instance.pk:
                valor_salvo = self.instance.valores_personalizados.filter(
                    campo=campo, instancia_grupo__isnull=True
                ).first()
                if valor_salvo:
                    if campo.tipo_campo == 'LISTA_MULTIPLA' and valor_salvo.valor:
                        self.fields[field_name].initial = [v.strip() for v in valor_salvo.valor.split(',')]
                    else:
                        self.fields[field_name].initial = valor_salvo.valor
            
            bound_field = self[field_name]
            
            if campo.nome_variavel == 'valor_apurado':
                self.campo_valor_apurado = bound_field
            else:
                self._campos_personalizados_simples_list.append(bound_field)

        if not self.produto.padrao_titulo:
            self.fields['titulo_manual'] = forms.CharField(
                label="Título Manual do Caso", required=True,
                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o título do caso'})
            )

    # --- MÉTODOS AUXILIARES PARA O TEMPLATE (ATUALIZADOS) ---
    @property
    def campos_fixos(self):
        return self._campos_fixos_list

    @property
    def campos_personalizados_simples(self):
        return self._campos_personalizados_simples_list

    def grupos_repetiveis(self):
        if not hasattr(self, 'estrutura') or not self.estrutura:
            return []
        return self.estrutura.grupos_repetiveis.all()
    
    # Este método não é mais necessário, mas o mantemos por segurança
    def get_campo_por_variavel_name(self, nome_variavel):
        if nome_variavel == 'valor_apurado':
            return self.campo_valor_apurado
        return None   


# ==============================================================================
# FORMULÁRIO BASE PARA GRUPOS REPETÍVEIS (SEM MUDANÇAS)
# ==============================================================================

class BaseGrupoForm(forms.Form):
    def __init__(self, *args, grupo_campos=None, cliente=None, produto=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['ORDER'] = forms.IntegerField(
            required=False,
            widget=HiddenInput(),
            initial=0
        )

        if not grupo_campos:
            return

        campos_ordenados = grupo_campos.ordenamentos_grupo.select_related('campo').order_by('order')

        for config in campos_ordenados:
            campo = config.campo
            field_name = f'campo_personalizado_{campo.id}'

            self.fields[field_name] = build_form_field(
                campo,
                is_required=False,
                cliente=cliente,
                produto=produto
            )

    class Meta:
        exclude = ['ORDER']


# ==============================================================================
# FORMULÁRIO DE VALOR (SEM MUDANÇAS)
# ==============================================================================

class ValorCampoPersonalizadoForm(forms.ModelForm):
    class Meta:
        model = ValorCampoPersonalizado
        fields = ['valor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.campo:
            campo = self.instance.campo
            self.fields['valor'] = build_form_field(
                campo,
                is_required=False,
                cliente=self.instance.caso.cliente if self.instance.caso else None,
                produto=self.instance.caso.produto if self.instance.caso else None
            )


# ==============================================================================
# OUTROS FORMULÁRIOS (SEM MUDANÇAS)
# ==============================================================================

class AndamentoForm(forms.ModelForm):
    class Meta:
        model = Andamento
        fields = ['data_andamento', 'descricao']
        widgets = {
            'data_andamento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class TimesheetForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        # 1. Remove o argumento 'user' dos kwargs antes de chamar o pai
        user = kwargs.pop('user', None)
        # 2. Chama o construtor original da classe pai
        super().__init__(*args, **kwargs)
        # 3. Agora, usa o objeto 'user' para customizar o formulário
        if user:
            # Define o usuário logado como o valor inicial do campo 'advogado'
            self.fields['advogado'].initial = user
            # Limita as opções do dropdown para ser apenas o usuário logado
            self.fields['advogado'].queryset = User.objects.filter(id=user.id)
    class Meta:
        # APONTA PARA O MODELO 'Timesheet' IMPORTADO
        model = Timesheet
        # DEFINE OS CAMPOS DO FORMULÁRIO
        fields = ['data_execucao', 'advogado', 'tempo', 'descricao']
        # DEFINE OS WIDGETS PARA CADA CAMPO
        widgets = {
            'data_execucao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'advogado': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            
            # AQUI ESTÁ A MUDANÇA PRINCIPAL: USA UM CAMPO DE TEXTO
            'tempo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM',
                'pattern': r'\d{1,2}:\d{2}', # Validação básica no HTML5
                'title': 'Use o formato HH:MM (ex: 01:30 para 1h e 30min)'
            })
        }

    # MÉTODO DE VALIDAÇÃO PARA CONVERTER 'HH:MM' EM UM VALOR VÁLIDO
    def clean_tempo_gasto(self):
        tempo_str = self.cleaned_data.get('tempo')
        
        if not tempo_str:
            # Se o campo não for obrigatório e estiver vazio, não faz nada
            return None

        # Regex para validar o formato HH:MM (horas e minutos)
        if not re.match(r'^\d{1,2}:\d{2}$', tempo_str):
            raise forms.ValidationError("Formato inválido. Use HH:MM (ex: 02:45).")
            
        try:
            horas, minutos = map(int, tempo_str.split(':'))
            if minutos >= 60:
                raise forms.ValidationError("Os minutos não podem ser 60 ou mais.")
            
            # Assumindo que seu modelo `Timesheet` tem um campo `tempo_gasto`
            # do tipo `DurationField`, que é o ideal para armazenar durações.
            return timedelta(hours=horas, minutes=minutos)
            
            # --- Alternativa ---
            # Se seu modelo armazena o tempo em minutos (IntegerField):
            # return (horas * 60) + minutos

        except (ValueError, TypeError):
            raise forms.ValidationError("Valores inválidos para horas ou minutos.")

class AcordoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['advogado_acordo'].initial = user
            self.fields['advogado_acordo'].queryset = User.objects.filter(id=user.id)

    class Meta:
        model = Acordo
        fields = ['valor_total', 'numero_parcelas', 'data_primeira_parcela', 'advogado_acordo']
        widgets = {
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'numero_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'data_primeira_parcela': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'advogado_acordo': forms.Select(attrs={'class': 'form-select'}),
        }


class DespesaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['advogado'].initial = user
            self.fields['advogado'].queryset = User.objects.filter(id=user.id)

    class Meta:
        model = Despesa
        fields = ['data_despesa', 'descricao', 'valor', 'advogado']
        widgets = {
            'data_despesa': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'advogado': forms.Select(attrs={'class': 'form-select'}),
        }