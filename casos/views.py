# 1. Imports Padrão do Python
import logging
from io import BytesIO
from datetime import date, timedelta, datetime
from decimal import Decimal
import re # Se você usa para validação

# 2. Imports de Terceiros
import openpyxl
from dateutil.relativedelta import relativedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from rest_framework import viewsets, status
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication

# 3. Imports do Django e Locais
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import Sum
from django.db import transaction, IntegrityError # Adicionado IntegrityError
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation # <<< VERIFIQUE SE ESTA LINHA EXISTE
from django.utils.formats import number_format # <<< E ESTA TAMBÉM
# Modelos de outros apps
from clientes.models import Cliente
from produtos.models import Produto
from django.utils.formats import number_format # <<< ADICIONE ESTA LINHA
from decimal import Decimal, InvalidOperation # <<< ADICIONE ESTA LINHA

# Modelos e Forms locais (do app 'casos')
from .models import Caso, Andamento, ModeloAndamento, Timesheet, Acordo, Parcela, Despesa, FluxoInterno
from .forms import CasoDinamicoForm, AndamentoForm, TimesheetForm, AcordoForm, DespesaForm
from .serializers import CasoSerializer

try:
    from .tasks import processar_linha_importacao
except ImportError as e:
     initial_logger = logging.getLogger(__name__)
     initial_logger.critical(f"Erro CRÍTICO ao importar a tarefa Celery 'processar_linha_importacao' em views.py: {e}.")
     # Define uma função dummy para evitar erros de NameError
     def processar_linha_importacao(*args, **kwargs):
         logger = logging.getLogger('casos_app')
         logger.critical("TAREFA CELERY 'processar_linha_importacao' NÃO ENCONTRADA!")

try:
    from .utils import get_cabecalho_exportacao
except ImportError:
    logger = logging.getLogger('casos_app')
    logger.warning("Função get_cabecalho_exportacao não encontrada em utils.py. Usando fallback.")
    # Define uma função dummy
    def get_cabecalho_exportacao(cliente, produto): return ([], [])

# Modelos do app 'campos_custom'
from campos_custom.models import EstruturaDeCampos, CampoPersonalizado, ValorCampoPersonalizado

# Integrações
from integrations.sharepoint import SharePoint
from .tasks import processar_linha_importacao

logger = logging.getLogger('casos_app')
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

def detalhe_caso(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    caso.refresh_from_db() # Garante que estamos vendo o estado mais atual
    
    # --- Lógica POST (Sua lógica original, sem mudanças) ---
    form_andamento = AndamentoForm()
    form_timesheet = TimesheetForm(user=request.user)
    form_acordo = AcordoForm(user=request.user)
    form_despesa = DespesaForm(user=request.user)

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
                # ... (Sua lógica de criação de parcelas vai aqui) ...
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
    
    # --- Lógica GET (Carregamento da Página) ---
    
    # ==============================================================================
    # LÓGICA DE BUSCA DE DADOS PERSONALIZADOS (ATUALIZADA PARA DATA E MOEDA)
    # ==============================================================================
    
    # Busca a ESTRUTURA de campos correta
    estrutura = EstruturaDeCampos.objects.filter(cliente=caso.cliente, produto=caso.produto).prefetch_related('campos').first()

    valores_para_template = [] # Lista final para o template
    
    if estrutura:
        # Pega todos os valores que JÁ EXISTEM para este caso DE UMA VEZ.
        valores_salvos_qs = caso.valores_personalizados.select_related('campo').all()
        # Cria um dicionário para acesso rápido: {id_do_campo: objeto_valor}
        valores_salvos_dict = {valor.campo.id: valor for valor in valores_salvos_qs}

        # Itera sobre os CAMPOS DA ESTRUTURA (as definições), na ordem correta
        try:
             # Tenta ordenar pelo 'through' model 'estruturacampoordenado'
             campos_ordenados = estrutura.campos.all().order_by('estruturacampoordenado__order')
        except Exception:
             # Fallback se 'estruturacampoordenado' não existir ou falhar
             campos_ordenados = estrutura.campos.all()

        for campo_definicao in campos_ordenados:
            
            # Tenta encontrar o valor salvo no dicionário
            valor_salvo = valores_salvos_dict.get(campo_definicao.id)

            if valor_salvo:
                # --- O VALOR EXISTE NO BANCO ---
                
                # 1. TRATAMENTO DE DATA (Converte string para objeto Date)
                if campo_definicao.tipo_campo == 'DATA' and valor_salvo.valor:
                    parsed_date = None
                    # Tenta os formatos na ordem correta (AAAA-MM-DD HH:MM:SS ou AAAA-MM-DD)
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'): 
                        try:
                            # Tenta parsear a string (ex: '2025-09-22 00:00:00')
                            parsed_date = datetime.strptime(valor_salvo.valor, fmt).date()
                            break # Sucesso
                        except (ValueError, TypeError):
                            continue # Tenta o próximo formato
                    
                    valor_salvo.valor_tratado = parsed_date # Passa o OBJETO DATE (ou None se falhou)
                
                # 2. TRATAMENTO DE MOEDA (Formata a string com R$)
                elif campo_definicao.tipo_campo == 'MOEDA' and valor_salvo.valor:
                    try:
                        # Tenta converter a string (ex: "15600.00" ou "15600") para Decimal
                        valor_decimal = Decimal(valor_salvo.valor)
                        # Formata como moeda BRL (ex: "15.600,00")
                        valor_formatado = number_format(valor_decimal, decimal_pos=2, force_grouping=True)
                        valor_salvo.valor_tratado = f"R$ {valor_formatado}" # Adiciona o símbolo
                    except (InvalidOperation, ValueError, TypeError):
                        # Se falhar (ex: valor era "N/A"), apenas mostra o valor original
                        valor_salvo.valor_tratado = valor_salvo.valor
                
                # 3. OUTROS TIPOS (Texto, Número, etc.)
                else:
                    valor_salvo.valor_tratado = valor_salvo.valor 
                
                valores_para_template.append(valor_salvo)
            
            else:
                # --- O VALOR NÃO EXISTE NO BANCO ---
                # Cria um "objeto" falso (placeholder) para exibir o rótulo
                placeholder_valor = ValorCampoPersonalizado() 
                placeholder_valor.campo = campo_definicao
                placeholder_valor.valor = None
                placeholder_valor.valor_tratado = None # O template tratará isso
                
                valores_para_template.append(placeholder_valor)
    
    # ==============================================================================
    # O RESTO DO CÓDIGO DA VIEW (Sua lógica original)
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
    tempo_total = soma_tempo_obj['total_tempo'] # Já é um timedelta ou None
    
    saldo_devedor_total = Decimal('0.00')
    # Otimização: Usar o prefetch para calcular o saldo em Python
    for acordo in acordos:
        saldo_acordo = sum(p.valor_parcela for p in acordo.parcelas.all() if p.status == 'EMITIDA' and p.valor_parcela is not None)
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
            # (Mantém o print de log que você tinha)
            print(f"Erro ao buscar anexos da pasta raiz para o caso #{caso.id}: {e}")

    # Montagem do Contexto Final
    context = {
        'caso': caso,
        'form_andamento': form_andamento,
        'form_timesheet': form_timesheet,
        'form_acordo': form_acordo,
        'form_despesa': form_despesa,
        
        'valores_personalizados': valores_para_template, # <<< LISTA ATUALIZADA
        
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
    # 1. Busca os objetos principais
    caso = get_object_or_404(Caso, pk=pk)
    produto = caso.produto
    cliente = caso.cliente
    
    # 2. Monta o dicionário de dados iniciais (LÓGICA ATUALIZADA)
    dados_iniciais = {
        'status': caso.status,
        'data_entrada': caso.data_entrada,
        'data_encerramento': caso.data_encerramento,
        'advogado_responsavel': caso.advogado_responsavel,
    }
    
    # --- LÓGICA DE CAMPOS PERSONALIZADOS CORRIGIDA ---
    valores_salvos_qs = caso.valores_personalizados.select_related('campo').all()
    
    for v in valores_salvos_qs:
        chave_formulario = f'campo_personalizado_{v.campo.id}'
        valor_final = v.valor # Valor padrão (string)

        # CORREÇÃO DA LÓGICA DE PARSE DE DATA
        if v.campo.tipo_campo == 'DATA' and v.valor:
            parsed_date = None
            # Tenta os formatos na ordem correta
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'): 
                try:
                    # Tenta parsear a string COMPLETA primeiro
                    parsed_date = datetime.strptime(v.valor, fmt).date()
                    break # Sucesso
                except (ValueError, TypeError):
                    continue # Tenta o próximo formato
            
            if parsed_date:
                valor_final = parsed_date # PASSA O OBJETO DATE
            # else: mantém a string original se o parse falhar
        
        dados_iniciais[chave_formulario] = valor_final
    # --- FIM DA LÓGICA CORRIGIDA ---

    if not produto.padrao_titulo:
        dados_iniciais['titulo_manual'] = caso.titulo
        
    # 3. Processa o formulário se for uma submissão (POST)
    if request.method == 'POST':
        form = CasoDinamicoForm(request.POST, cliente=cliente, produto=produto)
        if form.is_valid():
            dados_limpos = form.cleaned_data
            
            caso.status = dados_limpos['status']
            caso.data_entrada = dados_limpos['data_entrada']
            caso.data_encerramento = dados_limpos.get('data_encerramento')
            caso.advogado_responsavel = dados_limpos.get('advogado_responsavel')
            
            # Lógica de atualizar o título (Sua lógica original)
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
                
            caso.save() # Salva campos fixos e título

            # Lógica de atualizar valores personalizados (Sua lógica original)
            estrutura = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).first()
            if estrutura:
                for campo in estrutura.campos.all():
                    valor_novo = dados_limpos.get(f'campo_personalizado_{campo.id}')
                    # Garante que o valor salvo seja uma string
                    valor_a_salvar = str(valor_novo) if valor_novo is not None else ''
                    
                    ValorCampoPersonalizado.objects.update_or_create(
                        caso=caso, 
                        campo=campo, 
                        defaults={'valor': valor_a_salvar}
                    )
                    
            return redirect('casos:detalhe_caso', pk=caso.pk)
    else:
        # 4. Se for (GET), cria o formulário passando os dados iniciais CORRIGIDOS
        form = CasoDinamicoForm(initial=dados_iniciais, cliente=cliente, produto=produto)
        
    context = {'cliente': cliente, 'produto': produto, 'form': form, 'caso': caso}
    return render(request, 'casos/criar_caso_form.html', context)

@login_required
def exportar_casos_excel(request):
    """
    Exporta os casos FILTRADOS na lista de casos.
    Utiliza a "Opção 2": Exporta TODOS os campos fixos + TODOS os campos 
    personalizados (Planilha Mestra Larga com "buracos").
    Formata as datas para DD/MM/AAAA.
    """
    logger.info(f"Iniciando Exportação Mestra de Casos para o usuário: {request.user.username}")
    
    # 1. Obter todos os filtros da URL (do request.GET)
    filtro_titulo = request.GET.get('filtro_titulo', '')
    filtro_cliente_id = request.GET.get('filtro_cliente', '')
    filtro_produto_id = request.GET.get('filtro_produto', '')
    filtro_status = request.GET.get('filtro_status', '')
    filtro_advogado_id = request.GET.get('filtro_advogado', '')

    # 2. Iniciar o QuerySet básico
    casos_queryset = Caso.objects.all().select_related(
        'cliente', 'produto', 'advogado_responsavel' # Otimiza campos fixos
    ).prefetch_related( 
        'valores_personalizados__campo' # Pré-busca TODOS os valores e o campo relacionado
    ).order_by('-data_entrada')

    # 3. Aplicar filtros (se existirem)
    if filtro_titulo:
        casos_queryset = casos_queryset.filter(titulo__icontains=filtro_titulo)
    if filtro_status:
        casos_queryset = casos_queryset.filter(status=filtro_status)
    if filtro_advogado_id:
        casos_queryset = casos_queryset.filter(advogado_responsavel_id=filtro_advogado_id)
    if filtro_cliente_id:
        casos_queryset = casos_queryset.filter(cliente_id=filtro_cliente_id)
    if filtro_produto_id:
        casos_queryset = casos_queryset.filter(produto_id=filtro_produto_id)

    total_casos = casos_queryset.count()
    logger.debug(f"Queryset filtrado. {total_casos} casos para exportar.")
    
    if total_casos == 0:
        messages.warning(request, "Nenhum caso encontrado com os filtros aplicados. Nada para exportar.")
        return redirect('casos:lista_casos')

    # 4. Obter Cabeçalho MESTRE (Fixos + TODOS os Personalizados)
    # Chamamos a função SEM argumentos de cliente/produto
    try:
        # AGORA RECEBE O MAPA DE TIPOS
        lista_chaves, lista_cabecalhos, campos_tipo_map = get_cabecalho_exportacao(cliente=None, produto=None)
    except Exception as e:
        logger.error(f"Erro ao gerar cabeçalho mestre: {e}", exc_info=True)
        messages.error(request, "Erro ao gerar o cabeçalho da exportação.")
        return redirect('casos:lista_casos')
    
    logger.debug(f"Cabeçalho Mestre gerado com {len(lista_cabecalhos)} colunas.")
    
    # 5. Gerar o Arquivo Excel
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Exportacao Mestra Casos'
    
    sheet.append(lista_cabecalhos) # Linha 1 (Nomes de Exibição)
    
    # Opcional: Adicionar a linha de 'nome_variavel' (Linha 2)
    # sheet.append(lista_chaves) 
    
    # 6. Adicionar Linhas de Dados
    for caso in casos_queryset:
        linha_dados = []
        
        # Mapeia os valores personalizados DESTE caso
        # {'personalizado_aviso': '123', 'personalizado_cpf': '456'}
        valores_personalizados_case = {
            f'personalizado_{v.campo.nome_variavel}': v.valor 
            for v in caso.valores_personalizados.all() # Usa o prefetch
        }
        
        for chave in lista_chaves:
            valor = '' # Valor padrão agora é vazio (para os "buracos")

            # --- Campo Fixo ---
            if not chave.startswith('personalizado_'):
                if '__' in chave: # Ex: cliente__nome
                    try:
                        partes = chave.split('__')
                        obj = getattr(caso, partes[0], None)
                        valor = getattr(obj, partes[1], '') if obj else ''
                    except Exception: valor = ''
                elif chave == 'status': # Ex: get_status_display
                    valor = caso.get_status_display()
                else: # Ex: id, data_entrada
                    valor = getattr(caso, chave, '')
            
            # --- Campo Personalizado ---
            else:
                # Busca a chave (ex: 'personalizado_aviso') no dict do caso
                # Se o caso não tiver esse campo (produto diferente), o get retorna ''
                valor = valores_personalizados_case.get(chave, '') 
            
            # --- FORMATAÇÃO UNIVERSAL DE DATA (NOVO BLOCO) ---
            tipo_do_campo = campos_tipo_map.get(chave) # Pega o tipo (Fixo ou Personalizado)
            
            # 1. Se for um objeto de data/datetime (Campos Fixos como data_entrada)
            if isinstance(valor, (datetime, date)):
                 valor = valor.strftime('%d/%m/%Y')
            
            # 2. Se for um campo tipo 'DATA' (Campos Personalizados, que são strings)
            elif tipo_do_campo == 'DATA' and valor:
                parsed_date = None
                # Tenta formatos comuns (incluindo o que você mostrou: AAAA-MM-DD HH:MM:SS)
                # Adiciona mais formatos se necessário (ex: DD/MM/AAAA)
                formatos_data = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y') 
                for fmt in formatos_data:
                    try:
                        # Tira a parte da hora se houver (ex: .split(' ')[0])
                        # Mas como %H:%M:%S está no formato, podemos tentar direto
                        parsed_date = datetime.strptime(str(valor), fmt).date()
                        break # Se funcionou, para o loop
                    except (ValueError, TypeError):
                        continue # Tenta o próximo formato
                
                if parsed_date:
                    valor = parsed_date.strftime('%d/%m/%Y') # Formata para o Excel
                else:
                    valor = str(valor) # Mantém a string original se não conseguir parsear
            
            # 3. Converte o resto para string
            else:
                valor = str(valor) if valor is not None else ''
                
            linha_dados.append(valor) 

        sheet.append(linha_dados)
            
    # 7. Retornar a Resposta
    output = BytesIO() 
    workbook.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Define o nome do arquivo que o usuário fará download
    filename = 'casos_export_mestre_filtrado.xlsx' 
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    logger.info(f"Exportação Mestra ({total_casos} casos) concluída e enviada.")
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

class CasoAPIViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite que casos sejam visualizados, criados, atualizados ou deletados.
    """
    queryset = Caso.objects.all().order_by('-data_criacao')
    serializer_class = CasoSerializer

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    # Exemplo: Permite acesso apenas a usuários autenticados
    # permission_classes = [IsAuthenticated] 

    # Sobrescrevendo o método create para lidar com a criação
    def create(self, request, *args, **kwargs):
        # A lógica do serializador já cuidará da maioria das validações.
        # Aqui você pode adicionar lógica customizada antes de salvar.
        # Por exemplo, definir o advogado_responsavel automaticamente se não for fornecido.
        
        # O DRF já trata `cliente` e `produto` como IDs graças a PrimaryKeyRelatedField
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # Sobrescrevendo o método update (para PUT) e partial_update (para PATCH)
    def perform_update(self, serializer):
        # Você pode adicionar lógica customizada aqui antes de salvar a atualização
        # Por exemplo, se o status mudar para 'ENCERRADO', definir data_encerramento
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == 'ENCERRADO':
            if not serializer.instance.data_encerramento:
                serializer.validated_data['data_encerramento'] = timezone.now().date() # Aqui usa
        serializer.save()

    # Se você precisar de um endpoint específico para buscar por external_id (e não pelo ID do Django)
    # Exemplo: /api/casos/by_external_id/CASO-N8N-001/
    # Isso exigiria uma rota extra no urls.py
    # @action(detail=False, methods=['get'], url_path='by_external_id/(?P<external_id>[^/.]+)')
    # def by_external_id(self, request, external_id=None):
    #     caso = get_object_or_404(Caso, external_id=external_id)
    #     serializer = self.get_serializer(caso)
    #     return Response(serializer.data)


@login_required
def selecionar_filtros_exportacao(request):
    """
    Tela que permite ao usuário selecionar o Cliente e o Produto 
    para definir o escopo da exportação (o que define os campos personalizados).
    """
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        
        # A validação básica é feita pelo HTML
        if cliente_id and produto_id:
            # Redireciona para a URL de exportação dinâmica
            return redirect('casos:exportar_casos_dinamico', cliente_id=cliente_id, produto_id=produto_id)
            
    # Lógica GET: Carrega todos os clientes e produtos para os <select>
    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    
    context = {
        'clientes': clientes, 
        'produtos': produtos,
        'titulo': 'Exportação Dinâmica de Casos'
    }
    return render(request, 'casos/selecionar_filtros_exportacao.html', context)


@login_required
def exportar_casos_dinamico(request, cliente_id, produto_id):
    """
    Busca os dados dos Casos (fixos e personalizados) para a combinação Cliente/Produto 
    e gera um arquivo Excel dinâmico.
    """
    
    # Busca o Cliente e Produto, retornando 404 se não existirem
    cliente = get_object_or_404(Cliente, id=cliente_id)
    produto = get_object_or_404(Produto, id=produto_id)

    # 1. Obter Cabeçalhos e Chaves Dinamicamente
    # lista_chaves: ['id', 'titulo', 'cliente__nome', 'personalizado_numero_processo', ...]
    lista_chaves, lista_cabecalhos = get_cabecalho_exportacao(cliente, produto)
    
    # 2. Filtrar Casos
    # Filtra os casos da combinação, e pré-busca os relacionamentos (select_related)
    # e os valores personalizados (prefetch_related) para otimizar o banco de dados.
    casos_queryset = Caso.objects.filter(
        cliente=cliente, 
        produto=produto
    ).select_related(
        'cliente', 
        'produto', 
        'advogado_responsavel' # Exemplo de FK que pode estar nos fixos
    ).prefetch_related(
        'valores_personalizados__campo' # Busca os valores e os metadados do campo
    ).order_by('-data_entrada')
    
    # 3. Preparar a Exportação (OpenPyXL)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f'Export_{produto.nome[:30]}' # Limita o título da aba
    
    # Adicionar o Cabeçalho
    sheet.append(lista_cabecalhos)
    sheet.append(lista_chaves)
    
    # 4. Adicionar Linhas de Dados
    for caso in casos_queryset:
        linha_dados = []
        
        # Mapeia os valores personalizados para acesso rápido
        # {'personalizado_nome_variavel': valor, ...}
        valores_personalizados_case = {
            f'personalizado_{v.campo.nome_variavel}': v.valor 
            for v in caso.valores_personalizados.all()
        }
        
        for chave in lista_chaves:
            valor = '-' # Valor padrão se a chave não for encontrada

            # --- TRATAMENTO DE CAMPOS FIXOS (sem prefixo 'personalizado_') ---
            if not chave.startswith('personalizado_'):
                
                # 1. Trata campos de Foreign Key (FK) para mostrar o nome (Ex: cliente__nome)
                if '__' in chave:
                    partes = chave.split('__')
                    # Tenta acessar o objeto FK (e.g., caso.cliente) e depois o atributo (e.g., .nome)
                    obj = getattr(caso, partes[0], None)
                    valor = getattr(obj, partes[1], '-') if obj else '-'
                
                # 2. Trata campos de status (mostra o nome de exibição)
                elif chave == 'status':
                    valor = caso.get_status_display()
                
                # 3. Trata campos simples (acessa o atributo direto)
                else:
                    valor = getattr(caso, chave, '-')
            
            # --- TRATAMENTO DE CAMPOS PERSONALIZADOS ---
            else:
                # A chave tem o formato 'personalizado_nome_variavel'
                valor = valores_personalizados_case.get(chave, '-')
            
            # Garante que o valor é uma string para a planilha (evita erros de tipo)
            linha_dados.append(str(valor)) 

        sheet.append(linha_dados)
        
    # 5. Retornar a Resposta
    # Usa BytesIO para criar o arquivo Excel na memória antes de enviar
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Define o nome do arquivo que o usuário fará download
    filename = f'casos_exportados_{cliente.nome}_{produto.nome}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

# NOTA: O fluxo de controle (redirecionamento após o POST) já foi implementado 
# na view 'selecionar_filtros_exportacao' (Passo 1).

@login_required
def importar_casos_view(request):
    """
    Exibe o formulário de upload (GET) ou recebe o arquivo Excel (POST)
    e despacha as tarefas de importação para o Celery.
    """
    
    # --- Lógica GET: Exibir o formulário ---
    if request.method == 'GET':
        try:
            clientes = Cliente.objects.all().order_by('nome')
            produtos = Produto.objects.all().order_by('nome')
            
            # --- GARANTE QUE CONTEXT É UM DICIONÁRIO ---
            context = {
                'clientes': clientes,
                'produtos': produtos,
                'titulo': 'Importação Massiva de Casos' # Título para o <title> da página
            }
            # ----------------------------------------
            return render(request, 'casos/importar_casos_form.html', context)
        
        except Exception as e:
            logger.error(f"Erro ao carregar a página de importação (GET): {e}", exc_info=True)
            messages.error(request, "Erro ao carregar a página. Tente novamente.")
            # Redireciona para um local seguro, como a lista de casos
            return redirect('casos:lista_casos') # Ou 'home'

    # --- Lógica POST: Processar o upload ---
    elif request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        arquivo_excel = request.FILES.get('arquivo_excel')

        # Validação básica dos campos do formulário
        if not (cliente_id and produto_id and arquivo_excel):
            messages.error(request, "Todos os campos (Cliente, Produto e Arquivo) são obrigatórios.")
            # Recarrega a página GET com os selects
            clientes_qs = Cliente.objects.all().order_by('nome')
            produtos_qs = Produto.objects.all().order_by('nome')
            context = {'clientes': clientes_qs, 'produtos': produtos_qs, 'titulo': 'Importação Massiva de Casos'}
            return render(request, 'casos/importar_casos_form.html', context) # Renderiza de novo com erro

        try:
            cliente = get_object_or_404(Cliente, id=cliente_id)
            produto = get_object_or_404(Produto, id=produto_id)

            # --- Lógica de Leitura da Planilha e Envio para Celery ---
            logger.info(f"Recebido arquivo '{arquivo_excel.name}' para importação (Cliente ID: {cliente_id}, Produto ID: {produto_id}). User: {request.user.username}")

            # Obter Chaves Válidas e Estrutura de Campos
            lista_chaves_validas, _ = get_cabecalho_exportacao(cliente, produto)
            chaves_validas_set = set(lista_chaves_validas) # Converte para set para busca rápida O(1)
            estrutura_campos = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).prefetch_related('campos').first()

            # Mapa {nome_variavel_original: objeto CampoPersonalizado}
            campos_meta_map = {cm.nome_variavel: cm for cm in estrutura_campos.campos.all()} if estrutura_campos else {}
            logger.debug(f"View - Campos Personalizados encontrados para esta estrutura: {list(campos_meta_map.keys())}")

            # Carregar e Ler Planilha
            workbook = openpyxl.load_workbook(arquivo_excel, data_only=True) # data_only=True tenta ler valores em vez de fórmulas
            sheet = workbook.active
            logger.info(f"View - Arquivo Excel carregado. Planilha: '{sheet.title}'. Total Linhas (incl. header): {sheet.max_row}")

            if sheet.max_row < 2:
                 raise ValidationError("A planilha não contém dados para importar (está vazia ou tem apenas o cabeçalho).")

            # Ler e Normalizar Cabeçalho
            excel_headers_raw = [cell.value for cell in sheet[1]]
            # Normaliza: string, minúsculas, remove espaços extras, troca espaço por underscore
            excel_headers = [str(h).strip().lower().replace(' ', '_') if h else '' for h in excel_headers_raw]
            logger.info(f"View - Cabeçalhos lidos da planilha: {excel_headers_raw}")
            logger.debug(f"View - Cabeçalhos normalizados para mapeamento: {excel_headers}")

            # --- LÓGICA REVISADA E FINAL PARA CRIAR O HEADER_MAP ---
            header_map = {} # {excel_header_norm: nome_variavel_original OU chave_fixa}
            
            # Mapa auxiliar {nome_variavel MINÚSCULO: nome_variavel ORIGINAL}
            # Ex: {'aviso': 'aviso'} (se o seu nome_variavel for 'aviso' minúsculo)
            variaveis_personalizadas_lower = {
                nome_var.lower(): nome_var
                for nome_var in campos_meta_map.keys() # Itera sobre as chaves originais do mapa de metadados
            }
            logger.debug(f"View - Mapa auxiliar de variáveis personalizadas (lower -> original): {variaveis_personalizadas_lower}")

            # Itera sobre os cabeçalhos NORMALIZADOS do Excel
            for excel_header_norm in excel_headers:
                if not excel_header_norm: continue # Pula cabeçalhos vazios

                logger.debug(f"View - Processando header normalizado: '{excel_header_norm}'")
                chave_mapeada = None # Guarda a chave final que será usada no mapa

                # Tentativa 1: É um campo fixo EXATO e válido?
                chave_fixa = excel_header_norm # Ex: 'data_entrada'
                # Verifica se está na lista de chaves válidas E não tem prefixo/separador que indicaria personalizado ou FK
                if chave_fixa in chaves_validas_set and not chave_fixa.startswith('personalizado_') and '__' not in chave_fixa:
                    chave_mapeada = chave_fixa
                    logger.debug(f"View - Header '{excel_header_norm}' mapeado como Chave Fixa '{chave_mapeada}'")
                
                # Tentativa 2: É um campo personalizado (busca case-insensitive)?
                # Procura o cabeçalho normalizado do Excel (ex: 'aviso') no mapa de minúsculas
                elif excel_header_norm in variaveis_personalizadas_lower:
                    # Pega o nome_variavel ORIGINAL (ex: 'aviso')
                    nome_variavel_original = variaveis_personalizadas_lower[excel_header_norm]
                    # Verifica se a chave completa com prefixo está na lista de válidas (segurança extra)
                    chave_completa_pers = f'personalizado_{nome_variavel_original}'
                    if chave_completa_pers in chaves_validas_set:
                        chave_mapeada = nome_variavel_original # O mapa final terá {excel_header_norm : nome_variavel_original}
                        logger.debug(f"View - Header '{excel_header_norm}' mapeado como Nome Variável Personalizado '{chave_mapeada}' (Case-insensitive)")
                    else:
                        logger.warning(f"View - Header '{excel_header_norm}' parece personalizado mas a chave '{chave_completa_pers}' não está na lista de válidas. Ignorando.")

                # Tentativa 3 (Fallback para Excel com prefixo 'personalizado_'):
                elif excel_header_norm.startswith('personalizado_'):
                     nome_base = excel_header_norm.split('personalizado_', 1)[1]
                     if nome_base in variaveis_personalizadas_lower:
                          nome_variavel_original = variaveis_personalizadas_lower[nome_base]
                          chave_completa_pers = f'personalizado_{nome_variavel_original}'
                          if chave_completa_pers in chaves_validas_set:
                              chave_mapeada = nome_variavel_original
                              logger.debug(f"View - Header com prefixo '{excel_header_norm}' mapeado para Nome Variável '{chave_mapeada}' (Fallback)")
                          else:
                              logger.warning(f"View - Header com prefixo '{excel_header_norm}' ignorado (chave completa '{chave_completa_pers}' inválida).")
                     else:
                          logger.warning(f"View - Header com prefixo '{excel_header_norm}' ignorado (nome base '{nome_base}' não encontrado).")
                
                # Adiciona ao mapa final se alguma tentativa funcionou
                if chave_mapeada:
                    header_map[excel_header_norm] = chave_mapeada
                # Se não mapeou (e não era vazio)
                elif excel_header_norm:
                    logger.warning(f"View - Cabeçalho da planilha '{excel_header_norm}' não corresponde a nenhum campo válido e será ignorado.")
            
            logger.info(f"View - Mapa final de cabeçalhos criado para tarefa Celery: {header_map}")
            # --- FIM DA CORREÇÃO DO HEADER_MAP ---

            # Validação: Garante que algum cabeçalho útil foi mapeado
            mapeamentos_uteis = {k: v for k, v in header_map.items() if k != '_row_index'}
            if not mapeamentos_uteis:
                raise ValidationError("Nenhum cabeçalho na planilha corresponde aos campos fixos ou personalizados esperados. Verifique se os nomes das colunas batem com os 'Nomes da Variável' (ex: 'aviso') ou campos fixos (ex: 'status').")

            # Preparar e Enviar Tarefas para Celery
            total_linhas = sheet.max_row - 1
            delay_segundos = 10 # 3 minutos
            linhas_enviadas = 0

            logger.info(f"Enviando {total_linhas} tarefas para o Celery com delay de {delay_segundos}s entre cada uma.")

            # Cria mapa {nome_variavel_original: campo_id} para passar à task
            campos_meta_map_serializable = {nome_var: campo.id for nome_var, campo in campos_meta_map.items()}

            for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                 # Monta o dicionário de dados da linha {excel_header_norm: valor}
                 linha_dados = dict(zip(excel_headers, row))
                 linha_dados['_row_index'] = row_index # Adiciona índice para logging na task

                 # Filtra linha_dados para enviar apenas colunas mapeadas (opcional, economiza dados)
                 linha_dados_mapeada = {k: v for k, v in linha_dados.items() if k in header_map or k == '_row_index'}
                 
                 # Pula linhas completamente vazias que o openpyxl pode ler
                 if not any(v for k, v in linha_dados_mapeada.items() if k != '_row_index' and v is not None):
                     logger.info(f"View - Linha {row_index} pulada (vazia ou sem dados mapeáveis).")
                     continue

                 logger.debug(f"View - Enviando linha {row_index} para Celery. Dados Mapeados: {linha_dados_mapeada}")

                 # Envia a tarefa Celery com atraso
                 processar_linha_importacao.apply_async(
                     args=[
                         linha_dados_mapeada, # Envia apenas dados mapeados
                         cliente.id,
                         produto.id,
                         header_map, # Passa o mapa {excel_header_norm: nome_var_original ou chave_fixa}
                         list(chaves_validas_set), # Passa como lista
                         campos_meta_map_serializable, # Passa o mapa {nome_var_original: campo_id}
                         produto.padrao_titulo, # Passa a string do padrão de título
                         estrutura_campos.id if estrutura_campos else None
                     ],
                     countdown=linhas_enviadas * delay_segundos # Atraso cumulativo
                 )
                 linhas_enviadas += 1
            
            if linhas_enviadas == 0:
                 messages.warning(request, "Nenhuma linha válida para importar foi encontrada na planilha (após o cabeçalho).")
                 return redirect('casos:importar_casos_view')

            messages.success(request, f"Importação iniciada com sucesso! {linhas_enviadas} casos foram enviados para processamento em background (um a cada {delay_segundos // 60} minutos). Acompanhe os logs do Celery para o progresso.")
            # Redireciona de volta para a mesma página após o envio
            return redirect('casos:importar_casos_view')
            # --- Fim da Lógica de Leitura e Envio ---

        # Tratamento de Erros durante o processamento do Upload (antes de enviar ao Celery)
        except ValidationError as e:
            logger.error(f"Erro de validação no upload da importação: {e.message}")
            messages.error(request, f"Erro na Importação: {e.message}")
            # Recarrega a página GET com os selects em caso de erro de validação
            clientes_qs = Cliente.objects.all().order_by('nome')
            produtos_qs = Produto.objects.all().order_by('nome')
            context = {'clientes': clientes_qs, 'produtos': produtos_qs, 'titulo': 'Importação Massiva de Casos'}
            return render(request, 'casos/importar_casos_form.html', context)
        except Exception as e:
            logger.error(f"Erro inesperado ao iniciar a importação: {str(e)}", exc_info=True)
            messages.error(request, f"Erro inesperado ao iniciar a importação. Verifique o arquivo ou contate o suporte.")
            # Redireciona de volta para a página de importação em caso de erro geral
            return redirect('casos:importar_casos_view')

    # Se não for GET nem POST (improvável)
    logger.warning(f"Recebida requisição {request.method} inesperada para importar_casos_view.")
    return redirect('casos:importar_casos_view') # Redireciona por segurança

def processar_importacao_excel(request, cliente_id, produto_id, arquivo_excel):
    logger.info(f"Iniciando importação (Criação Apenas) para Cliente ID {cliente_id}, Produto ID {produto_id}")
    
    current_user = request.user # Pode ser útil para logs ou campos 'criado_por'
    cliente = get_object_or_404(Cliente, id=cliente_id)
    produto = get_object_or_404(Produto, id=produto_id)
    
    # 1. Obter Chaves Válidas (para saber quais colunas processar)
    # Usamos a função de cabeçalho para saber quais campos existem para esta combinação C+P
    lista_chaves_validas, _ = get_cabecalho_exportacao(cliente, produto)
    chaves_validas_set = set(lista_chaves_validas)
    logger.debug(f"Chaves válidas esperadas para esta estrutura: {lista_chaves_validas}")

    # Busca a ESTRUTURA para a geração de título e mapeamento de campos
    estrutura_campos = EstruturaDeCampos.objects.filter(cliente=cliente, produto=produto).prefetch_related('campos').first()
    if not estrutura_campos:
         logger.error(f"Nenhuma EstruturaDeCampos encontrada para Cliente {cliente_id} e Produto {produto_id}.")
         messages.error(request, "Nenhuma estrutura de campos personalizados encontrada para esta combinação de Cliente e Produto.")
         return redirect('casos:importar_casos_view')
         
    # Cria um mapa {nome_variavel: objeto_CampoPersonalizado} para acesso rápido
    campos_meta_map = {cm.nome_variavel: cm for cm in estrutura_campos.campos.all()}

    # 2. Ler Excel
    try:
        workbook = openpyxl.load_workbook(arquivo_excel)
        sheet = workbook.active
        logger.info(f"Arquivo Excel '{arquivo_excel.name}' carregado. Planilha: '{sheet.title}'")
    except Exception as e:
        logger.error(f"Erro ao carregar Excel: {e}", exc_info=True)
        raise ValidationError("O arquivo não é um Excel válido (.xlsx) ou está corrompido.")

    # 3. Ler Cabeçalho da Planilha
    if sheet.max_row < 2:
         logger.warning("Planilha vazia ou contém apenas o cabeçalho.")
         raise ValidationError("A planilha não contém dados para importar (mínimo 2 linhas).")

    excel_headers_raw = [cell.value for cell in sheet[1]]
    # Normaliza: minúsculas, troca espaço por underscore
    excel_headers = [str(h).strip().lower().replace(' ', '_') if h else '' for h in excel_headers_raw]
    logger.info(f"Cabeçalhos lidos: {excel_headers_raw}")
    logger.debug(f"Cabeçalhos normalizados: {excel_headers}")

    # 4. Criar Mapa de Cabeçalhos (Excel -> Chave Interna Django)
    header_map = {} # {excel_header_norm: chave_interna_valida}
    for excel_header_norm in excel_headers:
        # Tentativa 1: Nome exato (campos fixos como 'data_entrada', 'status')
        if excel_header_norm in chaves_validas_set:
            header_map[excel_header_norm] = excel_header_norm
        # Tentativa 2: Nome da variável de campo personalizado (ex: excel 'numero_processo' -> django 'personalizado_numero_processo')
        else:
            chave_possivel = f'personalizado_{excel_header_norm}'
            if chave_possivel in chaves_validas_set:
                header_map[excel_header_norm] = chave_possivel
            else:
                 logger.warning(f"Cabeçalho '{excel_header_norm}' da planilha não corresponde a nenhum campo fixo ou personalizado válido. Será ignorado.")
    logger.debug(f"Mapa de cabeçalhos: {header_map}") 
    
    # Validação Mínima: Garante que pelo menos um campo reconhecido existe
    if not header_map:
        logger.error("Nenhum cabeçalho na planilha corresponde aos campos esperados.")
        raise ValidationError("O cabeçalho da planilha não corresponde aos campos fixos ou personalizados esperados para esta combinação Cliente/Produto.")


    # 5. Iniciar Transação
    casos_criados = 0
    linhas_processadas = 0
    erros_linhas = [] # Guarda erros por linha

    try:
        with transaction.atomic():
            # Iterar pelas linhas
            for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                linhas_processadas += 1
                logger.debug(f"Processando linha {row_index}...")

                dados_caso_fixos = {}
                dados_personalizados_para_salvar = {} # {objeto_CampoPersonalizado: valor}
                dados_personalizados_para_titulo = {} # {nome_variavel: valor}

                row_data_dict = dict(zip(excel_headers, row))
                logger.debug(f"Dados brutos linha {row_index}: {row_data_dict}")

                # Flag para saber se a linha tem dados válidos
                linha_valida = False

                # Mapear dados da linha
                for header_norm, cell_value in row_data_dict.items():
                    # Ignora células vazias E cabeçalhos não mapeados
                    if cell_value is None or not header_norm or header_norm not in header_map: 
                        continue
                        
                    chave_interna = header_map[header_norm]
                    linha_valida = True # Marcar que a linha tem pelo menos um dado útil

                    # --- Processar Valor (Campos Fixos) ---
                    if not chave_interna.startswith('personalizado_') and '__' not in chave_interna:
                        campo_caso = chave_interna # Ex: 'data_entrada'
                        
                        # TRATAMENTO DE DATA (Exemplo)
                        if campo_caso in ['data_entrada', 'data_encerramento']:
                             if isinstance(cell_value, datetime):
                                dados_caso_fixos[campo_caso] = cell_value.date()
                             elif isinstance(cell_value, date):
                                 dados_caso_fixos[campo_caso] = cell_value
                             else: # Tentar parsear string AAAA-MM-DD
                                 try:
                                     # Tenta formato AAAA-MM-DD primeiro
                                     dados_caso_fixos[campo_caso] = datetime.strptime(str(cell_value).split(' ')[0], '%Y-%m-%d').date()
                                 except (ValueError, TypeError):
                                     try:
                                         # Tenta formato DD/MM/AAAA (comum no Brasil)
                                         dados_caso_fixos[campo_caso] = datetime.strptime(str(cell_value).split(' ')[0], '%d/%m/%Y').date()
                                     except (ValueError, TypeError):
                                         logger.warning(f"Valor de data inválido '{cell_value}' na linha {row_index}, coluna '{header_norm}'. Ignorando campo.")
                        
                        # TRATAMENTO DE STATUS (Exemplo: Aceitar 'Ativo' ou 'ATIVO')
                        elif campo_caso == 'status':
                            # Normaliza para a chave interna (ex: 'ATIVO')
                            valor_status = str(cell_value).strip().upper()
                            # Valida se é uma chave válida (opcional, mas bom)
                            if any(valor_status == choice[0] for choice in Caso.STATUS_CHOICES):
                                dados_caso_fixos[campo_caso] = valor_status
                            else:
                                logger.warning(f"Valor de status inválido '{cell_value}' na linha {row_index}. Ignorando campo.")
                        
                        # Outros campos fixos
                        else:
                            dados_caso_fixos[campo_caso] = cell_value
                    
                    # --- Processar Valor (Campos Personalizados) ---
                    elif chave_interna.startswith('personalizado_'):
                        nome_variavel = chave_interna.split('personalizado_')[1]
                        valor_str = str(cell_value)
                        dados_personalizados_para_titulo[nome_variavel] = valor_str
                        
                        campo_meta = campos_meta_map.get(nome_variavel)
                        if campo_meta:
                            dados_personalizados_para_salvar[campo_meta] = valor_str
                        else:
                            logger.warning(f"Metadados para nome_variavel '{nome_variavel}' (coluna '{header_norm}') não encontrados na estrutura. Valor ignorado.")

                # Se a linha não tinha nenhum dado mapeado, pular
                if not linha_valida:
                    logger.info(f"Linha {row_index} ignorada por não conter dados mapeáveis.")
                    continue

                # 6. Criar o Caso (sem título)
                try:
                    # Garante que campos obrigatórios (sem default) tenham algum valor
                    if 'data_entrada' not in dados_caso_fixos:
                         dados_caso_fixos['data_entrada'] = date.today() # Define um padrão se ausente
                         logger.warning(f"Linha {row_index}: 'data_entrada' não fornecida, usando data atual.")
                    # Adicione outras validações de campos obrigatórios aqui se necessário

                    novo_caso = Caso.objects.create(
                        cliente=cliente,
                        produto=produto,
                        titulo="[Título Pendente]", # Título temporário
                        **dados_caso_fixos
                    )
                    logger.info(f"Caso preliminar criado (ID {novo_caso.id}) para linha {row_index}.")
                except IntegrityError as e:
                    erro_msg = f"Erro de integridade ao criar caso para linha {row_index}: {e}. Dados: {dados_caso_fixos}"
                    logger.error(erro_msg)
                    erros_linhas.append(f"Linha {row_index}: {erro_msg}")
                    continue # Pula para a próxima linha

                # 7. Salvar Campos Personalizados
                for campo_meta, valor_a_salvar in dados_personalizados_para_salvar.items():
                    ValorCampoPersonalizado.objects.create(
                        caso=novo_caso,
                        campo=campo_meta,
                        valor=valor_a_salvar
                    )
                logger.debug(f"Campos personalizados salvos para caso ID {novo_caso.id}")

                # 8. Gerar Título (Copie/Adapte sua lógica de criar_caso)
                titulo_final = f"Caso Importado #{novo_caso.id}" # Título Padrão se a lógica falhar
                
                # VERIFIQUE SE ESTE BLOCO 'IF' EXISTE E ESTÁ CORRETO
                if produto.padrao_titulo and estrutura_campos: 
                    titulo_formatado = produto.padrao_titulo
                    logger.debug(f"Iniciando geração de título para caso {novo_caso.id} com padrão: '{titulo_formatado}'") # LOG
                    
                    # Usa os dados que já mapeamos e salvamos
                    # 'dados_personalizados_para_titulo' deve ter {nome_variavel: valor}
                    for campo_estrutura in estrutura_campos.campos.all(): 
                        chave_variavel = campo_estrutura.nome_variavel
                        # Pega o valor do dicionário que montamos ao ler a linha
                        valor = dados_personalizados_para_titulo.get(chave_variavel, '') 
                        placeholder = f'{{{chave_variavel}}}'
                        logger.debug(f"Substituindo '{placeholder}' por '{valor}'") # LOG
                        titulo_formatado = titulo_formatado.replace(placeholder, str(valor))
                        
                    titulo_final = titulo_formatado
                    logger.info(f"Título gerado para caso ID {novo_caso.id}: '{titulo_final}'") # LOG
                else:
                    logger.warning(f"Não foi possível gerar título automático para caso {novo_caso.id}. Produto sem padrão ou estrutura não encontrada.") # LOG
                
                # VERIFIQUE SE ESTE SAVE EXISTE
                # Salva o título no caso recém-criado
                novo_caso.titulo = titulo_final
                novo_caso.save(update_fields=['titulo']) 
                logger.info(f"Título final salvo para caso ID {novo_caso.id}.") # LOG
                # --- FIM DA GERAÇÃO DE TÍTULO ---
                casos_criados += 1

            # Fim do Loop pelas linhas

            # Se houve erros em linhas específicas, informa o usuário mas NÃO reverte a transação
            if erros_linhas:
                 messages.warning(request, 
                     f"Importação concluída com {len(erros_linhas)} erros em linhas específicas (verifique os logs). {casos_criados} casos foram criados com sucesso."
                 )
            else:
                 messages.success(request, 
                     f"Importação concluída com sucesso! {casos_criados} novos casos foram criados."
                 )
            
            # Se você quisesse reverter TUDO em caso de QUALQUER erro de linha:
            # if erros_linhas:
            #    raise ValidationError("Houve erros durante a importação. Nenhuma linha foi salva.")

            return redirect('casos:importar_casos_view') # Redireciona para a lista

    except ValidationError as e: # Captura erros de validação gerais (arquivo, cabeçalho)
        logger.error(f"Erro de validação durante importação: {e.message}")
        messages.error(request, f"Erro na Importação: {e.message}")
    except Exception as e: # Captura outros erros inesperados
        logger.error(f"Erro inesperado durante importação: {str(e)}", exc_info=True)
        messages.error(request, f"Erro inesperado durante a importação. Verifique os logs do servidor.")
        
    # Se chegou aqui, houve um erro antes ou durante a transação
    logger.warning("Redirecionando de volta ao formulário devido a erro.")
    return redirect('casos:importar_casos_view')