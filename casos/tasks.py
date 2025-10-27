# casos/tasks.py
from celery import shared_task
import logging
from datetime import datetime, date

# Imports do Django e Modelos (necessários para a tarefa)
from django.db import IntegrityError
from .models import Caso
from clientes.models import Cliente
from produtos.models import Produto
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado, EstruturaDeCampos

logger = logging.getLogger('casos_app') # Use o logger configurado no settings.py

@shared_task # Transforma a função em uma tarefa Celery
def processar_linha_importacao(
    linha_dados,              # Dicionário com dados da linha {excel_header_norm: valor}
    cliente_id,               # ID do Cliente selecionado
    produto_id,               # ID do Produto selecionado
    header_map,               # Mapa {excel_header_norm: nome_variavel_original ou chave_fixa}
    chaves_validas_list,      # Lista de chaves válidas (apenas para referência, não usado ativamente)
    campos_meta_map_serializable, # Mapa {nome_variavel_original: campo_id}
    padrao_titulo_produto,    # String do padrão de título
    estrutura_campos_id       # ID da EstruturaDeCampos (pode ser None)
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
        dados_personalizados_para_salvar = {} # {campo_id: valor} -> ID do CampoPersonalizado
        dados_personalizados_para_titulo = {} # {nome_variavel_original: valor}

        # Reconstrói o mapa {nome_variavel_original: campo_id} a partir dos args
        campos_meta_ids_map = campos_meta_map_serializable

        # --- Loop Principal de Processamento da Linha ---
        linha_valida = False # Flag para verificar se a linha tem algum dado útil
        for header_norm, cell_value in linha_dados.items():
            # Ignora células vazias, cabeçalhos vazios ou a chave interna _row_index
            if cell_value is None or not header_norm or header_norm == '_row_index':
                continue

            # Obtém o nome_variavel original OU o nome do campo fixo a partir do cabeçalho normalizado
            chave_interna = header_map.get(header_norm)
            if not chave_interna:
                 # O warning já foi dado na view ao criar o mapa, podemos pular o log aqui
                 continue

            linha_valida = True # Marcar que a linha tem dados

            # --- Processar Valor (Campos Personalizados) ---
            # Verifica se a chave_interna (nome_variavel original) existe no mapa de IDs de campos personalizados
            if chave_interna in campos_meta_ids_map:
                campo_id = campos_meta_ids_map[chave_interna]
                valor_str = str(cell_value)
                # Guarda para gerar o título (usando nome_variavel original como chave)
                dados_personalizados_para_titulo[chave_interna] = valor_str
                # Guarda para salvar no banco {ID do Campo : valor}
                dados_personalizados_para_salvar[campo_id] = valor_str
                logger.debug(f"[CELERY Task - Linha {row_index}] Mapeado campo personalizado '{chave_interna}' (ID: {campo_id}) com valor '{valor_str[:50]}...'")

            # --- Processar Valor (Campos Fixos) ---
            # Se não for personalizado E não contiver '__' (evita processar FKs aqui)
            elif '__' not in chave_interna:
                campo_caso = chave_interna # A chave já é o nome do campo fixo

                # TRATAMENTO DE DATA
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
                        logger.debug(f"[CELERY Task - Linha {row_index}] Mapeado campo fixo '{campo_caso}' (Data) com valor '{parsed_date}'")
                     else:
                        logger.warning(f"[CELERY Task - Linha {row_index}] Data inválida '{cell_value}' para '{header_norm}'. Campo ignorado.")

                # TRATAMENTO DE STATUS
                elif campo_caso == 'status':
                    valor_status = str(cell_value).strip().upper()
                    # Valida se é uma das chaves válidas definidas no modelo Caso
                    if any(valor_status == choice[0] for choice in Caso.STATUS_CHOICES):
                        dados_caso_fixos[campo_caso] = valor_status
                        logger.debug(f"[CELERY Task - Linha {row_index}] Mapeado campo fixo '{campo_caso}' com valor '{valor_status}'")
                    else:
                        logger.warning(f"[CELERY Task - Linha {row_index}] Status inválido '{cell_value}'. Campo ignorado.")

                # Outros campos fixos (Ex: advogado_responsavel - assumindo que é ID ou None)
                # Cuidado para não sobrescrever cliente/produto que já temos
                elif campo_caso not in ['cliente', 'produto', 'titulo', 'id']: # Ignora chaves óbvias
                    # TODO: Adicionar lógica para buscar User por nome/username se 'advogado_responsavel' vier como string
                    dados_caso_fixos[campo_caso] = cell_value
                    logger.debug(f"[CELERY Task - Linha {row_index}] Mapeado campo fixo '{campo_caso}' com valor '{str(cell_value)[:50]}...'")

        # --- Fim do Loop de Processamento da Linha ---

        # Se a linha não tinha nenhum dado mapeado, pular
        if not linha_valida:
            logger.info(f"[CELERY Task - Linha {row_index}] Ignorada por não conter dados mapeáveis.")
            return f"Linha {row_index} ignorada (sem dados válidos)."

        # Garante data_entrada padrão se ausente e obrigatório no modelo
        if 'data_entrada' not in dados_caso_fixos and not Caso._meta.get_field('data_entrada').blank:
             dados_caso_fixos['data_entrada'] = date.today()
             logger.warning(f"[CELERY Task - Linha {row_index}]: 'data_entrada' não fornecida, usando data atual como padrão.")

        # 6. Criar o Caso (sempre cria, pois é Abordagem 1)
        novo_caso = Caso.objects.create(
            cliente=cliente,
            produto=produto,
            titulo="[Título Pendente]", # Título temporário
            **dados_caso_fixos # Passa os campos fixos mapeados
        )
        logger.info(f"[CELERY Task - Linha {row_index}] Caso preliminar criado (ID {novo_caso.id}).")

        # 7. Salvar Campos Personalizados (Usando o mapa de IDs)
        logger.debug(f"[CELERY Task - Linha {row_index}] Dados a salvar para personalizados: {dados_personalizados_para_salvar}")
        if not dados_personalizados_para_salvar:
             logger.warning(f"[CELERY Task - Linha {row_index}] Nenhum dado personalizado mapeado para salvar.")

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
                 logger.error(f"[CELERY Task - Linha {row_index}] CRÍTICO: CampoPersonalizado com ID {campo_id} não encontrado! Valor '{valor_a_salvar}' não salvo.")
            except Exception as e:
                 logger.error(f"[CELERY Task - Linha {row_index}] Erro ao salvar campo personalizado ID {campo_id} para caso {novo_caso.id}: {e}", exc_info=True)

        logger.debug(f"[CELERY Task - Linha {row_index}] Loop de salvamento de campos personalizados concluído.")

        # 8. Gerar e Salvar Título Automático
        titulo_final = f"Caso Importado #{novo_caso.id}" # Título padrão se falhar
        if padrao_titulo_produto: # Usa o padrão passado como argumento
            titulo_formatado = padrao_titulo_produto
            logger.debug(f"[CELERY Task - Linha {row_index}] Gerando título com padrão: '{titulo_formatado}'. Dados disponíveis para título: {dados_personalizados_para_titulo}")
            # Usa os dados {nome_variavel_original: valor} que coletamos
            for nome_var, valor in dados_personalizados_para_titulo.items():
                placeholder = f'{{{nome_var}}}'
                # Garante que o valor seja string para o replace
                titulo_formatado = titulo_formatado.replace(placeholder, str(valor))
            titulo_final = titulo_formatado

        novo_caso.titulo = titulo_final
        novo_caso.save(update_fields=['titulo'])
        logger.info(f"[CELERY Task - Linha {row_index}] Título gerado e salvo para caso ID {novo_caso.id}: '{titulo_final}'")

        # O signal post_save será disparado aqui pelo create() e pelo save()

        return f"Linha {row_index} processada com sucesso. Caso ID {novo_caso.id} criado."

    # --- Tratamento de Erros Gerais da Tarefa ---
    except Cliente.DoesNotExist:
        logger.error(f"[CELERY Task - Linha {row_index}] CRÍTICO: Cliente com ID {cliente_id} não encontrado.")
        return f"Linha {row_index} falhou: Cliente não encontrado."
    except Produto.DoesNotExist:
        logger.error(f"[CELERY Task - Linha {row_index}] CRÍTICO: Produto com ID {produto_id} não encontrado.")
        return f"Linha {row_index} falhou: Produto não encontrado."
    # Removida a busca da Estrutura aqui, pois usamos o ID
    except IntegrityError as e: # Captura erros de banco de dados (ex: campo obrigatório faltando no create)
         logger.error(f"[CELERY Task - Linha {row_index}] Erro de integridade ao criar caso: {e}. Dados Fixos Tentados: {dados_caso_fixos}", exc_info=False) # exc_info=False para não poluir muito
         return f"Linha {row_index} falhou: Erro de integridade no banco ({e}). Verifique campos obrigatórios."
    except Exception as e: # Captura qualquer outro erro inesperado
        logger.error(f"[CELERY Task - Linha {row_index}] Erro INESPERADO durante processamento: {e}", exc_info=True) # exc_info=True para detalhes
        return f"Linha {row_index} falhou: Erro inesperado ({e})."