from django.shortcuts import render

# Create your views here.
# campos_custom/views.py

from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import ConfiguracaoEmMassaForm

class AdicionarCamposEmMassaView(LoginRequiredMixin, FormView):
    template_name = 'campos_custom/configuracao_em_massa_form.html'
    form_class = ConfiguracaoEmMassaForm
    success_url = reverse_lazy('campos_custom:configuracao_em_massa') # Volta para a mesma página

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Campos configurados com sucesso para o cliente e produto selecionados!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Configurador de Campos em Massa'
        return context