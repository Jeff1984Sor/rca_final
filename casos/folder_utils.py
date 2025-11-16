# casos/folder_utils.py

from pastas.models import EstruturaPasta
from integrations.sharepoint import SharePoint

def recriar_estrutura_de_pastas(caso_instance):
    """
    Cria a pasta principal e as subpastas para um caso no SharePoint.
    Esta função pode ser chamada por um signal ou por uma view.
    """
    print(f"Iniciando processo de criação de pastas para o Caso #{caso_instance.id}...")

    # 1. Busca a estrutura de pastas definida
    try:
        estrutura = EstruturaPasta.objects.get(
            cliente=caso_instance.cliente,
            produto=caso_instance.produto
        )
    except EstruturaPasta.DoesNotExist:
        print("Nenhuma estrutura de pastas encontrada. Nenhuma ação será tomada.")
        # Lança uma exceção para que a view saiba que falhou
        raise ValueError("Nenhuma estrutura de pastas foi definida para este Cliente/Produto no Admin.")

    pastas_a_criar = estrutura.pastas.all()
    if not pastas_a_criar:
        print("Estrutura encontrada, mas sem pastas associadas.")
        # Lança uma exceção
        raise ValueError("A estrutura de pastas encontrada está vazia (sem subpastas definidas).")

    # 2. Conecta ao SharePoint e cria as pastas
    try:
        sp = SharePoint()
        
        # Cria a pasta principal (ex: "29")
        nome_pasta_caso = str(caso_instance.id)
        folder_id = sp.criar_pasta_caso(nome_pasta_caso)
        
        # Salva o novo ID no modelo de Caso
        caso_instance.sharepoint_folder_id = folder_id
        caso_instance.save(update_fields=['sharepoint_folder_id'])
        
        # Cria as subpastas
        for pasta in pastas_a_criar:
            sp.criar_subpasta(folder_id, pasta.nome)
        
        print("Processo de criação de pastas no SharePoint concluído com sucesso!")
        return folder_id # Retorna o ID da nova pasta raiz

    except Exception as e:
        print(f"ERRO ao criar pastas no SharePoint para o Caso #{caso_instance.id}: {e}")
        # Relança a exceção para que a view possa mostrá-la ao usuário
        raise e