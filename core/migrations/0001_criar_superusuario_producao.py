# contas/migrations/0002_criar_superusuario_producao.py

from django.db import migrations
import os

def criar_superusuario(apps, schema_editor):
    # Usamos o modelo padrão de usuário do Django, que fica no app 'auth'
    User = apps.get_model('auth', 'User')

    # Buscamos as credenciais das variáveis de ambiente do Render
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    # Condição de segurança: só executa se todas as variáveis existirem
    if username and email and password:
        # Verifica se um usuário com este username ainda NÃO existe
        if not User.objects.filter(username=username).exists():
            print(f"\nCriando superusuário '{username}'...")
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            print(f"Superusuário '{username}' criado com sucesso!")
        else:
            print(f"\nSuperusuário '{username}' já existe no banco de dados. Nenhuma ação foi tomada.")
    else:
        print("\nVariáveis de ambiente para criação de superusuário não definidas. Pulando a criação.")


class Migration(migrations.Migration):

    dependencies = [
        # Garante que esta migração rode depois da migração inicial do app 'contas'
         
    ]

    operations = [
        migrations.RunPython(criar_superusuario),
    ]