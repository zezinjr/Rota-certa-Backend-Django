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
        'user': '1000/hour'
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

GOOGLE_MAPS_API_KEY = config("GOOGLE_MAPS_API_KEY", default="")
GOOGLE_ROUTES_API_URL = config(
    "GOOGLE_ROUTES_API_URL",
    default="https://routes.googleapis.com/directions/v2:computeRoutes",
)

SPECTACULAR_SETTINGS = {
    "TITLE": "Route-monitoring API",
    "DESCRIPTION": "API for routes management system",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}