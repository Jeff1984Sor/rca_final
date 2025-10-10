# clientes/forms.py
from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # Lista de campos do seu modelo que devem aparecer no formulário
        fields = [
            'nome', 'tipo', 'contato_empresa', 'logradouro', 'numero',
            'complemento', 'bairro', 'cidade', 'uf'
        ]