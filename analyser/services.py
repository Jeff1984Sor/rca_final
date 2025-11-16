# analyser/services.py - VERSÃO LIMPA E FUNCIONAL COM SUPORTE A MÚLTIPLOS FORMATOS

import logging
import json
import re
from datetime import datetime
from decimal import Decimal
import requests
from django.utils import timezone
from django.conf import settings
import time
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import ResultadoAnalise, LogAnalise, ModeloAnalise
from .document_converter import DocumentConverter  # ✅ NOVO IMPORT
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado
from integrations.sharepoint import SharePoint

logger = logging.getLogger(__name__)


class AnalyserService:
    """Serviço para análise de documentos com IA."""
    
    def __init__(self, caso, modelo_analise, arquivos_selecionados, usuario, resultado_id):
        self.caso = caso
        self.modelo = modelo_analise
        self.arquivos_info = arquivos_selecionados
        self.usuario = usuario
        self.resultado_id = resultado_id
        self.channel_layer = get_channel_layer()
        
        try:
            self.resultado = ResultadoAnalise.objects.get(id=self.resultado_id)
        except ResultadoAnalise.DoesNotExist:
            raise ValueError(f"ResultadoAnalise com ID {self.resultado_id} não encontrado.")

        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel(
            model_name=getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-pro')
        )

    def _send_update(self, event_type, data):
        """Envia mensagens via WebSocket."""
        try:
            room_group_name = f'analise_{self.resultado_id}'
            message = {'type': event_type, 'data': data}
            
            async_to_sync(self.channel_layer.group_send)(
                room_group_name,
                {'type': 'analysis.update', 'message': message}
            )
        except Exception as e:
            logger.warning(f"Aviso ao enviar update via WebSocket: {e}")

    # =========================================================================
    # CHAMADAS À API GEMINI
    # =========================================================================
    
    def _chamar_gemini(self, prompt: str, arquivo: dict = None, is_json: bool = True):
        """
        Chamada genérica ao Gemini com ou sem arquivo.
        
        Args:
            prompt: String do prompt
            arquivo: Dict com 'mime_type' e 'data' (opcional)
            is_json: Se True, extrai JSON; se False, retorna texto puro
            
        Returns:
            dict ou str dependendo de is_json
        """
        try:
            conteudo = [prompt, arquivo] if arquivo else prompt
            response = self.gemini_model.generate_content(conteudo)
            
            if is_json:
                return self._extrair_json_da_resposta(response.text)
            else:
                return response.text.strip()
                
        except ResourceExhausted as e:
            logger.warning(f"⚠️ Limite da API Gemini atingido: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro ao chamar Gemini: {e}")
            raise

    @retry(
        wait=wait_fixed(60),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(ResourceExhausted)
    )
    def _chamar_gemini_com_retry(self, prompt: str, arquivo: dict):
        """Chama Gemini com retry automático em caso de limite de taxa."""
        try:
            self._send_update('log', {'level': 'INFO', 'message': '🤖 Enviando requisição para a IA...'})
            response = self.gemini_model.generate_content([prompt, arquivo])
            self._send_update('log', {'level': 'SUCCESS', 'message': '✅ Resposta recebida da IA.'})
            return self._extrair_json_da_resposta(response.text)
        except ResourceExhausted as e:
            self._send_update('log', {
                'level': 'WARNING', 
                'message': '⚠️ Limite da API atingido. Aguardando 60s para tentar novamente...'
            })
            raise e
        except Exception as e:
            self._send_update('log', {'level': 'ERROR', 'message': f'❌ Erro na comunicação com Gemini: {e}'})
            raise

    # =========================================================================
    # PREPARAÇÃO DE ARQUIVOS - ATUALIZADO COM SUPORTE A MÚLTIPLOS FORMATOS
    # =========================================================================
    
    def _preparar_um_arquivo(self, arquivo_info: dict) -> dict:
        """
        Baixa um único arquivo do SharePoint e o prepara para a API Gemini.
        Suporta: PDF, DOCX, DOC, XLSX, XLS
        """
        nome_arquivo = arquivo_info.get("name", "desconhecido")
        mime_type = arquivo_info.get('type', 'application/pdf')
        
        self._log('INFO', f'  -> Baixando "{nome_arquivo}"...')
        
        # Baixa o conteúdo binário
        conteudo_bytes = self._baixar_do_sharepoint(arquivo_info)
        if not conteudo_bytes:
            raise ValueError("O conteúdo retornado está vazio.")
        
        # ✅ NOVO: Verifica se o formato é suportado
        if not DocumentConverter.is_supported(mime_type):
            self._log('WARNING', f'⚠️ Formato {mime_type} não suportado. Tentando enviar como PDF...')
            # Tenta enviar como PDF de qualquer forma
            mime_type = 'application/pdf'
        
        # ✅ NOVO: Converte para texto se não for PDF
        formato = DocumentConverter.get_format_type(mime_type)
        
        if formato and formato != 'PDF':
            self._log('INFO', f'  -> Convertendo {formato} para texto...')
            try:
                texto_extraido, formato_detectado = DocumentConverter.convert_to_text(
                    conteudo_bytes,
                    mime_type,
                    nome_arquivo
                )
                self._log('SUCCESS', f'  -> ✅ {formato_detectado} convertido com sucesso!')
                
                # Cria um "arquivo" de texto para enviar ao Gemini
                arquivo_preparado = {
                    'mime_type': 'text/plain',
                    'data': texto_extraido.encode('utf-8')
                }
            except Exception as e:
                self._log('WARNING', f'  -> ⚠️ Falha ao converter {formato}: {e}. Enviando como binary...')
                arquivo_preparado = {
                    'mime_type': mime_type,
                    'data': conteudo_bytes
                }
        else:
            # PDF ou formato desconhecido - envia como está
            arquivo_preparado = {
                'mime_type': mime_type,
                'data': conteudo_bytes
            }
        
        self._log('SUCCESS', f'  -> ✅ Arquivo "{nome_arquivo}" preparado ({len(conteudo_bytes) // 1024} KB).')
        return arquivo_preparado
    
    def _baixar_do_sharepoint(self, arquivo_info: dict) -> bytes:
        """Baixa o conteúdo de um arquivo do SharePoint."""
        nome_arquivo = arquivo_info.get('name', 'desconhecido')
        arquivo_id = arquivo_info.get('id')
        
        if not arquivo_id:
            raise ValueError("O dicionário 'arquivo_info' não contém um 'id'.")

        try:
            sp = SharePoint()
            item_details = sp.get_item_details(arquivo_id)
            
            download_url = item_details.get('@microsoft.graph.downloadUrl')
            
            if not download_url:
                raise ValueError(f"API do SharePoint não retornou URL para '{nome_arquivo}'.")
            
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            
            conteudo_bytes = response.content
            
            if not conteudo_bytes:
                raise ValueError(f"Arquivo '{nome_arquivo}' está vazio.")
            
            return conteudo_bytes
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Erro de rede ao baixar '{nome_arquivo}': {e}")
        except Exception as e:
            raise ConnectionError(f"Falha ao processar '{nome_arquivo}': {e}")

    # =========================================================================
    # GERAÇÃO DE PROMPTS
    # =========================================================================
    
    def _gerar_prompt_extracao(self):
        """Gera o prompt para extração de campos."""
        campos = self.modelo.get_campos_para_extrair()
        
        prompt = f"""# ANÁLISE DE DOCUMENTOS JURÍDICOS

{self.modelo.instrucoes_gerais}

## INFORMAÇÕES DO CASO
- **Cliente:** {self.caso.cliente.nome}
- **Produto:** {self.caso.produto.nome}
- **Caso ID:** #{self.caso.id}

## CAMPOS A EXTRAIR

Analise os documentos anexados e extraia as seguintes informações:
"""
        
        for i, campo in enumerate(campos, 1):
            prompt += f"\n### {i}. {campo['label']}\n"
            
            descricao = self.modelo.descricoes_campos.get(campo['nome'], '')
            if descricao:
                prompt += f"{descricao}\n"
            else:
                prompt += f"Extraia o valor do campo '{campo['label']}'.\n"
            
            prompt += f"**Tipo:** {campo['tipo']}\n"
            
            # Dicas específicas por tipo
            if campo['tipo'] == 'DATA':
                prompt += "**Formato esperado:** DD/MM/AAAA\n"
            elif campo['tipo'] in ['MOEDA', 'NUMERO_DEC']:
                prompt += "**Formato esperado:** Apenas números (ex: 10000.50)\n"
            elif campo['tipo'] == 'NUMERO_INT':
                prompt += "**Formato esperado:** Apenas números inteiros\n"
            elif campo['tipo'] == 'BOOLEANO':
                prompt += "**Formato esperado:** true ou false\n"
            
            prompt += "\n"
        
        prompt += """
## FORMATO DE RESPOSTA OBRIGATÓRIO

⚠️ IMPORTANTE: Responda APENAS com um JSON válido, sem nenhum texto adicional.

{
"""
        
        for i, campo in enumerate(campos):
            virgula = "," if i < len(campos) - 1 else ""
            prompt += f'  "{campo["label"]}": "valor_extraído"{virgula}\n'
        
        prompt += """}

## REGRAS

1. ✅ Se não encontrar: "Não encontrado"
2. ✅ Para datas: DD/MM/AAAA
3. ✅ Para valores: apenas números com ponto decimal
4. ✅ Retorne APENAS o JSON puro
5. ✅ Certifique-se de que o JSON está válido

---

**Agora analise os documentos e retorne APENAS o JSON.**
"""
        
        return prompt

    def _gerar_prompt_resumo(self, dados_extraidos):
        """Gera prompt para o resumo executivo."""
        prompt = f"""# GERAR RESUMO EXECUTIVO

Com base nos dados abaixo, crie um resumo executivo do caso.

## Informações do Caso
- **Cliente:** {self.caso.cliente.nome}
- **Produto:** {self.caso.produto.nome}
- **Caso ID:** #{self.caso.id}

## Dados Extraídos
```json
{json.dumps(dados_extraidos, indent=2, ensure_ascii=False)}
```

## Instruções
1. Resuma em até 3 parágrafos
2. Destaque pontos importantes
3. Linguagem clara e profissional
4. Foque no essencial
5. Não adicione informações extras

**Resumo Executivo:**
"""
        return prompt

    def _gerar_prompt_consolidacao_e_resumo(self, resultados_parciais: list) -> str:
        """Gera prompt para consolidar múltiplos resultados e gerar resumo."""
        json_resultados = json.dumps(resultados_parciais, indent=2, ensure_ascii=False)
        
        return f"""# CONSOLIDAÇÃO E RESUMO

Você tem duas tarefas. Sua resposta DEVE conter JSON e resumo separados por "---".

## TAREFA 1: Consolidar JSON
Consolide esta lista em um único JSON coerente:
```json
{json_resultados}
```

Regras:
1. Se o mesmo campo aparece múltiplas vezes, escolha o valor mais relevante
2. Elimine "Não encontrado" quando houver valor real
3. Retorne exatamente no formato: {{"campo": "valor"}}

## TAREFA 2: Gerar Resumo
Com base nos dados consolidados, crie um resumo executivo em até 3 parágrafos.

---

RESPONDA ASSIM (JSON primeiro, depois ----, depois resumo):
{{"campo_1": "valor", "campo_2": "valor"}}
---
Seu resumo aqui...
"""

    # =========================================================================
    # EXTRAÇÃO DE JSON
    # =========================================================================
    
    def _extrair_json_da_resposta(self, resposta_texto):
        """Extrai JSON da resposta do Gemini."""
        # Remove markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', resposta_texto, re.DOTALL)
        if json_match:
            resposta_texto = json_match.group(1)
        
        resposta_texto = resposta_texto.strip()
        
        try:
            dados = json.loads(resposta_texto)
            if not isinstance(dados, dict):
                raise ValueError("Resposta não é um objeto JSON válido")
            return dados
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse do JSON: {str(e)}")
            resposta_limpa = resposta_texto.replace('\n', ' ').replace('\r', '')
            try:
                dados = json.loads(resposta_limpa)
                return dados
            except:
                self._log('ERROR', '❌ Não foi possível fazer parse da resposta JSON')
                raise ValueError(f"Resposta não é um JSON válido: {resposta_texto[:200]}...")

    # =========================================================================
    # ANÁLISE EM LOTE (MÚLTIPLOS ARQUIVOS)
    # =========================================================================
    
    def executar_analise(self) -> ResultadoAnalise:
        """Análise em lote com MapReduce pattern."""
        self._log('INFO', f'🚀 Análise #{self.resultado.id} iniciada para o Caso #{self.caso.id}.')
        inicio = timezone.now()
        
        try:
            # --- Etapa 1: MAP - Analisa cada arquivo individualmente ---
            resultados_parciais = []
            for arquivo_info in self.arquivos_info:
                self._log('INFO', f'📄 Processando arquivo: {arquivo_info["name"]}...') 
                try:
                    arquivo_preparado = self._preparar_um_arquivo(arquivo_info)
                    prompt_extracao = self._gerar_prompt_extracao()
                    dados_parciais = self._chamar_gemini(prompt_extracao, arquivo_preparado, is_json=True)
                    resultados_parciais.append(dados_parciais)
                    self._log('SUCCESS', f'✅ Arquivo "{arquivo_info["name"]}" concluído.')
                except Exception as e:
                    self._log('WARNING', f'⚠️ Falha ao processar "{arquivo_info["name"]}": {e}')
                    continue
            
            if not resultados_parciais:
                raise ValueError("Nenhum arquivo pôde ser analisado com sucesso.")
            
            # --- Etapa 2: REDUCE - Consolida os resultados ---
            self._log('INFO', '🔄 Consolidando resultados...')
            prompt_combinado = self._gerar_prompt_consolidacao_e_resumo(resultados_parciais)
            resposta_completa = self._chamar_gemini(prompt_combinado, is_json=False)

            if "---" not in resposta_completa:
                raise ValueError("A resposta não continha o separador '---' esperado.")

            json_part_str, resumo_part_str = resposta_completa.split("---", 1)
            
            dados_extraidos = self._extrair_json_da_resposta(json_part_str)
            self.resultado.dados_extraidos = dados_extraidos
            self._log('SUCCESS', f'✅ Consolidação de {len(dados_extraidos)} campos concluída.')

            self.resultado.resumo_caso = resumo_part_str.strip()
            self._log('SUCCESS', '📄 Resumo gerado com sucesso.')

            self.resultado.status = 'CONCLUIDO'

        except Exception as e:
            logger.error(f"[Análise #{self.resultado.id}] Falha crítica: {str(e)}", exc_info=True)
            self.resultado.status = 'ERRO'
            self.resultado.mensagem_erro = str(e)
            self._log('ERROR', f'❌ Análise falhou: {str(e)}')
        
        finally:
            self.resultado.tempo_processamento = timezone.now() - inicio
            self.resultado.save()
            self._log('INFO', f'🏁 Análise finalizada. Status: {self.resultado.status}')

        return self.resultado

    # =========================================================================
    # ANÁLISE INTERATIVA (UM ARQUIVO)
    # =========================================================================
    
    def executar_analise_interativa(self):
        """Análise de um único arquivo com transmissão em tempo real."""
        self._send_update('log', {'level': 'INFO', 'message': 'Análise interativa iniciada.'})
        inicio = timezone.now()

        try:
            # Pega o primeiro arquivo da lista
            arquivo_para_analisar = self.arquivos_info[0]
            
            # --- Etapa 1: Preparar o arquivo ---
            self._send_update('log', {
                'level': 'INFO', 
                'message': f'📄 Baixando arquivo {arquivo_para_analisar.get("name", "...")} do SharePoint...'
            })
            arquivo_preparado = self._preparar_um_arquivo(arquivo_para_analisar)
            self._send_update('log', {'level': 'SUCCESS', 'message': '✅ Arquivo preparado.'})

            # --- Etapa 2: Chamar a IA ---
            prompt = self._gerar_prompt_extracao()
            dados_extraidos_completos = self._chamar_gemini_com_retry(prompt, arquivo_preparado)

            # --- Etapa 3: Transmitir resultados ---
            self._send_update('log', {'level': 'INFO', 'message': '🧠 Processando e transmitindo resultados...'})
            for campo_label, valor in dados_extraidos_completos.items():
                self.resultado.dados_extraidos[campo_label] = valor
                self._send_update('field_update', {'field_label': campo_label, 'value': valor})
                time.sleep(0.5)

            self.resultado.save(update_fields=['dados_extraidos'])
            self._send_update('log', {'level': 'SUCCESS', 'message': '✅ Todos os campos foram processados.'})

            # --- Etapa 4: Gerar resumo ---
            if self.modelo.gerar_resumo:
                self._send_update('log', {'level': 'INFO', 'message': '✍️ Gerando resumo executivo...'})
                prompt_resumo = self._gerar_prompt_resumo(self.resultado.dados_extraidos)
                resumo = self._chamar_gemini(prompt_resumo, is_json=False)
                
                self.resultado.resumo_caso = resumo
                self._send_update('summary_update', {'summary': self.resultado.resumo_caso})
                self._send_update('log', {'level': 'SUCCESS', 'message': '✅ Resumo gerado.'})

            # --- Etapa Final: Concluir ---
            self.resultado.status = 'CONCLUIDO'
            self.resultado.tempo_processamento = timezone.now() - inicio
            self.resultado.save()
            self._send_update('analysis_complete', {'status': 'CONCLUIDO'})
            self._send_update('log', {'level': 'SUCCESS', 'message': '🏁 Análise finalizada com sucesso!'})

        except Exception as e:
            logger.error(f"[Análise Interativa #{self.resultado_id}] Falha crítica: {e}", exc_info=True)
            self.resultado.status = 'ERRO'
            self.resultado.mensagem_erro = str(e)
            self.resultado.save()
            self._send_update('analysis_error', {'message': str(e)})

    # =========================================================================
    # APLICAÇÃO DOS DADOS AO CASO
    # =========================================================================
    
    def aplicar_ao_caso(self):
        """Aplica os dados extraídos ao caso no sistema."""
        if self.resultado.status != 'CONCLUIDO':
            raise ValueError("❌ Só análises concluídas podem ser aplicadas")
        
        if self.resultado.aplicado_ao_caso:
            raise ValueError("⚠️ Análise já foi aplicada")
        
        self._log('INFO', '💾 Aplicando dados ao caso...')
        
        campos = self.modelo.get_campos_para_extrair()
        campos_aplicados = 0
        
        for campo in campos:
            campo_label = campo['label']
            valor_extraido = self.resultado.dados_extraidos.get(campo_label)
            
            if not valor_extraido or valor_extraido == "Não encontrado":
                self._log('INFO', f'⏭️ Campo pulado: {campo_label}')
                continue
            
            try:
                if campo['is_padrao']:
                    self._atualizar_campo_padrao(campo['nome'], valor_extraido)
                else:
                    self._atualizar_campo_personalizado(campo['campo_id'], valor_extraido)
                
                campos_aplicados += 1
                self._log('SUCCESS', f'✅ {campo_label} = {valor_extraido}')
                
            except Exception as e:
                self._log('WARNING', f'⚠️ Erro em {campo_label}: {str(e)}')
        
        # Marca como aplicado
        self.resultado.aplicado_ao_caso = True
        self.resultado.data_aplicacao = timezone.now()
        self.resultado.aplicado_por = self.usuario
        self.resultado.save()
        
        self._log('SUCCESS', f'✅ Aplicação concluída! {campos_aplicados} campos atualizados')
    
    def _atualizar_campo_padrao(self, nome_campo, valor):
        """Atualiza campo padrão do Caso."""
        if nome_campo == 'valor_apurado':
            valor_limpo = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
            valor = Decimal(valor_limpo)
        
        elif nome_campo == 'data_entrada':
            if isinstance(valor, str):
                valor = datetime.strptime(valor, '%d/%m/%Y').date()
        
        setattr(self.caso, nome_campo, valor)
        self.caso.save()
    
    def _atualizar_campo_personalizado(self, campo_id, valor):
        """Atualiza campo personalizado."""
        campo = CampoPersonalizado.objects.get(id=campo_id)
        
        if campo.tipo_campo == 'DATA':
            pass
        elif campo.tipo_campo in ['MOEDA', 'NUMERO_DEC']:
            valor = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        elif campo.tipo_campo == 'NUMERO_INT':
            valor = str(valor).replace('.', '').replace(',', '').strip()
        
        ValorCampoPersonalizado.objects.update_or_create(
            caso=self.caso,
            campo=campo,
            instancia_grupo=None,
            defaults={'valor': str(valor)}
        )

    # =========================================================================
    # LOGGING
    # =========================================================================
    
    def _log(self, nivel, mensagem, detalhes=None):
        """Registra log da análise."""
        if self.resultado:
            LogAnalise.objects.create(
                resultado=self.resultado,
                nivel=nivel,
                mensagem=mensagem,
                detalhes=detalhes or {}
            )
        
        log_method = getattr(logger, nivel.lower() if nivel != 'SUCCESS' else 'info')
        log_method(f"[Análise #{self.resultado.id if self.resultado else '?'}] {mensagem}")


# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================

def testar_conexao_gemini():
    """Testa se a API do Gemini está funcionando."""
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        response = model.generate_content(
            "Responda apenas com: OK",
            generation_config=genai.GenerationConfig(temperature=0, max_output_tokens=10)
        )
        
        if "OK" in response.text:
            return True, "✅ Conexão com Gemini API funcionando!"
        else:
            return False, f"⚠️ Resposta inesperada: {response.text}"
            
    except Exception as e:
        return False, f"❌ Erro ao conectar: {str(e)}"