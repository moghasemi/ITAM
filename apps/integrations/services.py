"""ارسال رخدادها به سامانه مدیریت (Outbox Pattern).

رخدادها ابتدا در پایگاه داده ثبت می‌شوند و سپس با تلاش مجدد به مقصدهای
تعریف‌شده ارسال می‌گردند؛ بنابراین قطعی شبکه یا سامانه مدیریت باعث گم‌شدن
اطلاعات نمی‌شود.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request

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
def dispatch_event(event: OutboxEvent, endpoint: WebhookEndpoint) -> bool:
    """ارسال یک رخداد به یک مقصد؛ در صورت موفقیت True."""
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
    for key, value in (endpoint.extra_headers or {}).items():
        headers[str(key)] = str(value)

    request = urllib.request.Request(
        endpoint.url, data=body, headers=headers, method=endpoint.method or "POST"
    )

    started = time.monotonic()
    status_code = None
    response_text = ""
    ok = False
    error = ""
    try:
        with urllib.request.urlopen(request, timeout=endpoint.timeout_seconds or 10) as response:
            status_code = response.status
            response_text = response.read(2000).decode("utf-8", errors="replace")
            ok = 200 <= status_code < 300
            if not ok:
                error = f"کد پاسخ نامعتبر: {status_code}"
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        try:
            response_text = exc.read(2000).decode("utf-8", errors="replace")
        except Exception:
            response_text = ""
        error = f"خطای HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        error = f"عدم دسترسی به مقصد: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        error = f"خطای نامشخص: {exc}"

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
