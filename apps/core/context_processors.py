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
    all_centers = []
    user_center = None

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

        user_center = getattr(request.user, "center", None)
        if getattr(request.user, "is_admin_province", False) or request.user.is_superuser:
            try:
                # The header selector must never disclose centers outside the
                # user's active organizational scope (especially province admins).
                all_centers = list(
                    request.user.get_scoped_centers()
                    .filter(is_active=True)
                    .order_by("-is_headquarters", "name")
                )
            except Exception:
                all_centers = []

    return {
        "system_setting": setting,
        "site_title": (setting.site_name if setting else settings.ITAM["SITE_NAME"]),
        "org_name": (setting.org_name if setting else settings.ITAM["ORG_NAME"]),
        "unread_notifications": unread,
        "pending_hardware_confirmations": pending_count,
        "all_centers": all_centers,
        "user_center": user_center,
    }
