from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import Sum
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import openpyxl
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from campos_custom.models import EstruturaDeCampos

# Importações de modelos de outros apps
from clientes.models import Cliente
from produtos.models import Produto
from datetime import datetime

# Importações de modelos locais
from .models import Caso, Andamento, ModeloAndamento, Timesheet, Acordo, Parcela, Despesa, FluxoInterno
from campos_custom.models import ValorCampoPersonalizado

from integrations.sharepoint import SharePoint

# Importações de formulários locais
from .forms import CasoDinamicoForm, AndamentoForm, TimesheetForm, AcordoForm, DespesaForm

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
        # 1. Passamos o CLIENTE e o PRODUTO para o formulário
        form = CasoDinamicoForm(request.POST, cliente=cliente, produto=produto)
        if form.is_valid():
            dados_limpos = form.cleaned_data
            
            # --- LÓGICA DE GERAÇÃO DE TÍTULO ATUALIZADA ---
            titulo_final = ""
            if produto.padrao_titulo:
                titulo_final = produto.padrao_titulo
                estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
                if estrutura:
                    for campo in estrutura.campos.all().distinct():
                        valor = dados_limpos.get(f'campo_personalizado_{campo.id}') or ''
                        # 2. Usamos o NOME DA VARIÁVEL para a substituição!
                        chave_variavel = campo.nome_variavel 
                        titulo_final = titulo_final.replace(f'{{{chave_variavel}}}', str(valor))
            else:
                titulo_final = dados_limpos.get('titulo_manual', '')
            # --- FIM DA LÓGICA DE TÍTULO ---

            novo_caso = Caso.objects.create(
                cliente=cliente,
                produto=produto,
                data_entrada=dados_limpos['data_entrada'],
                status=dados_limpos['status'],
                # ... outros campos ...
                titulo=titulo_final
            )

            # --- LÓGICA DE SALVAR VALORES ATUALIZADA ---
            estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
            if estrutura:
                for campo in estrutura.campos.all():
                    valor = dados_limpos.get(f'campo_personalizado_{campo.id}')
                    if valor is not None: # Salva mesmo que o valor seja vazio (ex: string vazia)
                        ValorCampoPersonalizado.objects.create(caso=novo_caso, campo=campo, valor=str(valor))
            # --- FIM DA LÓGICA DE SALVAR ---
            
            return redirect('casos:lista_casos')
    else:
        # 3. Passamos também na requisição GET para o formulário ser montado corretamente
        form = CasoDinamicoForm(cliente=cliente, produto=produto)
        
    context = {'cliente': cliente, 'produto': produto, 'form': form}
    return render(request, 'casos/criar_caso_form.html', context)



@login_required
def lista_casos(request):
    casos_list = Caso.objects.select_related('cliente', 'produto', 'advogado_responsavel').all().order_by('-id')
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
    caso.refresh_from_db() # Garante que estamos vendo o estado mais atual do caso
    
    # Prepara os formulários com valores iniciais ou vazios
    form_andamento = AndamentoForm()
    form_timesheet = TimesheetForm(user=request.user)
    form_acordo = AcordoForm(user=request.user)
    form_despesa = DespesaForm(user=request.user)

    # Processamento de formulários enviados via POST (ESTA PARTE NÃO MUDA)
    if request.method == 'POST':
        if 'submit_andamento' in request.POST:
            form_andamento = AndamentoForm(request.POST)
            if form_andamento.is_valid():
                novo_andamento = form_andamento.save(commit=False)
                novo_andamento.caso = caso
                novo_andamento.autor = request.user
                novo_andamento.save()
                FluxoInterno.objects.create(caso=caso, tipo_evento='ANDAMENTO', descricao=f"Novo andamento adicionado.", autor=request.user)
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=andamentos')
        
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
                    FluxoInterno.objects.create(caso=caso, tipo_evento='TIMESHEET', descricao=f"Lançamento de {novo_timesheet.tempo} realizado por {novo_timesheet.advogado}.", autor=request.user)
                    Andamento.objects.create(
                        caso=caso,
                        data_andamento=novo_timesheet.data_execucao,
                        descricao=f"Lançamento de Timesheet:\nTempo: {tempo_str}\nAdvogado: {novo_timesheet.advogado}\nDescrição: {novo_timesheet.descricao}",
                        autor=request.user
                    )
                    url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                    return redirect(f'{url_destino}?aba=timesheet')

        elif 'submit_acordo' in request.POST:
            form_acordo = AcordoForm(request.POST, user=request.user)
            if form_acordo.is_valid():
                novo_acordo = form_acordo.save(commit=False)
                novo_acordo.caso = caso
                novo_acordo.save()
                FluxoInterno.objects.create(caso=caso, tipo_evento='ACORDO', descricao=f"Novo acordo de R$ {novo_acordo.valor_total} em {novo_acordo.numero_parcelas}x criado.", autor=request.user)
                # ... (lógica de criação de parcelas) ...
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=acordos')
        
        elif 'submit_despesa' in request.POST:
            form_despesa = DespesaForm(request.POST, user=request.user)
            if form_despesa.is_valid():
                nova_despesa = form_despesa.save(commit=False)
                nova_despesa.caso = caso
                nova_despesa.save()
                FluxoInterno.objects.create(caso=caso, tipo_evento='DESPESA', descricao=f"Nova despesa de R$ {nova_despesa.valor} lançada: '{nova_despesa.descricao}'.", autor=request.user)
                url_destino = reverse('casos:detalhe_caso', kwargs={'pk': caso.pk})
                return redirect(f'{url_destino}?aba=despesas')
    
    # --- Lógica GET (executada sempre) ---
    # Prepara os formulários em branco (NÃO MUDA)
    form_andamento = AndamentoForm()
    form_timesheet = TimesheetForm(user=request.user)
    form_acordo = AcordoForm(user=request.user)
    form_despesa = DespesaForm(user=request.user)
    
    # ==============================================================================
    # A ÚNICA MUDANÇA ESTÁ AQUI: BUSCA DE DADOS PARA AS ABAS
    # ==============================================================================
    
    # 1. Busca todos os valores que já foram salvos para este caso.
    valores_salvos_qs = caso.valores_personalizados.select_related('campo').all()
    # Cria um dicionário para acesso rápido: {id_do_campo: objeto_valor}
    valores_salvos_dict = {valor.campo.id: valor for valor in valores_salvos_qs}

    # 2. Busca a ESTRUTURA de campos correta para o cliente e produto deste caso.
    estrutura = EstruturaDeCampos.objects.filter(cliente=caso.cliente, produto=caso.produto).first()

    # 3. Monta a lista final de valores a serem exibidos, na ordem correta.
    valores_para_template = []
    if estrutura:
        # Itera sobre os campos definidos na estrutura.
        for campo in estrutura.campos.all():
            # Verifica se existe um valor salvo para este campo.
            valor_salvo = valores_salvos_dict.get(campo.id)
            if valor_salvo:
                valores_para_template.append(valor_salvo)
            if campo.tipo_campo == 'DATA' and valor_salvo.valor:
                    try:
                        # Tentamos converter a string 'AAAA-MM-DD' em um objeto de data
                        valor_salvo.valor_tratado = datetime.strptime(valor_salvo.valor, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        # Se a conversão falhar, usamos o valor original
                        valor_salvo.valor_tratado = valor_salvo.valor
            else:
                    # Para todos os outros tipos, apenas usamos o valor como está
                    valor_salvo.valor_tratado = valor_salvo.valor
                
            valores_para_template.append(valor_salvo)
    
    # ==============================================================================
    # O RESTO DO CÓDIGO CONTINUA EXATAMENTE IGUAL
    # ==============================================================================

    andamentos = caso.andamentos.select_related('autor').all()
    modelos_andamento = ModeloAndamento.objects.all()
    timesheets = caso.timesheets.select_related('advogado').all()
    acordos = caso.acordos.prefetch_related('parcelas').all()
    despesas = caso.despesas.select_related('advogado').all()
    historico_fases = caso.historico_fases.select_related('fase').order_by('data_entrada')
    
    acoes_pendentes = caso.acoes_pendentes.filter(status='PENDENTE').select_related('acao', 'responsavel')
    acoes_concluidas = caso.acoes_pendentes.filter(status='CONCLUIDA').select_related('acao', 'concluida_por').order_by('-data_conclusao')

    soma_tempo_obj = timesheets.aggregate(total_tempo=Sum('tempo'))
    tempo_total = soma_tempo_obj['total_tempo']
    
    saldo_devedor_total = Decimal('0.00')
    for acordo in acordos:
        saldo_acordo = acordo.parcelas.filter(status='EMITIDA').aggregate(soma=Sum('valor_parcela'))['soma']
        if saldo_acordo:
            saldo_devedor_total += saldo_acordo
            
    soma_despesas_obj = despesas.aggregate(total_despesas=Sum('valor'))
    total_despesas = soma_despesas_obj['total_despesas'] or Decimal('0.00')
    fluxo_interno = caso.fluxo_interno.select_related('autor').all()
    itens_anexos = []
    folder_name = "Raiz"
    if caso.sharepoint_folder_id:
        try:
            sp = SharePoint()
            itens_anexos = sp.listar_conteudo_pasta(caso.sharepoint_folder_id)
        except Exception as e:
            print(f"Erro ao buscar anexos da pasta raiz para o caso #{caso.id}: {e}")

    # Montagem do Contexto Final
    context = {
        'caso': caso,
        'form_andamento': form_andamento,
        'form_timesheet': form_timesheet,
        'form_acordo': form_acordo,
        'form_despesa': form_despesa,
        'valores_personalizados': valores_para_template, # <<< Usamos a nossa nova variável aqui
        'andamentos': andamentos,
        'modelos_andamento': modelos_andamento,
        'timesheets': timesheets,
        'acordos': acordos,
        'despesas': despesas,
        'historico_fases': historico_fases,
        'acoes_pendentes': acoes_pendentes,
        'acoes_concluidas': acoes_concluidas,
        'fluxo_interno': fluxo_interno,
        'tempo_total': tempo_total,
        'saldo_devedor_total': saldo_devedor_total,
        'total_despesas': total_despesas,
        'itens': itens_anexos,
        'folder_id': caso.sharepoint_folder_id,
        'root_folder_id': caso.sharepoint_folder_id,
        'folder_name': folder_name,
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
        # CORREÇÃO: Passamos o CLIENTE e o PRODUTO para o formulário
        form = CasoDinamicoForm(request.POST, cliente=cliente, produto=produto)
        if form.is_valid():
            dados_limpos = form.cleaned_data
            caso.status = dados_limpos['status']
            caso.data_entrada = dados_limpos['data_entrada']
            caso.data_encerramento = dados_limpos.get('data_encerramento')
            caso.advogado_responsavel = dados_limpos.get('advogado_responsavel')
            
            # Lógica de atualizar o título (precisa ser corrigida também)
            if produto.padrao_titulo:
                titulo_formatado = produto.padrao_titulo
                estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
                if estrutura:
                    for campo in estrutura.campos.all():
                        valor = dados_limpos.get(f'campo_personalizado_{campo.id}') or ''
                        chave_variavel = campo.nome_variavel
                        titulo_formatado = titulo_formatado.replace(f'{{{chave_variavel}}}', str(valor))
                caso.titulo = titulo_formatado
            else:
                caso.titulo = dados_limpos.get('titulo_manual', '')
                
            caso.save()

            # Lógica de atualizar valores
            estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
            if estrutura:
                for campo in estrutura.campos.all():
                    valor_novo = dados_limpos.get(f'campo_personalizado_{campo.id}')
                    ValorCampoPersonalizado.objects.update_or_create(
                        caso=caso, 
                        campo=campo, 
                        defaults={'valor': str(valor_novo) if valor_novo is not None else ''}
                    )
                    
            return redirect('casos:detalhe_caso', pk=caso.pk)
    else:
        # CORREÇÃO: Passamos também no GET
        form = CasoDinamicoForm(initial=dados_iniciais, cliente=cliente, produto=produto)
        
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
    context = {'form_despesa': form, 'despesa': despesa, 'caso': caso}
    return render(request, 'casos/despesa_form.html', context)

@login_required
def carregar_conteudo_pasta(request, folder_id):
    folder_name = "Raiz" # Padrão
    try:
        sp = SharePoint()
        conteudo = sp.listar_conteudo_pasta(folder_id)
        
        # Se não for a pasta raiz do caso, busca o nome da subpasta
        if folder_id != request.GET.get('root_folder_id'):
            folder_details = sp.get_folder_details(folder_id)
            folder_name = folder_details.get('name')

    except Exception as e:
        conteudo = None
        print(f"Erro ao buscar conteúdo da pasta {folder_id}: {e}")

    context = {
        'itens': conteudo,
        'folder_id': folder_id,
        'folder_name': folder_name, # Passa o nome da pasta para o template
        'root_folder_id': request.GET.get('root_folder_id', folder_id) # Mantém o ID da raiz
    }
    return render(request, 'casos/partials/lista_arquivos.html', context)

@require_POST # Esta view só aceita POST
@login_required
def upload_arquivo_sharepoint(request, folder_id):
    try:
        sp = SharePoint()
        files_uploaded = request.FILES.getlist('arquivos')
        
        if not files_uploaded:
            print("Tentativa de upload, mas nenhum arquivo foi enviado.")
            # Você pode querer retornar uma mensagem de erro aqui

        for file in files_uploaded:
            print(f"Processando upload do arquivo: {file.name}")
            sp.upload_arquivo(folder_id, file.name, file.read())

    except Exception as e:
        print(f"!!!!!! ERRO DURANTE O UPLOAD para a pasta {folder_id}: {e}")
        # Em caso de erro, é uma boa prática retornar uma resposta de erro para o HTMX
        return HttpResponse(f"<p style='color: red; padding: 10px;'>Erro no upload: {e}</p>", status=500)

    # --- LÓGICA CORRIGIDA APÓS O UPLOAD ---
    
    # 1. Recria a instância do SharePoint para garantir um token válido se o upload demorou.
    sp = SharePoint()
    
    # 2. Busca o conteúdo atualizado da pasta.
    conteudo = sp.listar_conteudo_pasta(folder_id)
    
    # 3. Pega o root_folder_id que foi enviado pelo campo oculto no formulário.
    root_folder_id = request.POST.get('root_folder_id')
    
    # 4. Busca o nome da pasta atual para exibir corretamente.
    folder_name = "Raiz" # Padrão
    if root_folder_id != folder_id:
        try:
            folder_details = sp.get_folder_details(folder_id)
            folder_name = folder_details.get('name')
        except Exception:
            pass # Se houver erro, mantém o nome 'Raiz'

    # 5. Monta o contexto completo para renderizar o template parcial.
    context = {
        'itens': conteudo,
        'folder_id': folder_id,
        'root_folder_id': root_folder_id,
        'folder_name': folder_name,
    }
    
    # 6. Retorna o template parcial atualizado.
    return render(request, 'casos/partials/lista_arquivos.html', context)


def preview_anexo(request, item_id):
    try:
        sp = SharePoint()
        preview_url = sp.get_preview_url(item_id)
    except Exception as e:
        return HttpResponse(f"<p style='color:red;'>Erro ao gerar preview: {e}</p>")
    
    # Retorna um iframe que aponta para a URL de preview
    return HttpResponse(f'<iframe src="{preview_url}"></iframe>')

@require_POST
@login_required
def criar_pasta_sharepoint(request, parent_folder_id):
    # O 'try' começa aqui
    try:
        # TODO ESTE BLOCO PRECISA SER INDENTADO
        nome_nova_pasta = request.POST.get('nome_pasta')
        if not nome_nova_pasta:
            return HttpResponse("<p style='color: red;'>O nome da pasta não pode ser vazio.</p>", status=400)

        sp = SharePoint()
        sp.criar_subpasta(parent_folder_id, nome_nova_pasta)
    
    # O 'except' deve estar alinhado com o 'try'
    except Exception as e:
        print(f"ERRO durante a criação da pasta em {parent_folder_id}: {e}")

    # Este código abaixo também precisa estar no nível correto (fora do try/except)
    sp = SharePoint()
    root_folder_id = request.POST.get('root_folder_id')
    conteudo = sp.listar_conteudo_pasta(parent_folder_id)
    
    folder_name = "Raiz"
    if root_folder_id != parent_folder_id:
        try:
            folder_details = sp.get_folder_details(parent_folder_id)
            folder_name = folder_details.get('name')
        except Exception:
            pass

    context = {
        'itens': conteudo,
        'folder_id': parent_folder_id,
        'root_folder_id': root_folder_id,
        'folder_name': folder_name,
    }
    return render(request, 'casos/partials/lista_arquivos.html', context)

@require_POST # Usamos POST para ações destrutivas
@login_required
def excluir_anexo_sharepoint(request, item_id):
    try:
        sp = SharePoint()
        sp.excluir_item(item_id)
        
    except Exception as e:
        print(f"ERRO durante a exclusão do item {item_id}: {e}")
        # Em caso de erro, podemos retornar uma mensagem para o usuário via HTMX
        # Para isso, usaríamos o hx-swap-oob="true" no template (mais avançado)
        # Por enquanto, falhar silenciosamente no log é suficiente.
        return HttpResponse(f"<p style='color:red;'>Erro ao excluir: {e}</p>", status=400)
    
    
    # Após excluir, recarregamos a lista da pasta "pai"
    parent_folder_id = request.POST.get('parent_folder_id')
    root_folder_id = request.POST.get('root_folder_id')

    sp = SharePoint()
    conteudo = sp.listar_conteudo_pasta(parent_folder_id)
    
    folder_name = "Raiz"
    if root_folder_id != parent_folder_id:
        try:
            folder_details = sp.get_folder_details(parent_folder_id)
            folder_name = folder_details.get('name')
        except Exception:
            pass

    context = {
        'itens': conteudo,
        'folder_id': parent_folder_id,
        'root_folder_id': root_folder_id,
        'folder_name': folder_name,
    }
    # 1. Cria uma resposta vazia
    response = HttpResponse(status=200)
    # 2. Adiciona o cabeçalho especial que o HTMX entende
    response['HX-Refresh'] = 'true'
    # 3. Retorna a resposta
    return response

