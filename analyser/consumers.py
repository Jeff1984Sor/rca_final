# analyser/consumers.py

import json
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync

class AnalysisConsumer(WebsocketConsumer):
    def connect(self):
        # Pega o ID do resultado da URL (ex: '33')
        self.resultado_id = self.scope['url_route']['kwargs']['resultado_id']
        # Cria um nome de "sala" único para esta análise (ex: 'analise_33')
        self.room_group_name = f'analise_{self.resultado_id}'

        # Junta-se à sala. A partir de agora, tudo enviado para esta sala
        # será recebido por este consumidor.
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        
        # Aceita a conexão WebSocket. Se você não chamar isso, a conexão é rejeitada.
        self.accept()

    def disconnect(self, close_code):
        # Quando o usuário fecha a aba, o consumidor sai da sala.
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    # Este método é chamado quando o AnalyserService envia uma mensagem para a sala.
    # O nome do método (analysis_update) corresponde ao 'type' que vamos definir no service.
    def analysis_update(self, event):
        message = event['message']
        # Envia a mensagem para o navegador do usuário através do WebSocket.
        self.send(text_data=json.dumps(message))