# casos/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from clientes.models import Cliente
from produtos.models import Produto
from .models import Caso
from campos_custom.models import CampoPersonalizado,ValorCampoPersonalizado 
from .forms import CasoDinamicoForm

@login_required
def selecionar_produto_cliente(request):
    # --- LÓGICA ADICIONADA ---
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        
        # Validação para garantir que ambos foram selecionados
        if cliente_id and produto_id:
            # Redireciona para a URL do Passo 2, passando os IDs
            return redirect('casos:criar_caso', cliente_id=cliente_id, produto_id=produto_id)
        # Se algo der errado (não deveria acontecer com 'required'), apenas recarrega a página
    # --- FIM DA LÓGICA ADICIONADA ---

    clientes = Cliente.objects.all().order_by('nome')
    produtos = Produto.objects.all().order_by('nome')
    
    context = {
        'clientes': clientes,
        'produtos': produtos,
    }
    return render(request, 'casos/selecionar_produto_cliente.html', context)

@login_required
def criar_caso(request, cliente_id, produto_id):
    cliente = Cliente.objects.get(id=cliente_id)
    produto = Produto.objects.get(id=produto_id)

    if request.method == 'POST':
        # Passamos o produto para o formulário saber quais campos criar
        form = CasoDinamicoForm(request.POST, produto=produto)
        if form.is_valid():
            # form.cleaned_data contém os dados já validados e convertidos!
            dados_limpos = form.cleaned_data
            
            # Lógica para montar o título (como fizemos antes)
            titulo_final = ""
            valores_para_titulo = {cp.nome_campo.replace(" ", ""): dados_limpos.get(f'campo_personalizado_{cp.id}') 
                                   for cp in produto.campos_personalizados.all()}

            if produto.padrao_titulo:
                titulo_final = produto.padrao_titulo.format(**valores_para_titulo)
            else:
                titulo_final = dados_limpos.get('titulo_manual', '')

            # Cria o caso com os dados limpos do formulário
            novo_caso = Caso.objects.create(
                cliente=cliente,
                produto=produto,
                data_entrada=dados_limpos['data_entrada'],
                status=dados_limpos['status'],
                data_encerramento=dados_limpos.get('data_encerramento'),
                titulo=titulo_final
            )

            # Salva os valores dos campos personalizados
            for campo in produto.campos_personalizados.all():
                valor = dados_limpos.get(f'campo_personalizado_{campo.id}')
                if valor:
                    ValorCampoPersonalizado.objects.create(
                        caso=novo_caso,
                        campo=campo,
                        valor=valor
                    )

            return redirect('casos:lista_casos') # Redireciona para a lista (que faremos depois)
    else:
        # Cria um formulário em branco, passando o produto
        form = CasoDinamicoForm(produto=produto)
    
    context = {
        'cliente': cliente,
        'produto': produto,
        'form': form, # Passamos o objeto de formulário para o template
    }
    return render(request, 'casos/criar_caso_form.html', context)

@login_required
def lista_casos(request):
    # Usamos select_related para otimizar a busca, pegando os dados
    # de cliente e produto na mesma consulta ao banco.
    casos_list = Caso.objects.select_related('cliente', 'produto').all().order_by('-data_entrada')

    # Lógica de filtro (podemos adicionar depois, como fizemos para clientes)
    
    context = {
        'casos': casos_list,
    }
    return render(request, 'casos/lista_casos.html', context)