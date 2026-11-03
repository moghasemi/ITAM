"""گیرنده‌های سیگنال هسته (پاک‌سازی کش)."""
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Holiday, SystemSetting


@receiver([post_save, post_delete], sender=Holiday)
def _holiday_changed(sender, **kwargs):
    cache.delete("itam:work-calendar")


@receiver([post_save, post_delete], sender=SystemSetting)
def _setting_changed(sender, **kwargs):
    cache.delete("itam:work-calendar")
    cache.delete("itam:system-setting")
