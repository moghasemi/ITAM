"""Database-backed login throttling shared by all application workers."""
from __future__ import annotations

import hashlib
import hmac
import sys
import time
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.db import OperationalError, connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import LoginAttempt, LoginThrottleLock

LOGIN_FAILURE_LIMIT = 5
LOGIN_IP_FAILURE_LIMIT = 40
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_ATTEMPT_RETENTION = timedelta(days=30)
LOGIN_LOCK_WAIT_SECONDS = 30
LOGIN_LOCK_RETRY_SECONDS = 0.05


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
    while SQLite obtains a database write lock. SQLite shared-cache databases
    can report SQLITE_LOCKED immediately instead of waiting, so acquisition
    retries that transient condition until the holder releases the transaction.
    The caller must keep this context around the complete login POST.
    """
    keys = _lock_keys(username, ip_address)
    if not keys:
        # Empty usernames are not throttle-counted, but still run normally.
        yield
        return

    deadline = time.monotonic() + LOGIN_LOCK_WAIT_SECONDS
    while True:
        atomic = transaction.atomic()
        entered = False
        try:
            atomic.__enter__()
            entered = True
            now = timezone.now()

            # Keep pruning and row creation in the same transaction as lock
            # acquisition, so SQLite lock conflicts are retried as one unit.
            LoginThrottleLock.objects.filter(
                updated_at__lt=now - LOGIN_ATTEMPT_RETENTION
            ).delete()

            for key in keys:
                LoginThrottleLock.objects.get_or_create(key=key)

            acquired = True
            for key in keys:  # deterministic ordering avoids cross-key deadlocks
                changed = LoginThrottleLock.objects.filter(key=key).update(
                    lock_version=F("lock_version") + 1,
                    updated_at=now,
                )
                if changed != 1:
                    acquired = False
                    break
        except OperationalError as exc:
            if entered:
                atomic.__exit__(type(exc), exc, exc.__traceback__)
            is_sqlite_lock = (
                connection.vendor == "sqlite" and "locked" in str(exc).lower()
            )
            if not is_sqlite_lock or time.monotonic() >= deadline:
                raise
            time.sleep(LOGIN_LOCK_RETRY_SECONDS)
            continue
        except BaseException:
            if entered:
                atomic.__exit__(*sys.exc_info())
            raise

        if not acquired:
            atomic.__exit__(None, None, None)
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Unable to acquire login admission locks; retry the login request."
                )
            time.sleep(LOGIN_LOCK_RETRY_SECONDS)
            continue

        # Keep the transaction open while the caller checks throttling,
        # authenticates, and records success/failure.
        try:
            yield
        except BaseException:
            atomic.__exit__(*sys.exc_info())
            raise
        else:
            atomic.__exit__(None, None, None)
        return


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
