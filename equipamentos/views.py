# equipamentos/views.py

from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Equipamento
from .forms import EquipamentoForm

# 1. View para LISTAR todos os equipamentos
class EquipamentoListView(LoginRequiredMixin, ListView):
    model = Equipamento
    template_name = 'equipamentos/equipamento_list.html'
    context_object_name = 'equipamentos'
    paginate_by = 15  # Mostra 15 equipamentos por página

# 2. View para ver os DETALHES de um equipamento
class EquipamentoDetailView(LoginRequiredMixin, DetailView):
    model = Equipamento
    template_name = 'equipamentos/equipamento_detail.html'
    context_object_name = 'equipamento'

# 3. View para ADICIONAR um novo equipamento
class EquipamentoCreateView(LoginRequiredMixin, CreateView):
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'equipamentos/equipamento_form.html'
    success_url = reverse_lazy('equipamentos:equipamento_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Adicionar Novo Equipamento'
        return context

# 4. View para EDITAR um equipamento existente
class EquipamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = Equipamento
    form_class = EquipamentoForm
    template_name = 'equipamentos/equipamento_form.html'
    success_url = reverse_lazy('equipamentos:equipamento_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Equipamento'
        return context