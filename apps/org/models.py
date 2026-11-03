"""ساختار سازمانی، مراکز استان، پیمانکار، قرارداد و سیاست‌های SLA."""
from __future__ import annotations

import datetime as dt
import math

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core import jalali
from apps.core.constants import PRIORITY_CHOICES, PRIORITY_MEDIUM, PRIORITY_ORDER
from apps.core.models import TimeStampedModel


class Center(TimeStampedModel):
    """مرکز اداری / شهرستانی تحت مدیریت و نظارت مرکز فناوری اطلاعات استان."""

    name = models.CharField("نام مرکز", max_length=150, unique=True)
    code = models.CharField("کد مرکز", max_length=30, blank=True, unique=True)
    province = models.CharField("استان", max_length=80, default="مرکزی")
    city = models.CharField("شهر / شهرستان", max_length=80, blank=True)
    address = models.TextField("نشانی", blank=True)
    phone = models.CharField("تلفن", max_length=30, blank=True)
    manager_name = models.CharField("نام مسئول مرکز", max_length=150, blank=True)
    it_lead_name = models.CharField("کارشناس ارشد IT مرکز", max_length=150, blank=True)
    is_headquarters = models.BooleanField(
        "مرکز ستاد / مدیریت استانی",
        default=False,
        help_text="مرکز اصلی فناوری اطلاعات و ستاد مدیریت استان",
    )
    is_active = models.BooleanField("فعال", default=True)
    notes = models.TextField("یادداشت", blank=True)

    class Meta:
        verbose_name = "مرکز"
        verbose_name_plural = "مراکز استان"
        ordering = ("-is_headquarters", "name")

    def __str__(self) -> str:
        prefix = "★ ستاد استان: " if self.is_headquarters else ""
        return f"{prefix}{self.name}"

    @property
    def display_title(self) -> str:
        if self.city and self.city != self.name:
            return f"{self.name} ({self.city})"
        return self.name


class Department(TimeStampedModel):
    """واحد سازمانی / اداره کل زیرمجموعه."""

    center = models.ForeignKey(
        Center,
        verbose_name="مرکز",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="departments",
    )
    name = models.CharField("نام واحد", max_length=150)
    code = models.CharField("کد واحد", max_length=30, blank=True)
    manager_name = models.CharField("نام مسئول واحد", max_length=150, blank=True)
    phone = models.CharField("تلفن", max_length=30, blank=True)
    description = models.TextField("توضیحات", blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "واحد سازمانی"
        verbose_name_plural = "واحدهای سازمانی"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("center", "name"), name="unique_department_per_center"
            )
        ]

    def __str__(self) -> str:
        if self.center:
            return f"{self.name} ({self.center.name})"
        return self.name


class Location(TimeStampedModel):
    """محل استقرار تجهیزات."""

    center = models.ForeignKey(
        Center,
        verbose_name="مرکز",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="locations",
    )
    name = models.CharField("عنوان محل", max_length=150)
    building = models.CharField("ساختمان", max_length=100, blank=True)
    floor = models.CharField("طبقه", max_length=50, blank=True)
    room = models.CharField("اتاق", max_length=50, blank=True)
    code = models.CharField("کد محل", max_length=30, blank=True)
    description = models.CharField("توضیحات", max_length=250, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "محل استقرار"
        verbose_name_plural = "محل‌های استقرار"
        ordering = ("building", "floor", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("center", "name", "building", "floor", "room"),
                name="unique_location_per_center",
            )
        ]

    def __str__(self) -> str:
        parts = [self.building, self.floor, self.name]
        label = " — ".join(part for part in parts if part)
        if self.center:
            return f"{label} [{self.center.name}]"
        return label

    @property
    def full_label(self) -> str:
        parts = [self.building, self.floor, self.room or self.name]
        label = " / ".join(part for part in parts if part)
        if self.center:
            return f"{self.center.name}: {label}"
        return label


class Contractor(TimeStampedModel):
    """شرکت پیمانکار خدمات فناوری اطلاعات (پشتیبان استانی)."""

    name = models.CharField("نام شرکت", max_length=200, unique=True)
    code = models.CharField("کد پیمانکار", max_length=30, blank=True)
    national_id = models.CharField("شناسه ملی", max_length=20, blank=True)
    economic_code = models.CharField("کد اقتصادی", max_length=20, blank=True)
    phone = models.CharField("تلفن", max_length=30, blank=True)
    email = models.EmailField("رایانامه", blank=True)
    address = models.TextField("نشانی", blank=True)
    contact_person = models.CharField("نام رابط", max_length=150, blank=True)
    contact_phone = models.CharField("تلفن رابط", max_length=30, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    notes = models.TextField("یادداشت", blank=True)

    class Meta:
        verbose_name = "پیمانکار"
        verbose_name_plural = "پیمانکاران"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    @property
    def active_contract(self):
        today = timezone.localdate()
        return (
            self.contracts.filter(
                status=Contract.STATUS_ACTIVE, start_date__lte=today, end_date__gte=today
            )
            .order_by("-start_date")
            .first()
        )


class Contract(TimeStampedModel):
    """قرارداد نگهداری و تعمیرات (با پشتیبانی از قرارداد استانی)."""

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_EXPIRED = "expired"
    STATUS_TERMINATED = "terminated"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_ACTIVE, "جاری"),
        (STATUS_SUSPENDED, "معلق"),
        (STATUS_EXPIRED, "منقضی"),
        (STATUS_TERMINATED, "فسخ‌شده"),
    )

    STATUS_CSS = {
        STATUS_DRAFT: "neutral",
        STATUS_ACTIVE: "success",
        STATUS_SUSPENDED: "warning",
        STATUS_EXPIRED: "danger",
        STATUS_TERMINATED: "neutral",
    }

    contractor = models.ForeignKey(
        Contractor,
        verbose_name="پیمانکار",
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    number = models.CharField("شماره قرارداد", max_length=60, unique=True)
    title = models.CharField("عنوان قرارداد", max_length=200)
    is_provincial = models.BooleanField(
        "قرارداد سراسری استانی",
        default=True,
        help_text="شرکت پشتیبان برای تمام مراکز استان در دوره قرارداد ارائه خدمت می‌کند",
    )
    centers = models.ManyToManyField(
        Center,
        verbose_name="مراکز تحت پوشش",
        blank=True,
        related_name="contracts",
        help_text="در صورت غیرفعال بودن قرارداد سراسری، مراکز تحت پوشش را انتخاب کنید",
    )
    start_date = models.DateField("تاریخ شروع")
    end_date = models.DateField("تاریخ پایان")
    visit_interval_days = models.PositiveIntegerField(
        "دوره بازدید (روز)", default=90, help_text="مثلاً ۹۰ روز برای بازدید فصلی"
    )
    visit_scope = models.TextField("شرح خدمات بازدید دوره‌ای", blank=True)
    repair_scope = models.TextField("شرح خدمات تعمیراتی", blank=True)
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField("یادداشت", blank=True)

    class Meta:
        verbose_name = "قرارداد"
        verbose_name_plural = "قراردادها"
        ordering = ("-start_date",)

    def __str__(self) -> str:
        scope = "[سراسری استان]" if self.is_provincial else "[مراکز منتخب]"
        return f"{self.number} — {self.contractor.name} {scope}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد."})

    def covers_center(self, center) -> bool:
        if self.is_provincial or center is None:
            return True
        return self.centers.filter(pk=center.pk if hasattr(center, "pk") else center).exists()

    @property
    def duration_days(self) -> int:
        if not (self.start_date and self.end_date):
            return 0
        return (self.end_date - self.start_date).days + 1

    @property
    def days_remaining(self) -> int:
        return (self.end_date - timezone.localdate()).days

    @property
    def is_current(self) -> bool:
        today = timezone.localdate()
        return self.status == self.STATUS_ACTIVE and self.start_date <= today <= self.end_date

    @property
    def progress_percent(self) -> float:
        total = self.duration_days
        if not total:
            return 0.0
        elapsed = (timezone.localdate() - self.start_date).days + 1
        return min(100.0, max(0.0, elapsed * 100 / total))

    @property
    def jalali_range(self) -> str:
        return (
            f"{jalali.format_jalali(self.start_date, 'Y/m/d')} تا "
            f"{jalali.format_jalali(self.end_date, 'Y/m/d')}"
        )

    @property
    def status_css(self) -> str:
        if self.status == self.STATUS_ACTIVE and self.days_remaining < 0:
            return "danger"
        return self.STATUS_CSS.get(self.status, "neutral")

    def planned_visit_count(self) -> int:
        interval = self.visit_interval_days or 0
        if interval <= 0:
            return 0
        return max(1, math.ceil(self.duration_days / interval))

    def sla_for(self, priority: str):
        policy = self.sla_policies.filter(priority=priority).first()
        if policy:
            return policy
        return None

    def sla_table(self):
        policies = list(self.sla_policies.all())
        policies.sort(key=lambda item: PRIORITY_ORDER.get(item.priority, 9))
        return policies


class SlaPolicy(TimeStampedModel):
    """زمان‌های تعهدشده پیمانکار به تفکیک اولویت (بر مبنای دقیقه کاری)."""

    contract = models.ForeignKey(
        Contract,
        verbose_name="قرارداد",
        on_delete=models.CASCADE,
        related_name="sla_policies",
    )
    priority = models.CharField(
        "اولویت", max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM
    )
    response_minutes = models.PositiveIntegerField(
        "زمان پاسخ (دقیقه)", default=240, help_text="فاصله اعلام خرابی تا حضور در محل"
    )
    resolve_minutes = models.PositiveIntegerField(
        "زمان رفع خرابی (دقیقه)", default=2880, help_text="فاصله حضور در محل تا اعلام رفع"
    )
    pause_on_parts_wait = models.BooleanField(
        "توقف ساعت در انتظار قطعه", default=True
    )
    description = models.CharField("توضیح", max_length=250, blank=True)

    class Meta:
        verbose_name = "سیاست SLA"
        verbose_name_plural = "سیاست‌های SLA"
        ordering = ("contract", "priority")
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "priority"), name="unique_sla_priority_per_contract"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_priority_display()} — {self.contract.number}"

    @property
    def response_label(self) -> str:
        from apps.core.utils import duration_fa
        return duration_fa(self.response_minutes)

    @property
    def resolve_label(self) -> str:
        from apps.core.utils import duration_fa
        return duration_fa(self.resolve_minutes)


def default_contract_window():
    today = timezone.localdate()
    return today, today.replace(year=today.year + 1) - dt.timedelta(days=1)
