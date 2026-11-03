"""پیکربندی برنامه هسته."""
from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs):
    """فعال‌سازی WAL و کلیدهای خارجی برای SQLite (مقاوم‌تر در دسترسی همزمان)."""
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=30000;")


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "هسته سامانه"

    def ready(self):
        from . import signals  # noqa: F401  (ثبت گیرنده‌های سیگنال)
