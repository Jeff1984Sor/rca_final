from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Equipamento
from .forms import EquipamentoForm
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Equipamento

# Imports necessários para a API funcionar
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# 1. View para LISTAR todos os equipamentos
class EquipamentoListView(LoginRequiredMixin, ListView):
    model = Equipamento
    template_name = 'equipamentos/equipamento_list.html'
    context_object_name = 'equipamentos'
    paginate_by = 15

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


# ==============================================================================
# API DE AUDITORIA (Fora das classes)
# ==============================================================================

@csrf_exempt 
def api_atualizar_hardware(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            serial = dados.get('serial_number')
            
            if not serial:
                return JsonResponse({'status': 'erro', 'mensagem': 'Serial não informado'}, status=400)

            # Tenta encontrar o equipamento pela Etiqueta Dell (S/N)
            try:
                equip = Equipamento.objects.get(etiqueta_servico_dell__iexact=serial)
            except Equipamento.DoesNotExist:
                # Se não achar por serial, tenta pelo Hostname
                try:
                    equip = Equipamento.objects.get(hostname__iexact=dados.get('hostname'))
                except Equipamento.DoesNotExist:
                    # Se não achar nada, cria um novo
                    equip = Equipamento(
                        nome_item=f"Novo PC - {dados.get('hostname')}",
                        etiqueta_servico_dell=serial
                    )

            # Atualiza os dados técnicos
            equip.hostname = dados.get('hostname')
            equip.sistema_operacional = dados.get('os')
            equip.processador = dados.get('cpu')
            equip.memoria_ram = dados.get('ram')
            equip.espaco_disco = dados.get('disk')
            equip.softwares_instalados = dados.get('softwares')
            
            # Salva no banco de dados
            equip.save()

            return JsonResponse({'status': 'sucesso', 'id': equip.id, 'msg': 'Dados atualizados!'})

        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)
    
    return JsonResponse({'status': 'erro', 'mensagem': 'Método não permitido'}, status=405)


@csrf_exempt # Permite que o script envie dados sem token de segurança web
def api_receber_dados(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            serial = dados.get('serial_number')
            hostname = dados.get('hostname')

            # Lógica: Procura pelo Serial Dell. Se não achar, procura pelo Hostname.
            # Se não achar nenhum, cria um novo.
            equipamento = None
            
            if serial:
                equipamento = Equipamento.objects.filter(etiqueta_servico_dell=serial).first()
            
            if not equipamento and hostname:
                equipamento = Equipamento.objects.filter(hostname=hostname).first()

            if not equipamento:
                equipamento = Equipamento(nome_item=f"PC {hostname}")

            # Atualiza os dados
            equipamento.etiqueta_servico_dell = serial
            equipamento.hostname = hostname
            equipamento.sistema_operacional = dados.get('os')
            equipamento.processador = dados.get('cpu')
            equipamento.memoria_ram = dados.get('ram')
            equipamento.espaco_disco = dados.get('disk')
            equipamento.softwares_instalados = dados.get('softwares')
            
            equipamento.save()
            
            return JsonResponse({'status': 'ok', 'msg': 'Atualizado com sucesso'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'msg': str(e)}, status=500)
    return JsonResponse({'status': 'erro'}, status=400)