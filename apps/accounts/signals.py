"""گیرنده‌های سیگنال مربوط به ورود و خروج کاربران."""
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from django.utils import timezone

from apps.core.middleware import client_ip
from apps.core.models import AuditLog
from .rate_limit import clear_login_failures, record_login_failure


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    User = sender
    User.objects.filter(pk=user.pk).update(last_seen_at=timezone.now())
    clear_login_failures(user.get_username())
    AuditLog.objects.create(
        user=user,
        user_label=str(user),
        action=AuditLog.ACTION_LOGIN,
        model_name="User",
        object_id=str(user.pk),
        object_label=str(user),
        ip_address=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:300],
        note="ورود به سامانه",
    )


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user is None:
        return
    AuditLog.objects.create(
        user=user,
        user_label=str(user),
        action=AuditLog.ACTION_LOGOUT,
        model_name="User",
        object_id=str(user.pk),
        object_label=str(user),
        ip_address=client_ip(request),
        note="خروج از سامانه",
    )


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get("username", "")
    ip_address = client_ip(request) if request else None
    record_login_failure(username, ip_address)
    AuditLog.objects.create(
        user=None,
        user_label=username or "ناشناس",
        action=AuditLog.ACTION_LOGIN_FAILED,
        model_name="User",
        object_label=username,
        ip_address=ip_address,
        note="تلاش ناموفق برای ورود",
    )
