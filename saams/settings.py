import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================
# ENV LOAD (optional)
# ==============================

def _load_local_env(env_path):
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_local_env(BASE_DIR / ".env")


# ==============================
# BASIC SETTINGS
# ==============================

DEBUG = os.environ.get("DEBUG", "False") == "True"

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

ALLOWED_HOSTS = ['.onrender.com', 'localhost', '127.0.0.1']


# ==============================
# APPS
# ==============================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',

    'accounts',
    'attendance.apps.AttendanceConfig',
    'results.apps.ResultsConfig',
    'homework.apps.HomeworkConfig',
    'notifications.apps.NotificationsConfig',
    'ai_tutor.apps.AiTutorConfig',
]


# ==============================
# MIDDLEWARE
# ==============================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',

    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ==============================
# URLS / TEMPLATES
# ==============================

ROOT_URLCONF = 'saams.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                "accounts.context_processors.user_profile_context",
                "notifications.context_processors.notification_context",
            ],
        },
    },
]

WSGI_APPLICATION = 'saams.wsgi.application'


# ==============================
# DATABASE
# ==============================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ==============================
# INTERNATIONAL
# ==============================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_TZ = True


# ==============================
# STATIC / MEDIA
# ==============================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'pwa_static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ==============================
# AUTH
# ==============================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/admin-dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

AUTH_USER_MODEL = 'accounts.CustomUser'


# ==============================
# SECURITY (RENDER FIX)
# ==============================

SECURE_SSL_REDIRECT = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True


# ==============================
# AI TUTOR
# ==============================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AI_TUTOR_MODEL = os.environ.get("AI_TUTOR_MODEL", "gpt-4.1-mini")
AI_TUTOR_MAX_OUTPUT_TOKENS = int(os.environ.get("AI_TUTOR_MAX_OUTPUT_TOKENS", "400"))


# ==============================
# WHITENOISE
# ==============================

def _whitenoise_add_headers(headers, path, url):
    if str(path).endswith("service-worker.js"):
        headers["Cache-Control"] = "no-cache"
    if str(path).endswith("manifest.json"):
        headers["Cache-Control"] = "no-cache"


WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_ADD_HEADERS_FUNCTION = _whitenoise_add_headers

if not DEBUG:
    if "test" in sys.argv:
        STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
    else:
        STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
