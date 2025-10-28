# campos_custom/forms.py

from django import forms
# Importa apenas os modelos que ainda existem
from .models import CampoPersonalizado 
# from .models import CampoPersonalizado, ConfiguracaoCampoPersonalizado # <-- LINHA ANTIGA E QUEBRADA

# O formulário abaixo dependia do modelo 'ConfiguracaoCampoPersonalizado'
# que foi removido. Vamos comentá-lo ou removê-lo.
#
# class ConfiguracaoEmMassaForm(forms.Form):
#     # ... (código antigo do seu formulário) ...
#     pass