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
    # Este é o campo mágico: permite selecionar vários campos
    campos = forms.ModelMultipleChoiceField(
        queryset=CampoPersonalizado.objects.all().order_by('nome_campo'),
        widget=forms.CheckboxSelectMultiple, # Mostra como checkboxes, fácil de selecionar
        label="Selecione os Campos da Biblioteca",
        required=True
    )

    def save(self):
        cliente = self.cleaned_data['cliente']
        produto = self.cleaned_data['produto']
        campos_selecionados = self.cleaned_data['campos']

        # Loop para criar cada configuração
        for campo in campos_selecionados:
            # `get_or_create` é seguro e evita criar duplicatas se a regra já existir
            ConfiguracaoCampoPersonalizado.objects.get_or_create(
                cliente=cliente,
                produto=produto,
                campo=campo,
                defaults={'ordem': 0} # Você pode definir uma ordem padrão
            )