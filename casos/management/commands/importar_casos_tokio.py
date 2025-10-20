# casos/management/commands/importar_casos_tokio.py

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from clientes.models import Cliente
from produtos.models import Produto
from casos.models import Caso
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado

class Command(BaseCommand):
    help = 'Importa casos do produto Tokio RCG a partir de uma planilha Excel.'

    def add_arguments(self, parser):
        parser.add_argument('caminho_excel', type=str, help='O caminho para o arquivo .xlsx')

    @transaction.atomic
    def handle(self, *args, **options):
        caminho_arquivo = options['caminho_excel']
        self.stdout.write(self.style.SUCCESS(f"Iniciando a importação do arquivo: {caminho_arquivo}"))

        try:
            cliente_tokio = Cliente.objects.get(nome='Tokio')
            produto_rcg = Produto.objects.get(nome='RCG')
        except (Cliente.DoesNotExist, Produto.DoesNotExist) as e:
            self.stderr.write(self.style.ERROR(f"Erro: Cliente 'Tokio' ou Produto 'RCG' não encontrado no banco. {e}"))
            return

        # ==============================================================================
        # PREPARAÇÃO DOS CAMPOS PERSONALIZADOS
        # ==============================================================================
        # 1. Cache dos campos personalizados: {nome_variavel: objeto_campo}
        # Isso evita dezenas de buscas no banco de dados dentro do loop.
        campos_dict = {cp.nome_variavel: cp for cp in CampoPersonalizado.objects.all()}
        self.stdout.write(f"Encontrados {len(campos_dict)} campos personalizados na biblioteca.")
        
        # Lê a planilha com a biblioteca pandas
        try:
            df = pd.read_excel(caminho_arquivo)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Arquivo não encontrado em: {caminho_arquivo}"))
            return

        # 2. Verificação das colunas da planilha
        colunas_planilha = df.columns
        colunas_necessarias = ['data_entrada', 'status', 'titulo'] # Nomes das colunas para os campos padrão
        for nome_variavel in campos_dict.keys():
            if nome_variavel not in colunas_planilha:
                self.stdout.write(self.style.WARNING(f"  -> Aviso: A coluna para a variável '{nome_variavel}' não foi encontrada na planilha. Ela será ignorada."))

        for index, row in df.iterrows():
            self.stdout.write(f"\nProcessando linha {index + 2} da planilha...")

            # --- Cria o objeto Caso com os dados padrão ---
            # Usamos .get() para evitar erros se uma coluna não existir
            novo_caso = Caso(
                cliente=cliente_tokio,
                produto=produto_rcg,
                data_entrada=row.get('data_entrada'),
                status=row.get('status'),
                titulo=row.get('titulo')
                # Adicione outros campos padrão do Caso aqui, se houver
            )
            
            # SALVAR O CASO AQUI DISPARA OS SIGNALS (SharePoint, E-mail)!
            novo_caso.save()
            self.stdout.write(self.style.SUCCESS(f"  -> Caso #{novo_caso.id} criado. Signals disparados."))

            # ==============================================================================
            # A LÓGICA PARA SALVAR OS DADOS ADICIONAIS ESTÁ AQUI
            # ==============================================================================
            valores_criados_count = 0
            # 3. Iteramos sobre o nosso dicionário de campos da biblioteca
            for nome_variavel, campo_obj in campos_dict.items():
                
                # 4. Verificamos se a planilha tem uma coluna com este nome de variável
                #    e se o valor nessa linha não está vazio (pd.notna).
                if nome_variavel in row and pd.notna(row[nome_variavel]):
                    valor_da_planilha = row[nome_variavel]
                    
                    # 5. Criamos o objeto ValorCampoPersonalizado, ligando-o ao novo caso e ao campo
                    ValorCampoPersonalizado.objects.create(
                        caso=novo_caso,
                        campo=campo_obj,
                        valor=str(valor_da_planilha) # Salvamos tudo como string, como o modelo espera
                    )
                    valores_criados_count += 1
            
            if valores_criados_count > 0:
                self.stdout.write(f"    -> {valores_criados_count} valor(es) de campos personalizados foram salvos para este caso.")
            else:
                self.stdout.write(self.style.WARNING("    -> Nenhum valor de campo personalizado encontrado nesta linha da planilha."))

        self.stdout.write(self.style.SUCCESS("\nImportação concluída com sucesso!"))