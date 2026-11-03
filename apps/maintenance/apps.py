"""پیکربندی برنامه بازدیدهای دوره‌ای."""
from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.maintenance"
    label = "maintenance"
    verbose_name = "بازدیدهای دوره‌ای"
