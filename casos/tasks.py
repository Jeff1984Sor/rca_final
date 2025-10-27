# casos/tasks.py
from celery import shared_task
import logging
from datetime import datetime, date

# Importe os modelos necessários
from .models import Caso
from clientes.models import Cliente
from django.db import IntegrityError
from produtos.models import Produto
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado, EstruturaDeCampos

logger = logging.getLogger('casos_app') # Use o logger configurado no settings.py

@shared_task # Transforma a função em uma tarefa Celery
def processar_linha_importacao(
    linha_dados,              # Dicionário com dados da linha {excel_header_norm: valor}
    cliente_id,               # ID do Cliente selecionado
    produto_id,               # ID do Produto selecionado
    header_map,               # Mapa {excel_header_norm: nome_variavel_original}
    chaves_validas_list,      # Lista de chaves válidas (fixas + personalizadas com prefixo)
    campos_meta_map_serializable, # Mapa {nome_variavel_original: campo_id}
    padrao_titulo_produto,    # String do padrão de título
    estrutura_campos_id       # ID da EstruturaDeCampos
    ):
    """
    Processa UMA ÚNICA linha de dados da planilha Excel para CRIAR um novo Caso.
    Recebe IDs e dados serializados para ser compatível com Celery.
    """
    row_index = linha_dados.get('_row_index', 'desconhecida')
    logger.info(f"[CELERY Task - Linha {row_index}] Iniciando processamento.")

    try:
        # Busca objetos FK uma vez por tarefa
        cliente = Cliente.objects.get(id=cliente_id)
        produto = Produto.objects.get(id=produto_id)
        # Não busca a estrutura aqui, usaremos o mapa de IDs passado

        dados_caso_fixos = {}                 # {nome_campo_fixo: valor}
        dados_personalizados_para_salvar = {} # {campo_id: valor} -> CORRIGIDO para ID
        dados_personalizados_para_titulo = {} # {nome_variavel_original: valor}

        # Mapeia dados da linha usando o header_map fornecido
        for header_norm, cell_value in linha_dados.items():
            if cell_value is None or not header_norm or header_norm == '_row_index':
                continue

            # Obtém o nome_variavel original a partir do cabeçalho normalizado do Excel
            nome_variavel_original = header_map.get(header_norm)
            if not nome_variavel_original:
                 # O warning já foi dado na view ao criar o mapa, podemos pular
                 continue

            # --- Processar Valor (Campos Fixos) ---
            # Verifica se a chave original NÃO começa com 'personalizado_' E NÃO contém '__'
            # (Assume que 'personalizado_' não é usado em nomes de campos fixos)
            if not nome_variavel_original.startswith('personalizado_') and '__' not in nome_variavel_original:
                campo_caso = nome_variavel_original # A chave já é o nome do campo fixo

                # TRATAMENTO DE DATA (Melhorado)
                if campo_caso in ['data_entrada', 'data_encerramento']:
                     parsed_date = None
                     if isinstance(cell_value, datetime):
                        parsed_date = cell_value.date()
                     elif isinstance(cell_value, date):
                         parsed_date = cell_value
                     else: # Tentar parsear string AAAA-MM-DD ou DD/MM/AAAA
                         for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                             try:
                                 # Tenta parsear a data, ignorando a hora se houver
                                 parsed_date = datetime.strptime(str(cell_value).split(' ')[0], fmt).date()
                                 break
                             except (ValueError, TypeError):
                                 continue
                     if parsed_date:
                        dados_caso_fixos[campo_caso] = parsed_date
                     else:
                        logger.warning(f"[CELERY Task - Linha {row_index}] Data inválida '{cell_value}' para '{header_norm}'. Campo ignorado.")

                # TRATAMENTO DE STATUS
                elif campo_caso == 'status':
                    valor_status = str(cell_value).strip().upper()
                    # Valida se é uma das chaves válidas definidas no modelo Caso
                    if any(valor_status == choice[0] for choice in Caso.STATUS_CHOICES):
                        dados_caso_fixos[campo_caso] = valor_status
                    else:
                        logger.warning(f"[CELERY Task - Linha {row_index}] Status inválido '{cell_value}'. Campo ignorado.")
                
                # Outros campos fixos (como 'titulo' se viesse da planilha, mas removemos)
                # Cuidado para não sobrescrever cliente/produto que já temos
                elif campo_caso not in ['cliente', 'produto', 'titulo']:
                    dados_caso_fixos[campo_caso] = cell_value

            # --- Processar Valor (Campos Personalizados) ---
            # Se o nome_variavel original (vindo do header_map) existir no mapa de IDs
            elif nome_variavel_original in campos_meta_map_serializable:
                campo_id = campos_meta_map_serializable[nome_variavel_original]
                valor_str = str(cell_value)
                dados_personalizados_para_titulo[nome_variavel_original] = valor_str
                dados_personalizados_para_salvar[campo_id] = valor_str # Armazena {campo_id: valor}

        # Garante data_entrada padrão se ausente e obrigatório
        if 'data_entrada' not in dados_caso_fixos and Caso._meta.get_field('data_entrada').blank is False:
             dados_caso_fixos['data_entrada'] = date.today()
             logger.warning(f"[CELERY Task - Linha {row_index}]: 'data_entrada' não fornecida, usando data atual como padrão.")

        # 6. Criar o Caso (sempre cria)
        novo_caso = Caso.objects.create(
            cliente=cliente,
            produto=produto,
            titulo="[Título Pendente]", # Título temporário
            **dados_caso_fixos
        )
        logger.info(f"[CELERY Task - Linha {row_index}] Caso preliminar criado (ID {novo_caso.id}).")

        # 7. Salvar Campos Personalizados (Usando o mapa de IDs)
        logger.debug(f"[CELERY Task - Linha {row_index}] Tentando salvar campos personalizados. Dados: {dados_personalizados_para_salvar}")
        if not dados_personalizados_para_salvar:
             logger.warning(f"[CELERY Task - Linha {row_index}] Nenhum campo personalizado encontrado nos dados mapeados para salvar.")

        for campo_id, valor_a_salvar in dados_personalizados_para_salvar.items():
            try:
                # Busca o objeto CampoPersonalizado pelo ID
                campo_meta = CampoPersonalizado.objects.get(id=campo_id)
                logger.debug(f"[CELERY Task - Linha {row_index}] Salvando Campo ID {campo_meta.id} ('{campo_meta.nome_campo}') com valor '{str(valor_a_salvar)[:50]}...'")
                ValorCampoPersonalizado.objects.create(
                    caso=novo_caso,
                    campo=campo_meta,
                    valor=valor_a_salvar # Salva o valor como string
                )
            except CampoPersonalizado.DoesNotExist:
                 logger.error(f"[CELERY Task - Linha {row_index}] CampoPersonalizado com ID {campo_id} não encontrado! Valor '{valor_a_salvar}' não salvo.")
            except Exception as e:
                 logger.error(f"[CELERY Task - Linha {row_index}] Erro ao salvar campo personalizado ID {campo_id}: {e}", exc_info=True)

        logger.debug(f"[CELERY Task - Linha {row_index}] Loop de salvamento de campos personalizados concluído.")

        # 8. Gerar e Salvar Título Automático
        titulo_final = f"Caso Importado #{novo_caso.id}" # Padrão
        if padrao_titulo_produto: # Usa o padrão passado como argumento
            titulo_formatado = padrao_titulo_produto
            logger.debug(f"[CELERY Task - Linha {row_index}] Gerando título com padrão: '{titulo_formatado}'. Dados disponíveis: {dados_personalizados_para_titulo}")
            # Usa os dados {nome_variavel_original: valor} que coletamos
            for nome_var, valor in dados_personalizados_para_titulo.items():
                placeholder = f'{{{nome_var}}}'
                titulo_formatado = titulo_formatado.replace(placeholder, valor)
            titulo_final = titulo_formatado

        novo_caso.titulo = titulo_final
        novo_caso.save(update_fields=['titulo'])
        logger.info(f"[CELERY Task - Linha {row_index}] Título gerado e salvo para caso ID {novo_caso.id}: '{titulo_final}'")

        # O signal post_save será disparado aqui pelo create() e pelo save() anterior

        return f"Linha {row_index} processada com sucesso. Caso ID {novo_caso.id} criado."

    # Tratamento de Erros Gerais da Tarefa
    except Cliente.DoesNotExist:
        logger.error(f"[CELERY Task - Linha {row_index}] Cliente com ID {cliente_id} não encontrado.")
        return f"Linha {row_index} falhou: Cliente não encontrado."
    except Produto.DoesNotExist:
        logger.error(f"[CELERY Task - Linha {row_index}] Produto com ID {produto_id} não encontrado.")
        return f"Linha {row_index} falhou: Produto não encontrado."
    except EstruturaDeCampos.DoesNotExist:
         logger.error(f"[CELERY Task - Linha {row_index}] EstruturaDeCampos com ID {estrutura_campos_id} não encontrada.")
         return f"Linha {row_index} falhou: Estrutura de Campos não encontrada."
    except IntegrityError as e: # Captura erros de banco de dados (ex: campo obrigatório faltando)
         logger.error(f"[CELERY Task - Linha {row_index}] Erro de integridade ao criar caso: {e}. Dados Fixos: {dados_caso_fixos}", exc_info=True)
         return f"Linha {row_index} falhou: Erro de integridade no banco ({e})."
    except Exception as e: # Captura qualquer outro erro inesperado
        logger.error(f"[CELERY Task - Linha {row_index}] Erro INESPERADO ao processar: {e}", exc_info=True)
        return f"Linha {row_index} falhou: Erro inesperado ({e})."