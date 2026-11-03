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
# امنیت پایه
# ---------------------------------------------------------------------------
def _secret_key() -> str:
    """کلید امنیتی پایدار؛ در اولین اجرا ساخته و ذخیره می‌شود."""
    key = os.environ.get("ITAM_SECRET_KEY")
    if key:
        return key
    key_file = BASE_DIR / "secret_key.txt"
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    generated = secrets.token_urlsafe(64)
    try:
        key_file.write_text(generated, encoding="utf-8")
    except OSError:  # محیط فقط-خواندنی
        pass
    return generated


SECRET_KEY = _secret_key()
DEBUG = env_bool("ITAM_DEBUG", True)

# در شبکه محلی معمولاً با IP یا نام سرور دسترسی انجام می‌شود
ALLOWED_HOSTS = env_list("ITAM_ALLOWED_HOSTS", ["*"])
CSRF_TRUSTED_ORIGINS = env_list("ITAM_CSRF_TRUSTED_ORIGINS", [])

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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(os.environ.get("ITAM_DB_PATH", BASE_DIR / "db.sqlite3")),
        "OPTIONS": {
            "timeout": 30,
            # فعال‌سازی WAL و کلیدهای خارجی در apps/core/apps.py انجام می‌شود
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
