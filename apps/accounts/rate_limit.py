"""Database-backed login throttling shared by all application workers."""
from __future__ import annotations

import hashlib
import hmac
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import LoginAttempt, LoginThrottleLock

LOGIN_FAILURE_LIMIT = 5
LOGIN_IP_FAILURE_LIMIT = 40
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_ATTEMPT_RETENTION = timedelta(days=30)


def _fingerprint(value: str, purpose: str) -> str:
    """Return a keyed digest; never store the submitted identity in this table."""
    normalized = (value or "").strip().casefold()
    key = str(settings.SECRET_KEY).encode("utf-8")
    message = f"{purpose}:{normalized}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def username_fingerprint(username: str) -> str:
    return _fingerprint(username, "username")


def _lock_keys(username: str, ip_address: str | None) -> list[str]:
    keys = []
    if (username or "").strip():
        keys.append(f"u:{username_fingerprint(username)}")
    if ip_address:
        keys.append(f"i:{_fingerprint(ip_address, 'ip')}")
    return sorted(set(keys))


@contextmanager
def login_admission_lock(username: str, ip_address: str | None = None):
    """Serialize throttle-check + authenticate + failure-recording for both DBs.

    UPDATE is intentional: PostgreSQL holds row locks until transaction end,
    while SQLite (which ignores select_for_update) obtains its database write
    lock. The caller must keep the context around the complete login POST.
    """
    keys = _lock_keys(username, ip_address)
    if not keys:
        # Empty usernames are not throttle-counted, but still run normally.
        yield
        return

    # Expired coordination rows are safe to prune. If a concurrent request
    # removes a row between ensure and UPDATE, the zero-row update retries.
    for _ in range(3):
        now = timezone.now()
        LoginThrottleLock.objects.filter(
            updated_at__lt=now - LOGIN_ATTEMPT_RETENTION
        ).delete()

        for key in keys:
            LoginThrottleLock.objects.get_or_create(key=key)

        acquired = True
        with transaction.atomic():
            for key in keys:  # deterministic ordering avoids cross-key deadlocks
                changed = LoginThrottleLock.objects.filter(key=key).update(
                    lock_version=F("lock_version") + 1,
                    updated_at=now,
                )
                if changed != 1:
                    acquired = False
                    break
            if acquired:
                yield
                return

    raise RuntimeError("Unable to acquire login admission locks; retry the login request.")


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
