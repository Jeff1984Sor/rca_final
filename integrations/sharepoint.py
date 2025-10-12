# integrations/sharepoint.py
import os
import msal
import requests

class SharePoint:
    def __init__(self):
        self.tenant_id = os.getenv('M365_TENANT_ID')
        self.client_id = os.getenv('M365_CLIENT_ID')
        self.client_secret = os.getenv('M365_CLIENT_SECRET')
        self.sharepoint_host = os.getenv('SHAREPOINT_HOSTNAME')
        self.sharepoint_site = os.getenv('SHAREPOINT_SITE_NAME')
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.graph_url = "https://graph.microsoft.com/v1.0"

        self.access_token = self._get_access_token()
        self.site_id = self._get_site_id()
        self.drive_id = self._get_drive_id()

    def _get_access_token(self):
        """Autentica e obtém um token de acesso."""
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=self.scope)
        if "access_token" in result:
            return result['access_token']
        else:
            raise Exception("Não foi possível obter o token de acesso: " + result.get("error_description"))

    def _get_headers(self):
        """Monta os cabeçalhos necessários para as requisições."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def _get_site_id(self):
        """Busca o ID do site do SharePoint."""
        url = f"{self.graph_url}/sites/{self.sharepoint_host}:/sites/{self.sharepoint_site}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status() # Lança um erro se a requisição falhar
        return response.json().get('id')

    def _get_drive_id(self):
        """Busca o ID da biblioteca de documentos ('Drive') principal do site."""
        url = f"{self.graph_url}/sites/{self.site_id}/drive"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json().get('id')

    # --- FUNÇÃO DE TESTE ---
    def test_connection(self):
        """Testa a conexão buscando o nome do site."""
        url = f"{self.graph_url}/sites/{self.site_id}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        site_data = response.json()
        print("Conexão bem-sucedida!")
        print(f"Nome do Site: {site_data.get('displayName')}")
        print(f"ID do Site: {self.site_id}")
        print(f"ID do Drive: {self.drive_id}")
        return site_data
    
    def criar_pasta_caso(self, nome_pasta_caso):
        """
        Cria uma pasta principal para o caso na raiz da biblioteca de documentos.
        Retorna o ID da pasta criada.
        """
        print(f"Tentando criar a pasta do caso: '{nome_pasta_caso}' no SharePoint...")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/root/children"
        
        payload = {
            "name": nome_pasta_caso,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        
        response = requests.post(url, headers=self._get_headers(), json=payload)
        response.raise_for_status() # Lança erro se a criação falhar
        
        folder_data = response.json()
        folder_id = folder_data.get('id')
        print(f"Pasta do caso '{nome_pasta_caso}' criada com sucesso! ID: {folder_id}")
        return folder_id

    def criar_subpasta(self, id_pasta_pai, nome_subpasta):
        """
        Cria uma subpasta dentro de uma pasta existente.
        """
        print(f"Tentando criar a subpasta: '{nome_subpasta}'...")

        url = f"{self.graph_url}/drives/{self.drive_id}/items/{id_pasta_pai}/children"
        
        payload = {
            "name": nome_subpasta,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail" # Falha se a subpasta já existir
        }
        
        response = requests.post(url, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        
        print(f"Subpasta '{nome_subpasta}' criada com sucesso!")
        return response.json()
    
    def listar_conteudo_pasta(self, folder_id):

        """
        Lista os arquivos e subpastas de uma pasta específica.
        'folder_id' pode ser o ID da pasta do caso ou de qualquer subpasta.
        """
        print(f"Listando conteúdo da pasta com ID: {folder_id}")
        
        # O parâmetro '$expand=thumbnails' tenta pegar uma miniatura, se disponível
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{folder_id}/children?$expand=thumbnails"
        
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        
        return response.json().get('value', [])
    def get_folder_details(self, folder_id):
        """Busca os metadados de um item (pasta ou arquivo) pelo seu ID."""
        print(f"Buscando detalhes do item com ID: {folder_id}")
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{folder_id}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_preview_url(self, item_id):
        """Obtém uma URL de preview para um arquivo."""
        print(f"Obtendo URL de preview para o item ID: {item_id}")
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{item_id}/preview"
        headers = self._get_headers()
        # Para o preview, a chamada é um POST vazio
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json().get('getUrl')
    
    def upload_arquivo(self, folder_id, file_name, file_content):
        """
        Faz o upload de um arquivo para uma pasta específica no SharePoint.
        :param folder_id: ID da pasta de destino.
        :param file_name: Nome do arquivo a ser criado.
        :param file_content: O conteúdo binário do arquivo.
        """
        print(f"--- INICIANDO UPLOAD NO SERVIÇO SHAREPOINT ---")
        print(f"Nome do arquivo: {file_name}")
        print(f"Pasta de destino ID: {folder_id}")
        
        # A URL para upload de arquivos usa o formato: /items/{parent-id}:/{filename}:/content
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{folder_id}:/{file_name}:/content"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/octet-stream' # Tipo de conteúdo para dados binários
        }
        
        response = requests.put(url, headers=headers, data=file_content)
        
        # Lança um erro HTTP se o status code não for de sucesso (200, 201, etc.)
        response.raise_for_status() 
        
        print(f"Arquivo '{file_name}' enviado com sucesso para o SharePoint!")
        return response.json()
    
    def excluir_item(self, item_id):
        """
        Exclui um item (arquivo ou pasta) do SharePoint pelo seu ID.
        """
        print(f"Excluindo item com ID: {item_id}...")
        
        url = f"{self.graph_url}/drives/{self.drive_id}/items/{item_id}"
        
        # A requisição de exclusão usa o método HTTP DELETE
        response = requests.delete(url, headers=self._get_headers())
        
        # raise_for_status() vai lançar um erro se a exclusão falhar
        # DELETE bem-sucedido retorna um status 204 No Content
        response.raise_for_status()
        
        print(f"Item com ID {item_id} excluído com sucesso!")
        # DELETE não retorna um corpo JSON, então não retornamos nada
        return True

    
    