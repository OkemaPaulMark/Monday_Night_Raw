"""
Django settings for Monday Night Raw — 7-a-side football stats platform.

Decision notes:
- App renamed from `statistics` → `stats` (Python stdlib name conflict).
- PostgreSQL is the primary database; SQLite is used only when USE_SQLITE=True
  for quick local smoke tests without Docker.
- Performance score weights live in PERFORMANCE_SCORE_WEIGHTS (single source).
"""

from pathlib import Path
import os

from dotenv import load_dotenv

# backend/ is BASE_DIR; project root is one level up
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / '.env')
load_dotenv(BASE_DIR / '.env')


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-only-change-me')
DEBUG = env_bool('DEBUG', True)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
    if host.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Local apps
    'accounts',
    'players',
    'matches',
    'stats',
    'awards',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
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

USE_SQLITE = env_bool('USE_SQLITE', False)

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'monday_night_raw'),
            'USER': os.getenv('POSTGRES_USER', 'mnraw'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'mnraw_dev_password'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173',
    ).split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Monday Night Raw API',
    'DESCRIPTION': '7-a-side football statistics and awards platform API.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Single source of truth for performance scoring (Phase 2 services will use this).
PERFORMANCE_SCORE_WEIGHTS = {
    'GOAL_WEIGHT': int(os.getenv('GOAL_WEIGHT', '5')),
    'ASSIST_WEIGHT': int(os.getenv('ASSIST_WEIGHT', '4')),
    'CLEAN_SHEET_WEIGHT': int(os.getenv('CLEAN_SHEET_WEIGHT', '3')),
    'WIN_WEIGHT': int(os.getenv('WIN_WEIGHT', '2')),
    # Career weight per past Player of the Week award, used only to seed
    # balanced team generation — not part of per-match performance scoring.
    'POTW_WEIGHT': int(os.getenv('POTW_WEIGHT', '8')),
    'DRAW_WEIGHT': int(os.getenv('DRAW_WEIGHT', '1')),
    # Raw performance points that map to a 5.0 star rating (lower = more generous)
    'RATING_POINTS_FOR_FIVE': int(os.getenv('RATING_POINTS_FOR_FIVE', '12')),
}

# Match rules — flexible Monday squads (even counts for equal teams)
MIN_MATCH_PLAYERS = int(os.getenv('MIN_MATCH_PLAYERS', '10'))
MAX_MATCH_PLAYERS = int(os.getenv('MAX_MATCH_PLAYERS', '14'))
# Legacy aliases (max / full squad)
PLAYERS_PER_TEAM = MAX_MATCH_PLAYERS // 2
EXPECTED_TOTAL_PLAYERS = MAX_MATCH_PLAYERS

# Seed credentials (dev only)
SEED_ADMIN_USERNAME = os.getenv('SEED_ADMIN_USERNAME', 'admin')
SEED_ADMIN_PASSWORD = os.getenv('SEED_ADMIN_PASSWORD', 'admin123')
SEED_ADMIN_EMAIL = os.getenv('SEED_ADMIN_EMAIL', 'admin@example.com')
