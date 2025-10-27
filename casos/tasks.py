# casos/tasks.py
from celery import shared_task
import logging
from datetime import datetime, date

# Imports do Django e Modelos (necessários para a tarefa)
from django.db import IntegrityError
# Garanta que estes imports estejam corretos para sua estrutura
try:
    from .models import Caso
    from clientes.models import Cliente
    from produtos.models import Produto
    from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado, EstruturaDeCampos
except ImportError as e:
    # Log de erro crítico se os modelos não puderem ser importados
    initial_logger = logging.getLogger(__name__)
    initial_logger.critical(f"Erro CRÍTICO ao importar modelos em tasks.py: {e}. Verifique os caminhos e dependências.")
    # Re-levanta a exceção para impedir que o Celery carregue a tarefa defeituosa
    raise ImportError(f"Não foi possível importar modelos necessários em tasks.py: {e}") from e


logger = logging.getLogger('casos_app') # Use o logger configurado no settings.py

@shared_task(bind=True) # bind=True pode ser útil para retentativas no futuro
def processar_linha_importacao(
    self, # Adicionado self por causa do bind=True
    linha_dados,              # Dicionário com dados da linha {excel_header_norm: valor}
    cliente_id,               # ID do Cliente selecionado
    produto_id,               # ID do Produto selecionado
    header_map,               # Mapa {excel_header_norm: nome_variavel_original ou chave_fixa}
    chaves_validas_list,      # Lista de chaves válidas (apenas para referência)
    campos_meta_map_serializable, # Mapa {nome_variavel_original: campo_id}
    padrao_titulo_produto,    # String do padrão de título
    estrutura_campos_id       # ID da EstruturaDeCampos (pode ser None)
    ):
    """
    Processa UMA ÚNICA linha de dados da planilha Excel para CRIAR um novo Caso.
    Recebe IDs e dados serializados para ser compatível com Celery.
    """
    row_index = linha_dados.get('_row_index', 'desconhecida')
    task_id = self.request.id # Pega o ID da tarefa Celery para rastreamento
    log_prefix = f"[CELERY Task {task_id} - Linha {row_index}]" # Prefixo para logs desta tarefa
    logger.info(f"{log_prefix} Iniciando processamento.")

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

        # --- Loop Principal de Processamento da Linha (COM ORDEM CORRIGIDA e LOGS DETALHADOS) ---
        linha_valida = False # Flag para verificar se a linha tem algum dado útil
        logger.debug(f"{log_prefix} Dados brutos recebidos da linha: {linha_dados}")
        logger.debug(f"{log_prefix} Mapa de cabeçalhos recebido: {header_map}")
        logger.debug(f"{log_prefix} Mapa de IDs de campos personalizados recebido: {campos_meta_ids_map}")

        for header_norm, cell_value in linha_dados.items():
            # Ignora células vazias, cabeçalhos vazios ou a chave interna _row_index
            if cell_value is None or not header_norm or header_norm == '_row_index':
                continue

            # Obtém o nome_variavel original OU o nome do campo fixo a partir do cabeçalho normalizado
            chave_interna = header_map.get(header_norm)
            if not chave_interna:
                 logger.warning(f"{log_prefix} Cabeçalho '{header_norm}' não encontrado no mapa. Ignorando valor '{str(cell_value)[:50]}...'.")
                 continue

            linha_valida = True # Marcar que a linha tem dados

            # <<< LOG DE DEPURAÇÃO CRUCIAL >>>
            logger.debug(f"{log_prefix} Verificando mapeamento: Header='{header_norm}', Chave Interna='{chave_interna}'")

            # --- VERIFICA PRIMEIRO SE É PERSONALIZADO ---
            # Usa o mapa {nome_variavel_original: campo_id}
            if chave_interna in campos_meta_ids_map:
                campo_id = campos_meta_ids_map[chave_interna]
                valor_str = str(cell_value)
                # Guarda para gerar o título (usando nome_variavel original)
                dados_personalizados_para_titulo[chave_interna] = valor_str
                # Guarda para salvar no banco {ID do Campo : valor}
                dados_personalizados_para_salvar[campo_id] = valor_str
                logger.debug(f"{log_prefix} OK - Mapeado como PERSONALIZADO. Chave='{chave_interna}', Campo ID='{campo_id}', Valor='{valor_str[:50]}...'")

            # --- SENÃO, TENTA VERIFICAR SE É FIXO ---
            # Se não for personalizado E não contiver '__'
            elif '__' not in chave_interna:
                campo_caso = chave_interna # A chave já é o nome do campo fixo

                processed_value = None # Variável para guardar o valor processado

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
                        processed_value = parsed_date
                        dados_caso_fixos[campo_caso] = parsed_date
                     else:
                        logger.warning(f"{log_prefix} Data inválida '{cell_value}' para '{header_norm}'. Campo ignorado.")

                # TRATAMENTO DE STATUS
                elif campo_caso == 'status':
                    valor_status = str(cell_value).strip().upper()
                    # Valida se é uma das chaves válidas definidas no modelo Caso
                    if any(valor_status == choice[0] for choice in Caso.STATUS_CHOICES):
                        processed_value = valor_status
                        dados_caso_fixos[campo_caso] = valor_status
                    else:
                        logger.warning(f"{log_prefix} Status inválido '{cell_value}'. Campo ignorado.")

                # Outros campos fixos
                # Cuidado para não sobrescrever cliente/produto/titulo/id
                elif campo_caso not in ['cliente', 'produto', 'titulo', 'id']:
                    # TODO: Adicionar lógica para buscar User por nome/username se 'advogado_responsavel' vier como string
                    processed_value = cell_value
                    dados_caso_fixos[campo_caso] = cell_value

                if processed_value is not None:
                     logger.debug(f"{log_prefix} OK - Mapeado como FIXO. Chave='{campo_caso}', Valor='{str(processed_value)[:50]}...'")

            # Se não for nenhum dos dois (ex: cliente__nome da exportação), será ignorado
            else:
                 logger.debug(f"{log_prefix} Chave '{chave_interna}' ignorada no mapeamento da linha (provavelmente FK com '__').")


        # --- Fim do Loop de Processamento da Linha ---

        # Se a linha não tinha nenhum dado mapeado, pular
        if not linha_valida:
            logger.info(f"{log_prefix} Ignorada por não conter dados mapeáveis.")
            return f"Linha {row_index} ignorada (sem dados válidos)."

        # Garante data_entrada padrão se ausente e obrigatório no modelo
        if 'data_entrada' not in dados_caso_fixos and not Caso._meta.get_field('data_entrada').blank:
             dados_caso_fixos['data_entrada'] = date.today()
             logger.warning(f"{log_prefix} 'data_entrada' não fornecida, usando data atual como padrão.")

        # 6. Criar o Caso (sempre cria)
        novo_caso = Caso.objects.create(
            cliente=cliente,
            produto=produto,
            titulo="[Título Pendente]", # Título temporário
            **dados_caso_fixos # Passa os campos fixos mapeados
        )
        logger.info(f"{log_prefix} Caso preliminar criado (ID {novo_caso.id}). Dados Fixos: {dados_caso_fixos}")

        # 7. Salvar Campos Personalizados (Usando o mapa de IDs)
        logger.debug(f"{log_prefix} Dados a salvar para personalizados: {dados_personalizados_para_salvar}")
        if not dados_personalizados_para_salvar:
             logger.warning(f"{log_prefix} Nenhum dado personalizado mapeado para salvar.")

        for campo_id, valor_a_salvar in dados_personalizados_para_salvar.items():
            try:
                # Busca o objeto CampoPersonalizado pelo ID
                campo_meta = CampoPersonalizado.objects.get(id=campo_id)
                logger.debug(f"{log_prefix} Salvando Campo ID {campo_meta.id} ('{campo_meta.nome_campo}') com valor '{str(valor_a_salvar)[:50]}...'")
                ValorCampoPersonalizado.objects.create(
                    caso=novo_caso,
                    campo=campo_meta,
                    valor=valor_a_salvar # Salva o valor como string
                )
            except CampoPersonalizado.DoesNotExist:
                 logger.error(f"{log_prefix} CRÍTICO: CampoPersonalizado com ID {campo_id} não encontrado! Valor '{valor_a_salvar}' não salvo.")
            except Exception as e:
                 logger.error(f"{log_prefix} Erro ao salvar campo personalizado ID {campo_id} para caso {novo_caso.id}: {e}", exc_info=True)

        logger.debug(f"{log_prefix} Loop de salvamento de campos personalizados concluído.")

        # 8. Gerar e Salvar Título Automático
        titulo_final = f"Caso Importado #{novo_caso.id}" # Título padrão se falhar
        if padrao_titulo_produto: # Usa o padrão passado como argumento
            titulo_formatado = padrao_titulo_produto
            logger.debug(f"{log_prefix} Gerando título com padrão: '{titulo_formatado}'. Dados disponíveis para título: {dados_personalizados_para_titulo}")
            # Usa os dados {nome_variavel_original: valor} que coletamos
            for nome_var, valor in dados_personalizados_para_titulo.items():
                placeholder = f'{{{nome_var}}}'
                # Garante que o valor seja string para o replace
                titulo_formatado = titulo_formatado.replace(placeholder, str(valor))
            titulo_final = titulo_formatado

        novo_caso.titulo = titulo_final
        novo_caso.save(update_fields=['titulo'])
        logger.info(f"{log_prefix} Título gerado e salvo para caso ID {novo_caso.id}: '{titulo_final}'")

        # O signal post_save será disparado aqui pelo create() e pelos save() anteriores

        return f"Linha {row_index} processada com sucesso. Caso ID {novo_caso.id} criado."

    # --- Tratamento de Erros Gerais da Tarefa ---
    except Cliente.DoesNotExist:
        logger.error(f"{log_prefix} CRÍTICO: Cliente com ID {cliente_id} não encontrado.")
        # Re-raise para que o Celery marque a tarefa como falha
        raise ValueError(f"Cliente ID {cliente_id} não encontrado.")
    except Produto.DoesNotExist:
        logger.error(f"{log_prefix} CRÍTICO: Produto com ID {produto_id} não encontrado.")
        raise ValueError(f"Produto ID {produto_id} não encontrado.")
    except IntegrityError as e: # Captura erros de banco de dados (ex: campo obrigatório faltando no create)
         logger.error(f"{log_prefix} Erro de integridade ao criar caso: {e}. Dados Fixos Tentados: {dados_caso_fixos}", exc_info=False)
         raise ValueError(f"Erro de integridade no banco ({e}). Verifique campos obrigatórios.")
    except Exception as e: # Captura qualquer outro erro inesperado
        logger.error(f"{log_prefix} Erro INESPERADO durante processamento: {e}", exc_info=True)
        # Re-raise para marcar a tarefa como falha
        raise e