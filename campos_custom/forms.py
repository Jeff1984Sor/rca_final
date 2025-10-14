# campos_custom/forms.py

from django import forms
from .models import CampoPersonalizado, ConfiguracaoCampoPersonalizado
from clientes.models import Cliente
from produtos.models import Produto

class ConfiguracaoEmMassaForm(forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Cliente"
    )
    produto = forms.ModelChoiceField(
        queryset=Produto.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Produto"
    )
    campos = forms.ModelMultipleChoiceField(
        queryset=CampoPersonalizado.objects.all().order_by('nome_campo'),
        widget=forms.CheckboxSelectMultiple,
        label="Selecione os Campos da Biblioteca",
        required=True
    )

    def save(self):
        cliente = self.cleaned_data['cliente']
        produto = self.cleaned_data['produto']
        campos_selecionados = self.cleaned_data['campos']

        for campo in campos_selecionados:
            ConfiguracaoCampoPersonalizado.objects.get_or_create(
                cliente=cliente,
                produto=produto,
                campo=campo,
                defaults={'ordem': 0}
            )