"""مدل‌های درخواست خرابی، گردش کار، توقف ساعت و اتصالات."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.constants import (
    PAUSE_OTHER,
    PAUSE_REASON_CHOICES,
    PRIORITY_CHOICES,
    PRIORITY_LABELS,
    PRIORITY_MEDIUM,
    FAILURE_TYPE_CHOICES,
    STATUS_CANCELED,
    STATUS_CLOSED,
    STATUS_REPORTED,
    STATUS_REJECTED,
    STATUS_USER_CONFIRMED,
    TICKET_CLOSED_STATUSES,
    TICKET_STATUS_CHOICES,
    TICKET_STATUS_LABELS,
    TICKET_STATUS_SEQUENCE,
)
from apps.core.models import TimeStampedModel
from apps.core import jalali


class Ticket(TimeStampedModel):
    """درخواست خرابی تجهیز و چرخه کامل رسیدگی."""

    number = models.CharField("شماره درخواست", max_length=30, unique=True, db_index=True)
    asset = models.ForeignKey(
        "assets.Asset",
        verbose_name="دارایی",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    center = models.ForeignKey(
        "org.Center",
        verbose_name="مرکز",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    contract = models.ForeignKey(
        "org.Contract",
        verbose_name="قرارداد",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    title = models.CharField("عنوان خرابی", max_length=200)
    description = models.TextField("شرح خرابی اعلام‌شده")
    priority = models.CharField(
        "اولویت", max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True
    )
    failure_type = models.CharField("نوع خرابی", max_length=20, choices=FAILURE_TYPE_CHOICES, blank=True)
    status = models.CharField(
        "وضعیت", max_length=20, choices=TICKET_STATUS_CHOICES, default=STATUS_REPORTED, db_index=True
    )

    # -- اعلام‌کننده (زمان اعلام از سمت اداره) ------------------------------
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="اعلام‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_tickets",
    )
    reporter_name = models.CharField("نام اعلام‌کننده", max_length=150, blank=True)
    reporter_phone = models.CharField("تلفن اعلام‌کننده", max_length=30, blank=True)
    reported_at = models.DateTimeField("زمان اعلام خرابی", default=timezone.now, db_index=True)

    # -- پیمانکار -----------------------------------------------------------
    assigned_contractor = models.ForeignKey(
        "org.Contractor",
        verbose_name="پیمانکار مجری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کارشناس پیمانکار",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    scheduled_at = models.DateTimeField("زمان قرار حضور", null=True, blank=True)

    # -- زمان‌های کلیدی SLA -------------------------------------------------
    acknowledged_at = models.DateTimeField("زمان پذیرش پیمانکار", null=True, blank=True)
    arrived_at = models.DateTimeField("زمان حضور در محل", null=True, blank=True)
    work_started_at = models.DateTimeField("زمان شروع تعمیر", null=True, blank=True)
    resolved_declared_at = models.DateTimeField("زمان اعلام رفع خرابی", null=True, blank=True)
    user_confirmed_at = models.DateTimeField("زمان تایید کاربر", null=True, blank=True)
    it_confirmed_at = models.DateTimeField("زمان تایید کارشناس IT", null=True, blank=True)
    closed_at = models.DateTimeField("زمان بسته شدن", null=True, blank=True)

    response_due_at = models.DateTimeField("مهلت حضور", null=True, blank=True)
    resolve_due_at = models.DateTimeField("مهلت رفع خرابی", null=True, blank=True)

    response_minutes_used = models.PositiveIntegerField("دقیقه تا حضور", null=True, blank=True)
    resolve_minutes_used = models.PositiveIntegerField("دقیقه تا رفع", null=True, blank=True)
    total_minutes_used = models.PositiveIntegerField("دقیقه کل چرخه", null=True, blank=True)
    paused_minutes = models.PositiveIntegerField("دقیقه توقف ساعت", default=0)
    response_met = models.BooleanField("SLA حضور رعایت شد", null=True, blank=True)
    resolve_met = models.BooleanField("SLA رفع رعایت شد", null=True, blank=True)

    # -- نتیجه رسیدگی -------------------------------------------------------
    root_cause = models.TextField("علت خرابی", blank=True)
    action_taken = models.TextField("اقدام انجام‌شده", blank=True)
    parts_text = models.CharField("قطعات مصرف‌شده", max_length=300, blank=True)
    user_confirm_note = models.CharField("یادداشت تایید کاربر", max_length=300, blank=True)
    it_confirm_note = models.CharField("یادداشت کارشناس IT", max_length=300, blank=True)
    satisfaction = models.PositiveSmallIntegerField(
        "رضایت کاربر (۱ تا ۵)", null=True, blank=True
    )
    rejection_reason = models.CharField("دلیل رد / لغو", max_length=300, blank=True)

    class Meta:
        verbose_name = "درخواست خرابی"
        verbose_name_plural = "درخواست‌های خرابی"
        ordering = ("-reported_at",)
        indexes = [
            models.Index(fields=("status", "priority")),
            models.Index(fields=("asset", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.number} — {self.title}"

    def get_absolute_url(self):
        return reverse("tickets:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        if not self.contract_id and self.asset_id and self.asset.contract_id:
            self.contract = self.asset.contract
        if not self.assigned_contractor_id and self.contract_id:
            self.assigned_contractor = self.contract.contractor
        if self.reported_at and not self.response_due_at:
            from .services import apply_sla_deadlines

            apply_sla_deadlines(self)
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number() -> str:
        from django.conf import settings as django_settings

        prefix = django_settings.ITAM.get("TICKET_PREFIX", "TK")
        jyear = jalali.jalaali_today().year
        pattern = f"{prefix}-{jyear}-"
        last = (
            Ticket.objects.filter(number__startswith=pattern)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        sequence = 1
        if last:
            try:
                sequence = int(last.rsplit("-", 1)[1]) + 1
            except (IndexError, ValueError):
                sequence = Ticket.objects.filter(number__startswith=pattern).count() + 1
        return f"{pattern}{sequence:04d}"

    # -- نمایش -------------------------------------------------------------
    @property
    def status_css(self) -> str:
        from apps.core.constants import TICKET_STATUS_CSS

        return TICKET_STATUS_CSS.get(self.status, "neutral")

    @property
    def priority_css(self) -> str:
        from apps.core.constants import PRIORITY_CSS

        return PRIORITY_CSS.get(self.priority, "neutral")

    @property
    def priority_label(self) -> str:
        return PRIORITY_LABELS.get(self.priority, self.priority)

    @property
    def is_open(self) -> bool:
        return self.status not in TICKET_CLOSED_STATUSES

    @property
    def is_closed(self) -> bool:
        return self.status in TICKET_CLOSED_STATUSES

    @property
    def is_sla_paused(self) -> bool:
        return self.pauses.filter(ended_at__isnull=True).exists()

    @property
    def reporter_label(self) -> str:
        if self.reported_by_id:
            return self.reported_by.display_name
        return self.reporter_name or "—"

    @property
    def current_step_index(self) -> int:
        try:
            return TICKET_STATUS_SEQUENCE.index(self.status)
        except ValueError:
            return 0

    def workflow_steps(self):
        """گام‌های گردش کار برای نمایش نوار پیشرفت."""
        current = self.current_step_index
        steps = []
        for index, code in enumerate(TICKET_STATUS_SEQUENCE):
            steps.append(
                {
                    "code": code,
                    "label": TICKET_STATUS_LABELS.get(code, code),
                    "done": index < current,
                    "active": index == current,
                }
            )
        return steps

    def response_minutes_display(self):
        from apps.core.utils import duration_fa

        if self.arrived_at and self.reported_at:
            return duration_fa((self.arrived_at - self.reported_at).total_seconds() / 60)
        return duration_fa(self.response_minutes_used) if self.response_minutes_used else "—"

    def resolve_minutes_display(self):
        from apps.core.utils import duration_fa

        if self.resolved_declared_at and self.arrived_at:
            return duration_fa((self.resolved_declared_at - self.arrived_at).total_seconds() / 60)
        return duration_fa(self.resolve_minutes_used) if self.resolve_minutes_used else "—"

    def total_minutes_display(self):
        from apps.core.utils import duration_fa

        return duration_fa(self.total_minutes_used) if self.total_minutes_used else "—"

    def timeline(self):
        """فهرست زمان‌های کلیدی برای نمایش خط زمان SLA."""
        rows = [
            ("اعلام خرابی توسط اداره", self.reported_at, "report"),
            ("پذیرش پیمانکار", self.acknowledged_at, "ack"),
            ("حضور در محل", self.arrived_at, "arrive"),
            ("شروع تعمیر", self.work_started_at, "work"),
            ("اعلام رفع خرابی", self.resolved_declared_at, "resolve"),
            ("تایید کاربر", self.user_confirmed_at, "user"),
            ("تایید کارشناس IT", self.it_confirmed_at, "it"),
            ("بسته شدن", self.closed_at, "close"),
        ]
        return [
            {"label": label, "at": at, "code": code, "done": at is not None}
            for label, at, code in rows
        ]

    def open_pause(self):
        return self.pauses.filter(ended_at__isnull=True).first()

    def pause_intervals(self):
        intervals = []
        for pause in self.pauses.all():
            intervals.append({"start": pause.started_at, "end": pause.ended_at, "reason": pause.reason})
        return intervals


class TicketEvent(models.Model):
    """رخدادهای درخواست — فقط افزودنی (منبع محاسبه SLA)."""

    EVENT_CREATED = "created"
    EVENT_ACKNOWLEDGED = "acknowledged"
    EVENT_ARRIVED = "arrived"
    EVENT_WORK_STARTED = "work_started"
    EVENT_PAUSED = "paused"
    EVENT_RESUMED = "resumed"
    EVENT_STATUS = "status_change"
    EVENT_RESOLVED = "resolved"
    EVENT_USER_CONFIRMED = "user_confirmed"
    EVENT_IT_CONFIRMED = "it_confirmed"
    EVENT_REJECTED = "rejected"
    EVENT_CANCELED = "canceled"
    EVENT_NOTE = "note"
    EVENT_HARDWARE = "hardware_check"
    EVENT_ATTACHMENT = "attachment"

    EVENT_CHOICES = (
        (EVENT_CREATED, "ثبت درخواست"),
        (EVENT_ACKNOWLEDGED, "پذیرش پیمانکار"),
        (EVENT_ARRIVED, "حضور در محل"),
        (EVENT_WORK_STARTED, "شروع تعمیر"),
        (EVENT_PAUSED, "توقف ساعت SLA"),
        (EVENT_RESUMED, "ادامه شمارش ساعت SLA"),
        (EVENT_STATUS, "تغییر وضعیت"),
        (EVENT_RESOLVED, "اعلام رفع خرابی"),
        (EVENT_USER_CONFIRMED, "تایید کاربر"),
        (EVENT_IT_CONFIRMED, "تایید کارشناس IT"),
        (EVENT_REJECTED, "رد درخواست"),
        (EVENT_CANCELED, "لغو درخواست"),
        (EVENT_NOTE, "یادداشت"),
        (EVENT_HARDWARE, "بازبینی سخت‌افزار"),
        (EVENT_ATTACHMENT, "پیوست"),
    )

    ticket = models.ForeignKey(
        Ticket, verbose_name="درخواست", on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField("نوع رخداد", max_length=30, choices=EVENT_CHOICES)
    from_status = models.CharField("وضعیت قبلی", max_length=20, blank=True)
    to_status = models.CharField("وضعیت جدید", max_length=20, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="اقدام‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_events",
    )
    actor_label = models.CharField("عنوان اقدام‌کننده", max_length=150, blank=True)
    note = models.TextField("توضیحات", blank=True)
    meta = models.JSONField("اطلاعات تکمیلی", default=dict, blank=True)
    at = models.DateTimeField("زمان رخداد", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "رخداد درخواست"
        verbose_name_plural = "رخدادهای درخواست"
        ordering = ("at", "pk")
        get_latest_by = "at"

    def __str__(self) -> str:
        return f"{self.ticket.number} — {self.get_event_type_display()}"

    @property
    def jalali_at(self) -> str:
        return jalali.format_jalali(self.at, "Y/m/d H:M:S")


class TicketPause(TimeStampedModel):
    """بازه توقف ساعت SLA (مثلاً انتظار قطعه)."""

    ticket = models.ForeignKey(
        Ticket, verbose_name="درخواست", on_delete=models.CASCADE, related_name="pauses"
    )
    reason = models.CharField(
        "دلیل توقف",
        max_length=30,
        choices=PAUSE_REASON_CHOICES,
        default=PAUSE_OTHER,
    )
    started_at = models.DateTimeField("شروع توقف", default=timezone.now)
    ended_at = models.DateTimeField("پایان توقف", null=True, blank=True)
    note = models.CharField("توضیحات", max_length=250, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_pauses",
    )

    class Meta:
        verbose_name = "توقف ساعت SLA"
        verbose_name_plural = "توقف‌های ساعت SLA"
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.ticket.number} — {self.get_reason_display()}"

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def minutes(self) -> float:
        end = self.ended_at or timezone.now()
        return (end - self.started_at).total_seconds() / 60


class TicketPart(TimeStampedModel):
    """قطعه مصرف/تعویض‌شده در جریان رسیدگی."""

    ACTION_REPLACED = "replaced"
    ACTION_INSTALLED = "installed"
    ACTION_REMOVED = "removed"
    ACTION_CLEANED = "cleaned"
    ACTION_CHOICES = (
        (ACTION_REPLACED, "تعویض"),
        (ACTION_INSTALLED, "نصب"),
        (ACTION_REMOVED, "برداشت"),
        (ACTION_CLEANED, "سرویس و تمیزکاری"),
    )

    ticket = models.ForeignKey(
        Ticket, verbose_name="درخواست", on_delete=models.CASCADE, related_name="parts"
    )
    component_type = models.ForeignKey(
        "assets.ComponentType",
        verbose_name="گونه قطعه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_parts",
    )
    name = models.CharField("نام قطعه", max_length=150)
    action = models.CharField("اقدام", max_length=20, choices=ACTION_CHOICES, default=ACTION_REPLACED)
    old_serial = models.CharField("سریال قبلی", max_length=120, blank=True)
    new_serial = models.CharField("سریال جدید", max_length=120, blank=True)
    quantity = models.PositiveSmallIntegerField("تعداد", default=1)
    unit_price = models.DecimalField("قیمت واحد (ریال)", max_digits=18, decimal_places=0, null=True, blank=True)
    notes = models.CharField("توضیحات", max_length=250, blank=True)

    class Meta:
        verbose_name = "قطعه مصرف‌شده"
        verbose_name_plural = "قطعات مصرف‌شده"
        ordering = ("pk",)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_action_display()})"


class TicketAttachment(TimeStampedModel):
    """پیوست درخواست (عکس قبل/بعد، رسید)."""

    KIND_BEFORE = "before"
    KIND_AFTER = "after"
    KIND_EVIDENCE = "evidence"
    KIND_RECEIPT = "receipt"
    KIND_CHOICES = (
        (KIND_BEFORE, "عکس قبل از تعمیر"),
        (KIND_AFTER, "عکس بعد از تعمیر"),
        (KIND_EVIDENCE, "مدرک / شواهد"),
        (KIND_RECEIPT, "رسید خدمات"),
    )

    ticket = models.ForeignKey(
        Ticket, verbose_name="درخواست", on_delete=models.CASCADE, related_name="attachments"
    )
    kind = models.CharField("نوع", max_length=20, choices=KIND_CHOICES, default=KIND_EVIDENCE)
    title = models.CharField("عنوان", max_length=150, blank=True)
    file = models.FileField("فایل", upload_to="tickets/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بارگذارنده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_ticket_files",
    )

    class Meta:
        verbose_name = "پیوست درخواست"
        verbose_name_plural = "پیوست‌های درخواست"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title or self.file.name
