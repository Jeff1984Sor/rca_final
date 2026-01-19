# casos/forms.py

from django import forms
from django.forms import formset_factory, modelformset_factory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms.widgets import HiddenInput
from datetime import timedelta
import re

# --- IMPORTANTE: ADICIONE O 'Q' AQUI ---
from django.db.models import Q 

# Importa os modelos de campos customizados
from campos_custom.models import (
    EstruturaDeCampos, 
    GrupoCampos, 
    CampoPersonalizado,
    InstanciaGrupoValor,
    ValorCampoPersonalizado,
    OpcoesListaPersonalizada
)

# --- IMPORTANTE: ADICIONE 'ConfiguracaoTomador' AQUI ---
from .models import (
    Caso, Andamento, Timesheet, Acordo, Despesa, 
    Tomador, ConfiguracaoTomador 
)
from clientes.models import Cliente
from produtos.models import Produto

User = get_user_model()

# ==============================================================================
# FUNÇÃO AUXILIAR
# ==============================================================================
def build_form_field(campo_obj: CampoPersonalizado, is_required=False, cliente=None, produto=None) -> forms.Field:
    """
    Cria o campo de formulário Django apropriado com base no 'tipo_campo'.
    Busca opções customizadas se o tipo for LISTA.
    """
    tipo = campo_obj.tipo_campo
    label = campo_obj.nome_campo
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
            help_text = f"⚠️ Opções não configuradas para '{label}'"
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
            label=label, required=is_required, widget=forms.NumberInput(attrs={'class': 'form-control'})
        )
    elif tipo == 'NUMERO_DEC' or tipo == 'MOEDA':
        return forms.DecimalField(
            label=label, required=is_required, decimal_places=2, 
            widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        )
    elif tipo == 'LISTA_USUARIOS':
        return forms.ModelChoiceField(
            queryset=User.objects.all(), label=label, required=is_required, 
            widget=forms.Select(attrs={'class': 'form-select'})
        )
    elif tipo == 'BOOLEANO':
        return forms.BooleanField(
            label=label, required=False, 
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
        )
    else: # TEXTO e TEXTO_LONGO
        widget = forms.Textarea(attrs={'class': 'form-control', 'rows': 3}) if tipo == 'TEXTO_LONGO' else forms.TextInput(attrs={'class': 'form-control'})
        return forms.CharField(label=label, required=is_required, widget=widget)


# ==============================================================================
# FORMULÁRIO DO TOMADOR
# ==============================================================================
class TomadorForm(forms.ModelForm):
    class Meta:
        model = Tomador
        fields = ['nome', 'cpf_cnpj'] # Liste aqui os campos do Model Tomador
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000.000.000-00'}),
        }

    # Se você tiver um __init__ personalizado, lembre-se de manter o super()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O Django UpdateView passa a 'instance' aqui automaticamente.
        # Se este método estiver sobrescrevendo os dados sem chamar o super,
        # os campos virão vazios.


# ==============================================================================
# FORMULÁRIO DINÂMICO DE CASO
# ==============================================================================
class CasoDinamicoForm(forms.ModelForm):
    """
    Formulário principal para criar/editar um Caso,
    incluindo campos fixos e personalizados simples.
    """
    class Meta:
        model = Caso
        fields = ['data_entrada', 'valor_apurado', 'data_encerramento', 'status', 'advogado_responsavel', 'tomador']
        widgets = {
            'data_entrada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valor_apurado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
            'tomador': forms.Select(attrs={'class': 'form-select select2-tomador'}),
        }

    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)

        # --- USA NOMES DE VARIÁVEIS INTERNAS (com underscore) ---
        # Filtra apenas campos que realmente existem no form final
        self._campos_fixos_list = [self[field_name] for field_name in self.Meta.fields if field_name in self.fields]
        self._campos_personalizados_simples_list = []
        self.campo_valor_apurado = None

        # =========================================================
        # LÓGICA DINÂMICA DO TOMADOR (VIA BANCO DE DADOS)
        # =========================================================
        mostrar_tomador = False

        if self.produto:
            # Busca regras no banco
            # 1. Regra específica para este cliente
            # 2. OU Regra geral (cliente vazio)
            regras = ConfiguracaoTomador.objects.filter(
                produto=self.produto,
                habilitar_tomador=True
            ).filter(
                Q(cliente=self.cliente) | Q(cliente__isnull=True)
            )
            
            # Se encontrar qualquer regra, habilita
            if regras.exists():
                mostrar_tomador = True

        if mostrar_tomador:
            # MOSTRA O CAMPO
            self.fields['tomador'].queryset = Tomador.objects.all().order_by('nome')
            self.fields['tomador'].widget.attrs.update({'class': 'form-select select2-tomador'})
        else:
            # ESCONDE O CAMPO
            if 'tomador' in self.fields:
                del self.fields['tomador']
                # Remove também da lista de renderização visual
                self._campos_fixos_list = [f for f in self._campos_fixos_list if f.name != 'tomador']

        # =========================================================

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
                    elif campo.tipo_campo == 'BOOLEANO':
                        self.fields[field_name].initial = (valor_salvo.valor == 'True')
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

    # --- MÉTODOS AUXILIARES PARA O TEMPLATE ---
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
    
    def get_campo_por_variavel_name(self, nome_variavel):
        if nome_variavel == 'valor_apurado':
            return self.campo_valor_apurado
        return None   


# ==============================================================================
# FORMULÁRIO BASE PARA GRUPOS REPETÍVEIS
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
# FORMULÁRIO DE VALOR
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
# OUTROS FORMULÁRIOS
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
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['advogado'].initial = user
            self.fields['advogado'].queryset = User.objects.filter(id=user.id)
    class Meta:
        model = Timesheet
        fields = ['data_execucao', 'advogado', 'tempo', 'descricao']
        widgets = {
            'data_execucao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'advogado': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'tempo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM',
                'pattern': r'\d{1,2}:\d{2}',
                'title': 'Use o formato HH:MM (ex: 01:30 para 1h e 30min)'
            })
        }

    def clean_tempo(self):
        tempo_str = self.cleaned_data.get('tempo')
        if not tempo_str:
            return None
        if not re.match(r'^\d{1,2}:\d{2}$', tempo_str):
            raise forms.ValidationError("Formato inválido. Use HH:MM (ex: 02:45).")
        try:
            horas, minutos = map(int, tempo_str.split(':'))
            if minutos >= 60:
                raise forms.ValidationError("Os minutos não podem ser 60 ou mais.")
            return timedelta(hours=horas, minutes=minutos)
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

class CasoInfoBasicasForm(forms.ModelForm):
    class Meta:
        model = Caso
        fields = ['status', 'data_entrada', 'valor_apurado', 'advogado_responsavel']
        widgets = {
            'data_entrada': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            
class CasoDadosAdicionaisForm(forms.Form):
    def __init__(self, *args, **kwargs):
        campos_personalizados = kwargs.pop('campos_personalizados', [])
        super().__init__(*args, **kwargs)

        for valor in campos_personalizados:
            campo = valor.campo
            field_name = f'campo_{campo.id}'
            
            if campo.tipo_campo == 'TEXTO_LONGO':
                self.fields[field_name] = forms.CharField(label=campo.nome_campo, required=False, initial=valor.valor, widget=forms.Textarea(attrs={'rows': 3}))
            elif campo.tipo_campo == 'DATA':
                self.fields[field_name] = forms.DateField(label=campo.nome_campo, required=False, initial=valor.valor, widget=forms.DateInput(attrs={'type': 'date'}))
            elif campo.tipo_campo == 'BOOLEANO':
                self.fields[field_name] = forms.BooleanField(label=campo.nome_campo, required=False, initial=(valor.valor == 'True'))
            else:
                self.fields[field_name] = forms.CharField(label=campo.nome_campo, required=False, initial=valor.valor)
        
        for field_name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')