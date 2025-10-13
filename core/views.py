from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from datetime import datetime, date
from django.contrib.auth import get_user_model

# Importações de modelos dos seus apps
from casos.models import Caso
from produtos.models import Produto
from clientes.models import Cliente
from workflow.models import InstanciaAcao

from decimal import Decimal

# Importação do formulário de login
from .forms import CustomAuthenticationForm

User = get_user_model()

@login_required
def home(request):
    # --- 1. FILTRO DE ANO ---
    ano_selecionado = int(request.GET.get('ano', datetime.today().year))
    anos_disponiveis = range(datetime.today().year - 5, datetime.today().year + 2)
    meses_nomes_completos = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    # --- 2. PREPARAÇÃO ---
    todos_produtos_nomes = list(Produto.objects.all().order_by('nome').values_list('nome', flat=True))

    # --- 3. LÓGICA PARA TABELA DE CASOS ABERTOS ---
    casos_abertos_ano = Caso.objects.filter(data_entrada__year=ano_selecionado)
    dados_abertos_agrupados = casos_abertos_ano.values('data_entrada__month', 'cliente__nome', 'produto__nome').annotate(total=Count('id'))
    
    dados_pivot_abertos = {}
    clientes_abertos = sorted(list(casos_abertos_ano.values_list('cliente__nome', flat=True).distinct()))
    
    for cliente in clientes_abertos:
        dados_pivot_abertos[cliente] = {p_nome: {'meses': [0]*12, 'total_ano': 0} for p_nome in todos_produtos_nomes}

    for item in dados_abertos_agrupados:
        cliente, produto, mes, total = item['cliente__nome'], item['produto__nome'], item['data_entrada__month'], item['total']
        if cliente in dados_pivot_abertos and produto in dados_pivot_abertos[cliente]:
            dados_pivot_abertos[cliente][produto]['meses'][mes - 1] = total

    for cliente_data in dados_pivot_abertos.values():
        for produto_data in cliente_data.values():
            produto_data['total_ano'] = sum(produto_data['meses'])

    totais_abertos_mes = [sum(dados_pivot_abertos[c][p]['meses'][i] for c in dados_pivot_abertos for p in dados_pivot_abertos[c]) for i in range(12)]
    total_geral_abertos = sum(totais_abertos_mes)

    # --- 4. LÓGICA PARA TABELA DE CASOS ENCERRADOS ---
    casos_encerrados_ano = Caso.objects.filter(status='ENCERRADO', data_encerramento__year=ano_selecionado)
    dados_encerrados_agrupados = casos_encerrados_ano.values('data_encerramento__month', 'cliente__nome', 'produto__nome').annotate(total=Count('id'))

    dados_pivot_encerrados = {}
    clientes_encerrados = sorted(list(casos_encerrados_ano.values_list('cliente__nome', flat=True).distinct()))

    for cliente in clientes_encerrados:
        dados_pivot_encerrados[cliente] = {p_nome: {'meses': [0]*12, 'total_ano': 0} for p_nome in todos_produtos_nomes}
        
    for item in dados_encerrados_agrupados:
        cliente, produto, mes, total = item['cliente__nome'], item['produto__nome'], item['data_encerramento__month'], item['total']
        if mes and cliente in dados_pivot_encerrados and produto in dados_pivot_encerrados[cliente]:
            dados_pivot_encerrados[cliente][produto]['meses'][mes - 1] = total

    for cliente_data in dados_pivot_encerrados.values():
        for produto_data in cliente_data.values():
            produto_data['total_ano'] = sum(produto_data['meses'])
            
    totais_encerrados_mes = [sum(dados_pivot_encerrados[c][p]['meses'][i] for c in dados_pivot_encerrados for p in dados_pivot_encerrados[c]) for i in range(12)]
    total_geral_encerrados = sum(totais_encerrados_mes)
    # --- 4. NOVA LÓGICA: TABELA DE PERFORMANCE POR PROFISSIONAL ---
    todos_advogados = User.objects.filter(casos_responsaveis__isnull=False).distinct().order_by('username')
    advogados_nomes = [adv.username for adv in todos_advogados]

    # Agrega os dados no formato que queremos
    dados_performance_qs = (
        Caso.objects
        .exclude(advogado_responsavel__isnull=True)
        .values(
            'advogado_responsavel__username',
            'cliente__nome',
            'produto__nome',
            'status'
        )
        .annotate(total=Count('id'))
        .order_by('advogado_responsavel__username', 'cliente__nome', 'produto__nome')
    )
    
    # Estrutura os dados: {advogado: [{cliente, produto, status, total}]}
    tabela_performance = {}
    status_map = dict(Caso.STATUS_CHOICES)
   
    for item in dados_performance_qs:
        advogado = item['advogado_responsavel__username']
        if advogado not in tabela_performance:
            tabela_performance[advogado] = []
        tabela_performance[advogado].append({
            'cliente': item['cliente__nome'],
            'produto': item['produto__nome'],
            'status': status_map.get(item['status']),
            'total': item['total']
        })

    # --- 5. DADOS PARA OUTROS KPIs ---
    dados_status_total_qs = Caso.objects.values('status').annotate(total=Count('id')).order_by('-total')
    status_map = dict(Caso.STATUS_CHOICES)
    dados_grafico_pizza = {status_map.get(s['status'], s['status']): s['total'] for s in dados_status_total_qs}
    pizza_labels = list(dados_grafico_pizza.keys())
    pizza_data = list(dados_grafico_pizza.values())
    
    acoes_do_dia = InstanciaAcao.objects.filter(responsavel=request.user, status='PENDENTE', data_prazo=date.today()).select_related('caso', 'acao', 'caso__cliente', 'caso__produto').order_by('caso__id')[:10]

    # --- 6. CONTEXTO FINAL ---
    context = {
        'ano_selecionado': ano_selecionado,
        'anos_disponiveis': anos_disponiveis,
        'meses_nomes': meses_nomes_completos,
        
        'todos_produtos': todos_produtos_nomes,
        
        'dados_pivot_abertos': dados_pivot_abertos,
        'totais_abertos_mes': totais_abertos_mes,
        'total_geral_abertos': total_geral_abertos,
        
        'dados_pivot_encerrados': dados_pivot_encerrados,
        'totais_encerrados_mes': totais_encerrados_mes,
        'total_geral_encerrados': total_geral_encerrados,
        
        'dados_grafico_pizza': dados_grafico_pizza,
        'pizza_labels': pizza_labels,
        'pizza_data': pizza_data,

        'acoes_do_dia': acoes_do_dia,
        'tabela_performance': tabela_performance,
        'advogados_cabecalho': advogados_nomes,
        'tabela_performance': tabela_performance,
    }
    
    return render(request, 'core/home.html', context)

class CustomLoginView(auth_views.LoginView):
    authentication_form = CustomAuthenticationForm
    template_name = 'registration/login.html'

def logout_view(request):
    logout(request)
    return redirect('login')