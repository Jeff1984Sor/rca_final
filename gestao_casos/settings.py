# gestao_casos/settings.py

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv


# ==============================================================================
# MEGA LOG DE DIAGNÓSTICO DE PRODUÇÃO
# ==============================================================================
print("\n" + "="*50)
print("INICIANDO DIAGNÓSTICO DE AMBIENTE DO SETTINGS.PY")
print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

# Verifica as variáveis essenciais
secret_key = os.environ.get('SECRET_KEY')
if secret_key:
    print("[OK] SECRET_KEY encontrada.")
else:
    print("[FALHA CRÍTICA] SECRET_KEY NÃO ENCONTRADA! O APP VAI QUEBRAR.")

database_url = os.environ.get('DATABASE_URL')
if database_url:
    print("[OK] DATABASE_URL encontrada.")
else:
    print("[FALHA CRÍTICA] DATABASE_URL NÃO ENCONTRADA! O APP VAI QUEBRAR.")

debug_mode = os.environ.get('DEBUG', 'False').lower()
print(f"Modo DEBUG detectado como: '{debug_mode}'")

print("FIM DO DIAGNÓSTICO")
print("="*50 + "\n")
# ==============================================================================

# Carrega variáveis de ambiente de um arquivo .env (para desenvolvimento local)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# Pega a chave secreta da variável de ambiente.
SECRET_KEY = os.environ.get('SECRET_KEY')

# ==============================================================================
# AQUI ESTÁ A MÁGICA: O DEBUG É LIDO DO SEU ARQUIVO .env
# ==============================================================================
# Se a variável DEBUG não existir, o padrão é 'False' (seguro para produção).
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
# ==============================================================================

# Configuração de hosts permitidos (automática para Render, manual para local)
ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
else:
    # Para desenvolvimento local
    ALLOWED_HOSTS.extend(['127.0.0.1', 'localhost'])


# ==============================================================================
# 2. APLICAÇÕES INSTALADAS
# ==============================================================================

INSTALLED_APPS = [
    # ... (sua lista de apps, com 'ordered_model' antes de 'django.contrib.admin') ...
    #'ordered_model',
    'nested_admin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_htmx',
    'core.apps.CoreConfig',
    'clientes.apps.ClientesConfig',
    'casos.apps.CasosConfig',
    'equipamentos.apps.EquipamentosConfig',
    'pastas.apps.PastasConfig',
    'campos_custom.apps.CamposCustomConfig',
    'produtos.apps.ProdutosConfig',
    'workflow.apps.WorkflowConfig',
]


# ==============================================================================
# 3. MIDDLEWARE E OUTRAS CONFIGURAÇÕES GERAIS
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'gestao_casos.urls'
WSGI_APPLICATION = 'gestao_casos.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ... (DATABASES, AUTH_PASSWORD_VALIDATORS, etc. não mudam) ...
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)

# ... (O resto do seu arquivo até o final) ...

# ==============================================================================
# 11. CONFIGURAÇÕES DE PRODUÇÃO E SEGURANÇA (A SOLUÇÃO FINAL)
# ==============================================================================

# Estas configurações SÓ serão aplicadas se DEBUG for False (ou seja, no Render)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True # <-- O VILÃO, AGORA DOMADO
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Esta configuração SÓ será aplicada se estiver no Render
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_EXTERNAL_HOSTNAME}', 'https://*.onrender.com']

# ==============================================================================
# 8. INTERNACIONALIZAÇÃO
# ==============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True


# ==============================================================================
# 9. ARQUIVOS ESTÁTICOS E MÍDIA (A CORREÇÃO ESTÁ AQUI)
# ==============================================================================

# URL base para servir os arquivos estáticos
STATIC_URL = 'static/'

# Pasta para onde o 'collectstatic' vai copiar todos os arquivos para produção
STATIC_ROOT = BASE_DIR / "staticfiles"

# Lista de pastas onde o Django vai procurar por arquivos estáticos adicionais
# (além dos que já estão dentro de cada app)
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Configurações para arquivos de Mídia (uploads de usuários)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
