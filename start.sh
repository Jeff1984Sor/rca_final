#!/bin/bash

# Este script executa os processos necessários para a aplicação no Render.

echo "A iniciar o script de inicialização v2..."

# 1. Executa as migrações da base de dados
echo "A executar as migrações da base de dados..."
python manage.py migrate

# 2. Inicia o Celery Worker em segundo plano
# O '&' no final é crucial para que o comando seja executado em background.
echo "A iniciar o Celery Worker em segundo plano..."
celery -A gestao_casos worker -l info &

# 3. Inicia o Gunicorn Web Server em primeiro plano
# A alteração está nesta linha: adicionámos o --bind para usar a porta do Render.
echo "A iniciar o Gunicorn Web Server na porta $PORT..."
gunicorn gestao_casos.wsgi --bind 0.0.0.0:$PORT
```

### O que fazer agora:

1.  **Copie o conteúdo** do ficheiro `start.sh` que atualizei no Canvas e substitua o conteúdo do seu ficheiro local.
2.  **Envie as alterações** para o seu repositório Git. O `git update-index` já foi feito, por isso não precisa de o fazer novamente.

    ```bash
    git add start.sh
    git commit -m "fix: Corrige o comando de arranque do Gunicorn para o Render"
    git push