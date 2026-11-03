"""اطلاعات مشترک قالب‌ها."""
from django.conf import settings

from .models import Notification, SystemSetting


def site_context(request):
    try:
        setting = SystemSetting.load()
    except Exception:
        setting = None

    unread = 0
    pending_count = 0
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        try:
            unread = Notification.objects.filter(user=request.user, is_read=False).count()
        except Exception:
            unread = 0
        try:
            from apps.assets.models import HardwareSnapshot

            pending_count = HardwareSnapshot.objects.pending_for(request.user).count()
        except Exception:
            pending_count = 0

    return {
        "system_setting": setting,
        "site_title": (setting.site_name if setting else settings.ITAM["SITE_NAME"]),
        "org_name": (setting.org_name if setting else settings.ITAM["ORG_NAME"]),
        "unread_notifications": unread,
        "pending_hardware_confirmations": pending_count,
    }
