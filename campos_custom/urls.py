from django.urls import path
from .views import AdicionarCamposEmMassaView

app_name = 'campos_custom'

urlpatterns = [    
    path('configurador-em-massa/', AdicionarCamposEmMassaView.as_view(), name='configuracao_em_massa'),
]