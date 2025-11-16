# integrations/sharepoint.py
import os
import msal
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class SharePoint:
    """
    Cliente para integração com Microsoft SharePoint Online via Microsoft Graph API.
    Fornece métodos para listar, fazer upload, download e gerenciar arquivos.
    """
    
    def __init__(self):
        self.tenant_id = os.getenv('M365_TENANT_ID')
        self.client_id = os.getenv('M365_CLIENT_ID')
        self.client_secret = os.getenv('M365_CLIENT_SECRET')
        self.sharepoint_host = os.getenv('SHAREPOINT_HOSTNAME')
        self.sharepoint_site = os.getenv('SHAREPOINT_SITE_NAME')
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.graph_url = "https://graph.microsoft.com/v1.0"

        self._access_token = None
        self._token_expiry = None
        self.site_id = self._get_site_id()
        self.drive_id = self._get_drive_id()
        
        logger.info(f"✅ SharePoint inicializado - Site ID: {self.site_id}, Drive ID: {self.drive_id}")

    def _get_access_token(self):
        """Autentica e obtém um token de acesso com cache."""
        if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
            logger.debug("🔑 Usando token em cache")
            return self._access_token
        
        logger.info("🔑 Obtendo novo token de acesso...")
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )
        
        result = app.acquire_token_for_client(scopes=self.scope)
        
        if "access_token" in result:
            self._access_token = result['access_token']
            self._token_expiry = datetime.now() + timedelta(minutes=55)
            logger.info("✅ Token obtido com sucesso")
            return self._access_token
        else:
            error_msg = result.get("error_description", "Erro desconhecido")
            logger.error(f"❌ Erro ao obter token: {error_msg}")
            raise Exception(f"Não foi possível obter o token de acesso: {error_msg}")

    @property
    def access_token(self):
        """Property para obter token (com cache automático)."""
        return self._get_access_token()

    def _get_headers(self):
        """Monta os cabeçalhos necessários para as requisições."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def _get_site_id(self):
        """Busca o ID do site do SharePoint."""
        logger.info(f"🔍 Buscando ID do site: {self.sharepoint_host}/sites/{self.sharepoint_site}")
        url = f"{self.graph_url}/sites/{self.sharepoint_host}:/sites/{self.sharepoint_site}"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            site_id = response.json().get('id')
            logger.info(f"✅ Site ID encontrado: {site_id}")
            return site_id
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao buscar Site ID: {e}")
            raise

    def _get_drive_id(self):
        """Busca o ID da biblioteca de documentos (Drive) principal do site."""
        logger.info(f"🔍 Buscando Drive ID para o site {self.site_id}")
        url = f"{self.graph_url}/sites/{self.site_id}/drive"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            drive_id = response.json().get('id')
            logger.info(f"✅ Drive ID encontrado: {drive_id}")
            return drive_id
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao buscar Drive ID: {e}")
            raise

    def test_connection(self):
        """Testa a conexão com SharePoint."""
        logger.info("🧪 Testando conexão com SharePoint...")
        try:
            url = f"{self.graph_url}/sites/{self.site_id}"
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            site_data = response.json()
            
            logger.info("✅ Conexão bem-sucedida!")
            logger.info(f"   → Nome do Site: {site_data.get('displayName')}")
            logger.info(f"   → ID do Site: {self.site_id}")
            logger.info(f"   → ID do Drive: {self.drive_id}")
            
            return site_data
        except Exception as e:
            logger.error(f"❌ Erro na conexão: {e}")
            raise
    
    def listar_arquivos_pasta_raiz(self) -> List[Dict]:
        """Lista todos os arquivos e pastas da raiz da biblioteca de documentos."""
        logger.info("📁 Listando arquivos e pastas da raiz...")
        try:
            return self.listar_conteudo_pasta('root')
        except Exception as e:
            logger.error(f"❌ Erro ao listar pasta raiz: {e}")
            return []
    
    def listar_arquivos_pasta(self, folder_id: str) -> List[Dict]:
        """Lista todos os arquivos e pastas de uma pasta específica."""
        logger.info(f"📁 Listando arquivos da pasta: {folder_id}...")
        try:
            return self.listar_conteudo_pasta(folder_id)
        except Exception as e:
            logger.error(f"❌ Erro ao listar pasta {folder_id}: {e}")
            return []
    
    def listar_conteudo_pasta(self, folder_id: str) -> List[Dict]:
        """Lista os arquivos e subpastas de uma pasta específica."""
        logger.debug(f"Listando conteúdo da pasta com ID: {folder_id}")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{folder_id}/children?$expand=thumbnails&$top=1000"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            itens = response.json().get('value', [])
            
            itens_processados = []
            for item in itens:
                item_processado = {
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'file': item.get('file', {}),
                    'folder': item.get('folder'),
                    'size': item.get('size', 0),
                    'createdDateTime': item.get('createdDateTime'),
                    'lastModifiedDateTime': item.get('lastModifiedDateTime'),
                    'webUrl': item.get('webUrl'),
                    'mimeType': item.get('file', {}).get('mimeType', 'folder') if item.get('folder') else item.get('file', {}).get('mimeType', 'application/octet-stream'),
                }
                itens_processados.append(item_processado)
            
            logger.info(f"✅ Encontrados {len(itens_processados)} itens na pasta")
            return itens_processados
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao listar conteúdo da pasta: {e}")
            raise
    
    def criar_pasta_caso(self, nome_pasta_caso: str) -> str:
        """Cria uma pasta principal para o caso na raiz da biblioteca de documentos."""
        logger.info(f"📁 Criando pasta do caso: '{nome_pasta_caso}'...")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/root/children"
        
        payload = {
            "name": nome_pasta_caso,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            response.raise_for_status()
            
            folder_data = response.json()
            folder_id = folder_data.get('id')
            logger.info(f"✅ Pasta '{nome_pasta_caso}' criada com sucesso! ID: {folder_id}")
            return folder_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao criar pasta: {e}")
            raise

    def criar_subpasta(self, id_pasta_pai: str, nome_subpasta: str) -> Dict:
        """Cria uma subpasta dentro de uma pasta existente."""
        logger.info(f"📁 Criando subpasta: '{nome_subpasta}' em {id_pasta_pai}...")

        url = f"{self.graph_url}/drives/{self.drive_id}/items/{id_pasta_pai}/children"
        
        payload = {
            "name": nome_subpasta,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail"
        }
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            response.raise_for_status()
            
            logger.info(f"✅ Subpasta '{nome_subpasta}' criada com sucesso!")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao criar subpasta: {e}")
            raise
    
    def get_item_details(self, item_id: str) -> Dict:
        """Busca os metadados de um item (pasta ou arquivo) pelo seu ID."""
        logger.debug(f"🔍 Buscando detalhes do item: {item_id}")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{item_id}"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            
            item_details = response.json()
            logger.debug(f"✅ Detalhes do item obtidos")
            
            return item_details

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao buscar detalhes do item {item_id}: {e}")
            raise
    
    def get_folder_details(self, folder_id: str) -> Dict:
        """Alias para get_item_details para melhor legibilidade."""
        return self.get_item_details(folder_id)
    
    def get_preview_url(self, item_id: str) -> Optional[str]:
        """Obtém uma URL de preview para um arquivo."""
        logger.info(f"📄 Obtendo URL de preview para: {item_id}")
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{item_id}/preview"
        
        try:
            headers = self._get_headers()
            response = requests.post(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            preview_url = response.json().get('getUrl')
            logger.info(f"✅ URL de preview obtida")
            return preview_url
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível obter preview: {e}")
            return None
    
    def upload_arquivo(self, folder_id: str, file_name: str, file_content: bytes) -> Dict:
        """Faz o upload de um arquivo para uma pasta específica no SharePoint."""
        logger.info(f"📤 Iniciando upload de '{file_name}' para pasta {folder_id}...")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{folder_id}:/{file_name}:/content"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            response = requests.put(url, headers=headers, data=file_content, timeout=60)
            response.raise_for_status()
            
            logger.info(f"✅ Arquivo '{file_name}' enviado com sucesso!")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao fazer upload: {e}")
            raise
    
    def download_arquivo(self, item_id: str) -> bytes:
        """Faz o download de um arquivo do SharePoint."""
        logger.info(f"📥 Iniciando download do arquivo: {item_id}...")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{item_id}/content"
        
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=60)
            response.raise_for_status()
            
            logger.info(f"✅ Arquivo baixado com sucesso ({len(response.content)} bytes)")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao fazer download: {e}")
            raise
    
    def excluir_item(self, item_id: str) -> bool:
        """Exclui um item (arquivo ou pasta) do SharePoint pelo seu ID."""
        logger.warning(f"🗑️  Excluindo item com ID: {item_id}...")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{item_id}"
        
        try:
            response = requests.delete(url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            
            logger.info(f"✅ Item {item_id} excluído com sucesso!")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao excluir item: {e}")
            raise
    
    def buscar_arquivo_por_nome(self, nome: str, folder_id: str = 'root') -> Optional[Dict]:
        """Busca um arquivo por nome em uma pasta específica."""
        logger.info(f"🔍 Buscando arquivo: '{nome}' em pasta {folder_id}...")
        
        try:
            itens = self.listar_conteudo_pasta(folder_id)
            for item in itens:
                if item['name'].lower() == nome.lower():
                    logger.info(f"✅ Arquivo encontrado: {item['id']}")
                    return item
            
            logger.info(f"⚠️ Arquivo '{nome}' não encontrado")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar arquivo: {e}")
            return None
    
    def obter_ou_criar_pasta_caso(self, nome_caso: str) -> str:
        """
        Obtém a pasta do caso ou a cria se não existir.
        
        :param nome_caso: Nome do caso (ex: "Caso #29")
        :return: ID da pasta do caso
        """
        logger.info(f"🔍 Buscando ou criando pasta do caso: '{nome_caso}'...")
        
        try:
            # Tenta buscar a pasta existente
            pasta = self.buscar_arquivo_por_nome(nome_caso, 'root')
            if pasta and pasta.get('folder'):
                logger.info(f"✅ Pasta do caso encontrada: {pasta['id']}")
                return pasta['id']
            
            # Se não existe, cria
            logger.info(f"📁 Criando nova pasta: '{nome_caso}'...")
            folder_id = self.criar_pasta_caso(nome_caso)
            return folder_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter/criar pasta do caso: {e}")
            raise

    # integrations/sharepoint.py (adicionar no final da classe)

def criar_pasta(self, nome_pasta: str, pasta_pai_id: str) -> Dict:
    """
    Alias universal para criar pasta (detecta se é raiz ou subpasta).
    """
    if pasta_pai_id == 'root':
        return {'id': self.criar_pasta_caso(nome_pasta)}
    else:
        return self.criar_subpasta(pasta_pai_id, nome_pasta)

def listar_arquivos_pasta(self, folder_id: str) -> List[Dict]:
    """
    Alias para listar_conteudo_pasta (para compatibilidade).
    """
    return self.listar_conteudo_pasta(folder_id)

def fazer_upload(self, arquivo, pasta_id: str) -> Dict:
    """
    Faz upload de um arquivo Django (InMemoryUploadedFile ou TemporaryUploadedFile).
    """
    logger.info(f"📤 Upload: {arquivo.name} -> pasta {pasta_id}")
    
    # Lê o conteúdo do arquivo
    arquivo.seek(0)  # Garante que está no início
    conteudo = arquivo.read()
    
    # Usa o método original upload_arquivo
    return self.upload_arquivo(pasta_id, arquivo.name, conteudo)

def baixar_arquivo(self, item_id: str) -> bytes:
    """
    Alias para download_arquivo (para compatibilidade).
    """
    return self.download_arquivo(item_id)

def obter_info_arquivo(self, item_id: str) -> Dict:
    """
    Alias para get_item_details (para compatibilidade).
    """
    return self.get_item_details(item_id)