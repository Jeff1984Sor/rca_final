# equipamentos/forms.py

from django import forms
from .models import Equipamento, Marca, TipoItem, CategoriaItem, StatusItem

class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        
        # Lista todos os campos do seu novo modelo que você quer que apareçam no formulário
        fields = [
            'nome_item',
            'tipo_item',
            'categoria_item',
            'marca',
            'modelo',
            'etiqueta_servico_dell',
            'hostname',
            'data_compra',
            'loja_compra',
            'valor_pago',
            'pago_por',
            'responsavel',
            'telefone_usuario',
            'anydesk',
            'status',
        ]
        
        # (Opcional) Adiciona widgets para melhorar a experiência do usuário
        widgets = {
            'data_compra': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Deixa todos os campos como não-obrigatórios, como no modelo
        for field in self.fields.values():
            field.required = False