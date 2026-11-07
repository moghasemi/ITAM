"""تنظیمات سامانه مدیریت دارایی و نگهداری فناوری اطلاعات (ITAM).

این سامانه برای اجرا در شبکه محلی (LAN) اداره طراحی شده است و به اینترنت نیاز ندارد.
"""
import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# وابستگی‌های همراه پروژه (vendor) — برای اجرای بدون اینترنت
# ---------------------------------------------------------------------------
VENDOR_DIR = BASE_DIR / "vendor"
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default=None):
    raw = os.environ.get(name, "")
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or (default or [])


# ---------------------------------------------------------------------------
# امنیت پایه و تنظیمات محیط عملیاتی (Production Hardening)
# ---------------------------------------------------------------------------
RUNNING_TESTS = "test" in sys.argv

DEBUG = env_bool("ITAM_DEBUG", False)

if DEBUG or RUNNING_TESTS:
    SECRET_KEY = os.environ.get("ITAM_SECRET_KEY") or "django-insecure-itam-dev-key-change-in-production-only-entropy-12345"
    ALLOWED_HOSTS = env_list("ITAM_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]", "testserver"])
else:
    SECRET_KEY = os.environ.get("ITAM_SECRET_KEY", "")
    if not SECRET_KEY:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("متغیر محیطی ITAM_SECRET_KEY در محیط عملیاتی (DEBUG=False) الزامی است.")
    if len(SECRET_KEY) < 50:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("طول کلید ITAM_SECRET_KEY در محیط عملیاتی باید حداقل ۵۰ نویسه با آنتروپی بالا باشد.")

    ALLOWED_HOSTS = env_list("ITAM_ALLOWED_HOSTS", [])
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("در محیط عملیاتی (DEBUG=False)، ITAM_ALLOWED_HOSTS باید صریحاً تعریف شود و نمی‌تواند ستاره (*) باشد.")

CSRF_TRUSTED_ORIGINS = env_list("ITAM_CSRF_TRUSTED_ORIGINS", [])

# HTTPS و کوکی‌های امن
SECURE_SSL_REDIRECT = env_bool("ITAM_SECURE_SSL_REDIRECT", False)
if env_bool("ITAM_USE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = env_bool("ITAM_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("ITAM_CSRF_COOKIE_SECURE", False)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

hsts_seconds = int(os.environ.get("ITAM_HSTS_SECONDS", 0))
if hsts_seconds > 0:
    SECURE_HSTS_SECONDS = hsts_seconds
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("ITAM_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("ITAM_HSTS_PRELOAD", False)
# ---------------------------------------------------------------------------
# برنامه‌ها
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # برنامه‌های سامانه
    "apps.core",
    "apps.accounts",
    "apps.org",
    "apps.assets",
    "apps.tickets",
    "apps.maintenance",
    "apps.integrations",
    "apps.reports",
]

try:  # pragma: no cover - بستگی به محیط نصب دارد
    import whitenoise  # noqa: F401

    USE_WHITENOISE = True
except ImportError:  # pragma: no cover
    USE_WHITENOISE = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]
if USE_WHITENOISE:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # کاربر جاری و نشانی IP را برای لاگ ممیزی نگه می‌دارد
    "apps.core.middleware.CurrentUserMiddleware",
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
                "apps.core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# پایگاه داده (SQLite — بکاپ با کپی یک فایل)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# پایگاه داده (پشتیبانی کامل از PostgreSQL برای سطح سازمانی و SQLite برای توسعه محلی)
# ---------------------------------------------------------------------------
DB_ENGINE = os.environ.get("ITAM_DB_ENGINE", "sqlite").lower()

if DB_ENGINE in ("postgres", "postgresql") or os.environ.get("ITAM_DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("ITAM_DB_NAME", "itam"),
            "USER": os.environ.get("ITAM_DB_USER", "postgres"),
            "PASSWORD": os.environ.get("ITAM_DB_PASSWORD", ""),
            "HOST": os.environ.get("ITAM_DB_HOST", "localhost"),
            "PORT": os.environ.get("ITAM_DB_PORT", "5432"),
            "OPTIONS": {
                "connect_timeout": int(os.environ.get("ITAM_DB_TIMEOUT", 10)),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.environ.get("ITAM_DB_PATH", BASE_DIR / "db.sqlite3")),
            "OPTIONS": {
                "timeout": 30,
            },
        }
    }

# ---------------------------------------------------------------------------
# احراز هویت
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# ---------------------------------------------------------------------------
# زبان، منطقه زمانی و قالب‌بندی (تاریخ شمسی در لایه نمایش انجام می‌شود)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# فایل‌های ایستا و رسانه‌ای
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

if USE_WHITENOISE:  # pragma: no cover
    STORAGES["staticfiles"] = {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    }

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # ۱۰ مگابایت
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024  # ۳۰ مگابایت (عکس‌های موبایل)
DATA_UPLOAD_MAX_NUMBER_FILES = 200

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# نشست‌ها
# ---------------------------------------------------------------------------
SESSION_COOKIE_AGE = 60 * 60 * 12  # ۱۲ ساعت
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_NAME = "itam_sessionid"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # برای فرم‌های AJAX لازم است
X_FRAME_OPTIONS = "SAMEORIGIN"

# رؤسای شبکه داخلی معمولاً HTTPS ندارند؛ این گزینه‌ها فقط در حالت غیر اشکال‌زدایی
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_SECURE = env_bool("ITAM_SECURE_COOKIES", False)
    CSRF_COOKIE_SECURE = env_bool("ITAM_SECURE_COOKIES", False)

# ---------------------------------------------------------------------------
# پیام‌ها (کلاس‌های CSS متناظر با قالب)
# ---------------------------------------------------------------------------
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# ---------------------------------------------------------------------------
# گزارش‌گیری
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
try:
    LOG_DIR.mkdir(exist_ok=True)
except OSError:
    pass

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "itam.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "itam": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# پارامترهای اختصاصی سامانه
# ---------------------------------------------------------------------------
ITAM = {
    "SITE_NAME": os.environ.get("ITAM_SITE_NAME", "سامانه مدیریت دارایی و نگهداری فناوری اطلاعات"),
    "ORG_NAME": os.environ.get("ITAM_ORG_NAME", "اداره"),
    # پیشوند شماره درخواست‌ها
    "TICKET_PREFIX": os.environ.get("ITAM_TICKET_PREFIX", "TK"),
    "VISIT_PREFIX": os.environ.get("ITAM_VISIT_PREFIX", "VS"),
    # آدرس پایه‌ای که در QR تجهیزات درج می‌شود (مثلاً http://10.0.0.5:8000)
    "PUBLIC_BASE_URL": os.environ.get("ITAM_PUBLIC_BASE_URL", ""),
    # پیش‌فرض ساعت کاری برای محاسبه SLA
    "WORK_START": os.environ.get("ITAM_WORK_START", "07:30"),
    "WORK_END": os.environ.get("ITAM_WORK_END", "15:30"),
}
