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
    # ==============================================================================
    # CAMPOS PARA RECEBER DADOS (write-only)
    # O n8n vai continuar enviando apenas os IDs no POST
    # ==============================================================================
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    produto = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all())
    advogado_responsavel = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), allow_null=True, required=False
    )
    fase_atual_wf = serializers.PrimaryKeyRelatedField(
        queryset=Fase.objects.all(), allow_null=True, required=False
    )

    # ==============================================================================
    # CAMPOS PARA ENVIAR DADOS NA RESPOSTA (read-only)
    # A API vai devolver estes campos extras para o n8n usar no e-mail
    # ==============================================================================
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True)
    produto_nome = serializers.CharField(source='produto.nome', read_only=True)
    advogado_email = serializers.EmailField(source='advogado_responsavel.email', read_only=True, allow_null=True)
    advogado_nome = serializers.CharField(source='advogado_responsavel.get_full_name', read_only=True, allow_null=True)


    class Meta:
        model = Caso
        # Adicionamos os campos read-only à lista de fields
        fields = [
            'id', 'external_id', 'cliente', 'produto', 'data_entrada', 'status',
            'sharepoint_folder_id', 'titulo', 'data_encerramento',
            'advogado_responsavel', 'fase_atual_wf', 'data_criacao',
            # Campos extras para a resposta da API:
            'cliente_nome', 'produto_nome', 'advogado_email', 'advogado_nome'
        ]
        read_only_fields = ['id', 'sharepoint_folder_id', 'data_criacao']