# analyser/services.py

import logging
import json
import re
from datetime import datetime
from decimal import Decimal
import requests

from django.utils import timezone
from django.conf import settings

import google.generativeai as genai

from .models import ResultadoAnalise, LogAnalise, ModeloAnalise
from campos_custom.models import CampoPersonalizado, ValorCampoPersonalizado

from .models import ResultadoAnalise,LogAnalise
from integrations.sharepoint import SharePoint

logger = logging.getLogger(__name__)


class AnalyserService:
    """
    Serviço para análise de documentos com Google Gemini AI.
    
    Fluxo:
    1. Baixa arquivos do SharePoint
    2. Gera prompt baseado no modelo de análise
    3. Envia para Gemini API
    4. Extrai dados estruturados (JSON)
    5. Gera resumo do caso
    6. Aplica dados ao caso
    """
    
    def __init__(self, caso, modelo_analise, arquivos_selecionados, usuario):
        self.caso = caso
        self.modelo = modelo_analise
        self.arquivos_info = arquivos_selecionados
        self.usuario = usuario
        self.resultado = None
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel(
            model_name=getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-pro')
        )
    
    def executar_analise(self) -> ResultadoAnalise:
        """
        Método principal que orquestra o processo de análise usando a estratégia MapReduce.
        """
        
        
        # Cria o registro da análise com status inicial 'PROCESSANDO'
        self.resultado = ResultadoAnalise.objects.create(
            caso=self.caso,
            modelo_usado=self.modelo,
            arquivos_analisados=self.arquivos_info,
            status='PROCESSANDO',
            criado_por=self.usuario
        )
        self._log('INFO', f'🚀 Análise #{self.resultado.id} iniciada para o Caso #{self.caso.id}.')
        inicio = timezone.now()
        try:
           # --- Etapa 1: MAP - Analisa cada arquivo individualmente ---
            resultados_parciais = []
            for arquivo_info in self.arquivos_info:
                self._log('INFO', f'📄 Processando arquivo: {arquivo_info["nome"]}...')
                try:
                    arquivo_preparado = self._preparar_um_arquivo(arquivo_info) # Prepara apenas um arquivo
                    prompt_extracao = self._gerar_prompt_extracao()
                    dados_parciais = self._chamar_gemini(prompt_extracao, arquivo_preparado, is_json=True)
                    resultados_parciais.append(dados_parciais)
                    self._log('SUCCESS', f'  -> ✅ Extração do arquivo "{arquivo_info["nome"]}" concluída.')
                except Exception as e:
                    self._log('WARNING', f'  -> ⚠️ Falha ao processar o arquivo "{arquivo_info["nome"]}": {e}')
                    continue
            if not resultados_parciais:
                raise ValueError("Nenhum arquivo pôde ser analisado com sucesso.")
            
            # --- Etapa 2: REDUCE - Consolida os resultados ---
            self._log('INFO', '🔄 Consolidando os resultados de todos os arquivos...')
            prompt_consolidacao = self._gerar_prompt_consolidacao(resultados_parciais)
            dados_extraidos = self._chamar_gemini(prompt_consolidacao, is_json=True)
            self.resultado.dados_extraidos = dados_extraidos
            self._log('SUCCESS', f'✅ Consolidação de {len(dados_extraidos)} campos concluída.')

            # --- Etapa 3: Gerar o resumo (se aplicável) ---
            if self.modelo.gerar_resumo:
                prompt_resumo = self._gerar_prompt_resumo(dados_extraidos)
                resumo = self._chamar_gemini(prompt_resumo, is_json=False)
                self.resultado.resumo_caso = resumo
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
            self._log('INFO', f'🏁 Análise finalizada com status: {self.resultado.status}. Duração: {self.resultado.tempo_processamento}.')

        return self.resultado
    

    # ✅✅✅ NOVO MÉTODO PARA CONSOLIDAÇÃO ✅✅✅
    def _gerar_prompt_consolidacao(self, resultados_parciais: list) -> str:
        """
        Gera um prompt para a IA consolidar múltiplos resultados JSON em um único.
        """
        json_resultados = json.dumps(resultados_parciais, indent=2, ensure_ascii=False)
        
        return f"""
# INSTRUÇÃO PRINCIPAL
Você recebeu uma lista de objetos JSON, cada um contendo dados extraídos de um documento diferente. Sua tarefa é consolidar todas essas informações em um **único objeto JSON final e coerente**.

# REGRAS DE CONSOLIDAÇÃO
1.  **Combine as informações:** Se o mesmo campo (ex: "valor_apurado") aparece em múltiplos JSONs, escolha o valor mais completo ou relevante. Se forem textos, concatene-os com "\\n".
2.  **Elimine "Não encontrado":** Se um campo tem um valor real em um JSON e "Não encontrado" em outro, use o valor real.
3.  **Mantenha o formato:** O JSON final deve ter as mesmas chaves que os JSONs de entrada.
4.  **OBRIGATÓRIO:** Sua resposta DEVE ser APENAS o JSON final consolidado. Não inclua explicações ou texto extra.

# DADOS PARCIAIS PARA CONSOLIDAR
```json
{json_resultados}"""


    # ==========================================================================
    # PREPARAÇÃO DE ARQUIVOS
    # ==========================================================================
    
    def _preparar_um_arquivo(self, arquivo_info: dict) -> dict:
        """
        Baixa um único arquivo do SharePoint e o prepara para a API Gemini.
        """
        nome_arquivo = arquivo_info.get("nome", "desconhecido")
        self._log('INFO', f'  -> Baixando "{nome_arquivo}"...')
        
        conteudo_bytes = self._baixar_do_sharepoint(arquivo_info)
        if not conteudo_bytes:
            raise ValueError("O conteúdo retornado está vazio.")
        
        arquivo_preparado = {
            'mime_type': arquivo_info.get('tipo', 'application/pdf'),
            'data': conteudo_bytes
        }
        
        self._log('SUCCESS', f'  -> ✅ Arquivo "{nome_arquivo}" preparado com sucesso ({len(conteudo_bytes) // 1024} KB).')
        return arquivo_preparado
    
    def _baixar_do_sharepoint(self, arquivo_info: dict) -> bytes:
        """
        Baixa o conteúdo de um único arquivo do SharePoint.
        
        Args:
            arquivo_info: Dicionário contendo pelo menos o 'id' e o 'nome' do arquivo.
            
        Returns:
            O conteúdo do arquivo em bytes.
            
        Raises:
            ConnectionError: Se houver um erro de rede ou autenticação com o SharePoint.
            ValueError: Se a URL de download não for encontrada ou o arquivo estiver vazio.
        """
        nome_arquivo = arquivo_info.get('nome', 'desconhecido')
        arquivo_id = arquivo_info.get('id')
        
        if not arquivo_id:
            raise ValueError("O dicionário 'arquivo_info' não contém um 'id'.")

        try:
            sp = SharePoint()
            
            # 1. Busca os detalhes do item para obter a URL de download
            # (Sugestão: renomear 'get_folder_details' para 'get_item_details' na sua classe SharePoint)
            item_details = sp.get_item_details(arquivo_id)
            
            download_url = item_details.get('@microsoft.graph.downloadUrl')
            
            if not download_url:
                raise ValueError(f"A API do SharePoint não retornou uma URL de download para o arquivo '{nome_arquivo}'.")
            
            # 2. Baixa o conteúdo do arquivo
            response = requests.get(download_url, timeout=30) # Adiciona um timeout de 30s
            response.raise_for_status() # Lança um erro para status 4xx/5xx
            
            conteudo_bytes = response.content
            
            # 3. Valida o conteúdo
            if not conteudo_bytes:
                raise ValueError(f"O arquivo '{nome_arquivo}' foi baixado mas está vazio.")
            
            return conteudo_bytes
            
        except requests.exceptions.RequestException as e:
            # Captura erros de rede específicos do 'requests'
            raise ConnectionError(f"Erro de rede ao tentar baixar '{nome_arquivo}': {e}")
        except Exception as e:
            # Captura outros erros (ex: da sua classe SharePoint, ValueErrors, etc.)
            # e os relança como um ConnectionError para ser tratado no método principal.
            raise ConnectionError(f"Falha ao processar o arquivo '{nome_arquivo}' no SharePoint: {e}")

    
    # ==========================================================================
    # GERAÇÃO DE PROMPT
    # ==========================================================================
    
    def _gerar_prompt_extracao(self):
        """
        Gera o prompt completo para o Gemini baseado no modelo de análise.
        
        Returns:
            str: Prompt formatado
        """
        campos = self.modelo.get_campos_para_extrair()
        
        prompt = f"""# ANÁLISE DE DOCUMENTOS JURÍDICOS

{self.modelo.instrucoes_gerais}

## INFORMAÇÕES DO CASO
- **Cliente:** {self.caso.cliente.nome}
- **Produto:** {self.caso.produto.nome}
- **Caso ID:** #{self.caso.id}

## CAMPOS A EXTRAIR DOS DOCUMENTOS

Analise os documentos anexados e extraia as seguintes informações:

"""
        
        for i, campo in enumerate(campos, 1):
            prompt += f"\n### {i}. {campo['label']}\n"
            
            # Adiciona descrição personalizada se houver
            descricao = self.modelo.descricoes_campos.get(campo['nome'], '')
            if descricao:
                prompt += f"{descricao}\n"
            else:
                prompt += f"Extraia o valor do campo '{campo['label']}' dos documentos.\n"
            
            # Adiciona informações sobre o tipo
            prompt += f"**Tipo:** {campo['tipo']}\n"
            
            # Dicas específicas por tipo
            if campo['tipo'] == 'DATA':
                prompt += "**Formato esperado:** DD/MM/AAAA\n"
                prompt += "**Exemplos válidos:** 15/03/2025, 01/01/2024\n"
            elif campo['tipo'] in ['MOEDA', 'NUMERO_DEC']:
                prompt += "**Formato esperado:** Apenas números (ex: 10000.50)\n"
                prompt += "**Observação:** Não inclua símbolos como R$, apenas o valor numérico\n"
            elif campo['tipo'] == 'NUMERO_INT':
                prompt += "**Formato esperado:** Apenas números inteiros (ex: 42)\n"
            elif campo['tipo'] == 'BOOLEANO':
                prompt += "**Formato esperado:** true ou false\n"
            elif campo['tipo'] == 'TEXTO':
                prompt += "**Formato esperado:** Texto curto e objetivo\n"
            elif campo['tipo'] in ['LISTA_USUARIOS', 'LISTA_UNICA']:
                prompt += "**Formato esperado:** Um valor da lista de opções\n"
            elif campo['tipo'] == 'LISTA_MULTIPLA':
                prompt += "**Formato esperado:** Valores separados por vírgula\n"
            
            prompt += "\n"
        
        prompt += """
## FORMATO DE RESPOSTA OBRIGATÓRIO

⚠️ IMPORTANTE: Você DEVE responder APENAS com um JSON válido, sem nenhum texto adicional.
Não inclua explicações, comentários, markdown ou qualquer texto fora do JSON.

Use exatamente os nomes dos campos listados acima como chaves do JSON.

Exemplo de formato:
{
"""
        
        for i, campo in enumerate(campos):
            virgula = "," if i < len(campos) - 1 else ""
            prompt += f'  "{campo["label"]}": "valor_extraído"{virgula}\n'
        
        prompt += """}

## REGRAS DE EXTRAÇÃO

1. ✅ Se não encontrar uma informação, use exatamente: "Não encontrado"
2. ✅ Para datas, use sempre formato DD/MM/AAAA
3. ✅ Para valores monetários e decimais, use apenas números com ponto decimal (ex: 10000.50)
4. ✅ Seja preciso e objetivo - extraia exatamente o que está no documento
5. ✅ Não invente informações - apenas extraia o que realmente existe
6. ✅ Se houver múltiplas ocorrências, use a primeira encontrada
7. ✅ Para campos booleanos, use "true" ou "false"
8. ✅ Retorne APENAS o JSON puro, sem markdown ou explicações
9. ✅ Certifique-se de que o JSON está válido e bem formatado

---

**📁 Documentos anexados para análise:**
"""
        
        for i, arquivo in enumerate(self.arquivos_info, 1):
            prompt += f"\n{i}. **{arquivo['nome']}**"
            if arquivo.get('pasta'):
                prompt += f" (Pasta: {arquivo['pasta']})"
        
        prompt += "\n\n**Agora analise os documentos e retorne APENAS o JSON com os dados extraídos.**"
        secao_arquivos = "\n".join(
                                        f"- **{arquivo['nome']}**" for arquivo in self.arquivos_info
                                    )
        return prompt
    
    def _gerar_prompt(self):
        """
        Gera o prompt completo para o Gemini baseado no modelo de análise.
        
        Returns:
            str: Prompt formatado
        """
        campos = self.modelo.get_campos_para_extrair()
        
        prompt = f"""# ANÁLISE DE DOCUMENTOS JURÍDICOS

{self.modelo.instrucoes_gerais}

## INFORMAÇÕES DO CASO
- **Cliente:** {self.caso.cliente.nome}
- **Produto:** {self.caso.produto.nome}
- **Caso ID:** #{self.caso.id}

## CAMPOS A EXTRAIR DOS DOCUMENTOS

Analise os documentos anexados e extraia as seguintes informações:

"""
        
        for i, campo in enumerate(campos, 1):
            prompt += f"\n### {i}. {campo['label']}\n"
            
            # Adiciona descrição personalizada se houver
            descricao = self.modelo.descricoes_campos.get(campo['nome'], '')
            if descricao:
                prompt += f"{descricao}\n"
            else:
                prompt += f"Extraia o valor do campo '{campo['label']}' dos documentos.\n"
            
            # Adiciona informações sobre o tipo
            prompt += f"**Tipo:** {campo['tipo']}\n"
            
            # Dicas específicas por tipo
            if campo['tipo'] == 'DATA':
                prompt += "**Formato esperado:** DD/MM/AAAA\n"
                prompt += "**Exemplos válidos:** 15/03/2025, 01/01/2024\n"
            elif campo['tipo'] in ['MOEDA', 'NUMERO_DEC']:
                prompt += "**Formato esperado:** Apenas números (ex: 10000.50)\n"
                prompt += "**Observação:** Não inclua símbolos como R$, apenas o valor numérico\n"
            elif campo['tipo'] == 'NUMERO_INT':
                prompt += "**Formato esperado:** Apenas números inteiros (ex: 42)\n"
            elif campo['tipo'] == 'BOOLEANO':
                prompt += "**Formato esperado:** true ou false\n"
            elif campo['tipo'] == 'TEXTO':
                prompt += "**Formato esperado:** Texto curto e objetivo\n"
            elif campo['tipo'] in ['LISTA_USUARIOS', 'LISTA_UNICA']:
                prompt += "**Formato esperado:** Um valor da lista de opções\n"
            elif campo['tipo'] == 'LISTA_MULTIPLA':
                prompt += "**Formato esperado:** Valores separados por vírgula\n"
            
            prompt += "\n"
        
        prompt += """
## FORMATO DE RESPOSTA OBRIGATÓRIO

⚠️ IMPORTANTE: Você DEVE responder APENAS com um JSON válido, sem nenhum texto adicional.
Não inclua explicações, comentários, markdown ou qualquer texto fora do JSON.

Use exatamente os nomes dos campos listados acima como chaves do JSON.

Exemplo de formato:
{
"""
        
        for i, campo in enumerate(campos):
            virgula = "," if i < len(campos) - 1 else ""
            prompt += f'  "{campo["label"]}": "valor_extraído"{virgula}\n'
        
        prompt += """}

## REGRAS DE EXTRAÇÃO

1. ✅ Se não encontrar uma informação, use exatamente: "Não encontrado"
2. ✅ Para datas, use sempre formato DD/MM/AAAA
3. ✅ Para valores monetários e decimais, use apenas números com ponto decimal (ex: 10000.50)
4. ✅ Seja preciso e objetivo - extraia exatamente o que está no documento
5. ✅ Não invente informações - apenas extraia o que realmente existe
6. ✅ Se houver múltiplas ocorrências, use a primeira encontrada
7. ✅ Para campos booleanos, use "true" ou "false"
8. ✅ Retorne APENAS o JSON puro, sem markdown ou explicações
9. ✅ Certifique-se de que o JSON está válido e bem formatado

---

**📁 Documentos anexados para análise:**
"""
        
        for i, arquivo in enumerate(self.arquivos, 1):
            prompt += f"\n{i}. **{arquivo['nome']}**"
            if arquivo.get('pasta'):
                prompt += f" (Pasta: {arquivo['pasta']})"
        
        prompt += "\n\n**Agora analise os documentos e retorne APENAS o JSON com os dados extraídos.**"
        
        return prompt
    
    # ==========================================================================
    # ANÁLISE COM GEMINI
    # ==========================================================================
    
    def _chamar_gemini(self, prompt: str, arquivos: list = None, is_json: bool = False):
        """
        Chama a API Gemini com um prompt e arquivos, e processa a resposta.

        Args:
            prompt: O texto do prompt a ser enviado.
            arquivos: Uma lista de dicionários de arquivos preparados (opcional).
            is_json: Se True, espera e tenta extrair um JSON da resposta.

        Returns:
            Um dicionário (se is_json=True) ou uma string com a resposta.
        """
        # --- 1. Monta o conteúdo da requisição ---
        content = [prompt]
        if arquivos:
            content.extend(arquivos)

        self._log('INFO', f"🤖 Enviando requisição para a IA ({'JSON' if is_json else 'Texto'}) com {len(arquivos or [])} arquivo(s)...")

        # --- 2. Define as configurações da API ---
        generation_config = genai.GenerationConfig(
            temperature=0.1 if is_json else 0.4,
            max_output_tokens=8192 if is_json else 2048
        )
        
        safety_settings = [
            {"category": c, "threshold": "BLOCK_NONE"} 
            for c in [
                "HARM_CATEGORY_HARASSMENT", 
                "HARM_CATEGORY_HATE_SPEECH", 
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", 
                "HARM_CATEGORY_DANGEROUS_CONTENT"
            ]
        ]

        # --- 3. Executa a chamada à API ---
        try:
            response = self.gemini_model.generate_content(
                content,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            self._log('SUCCESS', f'✅ Resposta recebida da IA ({len(response.text)} caracteres).')
            
            # --- 4. Processa a resposta ---
            if is_json:
                # Tenta extrair um objeto JSON da resposta de texto
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if not json_match:
                    raise ValueError("Nenhum objeto JSON foi encontrado na resposta da IA.")
                
                json_text = json_match.group(0)
                return json.loads(json_text)
            
            # Se não for JSON, retorna o texto limpo
            return response.text.strip()

        except Exception as e:
            logger.error(f"Erro na comunicação com a API Gemini: {e}", exc_info=True)
            self._log('ERROR', f'❌ Erro na comunicação com Gemini: {e}')
            # Relança a exceção para ser tratada pelo método `executar_analise`
            raise
    def _extrair_json_da_resposta(self, resposta_texto):
        """
        Extrai JSON da resposta do Gemini.
        Remove markdown e outros textos extras.
        
        Args:
            resposta_texto: String com a resposta do Gemini
            
        Returns:
            dict: Dados extraídos
        """
        # Remove markdown code blocks (```json ... ```)
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', resposta_texto, re.DOTALL)
        if json_match:
            resposta_texto = json_match.group(1)
        
        # Remove espaços em branco extras
        resposta_texto = resposta_texto.strip()
        
        try:
            # Parse JSON
            dados = json.loads(resposta_texto)
            
            # Valida que é um dicionário
            if not isinstance(dados, dict):
                raise ValueError("Resposta não é um objeto JSON válido")
            
            return dados
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse do JSON: {str(e)}")
            logger.error(f"Resposta recebida: {resposta_texto[:500]}...")
            
            # Tenta limpar e parsear novamente
            resposta_limpa = resposta_texto.replace('\n', ' ').replace('\r', '')
            try:
                dados = json.loads(resposta_limpa)
                return dados
            except:
                self._log('ERROR', f'❌ Não foi possível fazer parse da resposta JSON')
                raise ValueError(f"Resposta não é um JSON válido. Primeiros 200 caracteres: {resposta_texto[:200]}...")
    
    # ==========================================================================
    # GERAÇÃO DE RESUMO
    # ==========================================================================
    
    def _gerar_resumo(self, dados_extraidos):
        """
        Gera um resumo executivo do caso usando Gemini.
        
        Args:
            dados_extraidos: Dict com os dados extraídos
            
        Returns:
            str: Resumo do caso
        """
        prompt = f"""# GERAR RESUMO EXECUTIVO

Com base nos dados extraídos abaixo, crie um resumo executivo do caso jurídico.

## Informações do Caso
- **Cliente:** {self.caso.cliente.nome}
- **Produto:** {self.caso.produto.nome}
- **Caso ID:** #{self.caso.id}

## Dados Extraídos
```json
{json.dumps(dados_extraidos, indent=2, ensure_ascii=False)}
```

## Instruções para o Resumo
1. Resuma as informações principais do caso em até 3 parágrafos
2. Destaque pontos importantes (datas, valores, partes envolvidas)
3. Use linguagem clara, objetiva e profissional
4. Foque no essencial para entender rapidamente o caso
5. NÃO adicione informações que não estejam nos dados extraídos
6. NÃO inclua especulações ou suposições

**Resumo Executivo:**
"""
        
        try:
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1000,
                )
            )
            
            resumo = response.text.strip()
            
            self._log('SUCCESS', f'✅ Resumo gerado ({len(resumo)} caracteres)')
            
            return resumo
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {str(e)}")
            self._log('WARNING', f'⚠️ Não foi possível gerar o resumo: {str(e)}')
            return None
    
    def _gerar_prompt_resumo(self, dados_extraidos):
        """
        Gera um resumo executivo do caso usando Gemini.
        
        Args:
            dados_extraidos: Dict com os dados extraídos
            
        Returns:
            str: Resumo do caso
        """
        prompt = f"""# GERAR RESUMO EXECUTIVO

Com base nos dados extraídos abaixo, crie um resumo executivo do caso jurídico.

## Informações do Caso
- **Cliente:** {self.caso.cliente.nome}
- **Produto:** {self.caso.produto.nome}
- **Caso ID:** #{self.caso.id}

## Dados Extraídos
```json
{json.dumps(dados_extraidos, indent=2, ensure_ascii=False)}
```

## Instruções para o Resumo
1. Resuma as informações principais do caso em até 3 parágrafos
2. Destaque pontos importantes (datas, valores, partes envolvidas)
3. Use linguagem clara, objetiva e profissional
4. Foque no essencial para entender rapidamente o caso
5. NÃO adicione informações que não estejam nos dados extraídos
6. NÃO inclua especulações ou suposições

**Resumo Executivo:**
"""
        
        try:
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=100000,
                )
            )
            
            resumo = response.text.strip()
            
            self._log('SUCCESS', f'✅ Resumo gerado ({len(resumo)} caracteres)')
            
            return resumo
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo: {str(e)}")
            self._log('WARNING', f'⚠️ Não foi possível gerar o resumo: {str(e)}')
            return None
    # ==========================================================================
    # APLICAÇÃO DOS DADOS AO CASO
    # ==========================================================================
    
    def aplicar_ao_caso(self):
        """
        Aplica os dados extraídos ao caso no sistema.
        Atualiza campos padrão e personalizados.
        """
        if self.resultado.status != 'CONCLUIDO':
            raise ValueError("❌ Só é possível aplicar análises concluídas")
        
        if self.resultado.aplicado_ao_caso:
            raise ValueError("⚠️ Análise já foi aplicada ao caso")
        
        self._log('INFO', '💾 Aplicando dados ao caso...')
        print("💾 Aplicando dados ao caso...")
        
        campos = self.modelo.get_campos_para_extrair()
        campos_aplicados = 0
        campos_ignorados = 0
        campos_com_erro = 0
        
        for campo in campos:
            campo_label = campo['label']
            valor_extraido = self.resultado.dados_extraidos.get(campo_label)
            
            # Pula campos não encontrados
            if not valor_extraido or valor_extraido == "Não encontrado":
                campos_ignorados += 1
                self._log('INFO', f'⏭️ Campo pulado (não encontrado): {campo_label}')
                continue
            
            try:
                if campo['is_padrao']:
                    # Atualiza campo padrão do Caso
                    self._atualizar_campo_padrao(campo['nome'], valor_extraido)
                else:
                    # Atualiza campo personalizado
                    self._atualizar_campo_personalizado(campo['campo_id'], valor_extraido)
                
                campos_aplicados += 1
                self._log('SUCCESS', f'✅ Campo atualizado: {campo_label} = {valor_extraido}')
                
            except Exception as e:
                campos_com_erro += 1
                self._log('WARNING', f'⚠️ Erro ao atualizar {campo_label}: {str(e)}')
                print(f"⚠️ Erro ao atualizar {campo_label}: {str(e)}")
        
        # Atualiza resumo do caso (se existir no modelo)
        if self.resultado.resumo_caso:
            try:
                if hasattr(self.caso, 'resumo'):
                    self.caso.resumo = self.resultado.resumo_caso
                    self.caso.save()
                    self._log('SUCCESS', '✅ Resumo do caso atualizado')
            except Exception as e:
                self._log('WARNING', f'⚠️ Erro ao atualizar resumo: {str(e)}')
        
        # Marca como aplicado
        self.resultado.aplicado_ao_caso = True
        self.resultado.data_aplicacao = timezone.now()
        self.resultado.aplicado_por = self.usuario
        self.resultado.save()
        
        # Resumo final
        total = len(campos)
        self._log('SUCCESS', f'✅ Aplicação concluída! {campos_aplicados}/{total} campos atualizados')
        print(f"✅ Aplicação concluída! {campos_aplicados}/{total} campos")
        
        # Cria evento no fluxo interno (se existir)
        self._criar_evento_fluxo_interno(campos_aplicados, total)
    
    def _atualizar_campo_padrao(self, nome_campo, valor):
        """
        Atualiza campo padrão do modelo Caso.
        
        Args:
            nome_campo: Nome do campo no modelo
            valor: Valor a ser atualizado
        """
        # Conversão de tipos
        if nome_campo == 'valor_apurado':
            # Remove formatação e converte para Decimal
            valor_limpo = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
            valor = Decimal(valor_limpo)
        
        elif nome_campo == 'data_entrada':
            # Converte string DD/MM/AAAA para date
            if isinstance(valor, str):
                valor = datetime.strptime(valor, '%d/%m/%Y').date()
        
        # Atualiza o campo
        setattr(self.caso, nome_campo, valor)
        self.caso.save()
    
    def _atualizar_campo_personalizado(self, campo_id, valor):
        """
        Atualiza campo personalizado do caso.
        
        Args:
            campo_id: ID do CampoPersonalizado
            valor: Valor a ser atualizado
        """
        campo = CampoPersonalizado.objects.get(id=campo_id)
        
        # Conversão conforme o tipo
        if campo.tipo_campo == 'DATA':
            # Mantém como string DD/MM/AAAA
            pass
        elif campo.tipo_campo in ['MOEDA', 'NUMERO_DEC']:
            # Remove formatação para decimal
            valor = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        elif campo.tipo_campo == 'NUMERO_INT':
            # Remove formatação e mantém apenas números
            valor = str(valor).replace('.', '').replace(',', '').strip()
        elif campo.tipo_campo == 'BOOLEANO':
            # Converte para string True/False
            valor = 'True' if str(valor).lower() in ['true', 'sim', 'yes', '1'] else 'False'
        elif campo.tipo_campo in ['LISTA_UNICA', 'LISTA_USUARIOS']:
            # Mantém o valor como está
            pass
        elif campo.tipo_campo == 'LISTA_MULTIPLA':
            # Mantém separado por vírgula
            pass
        
        # Atualiza ou cria
        ValorCampoPersonalizado.objects.update_or_create(
            caso=self.caso,
            campo=campo,
            instancia_grupo=None,
            defaults={'valor': str(valor)}
        )
    
    def _criar_evento_fluxo_interno(self, campos_aplicados, total_campos):
        """
        Cria evento no fluxo interno do caso (se existir).
        
        Args:
            campos_aplicados: Número de campos atualizados
            total_campos: Total de campos analisados
        """
        try:
            from casos.models import EventoFluxoInterno
            
            EventoFluxoInterno.objects.create(
                caso=self.caso,
                tipo_evento='ANALISE_IA',
                descricao=f"✅ Análise automática com IA concluída.\n\n"
                          f"📊 Resultado: {campos_aplicados}/{total_campos} campos atualizados\n"
                          f"🤖 Modelo: {self.modelo.nome}\n"
                          f"📁 Arquivos: {len(self.arquivos)}",
                autor=self.usuario
            )
            self._log('SUCCESS', '✅ Evento criado no fluxo interno do caso')
        except ImportError:
            pass
        except Exception as e:
            self._log('WARNING', f'⚠️ Não foi possível criar evento no fluxo: {str(e)}')
    
    # ==========================================================================
    # LOGGING
    # ==========================================================================
    
    def _log(self, nivel, mensagem, detalhes=None):
        """
        Registra log da análise.
        
        Args:
            nivel: Nível do log (INFO, SUCCESS, WARNING, ERROR)
            mensagem: Mensagem do log
            detalhes: Dict com detalhes adicionais (opcional)
        """
        if self.resultado:
            LogAnalise.objects.create(
                resultado=self.resultado,
                nivel=nivel,
                mensagem=mensagem,
                detalhes=detalhes or {}
            )
        
        # Log no console também
        log_method = getattr(logger, nivel.lower() if nivel != 'SUCCESS' else 'info')
        log_method(f"[Análise #{self.resultado.id if self.resultado else '?'}] {mensagem}")


# ==============================================================================
# 🔧 FUNÇÕES AUXILIARES
# ==============================================================================

def testar_conexao_gemini():
    """
    Testa se a API do Gemini está funcionando corretamente.
    
    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        response = model.generate_content(
            "Responda apenas com a palavra: OK",
            generation_config=genai.GenerationConfig(
                temperature=0,
                max_output_tokens=10,
            )
        )
        
        if "OK" in response.text:
            return True, "✅ Conexão com Gemini API funcionando perfeitamente!"
        else:
            return False, f"⚠️ Resposta inesperada: {response.text}"
            
    except Exception as e:
        return False, f"❌ Erro ao conectar: {str(e)}"


def obter_modelos_disponiveis():
    """
    Lista modelos disponíveis na API do Gemini.
    
    Returns:
        list: Lista de modelos disponíveis
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        modelos = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos.append({
                    'name': m.name,
                    'display_name': m.display_name,
                    'description': m.description,
                })
        
        return modelos
        
    except Exception as e:
        logger.error(f"Erro ao listar modelos: {str(e)}")
        return []