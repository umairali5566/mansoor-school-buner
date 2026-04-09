import os
import sys
from pathlib import Path

try:
    import dj_database_url
except ImportError:  # pragma: no cover - optional until requirements are installed
    dj_database_url = None


BASE_DIR = Path(__file__).resolve().parent.parent
IS_TEST = "test" in sys.argv


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

DEBUG = False
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "saams-render-secret-key-change-this-before-production-2026-secure",
)

RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".onrender.com",
]

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

extra_allowed_hosts = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
ALLOWED_HOSTS.extend(extra_allowed_hosts)
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))


# ==============================
# APPS
# ==============================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "accounts",
    "attendance.apps.AttendanceConfig",
    "results.apps.ResultsConfig",
    "homework.apps.HomeworkConfig",
    "notifications.apps.NotificationsConfig",
    "ai_tutor.apps.AiTutorConfig",
]


# ==============================
# MIDDLEWARE
# ==============================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ==============================
# URLS / TEMPLATES
# ==============================

ROOT_URLCONF = "saams.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.user_profile_context",
                "notifications.context_processors.notification_context",
            ],
        },
    },
]

WSGI_APPLICATION = "saams.wsgi.application"


# ==============================
# DATABASE
# ==============================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url and dj_database_url is not None:
    DATABASES["default"] = dj_database_url.parse(
        database_url,
        conn_max_age=600,
        ssl_require=True,
    )


# ==============================
# INTERNATIONALIZATION
# ==============================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True


# ==============================
# STATIC / MEDIA
# ==============================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

STATICFILES_DIRS = [
    path
    for path in (
        BASE_DIR / "static",
        BASE_DIR / "pwa_static",
    )
    if path.exists()
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if IS_TEST:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False


def _whitenoise_add_headers(headers, path, url):
    if str(path).endswith("service-worker.js") or str(path).endswith("manifest.json"):
        headers["Cache-Control"] = "no-cache"


WHITENOISE_ADD_HEADERS_FUNCTION = _whitenoise_add_headers


# ==============================
# AUTH
# ==============================

AUTH_USER_MODEL = "accounts.CustomUser"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/admin-dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

LOGIN_THROTTLE_MAX_ATTEMPTS = 5
LOGIN_THROTTLE_WINDOW_SECONDS = 600


# ==============================
# SECURITY
# ==============================

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not IS_TEST

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = ["https://*.onrender.com"]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

extra_csrf_origins = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS.extend(extra_csrf_origins)
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))


# ==============================
# AI TUTOR OPTIONAL SETTINGS
# ==============================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AI_TUTOR_MODEL = os.environ.get("AI_TUTOR_MODEL", "gpt-4.1-mini")
AI_TUTOR_MAX_OUTPUT_TOKENS = int(os.environ.get("AI_TUTOR_MAX_OUTPUT_TOKENS", "400"))
