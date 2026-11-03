"""پیکربندی برنامه درخواست‌های خرابی."""
from django.apps import AppConfig


class TicketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tickets"
    label = "tickets"
    verbose_name = "درخواست‌های خرابی و SLA"
