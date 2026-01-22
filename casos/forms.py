# casos/forms.py

from django import forms
from django.forms import formset_factory, modelformset_factory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms.widgets import HiddenInput
from datetime import timedelta
import re

from django.db.models import Q
from django.db.models.functions import Lower

# Importa os modelos de campos customizados
from campos_custom.models import (
    EstruturaDeCampos, 
    GrupoCampos, 
    CampoPersonalizado,
    InstanciaGrupoValor,
    ValorCampoPersonalizado,
    OpcoesListaPersonalizada
)

from .models import (
    Caso, Andamento, Timesheet, Acordo, Despesa, 
    Tomador, ConfiguracaoTomador, Segurado 
)
from clientes.models import Cliente
from produtos.models import Produto

User = get_user_model()

# ==============================================================================
# FUNÇÃO AUXILIAR: CONSTRUTOR DE CAMPOS (ATUALIZADA)
# ==============================================================================
def build_form_field(campo_obj: CampoPersonalizado, is_required=False, cliente=None, produto=None) -> forms.Field:
    """
    Cria o campo de formulário Django apropriado com base no 'tipo_campo'.
    Injeta máscaras e classes especiais (money, custom-mask) conforme configuração.
    """
    tipo = campo_obj.tipo_campo
    label = campo_obj.nome_campo
    
    # Atributos base
    attrs = {'class': 'form-control'}
    
    # INJEÇÃO DE MÁSCARA (Vem do models.CampoPersonalizado)
    if campo_obj.mascara:
        attrs['data-mask'] = campo_obj.mascara
        attrs['class'] += ' custom-mask'
        attrs['placeholder'] = campo_obj.mascara

    # LÓGICA POR TIPO
    if tipo in ['LISTA_UNICA', 'LISTA_MULTIPLA']:
        try:
            opcoes_obj = OpcoesListaPersonalizada.objects.get(
                campo=campo_obj, cliente=cliente, produto=produto
            )
            opcoes = opcoes_obj.get_opcoes_como_lista()
            opcoes = sorted(opcoes, key=lambda opt: opt.strip().casefold())
            choices = [(opt.strip(), opt.strip()) for opt in opcoes]
        except OpcoesListaPersonalizada.DoesNotExist:
            choices = []
            help_text = f"⚠️ Opções não configuradas para '{label}'"
        else:
            help_text = None
        
        if tipo == 'LISTA_UNICA':
            return forms.ChoiceField(
                label=label, required=is_required,
                choices=[('', '--- Selecione ---')] + choices,
                widget=forms.Select(attrs={'class': 'form-select'}),
                help_text=help_text if not choices else None
            )
        else:  # LISTA_MULTIPLA
            return forms.MultipleChoiceField(
                label=label, required=is_required, choices=choices,
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                help_text=help_text if not choices else None
            )
    
    elif tipo == 'DATA':
        attrs.update({'type': 'date'})
        return forms.DateField(label=label, required=is_required, widget=forms.DateInput(attrs=attrs))

    elif tipo == 'NUMERO_INT':
        return forms.IntegerField(label=label, required=is_required, widget=forms.NumberInput(attrs=attrs))

    elif tipo == 'NUMERO_DEC' or tipo == 'MOEDA':
            if tipo == 'MOEDA':
                attrs['class'] += ' money'
            # SEMPRE usar TextInput para campos com máscara de moeda
            return forms.DecimalField(
                label=label, required=is_required, decimal_places=2, 
                widget=forms.TextInput(attrs=attrs) 
            )
    

    elif tipo == 'LISTA_USUARIOS':
        return forms.ModelChoiceField(
            queryset=User.objects.all().order_by('first_name', 'username'),
            label=label, required=is_required,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

    elif tipo == 'BOOLEANO':
        choices = [('True', 'Sim'), ('False', 'Não')]
        if not is_required:
            choices = [('', '---')] + choices
        return forms.ChoiceField(
            label=label,
            required=is_required,
            choices=choices,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

    elif tipo == 'TEXTO_LONGO':
        attrs.update({'rows': 3})
        return forms.CharField(label=label, required=is_required, widget=forms.Textarea(attrs=attrs))

    else: # TEXTO CURTO
        return forms.CharField(label=label, required=is_required, widget=forms.TextInput(attrs=attrs))


# ==============================================================================
# FORMULÁRIO DO TOMADOR
# ==============================================================================
class TomadorForm(forms.ModelForm):
    class Meta:
        model = Tomador
        fields = ['nome', 'tipo', 'cpf', 'cnpj']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control custom-mask', 'placeholder': '000.000.000-00', 'data-mask': '000.000.000-00'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control custom-mask', 'placeholder': '00.000.000/0000-00', 'data-mask': '00.000.000/0000-00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# ==============================================================================
# FORMULARIO DO SEGURADO
class SeguradoForm(forms.ModelForm):
    class Meta:
        model = Segurado
        fields = ['nome', 'tipo', 'cpf', 'cnpj']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control custom-mask', 'placeholder': '000.000.000-00', 'data-mask': '000.000.000-00'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control custom-mask', 'placeholder': '00.000.000/0000-00', 'data-mask': '00.000.000/0000-00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# FORMULÁRIO DINÂMICO DE CASO
# ==============================================================================
class CasoDinamicoForm(forms.ModelForm):
    class Meta:
        model = Caso
        fields = ['data_entrada', 'valor_apurado', 'data_encerramento', 'status', 'advogado_responsavel', 'segurado', 'tomador']
        widgets = {
            'data_entrada': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valor_apurado': forms.TextInput(attrs={
                'class': 'form-control js-moeda money',
                'inputmode': 'decimal',
                'placeholder': 'R$ 0,00'
            }),
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
            'segurado': forms.Select(attrs={'class': 'form-select select2-segurado'}),
            'tomador': forms.Select(attrs={'class': 'form-select select2-tomador'}),
        }

    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)
        
        # --- CAMPOS FIXOS ---
        self._campos_fixos_list = [self[field_name] for field_name in self.Meta.fields if field_name in self.fields]
        self._campos_personalizados_simples_list = []
        self.campo_valor_apurado = None

        # --- LÓGICA DINÂMICA DO TOMADOR ---
        mostrar_tomador = False
        if self.produto:
            regras = ConfiguracaoTomador.objects.filter(
                produto=self.produto, habilitar_tomador=True
            ).filter(Q(cliente=self.cliente) | Q(cliente__isnull=True))
            if regras.exists():
                mostrar_tomador = True

        if mostrar_tomador:
            self.fields['tomador'].queryset = Tomador.objects.all().order_by(Lower('nome'))
            self.fields['tomador'].widget.attrs.update({'class': 'form-select select2-tomador'})
            # Evita problemas de cursor ao renderizar choices em algumas bases
            self.fields['tomador'].choices = list(self.fields['tomador'].choices)
        
        if 'advogado_responsavel' in self.fields:
            self.fields['advogado_responsavel'].queryset = User.objects.all().order_by('first_name', 'username')
            self.fields['advogado_responsavel'].label_from_instance = (
                lambda u: u.get_full_name() or u.username
            )
        else:
            if 'tomador' in self.fields:
                del self.fields['tomador']
                self._campos_fixos_list = [f for f in self._campos_fixos_list if f.name != 'tomador']

        if 'segurado' in self.fields:
            self.fields['segurado'].queryset = Segurado.objects.all().order_by('nome')
            self.fields['segurado'].widget.attrs.update({'class': 'form-select select2-segurado'})
            self.fields['segurado'].choices = list(self.fields['segurado'].choices)

        # --- CARREGAMENTO DE ESTRUTURA ---
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

        # --- CAMPOS PERSONALIZADOS SIMPLES ---
        for config_campo in self.estrutura.ordenamentos_simples.select_related('campo').order_by('order'):
            campo = config_campo.campo
            is_required = config_campo.obrigatorio
            field_name = f'campo_personalizado_{campo.id}'

            self.fields[field_name] = build_form_field(
                campo, is_required=is_required, cliente=self.cliente, produto=self.produto
            )

            # Preencher valor se for edição
            if self.instance.pk:
                valor_salvo = self.instance.valores_personalizados.filter(
                    campo=campo, instancia_grupo__isnull=True
                ).first()
                if valor_salvo:
                    if campo.tipo_campo == 'LISTA_MULTIPLA' and valor_salvo.valor:
                        self.fields[field_name].initial = [v.strip() for v in valor_salvo.valor.split(',')]
                    elif campo.tipo_campo == 'BOOLEANO':
                        self.fields[field_name].initial = 'True' if str(valor_salvo.valor) == 'True' else 'False'
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

    @property
    def campos_fixos(self): return self._campos_fixos_list

    @property
    def campos_personalizados_simples(self): return self._campos_personalizados_simples_list

    def grupos_repetiveis(self):
        return self.estrutura.grupos_repetiveis.all() if hasattr(self, 'estrutura') and self.estrutura else []


# ==============================================================================
# FORMULÁRIO BASE PARA GRUPOS REPETÍVEIS (FORMSETS)
# ==============================================================================
class BaseGrupoForm(forms.Form):
    def __init__(self, *args, grupo_campos=None, cliente=None, produto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ORDER'] = forms.IntegerField(required=False, widget=HiddenInput(), initial=0)

        if not grupo_campos: return

        campos_ordenados = grupo_campos.ordenamentos_grupo.select_related('campo').order_by('order')
        for config in campos_ordenados:
            campo = config.campo
            field_name = f'campo_personalizado_{campo.id}'
            self.fields[field_name] = build_form_field(
                campo, is_required=False, cliente=cliente, produto=produto
            )


# ==============================================================================
# DADOS ADICIONAIS (MODAL DE EDIÇÃO NO DETALHE)
# ==============================================================================
class CasoDadosAdicionaisForm(forms.Form):
    def __init__(self, *args, **kwargs):
        campos_personalizados = kwargs.pop('campos_personalizados', [])
        super().__init__(*args, **kwargs)

        for valor in campos_personalizados:
            campo = valor.campo
            field_name = f'campo_{campo.id}'
            
            # Reutiliza o construtor para garantir que máscaras e tipos (Texto Longo) funcionem aqui também
            self.fields[field_name] = build_form_field(
                campo, is_required=False, 
                cliente=valor.caso.cliente if valor.caso else None,
                produto=valor.caso.produto if valor.caso else None
            )
            
            # Define o valor inicial
            if campo.tipo_campo == 'BOOLEANO':
                self.fields[field_name].initial = 'True' if str(valor.valor) == 'True' else 'False'
            elif campo.tipo_campo == 'LISTA_MULTIPLA' and valor.valor:
                self.fields[field_name].initial = [v.strip() for v in valor.valor.split(',')]
            else:
                self.fields[field_name].initial = valor.valor


# ==============================================================================
# OUTROS FORMULÁRIOS (PADRÃO)
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
        if 'advogado' in self.fields:
            self.fields['advogado'].queryset = User.objects.all().order_by('first_name', 'username')
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
            'tempo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM'})
        }

class AcordoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if 'advogado_acordo' in self.fields:
            self.fields['advogado_acordo'].queryset = User.objects.all().order_by('first_name', 'username')
        if user:
            self.fields['advogado_acordo'].initial = user
            self.fields['advogado_acordo'].queryset = User.objects.filter(id=user.id)
    class Meta:
        model = Acordo
        fields = ['valor_total', 'numero_parcelas', 'data_primeira_parcela', 'advogado_acordo']
        widgets = {
            'valor_total': forms.TextInput(attrs={'class': 'form-control money'}),
            'numero_parcelas': forms.NumberInput(attrs={'class': 'form-control'}),
            'data_primeira_parcela': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'advogado_acordo': forms.Select(attrs={'class': 'form-select'}),
        }

class DespesaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if 'advogado' in self.fields:
            self.fields['advogado'].queryset = User.objects.all().order_by('first_name', 'username')
        if user:
            self.fields['advogado'].initial = user
            self.fields['advogado'].queryset = User.objects.filter(id=user.id)
    class Meta:
        model = Despesa
        fields = ['data_despesa', 'descricao', 'valor', 'advogado']
        widgets = {
            'data_despesa': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.TextInput(attrs={'class': 'form-control money'}),
            'advogado': forms.Select(attrs={'class': 'form-select'}),
        }

class CasoInfoBasicasForm(forms.ModelForm):
    class Meta:
        model = Caso
        fields = ['status', 'data_entrada', 'valor_apurado', 'advogado_responsavel']
        widgets = {
            'data_entrada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_apurado': forms.TextInput(attrs={
                'class': 'form-control js-moeda money',
                'inputmode': 'decimal',
                'placeholder': 'R$ 0,00'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'advogado_responsavel' in self.fields:
            self.fields['advogado_responsavel'].queryset = User.objects.all().order_by('first_name', 'username')
            self.fields['advogado_responsavel'].label_from_instance = (
                lambda u: u.get_full_name() or u.username
            )

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        cpf = cleaned.get('cpf')
        cnpj = cleaned.get('cnpj')

        if tipo == 'PF':
            if not cpf:
                self.add_error('cpf', 'CPF é obrigatório para pessoa física.')
            cleaned['cnpj'] = None
        elif tipo == 'PJ':
            if not cnpj:
                self.add_error('cnpj', 'CNPJ é obrigatório para pessoa jurídica.')
            cleaned['cpf'] = None
        return cleaned
        for field_name, field in self.fields.items():
            existing_classes = field.widget.attrs.get('class', '').strip()
            if not existing_classes:
                field.widget.attrs['class'] = 'form-control'




