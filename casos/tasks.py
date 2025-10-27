# casos/tasks.py
from celery import shared_task
import logging
from datetime import datetime, date

# Importe os modelos necessários DENTRO da função ou no topo
from .models import Caso
from clientes.models import Cliente
from produtos.models import Produto
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado, EstruturaDeCampos

logger = logging.getLogger('casos_app') # Use o mesmo logger

@shared_task # Transforma a função em uma tarefa Celery
def processar_linha_importacao(linha_dados, cliente_id, produto_id, header_map, chaves_validas_set, campos_meta_map, padrao_titulo_produto, estrutura_campos_id):
    """
    Processa UMA ÚNICA linha de dados da planilha Excel.
    Recebe os dados já mapeados.
    """
    row_index = linha_dados.get('_row_index', 'desconhecida') # Adicionamos o índice da linha
    logger.info(f"[CELERY Task] Iniciando processamento da linha {row_index}")

    try:
        # Busca objetos FK uma vez por tarefa
        cliente = Cliente.objects.get(id=cliente_id)
        produto = Produto.objects.get(id=produto_id)
        estrutura_campos = EstruturaDeCampos.objects.get(id=estrutura_campos_id) if estrutura_campos_id else None

        dados_caso_fixos = {}
        dados_personalizados_para_salvar = {} # {objeto_CampoPersonalizado: valor}
        dados_personalizados_para_titulo = {} # {nome_variavel: valor}
        
        # Mapeia dados da linha (Lógica similar à view, mas para UMA linha)
        for header_norm, cell_value in linha_dados.items():
            if cell_value is None or not header_norm or header_norm == '_row_index': 
                continue
                
            chave_interna = header_map.get(header_norm)
            if not chave_interna: continue 
            
            # --- Processar Valor (Campos Fixos) ---
            if not chave_interna.startswith('personalizado_') and '__' not in chave_interna:
                campo_caso = chave_interna
                # TRATAMENTO DE DATA (Exemplo)
                if campo_caso in ['data_entrada', 'data_encerramento']:
                     if isinstance(cell_value, datetime):
                        dados_caso_fixos[campo_caso] = cell_value.date()
                     elif isinstance(cell_value, date):
                         dados_caso_fixos[campo_caso] = cell_value
                     else:
                         # Tentar parsear AAAA-MM-DD ou DD/MM/AAAA
                         parsed_date = None
                         for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                             try:
                                 parsed_date = datetime.strptime(str(cell_value).split(' ')[0], fmt).date()
                                 break
                             except (ValueError, TypeError):
                                 continue
                         if parsed_date:
                            dados_caso_fixos[campo_caso] = parsed_date
                         else:
                            logger.warning(f"[CELERY Task - Linha {row_index}] Data inválida '{cell_value}' para '{header_norm}'.")
                # TRATAMENTO DE STATUS 
                elif campo_caso == 'status':
                    valor_status = str(cell_value).strip().upper()
                    if any(valor_status == choice[0] for choice in Caso.STATUS_CHOICES):
                        dados_caso_fixos[campo_caso] = valor_status
                    else:
                        logger.warning(f"[CELERY Task - Linha {row_index}] Status inválido '{cell_value}'.")
                else:
                    dados_caso_fixos[campo_caso] = cell_value
            
            # --- Processar Valor (Campos Personalizados) ---
            elif chave_interna.startswith('personalizado_'):
                nome_variavel = chave_interna.split('personalizado_')[1]
                valor_str = str(cell_value)
                dados_personalizados_para_titulo[nome_variavel] = valor_str
                
                campo_meta = campos_meta_map.get(nome_variavel) # Usa o mapa passado como argumento
                if campo_meta:
                    dados_personalizados_para_salvar[campo_meta] = valor_str

        # Garante data_entrada padrão se ausente
        if 'data_entrada' not in dados_caso_fixos:
            dados_caso_fixos['data_entrada'] = date.today()

        # 6. Criar o Caso (sempre cria, pois é Abordagem 1)
        novo_caso = Caso.objects.create(
            cliente=cliente,
            produto=produto,
            titulo="[Título Pendente]",
            **dados_caso_fixos
        )
        logger.info(f"[CELERY Task] Caso preliminar criado (ID {novo_caso.id}) para linha {row_index}.")

        # 7. Salvar Campos Personalizados
        for campo_meta, valor_a_salvar in dados_personalizados_para_salvar.items():
            ValorCampoPersonalizado.objects.create(
                caso=novo_caso,
                campo=campo_meta,
                valor=valor_a_salvar
            )
        logger.debug(f"[CELERY Task] Campos personalizados salvos para caso ID {novo_caso.id}")

        # 8. Gerar e Salvar Título Automático
        titulo_final = f"Caso Importado #{novo_caso.id}"
        if padrao_titulo_produto and estrutura_campos:
            titulo_formatado = padrao_titulo_produto
            for nome_var, valor in dados_personalizados_para_titulo.items():
                titulo_formatado = titulo_formatado.replace(f'{{{nome_var}}}', valor)
            titulo_final = titulo_formatado
        
        novo_caso.titulo = titulo_final
        novo_caso.save(update_fields=['titulo'])
        logger.info(f"[CELERY Task] Título gerado e salvo para caso ID {novo_caso.id}: '{titulo_final}'")
        
        # AQUI O SIGNAL post_save SERÁ DISPARADO AUTOMATICAMENTE pelo create() e save()
        
        return f"Linha {row_index} processada com sucesso. Caso ID {novo_caso.id} criado."

    except Exception as e:
        logger.error(f"[CELERY Task] Erro ao processar linha {row_index}: {e}", exc_info=True)
        # Você pode decidir o que fazer com o erro (registrar, tentar de novo, etc.)
        # Retornar uma string de erro pode ser útil para logs gerais
        return f"Linha {row_index} falhou: {e}"