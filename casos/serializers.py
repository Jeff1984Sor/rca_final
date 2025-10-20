# casos/serializers.py

from rest_framework import serializers
from .models import Caso, Andamento, Timesheet, Acordo, Parcela, Despesa, FluxoInterno
from clientes.models import Cliente
from produtos.models import Produto
from django.contrib.auth import get_user_model
from workflow.models import Fase # Assumindo que você tem um modelo Fase em seu app 
from django.utils import timezone

User = get_user_model() # Obtém o modelo de usuário ativo (ex: User do Django)

class CasoSerializer(serializers.ModelSerializer):
    # Campos 'cliente' e 'produto' são ForeignKeys.
    # Usar PrimaryKeyRelatedField permite que a API receba apenas o ID.
    # Ex: "cliente": 1, "produto": 5
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    produto = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all())

    class Meta:
        model = Caso
        
        # Lista de campos que a API vai aceitar/retornar.
        # Adicione ou remova campos conforme sua necessidade.
        fields = [
            'id', 
            'cliente', 
            'produto', 
            'data_entrada', 
            'status', 
            'titulo', 
            'data_encerramento',
            'advogado_responsavel',
            'fase_atual_wf',
            'data_criacao',
            # Não inclua 'sharepoint_folder_id' aqui se ele for gerado depois
        ]
        
        # Campos que são lidos (retornados pela API), mas não exigidos no POST
        read_only_fields = ['id', 'data_criacao', 'titulo']