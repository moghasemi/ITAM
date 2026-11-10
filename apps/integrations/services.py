"""ارسال رخدادها به سامانه مدیریت (Outbox Pattern).

رخدادها ابتدا در پایگاه داده ثبت می‌شوند و سپس با تلاش مجدد به مقصدهای
تعریف‌شده ارسال می‌گردند؛ بنابراین قطعی شبکه یا سامانه مدیریت باعث گم‌شدن
اطلاعات نمی‌شود.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import json
import logging
import os
import re
import socket
import ssl
import time
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from django.db.models import Q
from django.utils import timezone

from apps.core.models import SystemSetting
from apps.core.utils import log_action

from .models import ApiCallLog, OutboxEvent, WebhookEndpoint

logger = logging.getLogger("itam")

USER_AGENT = "ITAM-EventDispatcher/1.0"
SIGNATURE_HEADER = "X-ITAM-Signature"
EVENT_HEADER = "X-ITAM-Event"
IDEMPOTENCY_HEADER = "X-ITAM-Idempotency-Key"
SENSITIVE_LOG_KEYS = {
    "password",
    "passwd",
    "secret",
    "clientsecret",
    "token",
    "accesstoken",
    "refreshtoken",
    "authorization",
    "apikey",
    "privatekey",
    "cookie",
    "setcookie",
    "nationalid",
    "nationalcode",
    "phone",
    "mobile",
    "email",
    "birthdate",
}

LOG_REDACTED_VALUE = "[REDACTED]"


def _safe_log_url(raw_url: str) -> str:
    """Remove credentials, query parameters and fragments before logging."""
    try:
        parsed = urlsplit(str(raw_url))

        hostname = parsed.hostname
        if not hostname:
            return "[invalid URL]"

        if ":" in hostname:
            hostname = f"[{hostname}]"

        port = parsed.port
        netloc = f"{hostname}:{port}" if port else hostname

        return parsed._replace(
            netloc=netloc,
            query="",
            fragment="",
        ).geturl()[:400]

    except (TypeError, ValueError):
        return "[invalid URL]"

def _redact_log_data(value):
    """Recursively redact sensitive fields in JSON-compatible data."""
    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            normalized_key = re.sub(
                r"[^a-z0-9]",
                "",
                str(key).lower(),
            )

            if any(
                sensitive in normalized_key
                for sensitive in SENSITIVE_LOG_KEYS
            ):
                result[key] = LOG_REDACTED_VALUE
            else:
                result[key] = _redact_log_data(item)

        return result

    if isinstance(value, list):
        return [_redact_log_data(item) for item in value]

    return value


def _safe_log_request_body(body: bytes) -> str:
    """Store only JSON request data with sensitive fields redacted."""
    try:
        data = json.loads(body.decode("utf-8"))
        safe_data = _redact_log_data(data)

        return json.dumps(
            safe_data,
            ensure_ascii=False,
        )[:8000]

    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return "[request body omitted: invalid or non-JSON content]"

# ---------------------------------------------------------------------------
# بسته‌بندی رخداد
# ---------------------------------------------------------------------------
def build_envelope(event: OutboxEvent) -> dict:
    """ساخت قالب استاندارد رخداد برای ارسال به مدیریت."""
    setting = None
    try:
        setting = SystemSetting.load()
    except Exception:
        pass
    return {
        "event_id": str(event.idempotency_key),
        "event_type": event.event_type,
        "occurred_at": event.created_at.isoformat(),
        "source": {
            "system": "ITAM",
            "org": setting.org_name if setting else "",
            "site": setting.site_name if setting else "",
        },
        "aggregate": {"type": event.aggregate_type, "id": event.aggregate_id},
        "actor": event.actor_label,
        "data": event.payload,
    }


def sign_payload(body: bytes, secret: str) -> str:
    """امضای HMAC-SHA256 بدنه درخواست."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# ارسال
# ---------------------------------------------------------------------------
def _resolve_webhook_target(raw_url: str):
    """Validate and pin a webhook destination to prevent SSRF and DNS rebinding."""
    parsed = urlsplit(raw_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("نشانی مقصد باید یک URL معتبر HTTP/HTTPS باشد.")
    if parsed.username or parsed.password:
        raise ValueError("قرار دادن اطلاعات کاربری در URL مقصد مجاز نیست.")

    host = parsed.hostname.rstrip(".").lower()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    allowlist = {
        item.strip().lower().rstrip(".")
        for item in os.environ.get("ITAM_WEBHOOK_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    explicitly_allowed = host in allowlist
    if port not in (80, 443) and not explicitly_allowed:
        raise ValueError("پورت مقصد فقط 80/443 است؛ پورت سفارشی باید در ITAM_WEBHOOK_ALLOWED_HOSTS مجاز شود.")

    try:
        resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"نام میزبان مقصد قابل resolve نیست: {exc}") from exc

    addresses = []
    for item in resolved:
        address = item[4][0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError("مقصد به هیچ نشانی IP حل نشد.")

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global and not explicitly_allowed:
            raise ValueError(
                "مقصدهای خصوصی/محلی مجاز نیستند؛ در صورت نیاز، نام میزبان دقیق را در ITAM_WEBHOOK_ALLOWED_HOSTS ثبت کنید."
            )
        if parsed.scheme == "http" and ip.is_global:
            raise ValueError(
                "ارسال HTTP رمزنگاری‌نشده به نشانی عمومی مجاز نیست؛ برای مقصد عمومی از HTTPS استفاده کنید."
            )

    # The socket is connected to this exact validated IP below; DNS is not resolved again.
    return parsed, addresses[0], port


def _claim_delivery(delivery, endpoint):
    """Atomically claim a delivery; return its fencing token or None."""
    from .models import OutboxDelivery

    now = timezone.now()
    token = uuid.uuid4()
    timeout = max(int(endpoint.timeout_seconds or 10), 10)
    lease_until = now + timedelta(seconds=timeout + 60)

    claimed = OutboxDelivery.objects.filter(
        pk=delivery.pk,
        status__in=[OutboxEvent.STATUS_PENDING, OutboxEvent.STATUS_FAILED],
    ).filter(
        Q(lock_token__isnull=True) | Q(locked_until__lte=now)
    ).update(
        lock_token=token,
        locked_until=lease_until,
    )
    return token if claimed == 1 else None


def dispatch_event(
    event: OutboxEvent, endpoint: WebhookEndpoint, delivery=None, lock_token=None
) -> bool:
    """ارسال یک رخداد به یک مقصد و ثبت مستقل وضعیت همان تحویل."""
    from .models import OutboxDelivery

    if delivery is None:
        delivery, _ = OutboxDelivery.objects.get_or_create(event=event, endpoint=endpoint)
    if delivery.status == OutboxEvent.STATUS_SENT:
        return True
    if delivery.status == OutboxEvent.STATUS_DEAD:
        return False
    if lock_token is None:
        # Keep direct/internal callers safe too; no dispatch path may bypass
        # the atomic claim protocol.
        lock_token = _claim_delivery(delivery, endpoint)
        if lock_token is None:
            return False
        delivery.refresh_from_db()
    if not OutboxDelivery.objects.filter(
        pk=delivery.pk, lock_token=lock_token, locked_until__gt=timezone.now()
    ).exists():
        return False

    envelope = build_envelope(event)
    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": USER_AGENT,
        EVENT_HEADER: event.event_type,
        IDEMPOTENCY_HEADER: str(event.idempotency_key),
    }
    if endpoint.auth_type == WebhookEndpoint.AUTH_HMAC and endpoint.secret:
        headers[SIGNATURE_HEADER] = sign_payload(body, endpoint.secret)
    elif endpoint.auth_type == WebhookEndpoint.AUTH_TOKEN and endpoint.token:
        headers["Authorization"] = f"Bearer {endpoint.token}"

    header_validation_error = ""

    reserved_headers = {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "authorization",
        "content-type",
        "user-agent",
        SIGNATURE_HEADER.lower(),
        EVENT_HEADER.lower(),
        IDEMPOTENCY_HEADER.lower(),
    }

    used_headers = {key.lower() for key in headers}

    for key, value in (endpoint.extra_headers or {}).items():
        key, value = str(key), str(value)

        normalized_key = key.lower()

        if not key or not re.fullmatch(
            r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", key
        ):
            header_validation_error = "نام سرآیند سفارشی نامعتبر است."
            break

        if normalized_key in reserved_headers:
            header_validation_error = (
                f"بازنویسی سرآیند رزروشده مجاز نیست: {key}"
            )
            break

        if normalized_key in used_headers:
            header_validation_error = (
                f"سرآیند تکراری مجاز نیست: {key}"
            )
            break

        if any(char in value for char in "\r\n"):
            header_validation_error = (
                "سرآیند سفارشی دارای CR/LF غیرمجاز است."
            )
            break

        used_headers.add(normalized_key)
        headers[key] = value

    started = time.monotonic()
    status_code = None
    response_text = ""
    ok = False
    error = ""
    connection = None
    try:
        if header_validation_error:
            raise ValueError(header_validation_error)
        parsed, pinned_ip, port = _resolve_webhook_target(endpoint.url)
        connection_type = (
            http.client.HTTPSConnection if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        if parsed.scheme == "https":
            connection = connection_type(
                parsed.hostname, port, timeout=endpoint.timeout_seconds or 10,
                context=ssl.create_default_context(),
            )
        else:
            connection = connection_type(
                parsed.hostname, port, timeout=endpoint.timeout_seconds or 10
            )

        def _pinned_connect(address, timeout, source_address=None):
            return socket.create_connection((pinned_ip, port), timeout, source_address)

        connection._create_connection = _pinned_connect
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        connection.request(endpoint.method or "POST", target, body=body, headers=headers)
        response = connection.getresponse()
        status_code = response.status
        response_text = response.read(2000).decode("utf-8", errors="replace")
        ok = 200 <= status_code < 300
        if not ok:
            error = (
                "هدایت HTTP غیرفعال است؛ مقصد باید مستقیماً پاسخ موفق بدهد."
                if 300 <= status_code < 400
                else f"کد پاسخ نامعتبر: {status_code}"
            )
    except Exception as exc:  # noqa: BLE001
        error = f"عدم امکان ارسال امن به مقصد: {exc}"
    finally:
        if connection is not None:
            connection.close()

    now = timezone.now()
    duration_ms = int((time.monotonic() - started) * 1000)
    ApiCallLog.objects.create(
    endpoint=endpoint,
    event=event,
    method=endpoint.method or "POST",
    url=_safe_log_url(endpoint.url),
    request_body=_safe_log_request_body(body),
    response_status=status_code,
    response_body=(
        "[response body omitted for security]"
        if response_text
        else ""
    ),
    duration_ms=duration_ms,
    ok=ok,
    )
    next_attempt = delivery.attempts + 1
    if ok:
        next_status = OutboxEvent.STATUS_SENT
        next_dispatched_at = now
        next_error = ""
    else:
        next_status = (
            OutboxEvent.STATUS_DEAD
            if next_attempt >= endpoint.max_attempts
            else OutboxEvent.STATUS_FAILED
        )
        next_dispatched_at = delivery.dispatched_at
        next_error = (error or "خطای ارسال")[:2000]

    update_values = {
        "status": next_status,
        "attempts": next_attempt,
        "last_attempt_at": now,
        "dispatched_at": next_dispatched_at,
        "last_error": next_error,
    }
    if lock_token is not None:
        # Fencing token: a worker whose lease was replaced cannot overwrite
        # the result recorded by the newer owner.
        saved = OutboxDelivery.objects.filter(
            pk=delivery.pk, lock_token=lock_token
        ).update(**update_values, lock_token=None, locked_until=None)
        if saved != 1:
            logger.warning(
                "نتیجه ارسال رخداد %s توسط worker بدون مالکیت قفل نادیده گرفته شد.",
                event.pk,
            )
            return False
    else:
        for field, value in update_values.items():
            setattr(delivery, field, value)
        delivery.save(update_fields=list(update_values))

    if ok:
        endpoint.last_success_at = now
        endpoint.failure_count = 0
        endpoint.save(update_fields=["last_success_at", "failure_count"])
    else:
        endpoint.last_failure_at = now
        endpoint.failure_count += 1
        endpoint.save(update_fields=["last_failure_at", "failure_count"])
        logger.warning(
            "ارسال رخداد %s به مقصد %s ناموفق بود: %s",
            event.pk, endpoint.pk, next_error,
        )
    return ok


def dispatch_pending(limit: int = 100, user=None) -> dict:
    """ارسال هر رخداد به تمام مقصدهای واجد شرایط با retry مستقل."""
    from .models import OutboxDelivery

    endpoints = list(WebhookEndpoint.objects.filter(is_active=True))
    summary = {
        "endpoints": len(endpoints),
        "processed": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
    }
    if not endpoints:
        return summary

    pending = OutboxEvent.objects.filter(
        status__in=[OutboxEvent.STATUS_PENDING, OutboxEvent.STATUS_FAILED]
    ).order_by("created_at")[:limit]

    for event in pending:
        targets = [endpoint for endpoint in endpoints if endpoint.accepts(event.event_type)]
        if not targets:
            summary["skipped"] += 1
            continue
        summary["processed"] += 1
        for endpoint in targets:
            delivery, _ = OutboxDelivery.objects.get_or_create(
                event=event, endpoint=endpoint
            )
            if delivery.status in (OutboxEvent.STATUS_SENT, OutboxEvent.STATUS_DEAD):
                continue
            lock_token = _claim_delivery(delivery, endpoint)
            if lock_token is None:
                summary["skipped"] += 1
                continue
            delivery.refresh_from_db()
            if dispatch_event(event, endpoint, delivery, lock_token=lock_token):
                summary["sent"] += 1
            else:
                summary["failed"] += 1

        deliveries = list(event.deliveries.select_related("endpoint"))
        if deliveries and all(d.status == OutboxEvent.STATUS_SENT for d in deliveries):
            event.status = OutboxEvent.STATUS_SENT
            event.dispatched_at = timezone.now()
            event.last_error = ""
        elif deliveries and any(d.status == OutboxEvent.STATUS_PENDING for d in deliveries):
            # A pending delivery may be owned by another live dispatcher.
            # Do not turn an in-flight event into FAILED during this run.
            event.status = OutboxEvent.STATUS_PENDING
            event.last_error = ""
        elif deliveries and all(
            d.status in (OutboxEvent.STATUS_SENT, OutboxEvent.STATUS_DEAD)
            for d in deliveries
        ) and any(d.status == OutboxEvent.STATUS_DEAD for d in deliveries):
            event.status = OutboxEvent.STATUS_DEAD
            event.last_error = "؛ ".join(
                f"{d.endpoint.name}: {d.last_error}"
                for d in deliveries if d.status != OutboxEvent.STATUS_SENT
            )[:2000]
        else:
            event.status = OutboxEvent.STATUS_FAILED
            event.last_error = "؛ ".join(
                f"{d.endpoint.name}: {d.last_error}"
                for d in deliveries if d.status != OutboxEvent.STATUS_SENT
            )[:2000]
        event.last_attempt_at = timezone.now()
        event.attempts = max((d.attempts for d in deliveries), default=event.attempts)
        event.endpoint = None
        event.save(update_fields=[
            "status", "dispatched_at", "last_error", "last_attempt_at",
            "attempts", "endpoint",
        ])

    if summary["processed"]:
        log_action(
            "dispatch",
            None,
            model_name="OutboxEvent",
            object_label="ارسال رخدادها به مدیریت",
            note=f"تحویل‌های موفق: {summary['sent']} — ناموفق: {summary['failed']}",
            user=user,
        )
    return summary


def requeue_dead_events(user=None) -> int:
    """بازگرداندن رخدادهای متوقف‌شده به صف."""
    queryset = OutboxEvent.objects.filter(status=OutboxEvent.STATUS_DEAD)
    count = queryset.count()
    for event in queryset:
        event.deliveries.filter(status=OutboxEvent.STATUS_DEAD).update(
            status=OutboxEvent.STATUS_PENDING, attempts=0,
            last_error="", last_attempt_at=None, dispatched_at=None,
        )
        event.requeue()
    if count:
        log_action(
            "dispatch",
            None,
            model_name="OutboxEvent",
            object_label="بازگردانی رخدادهای متوقف",
            note=f"{count} رخداد به صف بازگشت",
            user=user,
        )
    return count


def outbox_statistics() -> dict:
    from django.db.models import Count

    rows = OutboxEvent.objects.values("status").annotate(total=Count("id"))
    data = {row["status"]: row["total"] for row in rows}
    return {
        "pending": data.get(OutboxEvent.STATUS_PENDING, 0),
        "sent": data.get(OutboxEvent.STATUS_SENT, 0),
        "failed": data.get(OutboxEvent.STATUS_FAILED, 0),
        "dead": data.get(OutboxEvent.STATUS_DEAD, 0),
        "total": sum(data.values()),
    }
