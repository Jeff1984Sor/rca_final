# campos_custom/urls.py

from django.urls import path
# A linha abaixo está quebrando
# from .views import AdicionarCamposEmMassaView

app_name = 'campos_custom'

urlpatterns = [
    # A linha abaixo também está quebrando
    # path('adicionar-em-massa/', AdicionarCamposEmMassaView.as_view(), name='adicionar_em_massa'),
]