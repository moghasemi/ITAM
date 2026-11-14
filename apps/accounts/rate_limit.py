"""Database-backed login throttling shared by all application workers."""
from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginAttempt

LOGIN_FAILURE_LIMIT = 5
LOGIN_IP_FAILURE_LIMIT = 40
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_ATTEMPT_RETENTION = timedelta(days=30)


def username_fingerprint(username: str) -> str:
    """Return a keyed digest; never store the submitted username in this table."""
    normalized = (username or "").strip().casefold()
    key = str(settings.SECRET_KEY).encode("utf-8")
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def is_login_throttled(username: str, ip_address: str | None = None) -> bool:
    if not (username or "").strip():
        return False
    cutoff = timezone.now() - LOGIN_FAILURE_WINDOW
    recent = LoginAttempt.objects.filter(attempted_at__gte=cutoff)
    if recent.filter(username_hash=username_fingerprint(username)).count() >= LOGIN_FAILURE_LIMIT:
        return True
    if ip_address and recent.filter(ip_address=ip_address).count() >= LOGIN_IP_FAILURE_LIMIT:
        return True
    return False


def record_login_failure(username: str, ip_address: str | None = None) -> None:
    if not (username or "").strip():
        return
    now = timezone.now()
    LoginAttempt.objects.create(
        username_hash=username_fingerprint(username),
        ip_address=ip_address or None,
        attempted_at=now,
    )
    # Bound table growth without requiring a scheduled cleanup job.
    LoginAttempt.objects.filter(
        attempted_at__lt=now - LOGIN_ATTEMPT_RETENTION
    ).delete()


def clear_login_failures(username: str) -> None:
    if not (username or "").strip():
        return
    LoginAttempt.objects.filter(
        username_hash=username_fingerprint(username)
    ).delete()
