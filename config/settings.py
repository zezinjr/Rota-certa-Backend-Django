from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from corsheaders.defaults import default_methods
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent


DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY', default='insecure-key-change-me')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0').split(',')
if DEBUG:
    # Para desenvolvimento local (Flutter emulador/device), evita erro de host inválido.
    ALLOWED_HOSTS = ["*"]



INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    # Apps
    "core",
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',  # só uma vez
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


def build_database_config(database_url: str):
    if not database_url or database_url.startswith("sqlite"):
        parsed = urlparse(database_url or "")
        db_name = parsed.path.lstrip("/") if parsed.path else "db.sqlite3"
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / db_name,
        }

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or 5432,
    }


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
DATABASES = {
    "default": build_database_config(
        config("DATABASE_URL", default="sqlite:///db.sqlite3")
    )
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:4200"
]
STATIC_URL = 'static/'
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_METHODS = default_methods

REST_FRAMEWORK = {
"DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.AccessAccountJWTAuthentication",
    ],
    # Toda a API exige login de gestor por padrão. Endpoints de login/senha
    # (AllowAny), do motorista (IsDriver) e do colaborador (IsEmployee)
    # declaram as próprias permissões.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "core.permissions.IsManager",
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        # Rastreamento ao vivo: o motorista envia o GPS e o colaborador consulta
        # a cada poucos segundos, por isso têm limites próprios.
        'driver_location': '3600/hour',
        'trip_live': '3600/hour',
    }
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "access_account_id",
    "AUTH_TOKEN_CLASSES": (
        "core.tokens.AccessAccountAccessToken",
        "core.tokens.AccessAccountRefreshToken",
    ),
    "CHECK_REVOKE_TOKEN": False,
    "UPDATE_LAST_LOGIN": False,
}

ACCESS_ACCOUNT_MAX_FAILED_ATTEMPTS = 5
ACCESS_ACCOUNT_LOCKOUT_MINUTES = 30

ACCESS_ACCOUNT_AUTO_CREATE = config(
    "ACCESS_ACCOUNT_AUTO_CREATE", default=True, cast=bool
)
ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD = config(
    "ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD",
    default="",
)
ACCESS_ACCOUNT_SYNC_EMAIL = config(
    "ACCESS_ACCOUNT_SYNC_EMAIL",
    default=True,
    cast=bool,
)

PASSWORD_RESET_CODE_TTL_MINUTES = config(
    "PASSWORD_RESET_CODE_TTL_MINUTES",
    default=15,
    cast=int,
)
PASSWORD_RESET_CODE_LENGTH = config(
    "PASSWORD_RESET_CODE_LENGTH",
    default=6,
    cast=int,
)
PASSWORD_RESET_RETURN_CODE_IN_RESPONSE = config(
    "PASSWORD_RESET_RETURN_CODE_IN_RESPONSE",
    default=DEBUG,
    cast=bool,
)
PASSWORD_RESET_FORCE_MUST_CHANGE_PASSWORD = config(
    "PASSWORD_RESET_FORCE_MUST_CHANGE_PASSWORD",
    default=False,
    cast=bool,
)

# Acompanhamento ao vivo (core/live.py)
LIVE_LOCATION_MAX_AGE_SECONDS = 120   # posição mais antiga que isso não conta como "ao vivo"
LIVE_AVERAGE_SPEED_KMH = 25           # velocidade média usada na previsão de chegada
LIVE_STOP_DWELL_SECONDS = 60          # tempo parado em cada parada antes da sua
LIVE_ARRIVING_METERS = 300            # "chegando" quando a van está a essa distância do ponto
LIVE_DESTINATION_METERS = 150         # "chegou" quando está a essa distância da empresa

GOOGLE_MAPS_API_KEY = config("GOOGLE_MAPS_API_KEY", default="")
# Trajeto das rotas pelas ruas (Google Routes API, calculado uma vez por rota). Ver core/road_path.py.
ROAD_PATH_ENABLED = config("ROAD_PATH_ENABLED", default=True, cast=bool)
GOOGLE_ROUTES_API_URL = config(
    "GOOGLE_ROUTES_API_URL",
    default="https://routes.googleapis.com/directions/v2:computeRoutes",
)

# Avisos da van pelo WhatsApp. Ver core/whatsapp.py, core/notifications.py e o README.
# Provedor: "meta" (API oficial, com modelos aprovados) ou "evolution" (Evolution API, número via QR code).
# Sem as credenciais do provedor escolhido, nada é enviado.
WHATSAPP_PROVIDER = config("WHATSAPP_PROVIDER", default="meta")
EVOLUTION_API_URL = config("EVOLUTION_API_URL", default="http://localhost:8080")
EVOLUTION_API_KEY = config("EVOLUTION_API_KEY", default="")
EVOLUTION_INSTANCE = config("EVOLUTION_INSTANCE", default="rotacerta")
# Meta WhatsApp Cloud API
WHATSAPP_TOKEN = config("WHATSAPP_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID = config("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_API_URL = config("WHATSAPP_API_URL", default="https://graph.facebook.com")
WHATSAPP_API_VERSION = config("WHATSAPP_API_VERSION", default="v21.0")
WHATSAPP_TEMPLATE_LANGUAGE = config("WHATSAPP_TEMPLATE_LANGUAGE", default="pt_BR")
WHATSAPP_TEMPLATE_DEPARTURE = config("WHATSAPP_TEMPLATE_DEPARTURE", default="rota_van_saiu")
WHATSAPP_TEMPLATE_APPROACHING = config("WHATSAPP_TEMPLATE_APPROACHING", default="rota_van_a_caminho")
WHATSAPP_TEMPLATE_ARRIVING = config("WHATSAPP_TEMPLATE_ARRIVING", default="rota_van_chegando")
# Quais avisos enviar (cada mensagem tem custo): departure, approaching, arriving.
WHATSAPP_EVENTS = config("WHATSAPP_EVENTS", default="approaching,arriving")
WHATSAPP_APPROACHING_MINUTES = config("WHATSAPP_APPROACHING_MINUTES", default=10, cast=int)
WHATSAPP_DEFAULT_COUNTRY_CODE = config("WHATSAPP_DEFAULT_COUNTRY_CODE", default="55")
# Envia numa thread depois do commit; False envia na hora (testes).
WHATSAPP_ASYNC = config("WHATSAPP_ASYNC", default=True, cast=bool)

SPECTACULAR_SETTINGS = {
    "TITLE": "Route-monitoring API",
    "DESCRIPTION": "API for routes management system",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}