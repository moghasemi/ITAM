"""مدل‌های بازدید دوره‌ای و چک‌لیست تجهیزات."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core import jalali
from apps.core.constants import (
    CHECK_CONDITION_CHOICES,
    CHECK_HEALTHY,
    VISIT_DONE,
    VISIT_IN_PROGRESS,
    VISIT_PLANNED,
    VISIT_STATUS_CHOICES,
)
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_image_file


class MaintenanceVisit(TimeStampedModel):
    """یک نوبت بازدید دوره‌ای پیمانکار در قالب قرارداد."""

    number = models.CharField("شماره بازدید", max_length=30, unique=True, db_index=True)
    contract = models.ForeignKey(
        "org.Contract",
        verbose_name="قرارداد",
        on_delete=models.CASCADE,
        related_name="visits",
    )
    contractor = models.ForeignKey(
        "org.Contractor",
        verbose_name="پیمانکار",
        on_delete=models.PROTECT,
        related_name="visits",
    )
    sequence_number = models.PositiveIntegerField("شماره بازدید در قرارداد", default=1)
    period_label = models.CharField("عنوان دوره", max_length=120, blank=True)
    scheduled_date = models.DateField("تاریخ برنامه‌ریزی‌شده", db_index=True)
    scheduled_end_date = models.DateField("آخرین مهلت انجام", null=True, blank=True)

    status = models.CharField(
        "وضعیت", max_length=20, choices=VISIT_STATUS_CHOICES, default=VISIT_PLANNED, db_index=True
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کارشناس بازدیدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visits",
    )
    started_at = models.DateTimeField("زمان شروع بازدید", null=True, blank=True)
    finished_at = models.DateTimeField("زمان پایان بازدید", null=True, blank=True)

    report_text = models.TextField("گزارش بازدید", blank=True)
    recommendation = models.TextField("پیشنهادها و موارد نیازمند اقدام", blank=True)
    technician_signature_name = models.CharField("نام امضاکننده پیمانکار", max_length=150, blank=True)
    it_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تایید کارشناس IT",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_visits",
    )
    it_confirmed_at = models.DateTimeField("زمان تایید کارشناس IT", null=True, blank=True)
    it_note = models.CharField("یادداشت کارشناس IT", max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="برنامه‌ریز",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_visits",
    )

    class Meta:
        verbose_name = "بازدید دوره‌ای"
        verbose_name_plural = "بازدیدهای دوره‌ای"
        ordering = ("-scheduled_date",)
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "sequence_number"), name="unique_visit_sequence"
            )
        ]

    def __str__(self) -> str:
        return f"{self.number} — {self.contract.contractor.name}"

    def get_absolute_url(self):
        return reverse("maintenance:visit_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        if not self.contractor_id and self.contract_id:
            self.contractor = self.contract.contractor
        if not self.period_label:
            self.period_label = f"بازدید دوره‌ای شماره {self.sequence_number}"
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number() -> str:
        from django.conf import settings as django_settings

        prefix = django_settings.ITAM.get("VISIT_PREFIX", "VS")
        jyear = jalali.jalaali_today().year
        pattern = f"{prefix}-{jyear}-"
        last = (
            MaintenanceVisit.objects.filter(number__startswith=pattern)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        sequence = 1
        if last:
            try:
                sequence = int(last.rsplit("-", 1)[1]) + 1
            except (IndexError, ValueError):
                sequence = MaintenanceVisit.objects.filter(number__startswith=pattern).count() + 1
        return f"{pattern}{sequence:04d}"

    # -- نمایش -------------------------------------------------------------
    @property
    def status_css(self) -> str:
        from apps.core.constants import VISIT_STATUS_CSS

        return VISIT_STATUS_CSS.get(self.status, "neutral")

    @property
    def jalali_scheduled(self) -> str:
        return jalali.format_jalali(self.scheduled_date, "l j F Y")

    @property
    def is_overdue(self) -> bool:
        if self.status in (VISIT_DONE,):
            return False
        deadline = self.scheduled_end_date or self.scheduled_date
        return deadline < timezone.localdate()

    @property
    def days_late(self) -> int:
        if not self.is_overdue:
            return 0
        deadline = self.scheduled_end_date or self.scheduled_date
        return (timezone.localdate() - deadline).days

    @property
    def checks_total(self) -> int:
        return self.checks.count()

    @property
    def checks_done(self) -> int:
        return self.checks.filter(checked=True).count()

    @property
    def completion_percent(self) -> float:
        total = self.checks_total
        if not total:
            return 0.0
        return self.checks_done * 100 / total

    @property
    def faulty_count(self) -> int:
        return self.checks.exclude(condition=CHECK_HEALTHY).filter(checked=True).count()

    @property
    def duration_minutes(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds() / 60
        return None

    # -- گردش کار -----------------------------------------------------------
    def start(self, user):
        if self.status == VISIT_PLANNED:
            self.status = VISIT_IN_PROGRESS
            self.started_at = timezone.now()
            if not self.technician_id:
                self.technician = user
            self.save(update_fields=["status", "started_at", "technician", "updated_at"])

    def complete(self, user):
        self.status = VISIT_DONE
        self.finished_at = timezone.now()
        if not self.started_at:
            self.started_at = self.finished_at
        if not self.technician_id:
            self.technician = user
        if not self.technician_signature_name:
            self.technician_signature_name = user.display_name
        self.save(
            update_fields=[
                "status",
                "finished_at",
                "started_at",
                "technician",
                "technician_signature_name",
                "updated_at",
            ]
        )

    def reopen(self, user):
        self.status = VISIT_IN_PROGRESS
        self.finished_at = None
        self.save(update_fields=["status", "finished_at", "updated_at"])


class VisitAssetCheck(TimeStampedModel):
    """وضعیت یک تجهیز در یک نوبت بازدید."""

    visit = models.ForeignKey(
        MaintenanceVisit,
        verbose_name="بازدید",
        on_delete=models.CASCADE,
        related_name="checks",
    )
    asset = models.ForeignKey(
        "assets.Asset",
        verbose_name="دارایی",
        on_delete=models.CASCADE,
        related_name="visit_checks",
    )
    checked = models.BooleanField("بازدید انجام شد", default=False)
    condition = models.CharField(
        "وضعیت تجهیز", max_length=20, choices=CHECK_CONDITION_CHOICES, default=CHECK_HEALTHY
    )
    actions_taken = models.TextField("خدمات انجام‌شده", blank=True)
    parts_replaced = models.CharField("قطعات تعویض‌شده", max_length=250, blank=True)
    next_due_date = models.DateField("بازدید بعدی", null=True, blank=True)
    hardware_snapshot = models.ForeignKey(
        "assets.HardwareSnapshot",
        verbose_name="اسنپ‌شات سخت‌افزاری ثبت‌شده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visit_checks",
    )
    photo = models.FileField(
        "عکس",
        upload_to="visits/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    notes = models.CharField("یادداشت", max_length=250, blank=True)
    checked_at = models.DateTimeField("زمان بازدید", null=True, blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بازدیدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_checks",
    )

    class Meta:
        verbose_name = "برگه بازدید تجهیز"
        verbose_name_plural = "برگه‌های بازدید تجهیز"
        ordering = ("asset__asset_tag",)
        constraints = [
            models.UniqueConstraint(fields=("visit", "asset"), name="unique_visit_asset"),
        ]

    def __str__(self) -> str:
        return f"{self.asset.asset_tag} در {self.visit.number}"

    @property
    def condition_css(self) -> str:
        from apps.core.constants import CHECK_CONDITION_CSS

        return CHECK_CONDITION_CSS.get(self.condition, "neutral")

    def mark_checked(self, user, condition=None, actions="", notes=""):
        self.checked = True
        self.checked_at = timezone.now()
        self.checked_by = user
        if condition:
            self.condition = condition
        if actions:
            self.actions_taken = actions
        if notes:
            self.notes = notes
        self.save()
