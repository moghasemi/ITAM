"""مدل‌های یکپارچه‌سازی: صف رخدادها (Outbox) و لاگ ارسال به مدیریت."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.constants import EVENT_TYPE_CHOICES
from apps.core.models import TimeStampedModel


class WebhookEndpoint(TimeStampedModel):
    """مقصد ارسال رخدادها به سامانه مدیریت."""

    AUTH_NONE = "none"
    AUTH_TOKEN = "token"
    AUTH_HMAC = "hmac"
    AUTH_CHOICES = (
        (AUTH_NONE, "بدون احراز هویت"),
        (AUTH_TOKEN, "توکن در سرآیند"),
        (AUTH_HMAC, "امضای HMAC-SHA256"),
    )

    name = models.CharField("عنوان مقصد", max_length=150, unique=True)
    url = models.URLField("نشانی درگاه", max_length=400)
    method = models.CharField("روش", max_length=10, default="POST")
    auth_type = models.CharField("نوع احراز هویت", max_length=20, choices=AUTH_CHOICES, default=AUTH_NONE)
    token = models.CharField("توکن", max_length=300, blank=True)
    secret = models.CharField("کلید امضا", max_length=300, blank=True)
    extra_headers = models.JSONField("سرآیندهای اضافی", default=dict, blank=True)
    event_filter = models.CharField(
        "پالایه رخدادها",
        max_length=400,
        blank=True,
        help_text="فهرست نوع رخدادها با کاما؛ خالی یعنی همه رخدادها",
    )
    is_active = models.BooleanField("فعال", default=True)
    timeout_seconds = models.PositiveSmallIntegerField("مهلت ارسال (ثانیه)", default=10)
    max_attempts = models.PositiveSmallIntegerField("حداکثر تلاش", default=5)

    last_success_at = models.DateTimeField("آخرین ارسال موفق", null=True, blank=True)
    last_failure_at = models.DateTimeField("آخرین خطا", null=True, blank=True)
    failure_count = models.PositiveIntegerField("تعداد خطاهای پی‌درپی", default=0)

    class Meta:
        verbose_name = "مقصد ارسال رخداد"
        verbose_name_plural = "مقصدهای ارسال رخداد"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"

    def accepts(self, event_type: str) -> bool:
        if not self.event_filter:
            return True
        allowed = {item.strip() for item in self.event_filter.split(",") if item.strip()}
        return event_type in allowed


class OutboxEvent(models.Model):
    """صف رخدادهای سامانه؛ تضمین عدم گم‌شدن رخداد تا زمان ارسال موفق."""

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_DEAD = "dead"
    STATUS_CHOICES = (
        (STATUS_PENDING, "در انتظار ارسال"),
        (STATUS_SENT, "ارسال‌شده"),
        (STATUS_FAILED, "خطا در ارسال"),
        (STATUS_DEAD, "متوقف‌شده (نیازمند بررسی)"),
    )
    STATUS_CSS = {
        STATUS_PENDING: "warning",
        STATUS_SENT: "success",
        STATUS_FAILED: "danger",
        STATUS_DEAD: "danger",
    }

    event_type = models.CharField("نوع رخداد", max_length=60, choices=EVENT_TYPE_CHOICES, db_index=True)
    aggregate_type = models.CharField("موجودیت", max_length=60, blank=True)
    aggregate_id = models.CharField("شناسه موجودیت", max_length=64, blank=True)
    payload = models.JSONField("داده رخداد", default=dict, blank=True)
    idempotency_key = models.UUIDField("کلید یکتایی", default=uuid.uuid4, unique=True, editable=False)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر عامل",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbox_events",
    )
    actor_label = models.CharField("عنوان کاربر عامل", max_length=150, blank=True)

    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField("تعداد تلاش", default=0)
    last_attempt_at = models.DateTimeField("آخرین تلاش", null=True, blank=True)
    dispatched_at = models.DateTimeField("زمان ارسال موفق", null=True, blank=True)
    last_error = models.TextField("آخرین خطا", blank=True)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        verbose_name="مقصد",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    created_at = models.DateTimeField("زمان رخداد", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "رخداد صف ارسال"
        verbose_name_plural = "رخدادهای صف ارسال"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("aggregate_type", "aggregate_id")),
        ]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} — {self.aggregate_id}"

    @property
    def status_css(self) -> str:
        return self.STATUS_CSS.get(self.status, "neutral")

    @property
    def is_dispatched(self) -> bool:
        return self.status == self.STATUS_SENT

    def mark_sent(self, endpoint=None):
        self.status = self.STATUS_SENT
        self.dispatched_at = timezone.now()
        self.last_attempt_at = self.dispatched_at
        self.attempts += 1
        self.last_error = ""
        if endpoint is not None:
            self.endpoint = endpoint
        self.save(
            update_fields=[
                "status",
                "dispatched_at",
                "last_attempt_at",
                "attempts",
                "last_error",
                "endpoint",
            ]
        )

    def mark_failed(self, error: str, max_attempts: int = 5, endpoint=None):
        self.attempts += 1
        self.last_attempt_at = timezone.now()
        self.last_error = (error or "")[:2000]
        if endpoint is not None:
            self.endpoint = endpoint
        self.status = self.STATUS_DEAD if self.attempts >= max_attempts else self.STATUS_FAILED
        self.save(
            update_fields=[
                "status",
                "attempts",
                "last_attempt_at",
                "last_error",
                "endpoint",
            ]
        )

    def requeue(self):
        self.status = self.STATUS_PENDING
        self.last_error = ""
        self.attempts = 0
        self.save(update_fields=["status", "last_error", "attempts"])

    # -- تولید رخداد --------------------------------------------------------
    @classmethod
    def emit(cls, event_type, payload=None, *, aggregate_type="", aggregate_id="", actor=None, actor_label=""):
        from apps.core.middleware import get_current_user

        if actor is None:
            current = get_current_user()
            if current is not None and getattr(current, "is_authenticated", False):
                actor = current
        if not actor_label and actor is not None:
            actor_label = str(actor)
        return cls.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id or ""),
            payload=payload or {},
            actor=actor,
            actor_label=actor_label,
        )


class ApiCallLog(models.Model):
    """لاگ فراخوانی درگاه مدیریت."""

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        verbose_name="مقصد",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    event = models.ForeignKey(
        OutboxEvent,
        verbose_name="رخداد",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    method = models.CharField("روش", max_length=10, default="POST")
    url = models.CharField("نشانی", max_length=400)
    request_body = models.TextField("بدنه درخواست", blank=True)
    response_status = models.PositiveSmallIntegerField("کد پاسخ", null=True, blank=True)
    response_body = models.TextField("بدنه پاسخ", blank=True)
    duration_ms = models.PositiveIntegerField("مدت (میلی‌ثانیه)", null=True, blank=True)
    ok = models.BooleanField("موفق", default=False, db_index=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "لاگ ارسال به مدیریت"
        verbose_name_plural = "لاگ ارسال به مدیریت"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        state = "موفق" if self.ok else "ناموفق"
        return f"{self.method} {self.url} — {state}"



class OutboxDelivery(TimeStampedModel):
    """وضعیت مستقل تحویل هر رخداد به هر مقصد فعال."""

    STATUS_CHOICES = OutboxEvent.STATUS_CHOICES

    event = models.ForeignKey(
        OutboxEvent, on_delete=models.CASCADE, related_name="deliveries",
        verbose_name="رخداد",
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.PROTECT, related_name="deliveries",
        verbose_name="مقصد",
    )
    status = models.CharField(
        "وضعیت تحویل", max_length=20, choices=STATUS_CHOICES,
        default=OutboxEvent.STATUS_PENDING, db_index=True,
    )
    attempts = models.PositiveSmallIntegerField("تعداد تلاش", default=0)
    last_attempt_at = models.DateTimeField("آخرین تلاش", null=True, blank=True)
    dispatched_at = models.DateTimeField("زمان ارسال موفق", null=True, blank=True)
    last_error = models.TextField("آخرین خطا", blank=True)
    lock_token = models.UUIDField("شناسه قفل", null=True, blank=True, editable=False)
    locked_until = models.DateTimeField("انقضای قفل", null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "تحویل رخداد"
        verbose_name_plural = "تحویل‌های رخداد"
        ordering = ("event__created_at", "endpoint__name")
        constraints = [
            models.UniqueConstraint(
                fields=("event", "endpoint"), name="unique_outbox_delivery_per_endpoint"
            )
        ]
        indexes = [
            models.Index(
                fields=("status", "created_at"),
                name="integrations_outbox_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.event_id} → {self.endpoint.name} ({self.status})"
