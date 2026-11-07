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
import socket
import ssl
import time
from urllib.parse import urlsplit

from django.utils import timezone

from apps.core.models import SystemSetting
from apps.core.utils import log_action

from .models import ApiCallLog, OutboxEvent, WebhookEndpoint

logger = logging.getLogger("itam")

USER_AGENT = "ITAM-EventDispatcher/1.0"
SIGNATURE_HEADER = "X-ITAM-Signature"
EVENT_HEADER = "X-ITAM-Event"
IDEMPOTENCY_HEADER = "X-ITAM-Idempotency-Key"


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

    # The socket is connected to this exact validated IP below; DNS is not resolved again.
    return parsed, addresses[0], port


def dispatch_event(event: OutboxEvent, endpoint: WebhookEndpoint) -> bool:
    """ارسال یک رخداد؛ مقصدهای خصوصی فقط با allowlist صریح مجازند."""
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
    for key, value in (endpoint.extra_headers or {}).items():
        key, value = str(key), str(value)
        if key.lower() in {"host", "content-length", "transfer-encoding", "connection", "authorization"}:
            header_validation_error = f"سرآیند رزروشده قابل بازنویسی نیست: {key}"
            break
        if any(char in key + value for char in "\r\n"):
            header_validation_error = "سرآیند سفارشی دارای CR/LF غیرمجاز است."
            break
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

    duration_ms = int((time.monotonic() - started) * 1000)
    ApiCallLog.objects.create(
        endpoint=endpoint,
        event=event,
        method=endpoint.method or "POST",
        url=endpoint.url,
        request_body=body.decode("utf-8", errors="replace")[:8000],
        response_status=status_code,
        response_body=response_text[:4000],
        duration_ms=duration_ms,
        ok=ok,
    )

    if ok:
        endpoint.last_success_at = timezone.now()
        endpoint.failure_count = 0
        endpoint.save(update_fields=["last_success_at", "failure_count"])
        event.mark_sent(endpoint)
        return True

    endpoint.last_failure_at = timezone.now()
    endpoint.failure_count += 1
    endpoint.save(update_fields=["last_failure_at", "failure_count"])
    event.mark_failed(error or "خطای ارسال", max_attempts=endpoint.max_attempts, endpoint=endpoint)
    logger.warning("ارسال رخداد %s ناموفق بود: %s", event.pk, error)
    return False


def dispatch_pending(limit: int = 100, user=None) -> dict:
    """ارسال رخدادهای در انتظار به مقصدهای فعال."""
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
            if dispatch_event(event, endpoint):
                summary["sent"] += 1
                break
            summary["failed"] += 1

    if summary["processed"]:
        log_action(
            "dispatch",
            None,
            model_name="OutboxEvent",
            object_label="ارسال رخدادها به مدیریت",
            note=f"ارسال‌شده: {summary['sent']} — ناموفق: {summary['failed']}",
            user=user,
        )
    return summary


def requeue_dead_events(user=None) -> int:
    """بازگرداندن رخدادهای متوقف‌شده به صف."""
    queryset = OutboxEvent.objects.filter(status=OutboxEvent.STATUS_DEAD)
    count = queryset.count()
    for event in queryset:
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
