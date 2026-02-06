"""
Django settings for SaaS Agentes de IA project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # Ligado para debug - desativar após testes

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()] if not DEBUG else ["*"]
ALLOWED_HOSTS.append("petra-nonlogistical-freeman.ngrok-free.dev")

# Configurações de Proxy e SSL (Traefik)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# CSRF e Cookies
CSRF_TRUSTED_ORIGINS = [
    "https://pandia.com.br",
    "https://www.pandia.com.br",
    "https://petra-nonlogistical-freeman.ngrok-free.dev"
]
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False  # Traefik já faz isso


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps do projeto
    "core",
    "accounts",
    "organizations",
    "agents",
    "integrations",
    "webhooks",
    "api",
    "ui",
    "audit",
    "admin_panel",
    "payments",  # Asaas + Mercado Pago integration
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Servir arquivos estáticos
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.LoginRequiredMiddleware",  # Força login em todas as páginas
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(os.getenv("DATABASE_PATH", BASE_DIR / "db.sqlite3")),
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "pt-br")
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files (uploads)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Whitenoise configuration
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication URLs
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "ui:welcome"
LOGOUT_REDIRECT_URL = "accounts:login"

# Authentication Backends (permite login com email ou username)
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailOrUsernameBackend',  # Nosso backend personalizado
    'django.contrib.auth.backends.ModelBackend',  # Backend padrão como fallback
]

# CSRF Trusted Origins (Legacy env var support)
csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if csrf_origins:
    extra_origins = [origin.strip() for origin in csrf_origins.split(",") if origin.strip()]
    CSRF_TRUSTED_ORIGINS.extend(extra_origins)

# Adicionar ngrok URLs (aceitar qualquer subdomínio ngrok em desenvolvimento)
if DEBUG:
    # Aceitar qualquer URL do ngrok
    CSRF_TRUSTED_ORIGINS.extend([
        "https://*.ngrok-free.app",
        "https://*.ngrok.io",
        "https://*.ngrok-free.dev",
    ])

# Cache configuration (para rate limiting)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Messages framework
from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.DEBUG: "debug",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "error",
}

# Evolution API Settings
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")

# Gemini AI Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Asaas Settings (Assinaturas SaaS)
ASAAS_API_KEY = os.getenv("ASAAS_API_KEY", "")
ASAAS_WEBHOOK_TOKEN = os.getenv("ASAAS_WEBHOOK_TOKEN", "asaas_webhook_pandia_2025_secure")
ASAAS_ENVIRONMENT = os.getenv("ASAAS_ENVIRONMENT", "production")  # sandbox ou production
ASAAS_API_URL = (
    "https://api.asaas.com/v3" 
    if ASAAS_ENVIRONMENT == "production" 
    else "https://sandbox.asaas.com/api/v3"
)

# Asaas Subscription Settings
ASAAS_SUBSCRIPTION_VALUE = float(os.getenv("ASAAS_SUBSCRIPTION_VALUE", "0"))  # R$ por mês
ASAAS_SUBSCRIPTION_CYCLE = os.getenv("ASAAS_SUBSCRIPTION_CYCLE", "MONTHLY")  # MONTHLY, WEEKLY, etc

# Stripe Connect Settings (Legado - mantido para retrocompatibilidade)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Cakto Gateway Settings (Assinaturas)
CAKTO_CLIENT_ID = os.getenv("CAKTO_CLIENT_ID", "")
CAKTO_CLIENT_SECRET = os.getenv("CAKTO_CLIENT_SECRET", "")
CAKTO_WEBHOOK_TOKEN = os.getenv("CAKTO_WEBHOOK_TOKEN", "cakto_webhook_pandia_2025")
CAKTO_TEST_MODE = os.getenv("CAKTO_TEST_MODE", "true").lower() == "true"
CAKTO_API_URL = "https://api.cakto.com.br/public_api"

# Valor da assinatura (R$ 1,00 em modo teste, R$ 140,00 em produção)
from decimal import Decimal
CAKTO_PLAN_VALUE = Decimal("1.00") if CAKTO_TEST_MODE else Decimal("140.00")
CAKTO_PLAN_NAME = "Plano Mensal PanDia"
CAKTO_DEFAULT_TRIAL_DAYS = 15
