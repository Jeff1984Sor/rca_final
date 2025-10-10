from django.shortcuts import render, redirect, get_object_or_404
from .models import Cliente
from django.contrib.auth.decorators import login_required
from .forms import ClienteForm
from django.http import HttpResponse
import openpyxl

@login_required
def lista_clientes(request):
    # Começa com todos os clientes
    clientes_list = Cliente.objects.all().order_by('nome')
    
    # Pega os valores dos filtros do request.GET (se existirem)
    filtro_nome = request.GET.get('filtro_nome', '')
    filtro_tipo = request.GET.get('filtro_tipo', '')

    # Aplica os filtros na queryset se eles foram preenchidos
    if filtro_nome:
        clientes_list = clientes_list.filter(nome__icontains=filtro_nome)
    
    if filtro_tipo:
        clientes_list = clientes_list.filter(tipo=filtro_tipo)

    context = {
        'clientes': clientes_list,
        'filtro_nome': filtro_nome, # Envia os valores dos filtros de volta para o template
        'filtro_tipo': filtro_tipo,
    }
    return render(request, 'clientes/lista_clientes.html', context)

@login_required
def criar_cliente(request):
    if request.method == 'POST':
        # Se o formulário foi enviado, processa os dados
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save() # Salva o novo cliente no banco de dados
            return redirect('clientes:lista_clientes') # Redireciona para a lista
    else:
        # Se a página foi apenas acessada (GET), mostra um formulário em branco
        form = ClienteForm()

    context = {
        'form': form
    }
    return render(request, 'clientes/cliente_form.html', context)

@login_required
def editar_cliente(request, pk):
    # 1. Busca o cliente pelo ID (pk) ou retorna um erro 404 se não encontrar
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        # Passa a 'instance' para o formulário saber que está editando um objeto existente
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('clientes:lista_clientes')
    else:
        # Preenche o formulário com os dados do cliente existente
        form = ClienteForm(instance=cliente)

    context = {
        'form': form
    }
    # Reutiliza o mesmo template do formulário de criação!
    return render(request, 'clientes/cliente_form.html', context)


@login_required
def deletar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        # Se o formulário de confirmação foi enviado, deleta o objeto
        cliente.delete()
        # Redireciona para a lista de clientes
        return redirect('clientes:lista_clientes')
    
    # Se for um GET, apenas mostra a página de confirmação
    context = {
        'cliente': cliente
    }
    return render(request, 'clientes/cliente_confirm_delete.html', context)

@login_required
def exportar_clientes_excel(request):
    # Reutiliza a mesma lógica de filtro da lista de clientes
    clientes_list = Cliente.objects.all().order_by('nome')
    filtro_nome = request.GET.get('filtro_nome', '')
    filtro_tipo = request.GET.get('filtro_tipo', '')

    if filtro_nome:
        clientes_list = clientes_list.filter(nome__icontains=filtro_nome)
    if filtro_tipo:
        clientes_list = clientes_list.filter(tipo=filtro_tipo)

    # Cria um "workbook" (arquivo Excel) em memória
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Clientes'

    # Cria o cabeçalho
    headers = ['Nome', 'Tipo', 'Contato', 'Logradouro', 'Cidade', 'UF']
    sheet.append(headers)

    # Adiciona os dados dos clientes
    for cliente in clientes_list:
        tipo_display = cliente.get_tipo_display() or ''
        sheet.append([
            cliente.nome,
            tipo_display,
            cliente.contato_empresa,
            cliente.logradouro,
            cliente.cidade,
            cliente.uf,
        ])
    
    # Prepara a resposta HTTP para servir o arquivo
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="clientes.xlsx"'
    
    # Salva o workbook na resposta
    workbook.save(response)

    return response