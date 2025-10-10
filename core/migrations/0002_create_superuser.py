# core/migrations/0002_create_superuser.py
from django.db import migrations
from django.contrib.auth import get_user_model

def create_superuser(apps, schema_editor):
    User = get_user_model()
    
    # DEFINA AQUI OS DADOS DO SEU PRIMEIRO SUPERUSUÁRIO
    # ATENÇÃO: USE UMA SENHA FORTE. ESTE CÓDIGO FICARÁ NO SEU GITHUB.
    USERNAME = 'admin'
    EMAIL = 'admin@exemplo.com'
    PASSWORD = 'Maya24@@'

    if not User.objects.filter(username=USERNAME).exists():
        print(f'Criando superusuário {USERNAME}')
        User.objects.create_superuser(username=USERNAME, email=EMAIL, password=PASSWORD)
    else:
        print(f'Superusuário {USERNAME} já existe.')


class Migration(migrations.Migration):

    dependencies = [
        # Esta migração depende da última migração do app de autenticação
        # Para descobrir qual é, rode `py manage.py showmigrations auth` e pegue a última
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]