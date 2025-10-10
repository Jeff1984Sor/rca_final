from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import Sum
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
import openpyxl
from io import BytesIO # Para criar o PDF em memória
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from dateutil.relativedelta import relativedelta
from .forms import AcordoForm # Adicione a importação
from .models import Parcela # Adicione a importação
from dateutil.relativedelta import relativedelta # Garanta que está importado
from decimal import Decimal # Para cálculos precisos com dinheiro
from django.views.decorators.http import require_POST
from datetime import date
from .forms import DespesaForm

# Importações de modelos de outros apps
from clientes.models import Cliente
from produtos.models import Produto

# Importações de modelos locais
from .models import Caso, Andamento, ModeloAndamento, Timesheet, Acordo, Parcela, Despesa
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado 

# Importações de formulários locais
from .forms import CasoDinamicoForm, AndamentoForm, TimesheetForm

User = get_user_model()


@login_required
def selecionar_produto_cliente(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        if cliente_id and produto_id:
            return redirect('casos:criar_caso', cliente_id=cliente_id, produto_id=produto_id)

    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    context = {'clientes': clientes, 'produtos': produtos}
    return render(request, 'casos/selecionar_produto_cliente.html', context)


@login_required
def criar_caso(request, cliente_id, produto_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    produto = get_object_or_404(Produto, id=produto_id)
    if request.method == 'POST':
        form = CasoDinamicoForm(request.POST, produto=produto)
        if form.is_valid():
            dados_limpos = form.cleaned_data
            titulo_final = ""
            if produto.padrao_titulo:
                titulo_final = produto.padrao_titulo
                for campo in produto.campos_personalizados.all():
                    valor = dados_limpos.get(f'campo_personalizado_{campo.id}') or ''
                    chave = campo.nome_campo.replace(" ", "")
                    titulo_final = titulo_final.replace(f'{{{chave}}}', str(valor))
            else:
                titulo_final = dados_limpos.get('titulo_manual', '')

            novo_caso = Caso.objects.create(
                cliente=cliente,
                produto=produto,
                data_entrada=dados_limpos['data_entrada'],
                status=dados_limpos['status'],
                data_encerramento=dados_limpos.get('data_encerramento'),
                advogado_responsavel=dados_limpos.get('advogado_responsavel'),
                titulo=titulo_final
            )
            for campo in produto.campos_personalizados.all():
                valor = dados_limpos.get(f'campo_personalizado_{campo.id}')
                if valor:
                    ValorCampoPersonalizado.objects.create(caso=novo_caso, campo=campo, valor=valor)
            return redirect('casos:lista_casos')
    else:
        form = CasoDinamicoForm(produto=produto)
    context = {'cliente': cliente, 'produto': produto, 'form': form}
    return render(request, 'casos/criar_caso_form.html', context)


@login_required
def lista_casos(request):
    casos_list = Caso.objects.select_related('cliente', 'produto', 'advogado_responsavel').all().order_by('-data_entrada')
    
    filtro_titulo = request.GET.get('filtro_titulo', '')
    filtro_cliente = request.GET.get('filtro_cliente', '')
    filtro_produto = request.GET.get('filtro_produto', '')
    filtro_status = request.GET.get('filtro_status', '')
    filtro_advogado = request.GET.get('filtro_advogado', '')

    if filtro_titulo:
        casos_list = casos_list.filter(titulo__icontains=filtro_titulo)
    if filtro_cliente:
        casos_list = casos_list.filter(cliente_id=filtro_cliente)
    if filtro_produto:
        casos_list = casos_list.filter(produto_id=filtro_produto)
    if filtro_status:
        casos_list = casos_list.filter(status=filtro_status)
    if filtro_advogado:
        casos_list = casos_list.filter(advogado_responsavel_id=filtro_advogado)

    context = {
        'casos': casos_list,
        'valores_filtro': request.GET,
        'todos_clientes': Cliente.objects.all().order_by('nome'),
        'todos_produtos': Produto.objects.all().order_by('nome'),
        'todos_advogados': User.objects.all().order_by('first_name', 'username'),
        'status_choices': Caso.STATUS_CHOICES,
    }
    return render(request, 'casos/lista_casos.html', context)


@login_required
def detalhe_caso(request, pk):
    caso = get_object_or_404(Caso, pk=pk)

    # Processamento de formulários enviados via POST
    if request.method == 'POST':
        
        # Formulário de Andamento
        if 'submit_andamento' in request.POST:
            form_andamento = AndamentoForm(request.POST)
            if form_andamento.is_valid():
                novo_andamento = form_andamento.save(commit=False)
                novo_andamento.caso = caso
                novo_andamento.autor = request.user
                novo_andamento.save()
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=andamentos')
        
        # Formulário de Timesheet
        elif 'submit_timesheet' in request.POST:
            form_timesheet = TimesheetForm(request.POST, user=request.user)
            if form_timesheet.is_valid():
                novo_timesheet = form_timesheet.save(commit=False)
                tempo_str = request.POST.get('tempo', '00:00')
                try:
                    horas, minutos = map(int, tempo_str.split(':'))
                    novo_timesheet.tempo = timedelta(hours=horas, minutes=minutos)
                except (ValueError, TypeError):
                    form_timesheet.add_error('tempo', 'Formato de tempo inválido. Use HH:MM.')
                else:
                    novo_timesheet.caso = caso
                    novo_timesheet.save()
                    Andamento.objects.create(
                        caso=caso,
                        data_andamento=novo_timesheet.data_execucao,
                        descricao=f"Lançamento de Timesheet:\nTempo: {tempo_str}\nAdvogado: {novo_timesheet.advogado}\nDescrição: {novo_timesheet.descricao}",
                        autor=request.user
                    )
                    url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                    return redirect(f'{url_destino}?aba=timesheet')

        # Formulário de Acordo
        elif 'submit_acordo' in request.POST:
            form_acordo = AcordoForm(request.POST, user=request.user)
            if form_acordo.is_valid():
                novo_acordo = form_acordo.save(commit=False)
                novo_acordo.caso = caso
                novo_acordo.save()
                
                valor_total = novo_acordo.valor_total
                num_parcelas = novo_acordo.numero_parcelas
                valor_parcela = round(Decimal(valor_total) / num_parcelas, 2)
                
                for i in range(num_parcelas):
                    data_vencimento = novo_acordo.data_primeira_parcela + relativedelta(months=i)
                    Parcela.objects.create(
                        acordo=novo_acordo,
                        numero_parcela=i + 1,
                        valor_parcela=valor_parcela,
                        data_vencimento=data_vencimento
                    )
                
                soma_parcelas = valor_parcela * num_parcelas
                diferenca = valor_total - soma_parcelas
                if diferenca != 0:
                    ultima_parcela = novo_acordo.parcelas.order_by('-numero_parcela').first()
                    if ultima_parcela:
                        ultima_parcela.valor_parcela += diferenca
                        ultima_parcela.save()
                
        if 'submit_despesa' in request.POST:
            form_despesa = DespesaForm(request.POST, user=request.user)
            if form_despesa.is_valid():
                nova_despesa = form_despesa.save(commit=False)
                nova_despesa.caso = caso
                nova_despesa.save()
                
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=despesas')
              
               
    # Lógica GET (executada sempre que a página é carregada ou se um form POST for inválido)
    form_andamento = AndamentoForm()
    form_timesheet = TimesheetForm(user=request.user)
    form_acordo = AcordoForm(user=request.user)

    # Coleta de dados para exibir nas abas
    valores_personalizados = caso.valores_personalizados.select_related('campo').order_by('campo__ordem')
    andamentos = caso.andamentos.select_related('autor').all()
    modelos_andamento = ModeloAndamento.objects.all()
    timesheets = caso.timesheets.select_related('advogado').all()
    acordos = caso.acordos.prefetch_related('parcelas').all()
    
    # Cálculo do somatório de timesheet
    soma_total_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_total_obj['total_tempo']

    saldo_devedor_total = Decimal('0.00')
    for acordo in acordos:
            # Soma o valor de todas as parcelas com status 'EMITIDA'
                    saldo_acordo = acordo.parcelas.filter(status='EMITIDA').aggregate(soma=Sum('valor_parcela'))['soma']
                    if saldo_acordo:
                            saldo_devedor_total += saldo_acordo
    despesas = caso.despesas.select_related('advogado').all()
    
    # 2. Calcula o somatório total do campo 'valor'
    soma_despesas_obj = despesas.aggregate(total_despesas=Sum('valor'))
    total_despesas = soma_despesas_obj['total_despesas'] or Decimal('0.00')
    form_despesa = DespesaForm(user=request.user) # Cria um formulário de despesa em branco

    context = {
        'caso': caso,
        'valores_personalizados': valores_personalizados,
        'andamentos': andamentos,
        'modelos_andamento': modelos_andamento,
        'timesheets': timesheets,
        'acordos': acordos,
        'saldo_devedor_total': saldo_devedor_total,
        'tempo_total': tempo_total,
        'form_andamento': form_andamento,
        'form_timesheet': form_timesheet,
        'form_acordo': form_acordo,
        'form_despesa': form_despesa,
        'despesas': despesas,
        'total_despesas': total_despesas,
    }
    return render(request, 'casos/detalhe_caso.html', context)

@login_required
def editar_caso(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    produto = caso.produto
    cliente = caso.cliente
    dados_iniciais = {
        'status': caso.status,
        'data_entrada': caso.data_entrada,
        'data_encerramento': caso.data_encerramento,
        'advogado_responsavel': caso.advogado_responsavel,
    }
    valores_existentes = {f'campo_personalizado_{v.campo.id}': v.valor for v in caso.valores_personalizados.all()}
    dados_iniciais.update(valores_existentes)
    if not produto.padrao_titulo:
        dados_iniciais['titulo_manual'] = caso.titulo
    if request.method == 'POST':
        form = CasoDinamicoForm(request.POST, produto=produto)
        if form.is_valid():
            dados_limpos = form.cleaned_data
            caso.status = dados_limpos['status']
            caso.data_entrada = dados_limpos['data_entrada']
            caso.data_encerramento = dados_limpos.get('data_encerramento')
            caso.advogado_responsavel = dados_limpos.get('advogado_responsavel')
            if produto.padrao_titulo:
                titulo_formatado = produto.padrao_titulo
                for campo in produto.campos_personalizados.all():
                    valor = dados_limpos.get(f'campo_personalizado_{campo.id}') or ''
                    chave = campo.nome_campo.replace(" ", "")
                    titulo_formatado = titulo_formatado.replace(f'{{{chave}}}', str(valor))
                caso.titulo = titulo_formatado
            else:
                caso.titulo = dados_limpos.get('titulo_manual', '')
            caso.save()
            for campo in produto.campos_personalizados.all():
                valor_novo = dados_limpos.get(f'campo_personalizado_{campo.id}')
                ValorCampoPersonalizado.objects.update_or_create(caso=caso, campo=campo, defaults={'valor': valor_novo})
            return redirect('casos:detalhe_caso', pk=caso.pk)
    else:
        form = CasoDinamicoForm(initial=dados_iniciais, produto=produto)
    context = {'cliente': cliente, 'produto': produto, 'form': form, 'caso': caso}
    return render(request, 'casos/criar_caso_form.html', context)


@login_required
def exportar_casos_excel(request):
    casos_list = Caso.objects.select_related('cliente', 'produto', 'advogado_responsavel').all().order_by('-data_entrada')
    filtro_titulo = request.GET.get('filtro_titulo', '')
    filtro_cliente = request.GET.get('filtro_cliente', '')
    filtro_produto = request.GET.get('filtro_produto', '')
    filtro_status = request.GET.get('filtro_status', '')
    filtro_advogado = request.GET.get('filtro_advogado', '')
    if filtro_titulo:
        casos_list = casos_list.filter(titulo__icontains=filtro_titulo)
    if filtro_cliente:
        casos_list = casos_list.filter(cliente_id=filtro_cliente)
    if filtro_produto:
        casos_list = casos_list.filter(produto_id=filtro_produto)
    if filtro_status:
        casos_list = casos_list.filter(status=filtro_status)
    if filtro_advogado:
        casos_list = casos_list.filter(advogado_responsavel_id=filtro_advogado)
    
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Casos'
    headers = ['ID', 'Título', 'Cliente', 'Produto', 'Status', 'Data de Entrada', 'Advogado Responsável']
    sheet.append(headers)
    for caso in casos_list:
        advogado = '-'
        if caso.advogado_responsavel:
            advogado = caso.advogado_responsavel.get_full_name() or caso.advogado_responsavel.username
        sheet.append([
            caso.id,
            caso.titulo,
            caso.cliente.nome,
            caso.produto.nome,
            caso.get_status_display(),
            caso.data_entrada.strftime('%d/%m/%Y') if caso.data_entrada else '',
            advogado
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="casos.xlsx"'
    workbook.save(response)
    return response


@login_required
def exportar_andamentos_excel(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    andamentos = caso.andamentos.select_related('autor').order_by('data_andamento')
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f'Andamentos Caso #{caso.id}'
    headers = ['Data do Andamento', 'Descrição', 'Criado por', 'Data de Criação']
    sheet.append(headers)
    for andamento in andamentos:
        autor_nome = '-'
        if andamento.autor:
            autor_nome = andamento.autor.get_full_name() or andamento.autor.username
        data_andamento_formatada = andamento.data_andamento.strftime('%d/%m/%Y')
        data_criacao_formatada = timezone.localtime(andamento.data_criacao).strftime('%d/%m/%Y %H:%M')
        sheet.append([
            data_andamento_formatada,
            andamento.descricao,
            autor_nome,
            data_criacao_formatada,
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="andamentos_caso_{caso.id}.xlsx"'
    workbook.save(response)
    return response


# casos/views.py
# ...

@login_required
def exportar_timesheet_excel(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    timesheets = caso.timesheets.select_related('advogado').order_by('data_execucao')

    soma_total_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_total_obj['total_tempo'] or timedelta(0)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f'Timesheet Caso #{caso.id}'

    # 1. ORDEM DO CABEÇALHO ATUALIZADA
    headers = ['Data da Execução', 'Advogado', 'Descrição', 'Tempo Gasto']
    sheet.append(headers)

    for ts in timesheets:
        advogado_nome = '-'
        if ts.advogado:
            advogado_nome = ts.advogado.get_full_name() or ts.advogado.username
        
        tempo_str = str(ts.tempo)

        # 2. ORDEM DOS DADOS ATUALIZADA PARA CORRESPONDER AO CABEÇALHO
        sheet.append([
            ts.data_execucao.strftime('%d/%m/%Y'),
            advogado_nome,
            ts.descricao,
            tempo_str,
        ])
    
    sheet.append([]) # Linha em branco

    # 3. LÓGICA DO TOTAL ATUALIZADA
    from openpyxl.styles import Font
    bold_font = Font(bold=True)
    
    # Cria a linha do total com células vazias para alinhar
    # A coluna D é a 4ª coluna.
    linha_total = ['', '', 'Total:', str(tempo_total)]
    sheet.append(linha_total)

    # Aplica o negrito na célula "Total:" (que agora é a C)
    # e no valor total (que agora é a D)
    sheet['C' + str(sheet.max_row)].font = bold_font
    sheet['D' + str(sheet.max_row)].font = bold_font

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="timesheet_caso_{caso.id}.xlsx"'
    
    workbook.save(response)
    return response


@login_required
def exportar_timesheet_pdf(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    timesheets = caso.timesheets.select_related('advogado').order_by('data_execucao')
    soma_total_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_total_obj['total_tempo'] or timedelta(0)

    # 1. Configuração do Buffer e do Documento PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=inch/2, leftMargin=inch/2, topMargin=inch/2, bottomMargin=inch/2)
    
    # 2. Preparação de Estilos e Conteúdo
    styles = getSampleStyleSheet()
    story = []

    # Título do Documento
    story.append(Paragraph(f"Relatório de Timesheet - Caso #{caso.id}", styles['h1']))
    story.append(Paragraph(f"<b>Cliente:</b> {caso.cliente.nome}", styles['Normal']))
    story.append(Paragraph(f"<b>Produto:</b> {caso.produto.nome}", styles['Normal']))
    story.append(Spacer(1, 0.25*inch)) # Espaçamento

    # 3. Preparação dos Dados para a Tabela
    # Cabeçalho
    data = [['Data', 'Advogado', 'Descrição', 'Tempo Gasto']]
    
    # Linhas de dados
    for ts in timesheets:
        advogado_nome = ts.advogado.get_full_name() or ts.advogado.username if ts.advogado else '-'
        data.append([
            ts.data_execucao.strftime('%d/%m/%Y'),
            advogado_nome,
            Paragraph(ts.descricao.replace('\n', '<br/>'), styles['Normal']), # Permite quebra de linha na descrição
            str(ts.tempo)
        ])

    # Linha de total
    data.append(['', '', Paragraph("<b>Total:</b>", styles['Normal']), Paragraph(f"<b>{str(tempo_total)}</b>", styles['Normal'])])

    # 4. Criação e Estilização da Tabela
    table = Table(data, colWidths=[1.2*inch, 1.5*inch, 3.3*inch, 1.2*inch])
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey), # Fundo cinza no cabeçalho
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Negrito no cabeçalho
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige), # Cor de fundo alternada (opcional)
        ('GRID', (0, 0), (-1, -1), 1, colors.black), # Adiciona grades
        ('ALIGN', (2, 1), (2, -1), 'LEFT'), # Alinha a descrição à esquerda
        ('ALIGN', (2, -1), (3, -1), 'RIGHT'), # Alinha o 'Total:' à direita
        ('SPAN', (2, -1), (2, -1)), # Mescla células se necessário (aqui alinhando o 'Total:')
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'), # Negrito na linha de total
    ])
    table.setStyle(style)
    
    story.append(table)
    
    # 5. Geração do PDF
    doc.build(story)
    
    # 6. Preparação da Resposta HTTP
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="timesheet_caso_{caso.id}.pdf"'
    
    return response


@login_required
def editar_timesheet(request, pk):
    # Busca o lançamento de timesheet específico pelo seu ID (pk)
    timesheet = get_object_or_404(Timesheet, pk=pk)
    # Pega o caso ao qual este timesheet pertence, para poder redirecionar de volta
    caso = timesheet.caso

    if request.method == 'POST':
        # Passa os dados do POST e a 'instance' para o formulário
        form = TimesheetForm(request.POST, instance=timesheet)
        if form.is_valid():
            # Faz a conversão manual do tempo, como na criação
            ts_editado = form.save(commit=False)
            tempo_str = request.POST.get('tempo')
            try:
                horas, minutos = map(int, tempo_str.split(':'))
                ts_editado.tempo = timedelta(hours=horas, minutes=minutos)
            except (ValueError, TypeError):
                form.add_error('tempo', 'Formato de tempo inválido. Use HH:MM.')
            else:
                ts_editado.save() # Salva o objeto já com o tempo convertido
                
                # Redireciona de volta para a página de detalhes do caso, na aba correta
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=timesheet')
    else:
    # Se for um GET, cria o formulário preenchido
        initial_data = {}
    
    # --- LÓGICA DE FORMATAÇÃO DA HORA ATUALIZADA ---
    if timesheet.tempo:
        total_seconds = int(timesheet.tempo.total_seconds())
        horas = total_seconds // 3600
        minutos = (total_seconds % 3600) // 60
        # zfill(2) garante que sempre teremos 2 dígitos, ex: '5' vira '05'
        initial_data['tempo'] = f"{str(horas).zfill(2)}:{str(minutos).zfill(2)}"
        form = TimesheetForm(instance=timesheet, initial=initial_data)

    context = {
        'form': form,
        'timesheet': timesheet,
        'caso': caso,
    }
    # Vamos criar um novo template para a edição
    return render(request, 'casos/timesheet_form.html', context)


@login_required
def deletar_timesheet(request, pk):
    # Busca o lançamento de timesheet específico
    timesheet = get_object_or_404(Timesheet, pk=pk)
    # Pega o caso associado para o redirecionamento
    caso = timesheet.caso

    if request.method == 'POST':
        # Se o formulário de confirmação foi enviado, deleta o objeto
        timesheet.delete()
        # Redireciona de volta para a página de detalhes do caso, na aba correta
        url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
        return redirect(f'{url_destino}?aba=timesheet')
    
    # Se for um GET, apenas mostra a página de confirmação
    context = {
        'timesheet': timesheet,
        'caso': caso,
    }
    return render(request, 'casos/timesheet_confirm_delete.html', context)

@require_POST
@login_required
def quitar_parcela(request, pk):
    parcela = get_object_or_404(Parcela, pk=pk)
    
    # Lógica de "toggle" aprimorada
    if parcela.status == 'QUITADA':
        parcela.status = 'EMITIDA'
        parcela.data_pagamento = None # Limpa a data de pagamento
    else:
        parcela.status = 'QUITADA'
        parcela.data_pagamento = date.today() # Define a data de pagamento como hoje
    
    parcela.save()
    
    # Retorna o template parcial com a linha atualizada
    return render(request, 'casos/partials/parcela_linha.html', {'parcela': parcela})



@login_required
def editar_acordo(request, pk):
    acordo = get_object_or_404(Acordo, pk=pk)
    caso = acordo.caso

    if request.method == 'POST':
        form = AcordoForm(request.POST, instance=acordo, user=request.user)
        if form.is_valid():
            # Salva as alterações no acordo principal
            acordo_editado = form.save()

            # --- LÓGICA DE RECRIAÇÃO DAS PARCELAS ---
            # 1. Deleta todas as parcelas antigas deste acordo
            acordo_editado.parcelas.all().delete()

            # 2. Recria as parcelas com os novos dados (mesma lógica da criação)
            valor_total = acordo_editado.valor_total
            num_parcelas = acordo_editado.numero_parcelas
            valor_parcela = round(Decimal(valor_total) / num_parcelas, 2)
            
            for i in range(num_parcelas):
                data_vencimento = acordo_editado.data_primeira_parcela + relativedelta(months=i)
                Parcela.objects.create(
                    acordo=acordo_editado,
                    numero_parcela=i + 1,
                    valor_parcela=valor_parcela,
                    data_vencimento=data_vencimento,
                )
            
            soma_parcelas = valor_parcela * num_parcelas
            diferenca = valor_total - soma_parcelas
            if diferenca != 0:
                ultima_parcela = acordo_editado.parcelas.order_by('-numero_parcela').first()
                if ultima_parcela:
                    ultima_parcela.valor_parcela += diferenca
                    ultima_parcela.save()
            
            url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
            return redirect(f'{url_destino}?aba=acordos')
    else:
        # Cria o formulário preenchido com os dados do acordo existente
        form = AcordoForm(instance=acordo, user=request.user)
    
    context = {
        'form_acordo': form,
        'acordo': acordo,
        'caso': caso,
    }
    # Vamos criar um novo template para a edição do acordo
    return render(request, 'casos/acordo_form.html', context)

@login_required
def editar_despesa(request, pk):
    despesa = get_object_or_404(Despesa, pk=pk)
    caso = despesa.caso

    if request.method == 'POST':
        form = DespesaForm(request.POST, instance=despesa, user=request.user)
        if form.is_valid():
            form.save()
            url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
            return redirect(f'{url_destino}?aba=despesas')
    else:
        form = DespesaForm(instance=despesa, user=request.user)

    context = {
        'form_despesa': form,
        'despesa': despesa,
        'caso': caso,
    }
    return render(request, 'casos/despesa_form.html', context)
