# casos/forms.py
from django import forms
from .models import Caso
from campos_custom.models import CampoPersonalizado

# ... (seu CasoForm existente, se houver) ...

# NOVO FORMULÁRIO DINÂMICO
class CasoDinamicoForm(forms.Form):
    # Campos Padrão que sempre estarão aqui
    data_entrada = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    status = forms.ChoiceField(choices=Caso.STATUS_CHOICES, required=True)
    data_encerramento = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    titulo_manual = forms.CharField(max_length=255, required=False)
    
    def __init__(self, *args, **kwargs):
        # Pega o produto que passaremos da view
        produto = kwargs.pop('produto', None)
        super().__init__(*args, **kwargs)

        if produto:
            # Busca os campos personalizados para este produto
            campos_personalizados = CampoPersonalizado.objects.filter(produto=produto).order_by('ordem')
            
            # Adiciona dinamicamente os campos ao formulário
            for campo in campos_personalizados:
                field_name = f'campo_personalizado_{campo.id}'
                field_label = campo.nome_campo
                field_required = campo.obrigatorio

                if campo.tipo_campo == 'TEXTO':
                    self.fields[field_name] = forms.CharField(label=field_label, required=field_required)
                elif campo.tipo_campo == 'NUMERO_INT':
                    self.fields[field_name] = forms.IntegerField(label=field_label, required=field_required)
                elif campo.tipo_campo == 'DATA':
                    self.fields[field_name] = forms.DateField(label=field_label, required=field_required, widget=forms.DateInput(attrs={'type': 'date'}))
                elif campo.tipo_campo == 'LISTA_UNICA':
                    opcoes = [(opt, opt) for opt in campo.get_opcoes_como_lista]
                    self.fields[field_name] = forms.ChoiceField(label=field_label, required=field_required, choices=opcoes)