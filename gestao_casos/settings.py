import os
from pathlib import Path
import dj_database_url
from environs import Env  # Usaremos environs para gerenciar tudo

# ==============================================================================
# 1. CONFIGURAÇÃO BÁSICA E VARIÁVEIS DE AMBIENTE
# ==============================================================================

# Define o diretório base do projeto (RCA_Final/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Instancia o leitor de variáveis de ambiente e lê o arquivo .env
env = Env()
env.read_env()

# Pega a chave secreta da variável de ambiente. Essencial para segurança.
# O `env.str()` garante que o programa vai quebrar se a variável não for encontrada.
SECRET_KEY = env.str('SECRET_KEY')

# O modo DEBUG é lido do arquivo .env. Se não for encontrado, o padrão é False (seguro).
DEBUG = env.bool('DEBUG', default=False)

# Configuração de hosts permitidos (automática para Render, manual para local)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# ==============================================================================
# 2. APLICAÇÕES INSTALADAS (APPS)
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps de terceiros
    'django_htmx',
    'nested_admin',
    'rest_framework',
    'rest_framework.authtoken',  # Adicionado para a autenticação da API (n8n)

    # Seus apps
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
# 3. MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Para servir arquivos estáticos em produção
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]


# ==============================================================================
# 4. URLs e Aplicação WSGI
# ==============================================================================

ROOT_URLCONF = 'gestao_casos.urls'
WSGI_APPLICATION = 'gestao_casos.wsgi.application'


# ==============================================================================
# 5. BANCO DE DADOS (CONFIGURAÇÃO ÚNICA E CORRIGIDA)
# ==============================================================================

# Lê a DATABASE_URL do ambiente
DATABASE_URL = env.str('DATABASE_URL')

# Verifica se a URL é para sqlite. Se NÃO for, ativa o ssl_require.
# Isso corrige o erro 'sslmode' ao rodar localmente.
SSL_REQUIRE = not DATABASE_URL.startswith('sqlite')

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=SSL_REQUIRE
    )
}


# ==============================================================================
# 6. TEMPLATES
# ==============================================================================

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


# ==============================================================================
# 7. VALIDAÇÃO DE SENHAS
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ==============================================================================
# 8. INTERNACIONALIZAÇÃO (I18N)
# ==============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True


# ==============================================================================
# 9. ARQUIVOS ESTÁTICOS (STATIC) E DE MÍDIA (MEDIA)
# ==============================================================================

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ==============================================================================
# 10. CONFIGURAÇÕES DE E-MAIL
# ==============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.office35.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env.str('EMAIL_HOST_USER', default=None)
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD', default=None)


# ==============================================================================
# 11. CONFIGURAÇÕES DE PRODUÇÃO E SEGURANÇA
# ==============================================================================

# Estas configurações só são aplicadas se DEBUG for False (ou seja, no Render)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# ==============================================================================
# 12. OUTRAS CONFIGURAÇÕES
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
