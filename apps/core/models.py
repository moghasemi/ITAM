"""مدل‌های هسته: تنظیمات سامانه، تعطیلات، لاگ ممیزی و اعلان‌ها."""
from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from . import jalali
from .validators import validate_image_file

#: روزهای هفته به تفکیک شماره روز پایتون (دوشنبه = ۰)
WEEKDAY_CHOICES = (
    (5, "شنبه"),
    (6, "یک‌شنبه"),
    (0, "دوشنبه"),
    (1, "سه‌شنبه"),
    (2, "چهارشنبه"),
    (3, "پنج‌شنبه"),
    (4, "جمعه"),
)

DEFAULT_WORK_DAYS = [5, 6, 0, 1, 2]  # شنبه تا چهارشنبه

SETTING_CACHE_KEY = "itam:system-setting"


class TimeStampedModel(models.Model):
    """مدل پایه با مهر زمانی ثبت و ویرایش."""

    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("آخرین ویرایش", auto_now=True)

    class Meta:
        abstract = True


class SystemSetting(models.Model):
    """تنظیمات سراسری سامانه (تنها یک رکورد)."""

    COUNTING_24_7 = "24_7"
    COUNTING_WORK_HOURS = "work_hours"
    COUNTING_CHOICES = (
        (COUNTING_WORK_HOURS, "فقط ساعت کاری اداره"),
        (COUNTING_24_7, "شبانه‌روزی (۲۴ ساعته)"),
    )

    org_name = models.CharField("نام اداره / سازمان", max_length=200, default="اداره")
    site_name = models.CharField(
        "عنوان سامانه",
        max_length=200,
        default="سامانه مدیریت دارایی و نگهداری فناوری اطلاعات",
    )
    public_base_url = models.CharField(
        "آدرس پایه سامانه در شبکه",
        max_length=200,
        blank=True,
        help_text="این آدرس داخل QR تجهیزات درج می‌شود؛ مثال: http://10.0.0.5:8000",
    )

    counting_mode = models.CharField(
        "مبنای محاسبه SLA",
        max_length=20,
        choices=COUNTING_CHOICES,
        default=COUNTING_WORK_HOURS,
    )
    work_start = models.TimeField("شروع ساعت کاری", default=dt.time(7, 30))
    work_end = models.TimeField("پایان ساعت کاری", default=dt.time(15, 30))
    work_days = models.JSONField("روزهای کاری هفته", default=list, blank=True)
    exclude_holidays = models.BooleanField("کسر تعطیلات رسمی از SLA", default=True)

    default_response_minutes = models.PositiveIntegerField(
        "زمان پاسخ پیش‌فرض (دقیقه کاری)", default=240
    )
    default_resolve_minutes = models.PositiveIntegerField(
        "زمان رفع خرابی پیش‌فرض (دقیقه کاری)", default=2880
    )
    pause_clock_on_parts_wait = models.BooleanField(
        "توقف ساعت SLA در انتظار قطعه", default=True
    )
    require_user_confirmation = models.BooleanField("تایید کاربر الزامی است", default=True)
    require_it_confirmation = models.BooleanField(
        "تایید کارشناس فناوری اطلاعات مرکز الزامی است", default=True
    )
    baseline_requires_it_confirm = models.BooleanField(
        "اسنپ‌شات پایه سخت‌افزار نیازمند تایید کارشناس IT است", default=True
    )
    hardware_diff_alerts = models.BooleanField(
        "هشدار در صورت تغییر اقلام سخت‌افزاری کیس", default=True
    )

    logo = models.FileField(
        "نشان سازمان",
        upload_to="settings/",
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    footer_note = models.CharField("یادداشت پاصفحه", max_length=300, blank=True)

    updated_at = models.DateTimeField("آخرین ویرایش", auto_now=True)

    class Meta:
        verbose_name = "تنظیمات سامانه"
        verbose_name_plural = "تنظیمات سامانه"

    def __str__(self) -> str:
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        if not self.work_days:
            self.work_days = list(DEFAULT_WORK_DAYS)
        super().save(*args, **kwargs)
        cache.delete(SETTING_CACHE_KEY)

    @classmethod
    def load(cls) -> "SystemSetting":
        """دریافت تنظیمات با کش؛ در صورت نبود رکورد، ساخته می‌شود."""
        setting = cache.get(SETTING_CACHE_KEY)
        if setting is None:
            setting, _ = cls.objects.get_or_create(pk=1)
            cache.set(SETTING_CACHE_KEY, setting, 300)
        return setting

    @property
    def work_day_set(self) -> set[int]:
        days = self.work_days or DEFAULT_WORK_DAYS
        return {int(day) for day in days}

    @property
    def is_24_7(self) -> bool:
        return self.counting_mode == self.COUNTING_24_7

    def base_url(self) -> str:
        """آدرس پایه برای ساخت لینک QR."""
        if self.public_base_url:
            return self.public_base_url.rstrip("/")
        return ""

    def work_day_labels(self) -> str:
        labels = dict(WEEKDAY_CHOICES)
        return "، ".join(labels.get(day, str(day)) for day in DEFAULT_WORK_DAYS if day in self.work_day_set)


class Holiday(TimeStampedModel):
    """تعطیلات رسمی برای محاسبه دقیق SLA."""

    title = models.CharField("عنوان", max_length=150)
    date = models.DateField("تاریخ")
    is_recurring_annual = models.BooleanField(
        "هر سال تکرار می‌شود", default=False, help_text="بر اساس ماه و روز شمسی"
    )
    is_active = models.BooleanField("فعال", default=True)
    note = models.CharField("توضیح", max_length=200, blank=True)

    class Meta:
        verbose_name = "تعطیل رسمی"
        verbose_name_plural = "تعطیلات رسمی"
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(fields=("date",), name="unique_holiday_date"),
        ]

    def __str__(self) -> str:
        return f"{self.title} — {self.jalali_date()}"

    def jalali_date(self) -> str:
        return jalali.format_jalali(self.date, "Y/m/d")

    def jalali_key(self) -> tuple[int, int]:
        jdate = jalali.to_jalali(self.date)
        return jdate.month, jdate.day


class AuditLog(models.Model):
    """لاگ ممیزی فقط-افزودنی؛ تمام رخدادهای مهم سامانه."""

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_LOGIN = "login"
    ACTION_LOGIN_FAILED = "login_failed"
    ACTION_LOGOUT = "logout"
    ACTION_STATUS = "status_change"
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_EXPORT = "export"
    ACTION_DISPATCH = "dispatch"
    ACTION_VIEW = "view"
    ACTION_CHOICES = (
        (ACTION_CREATE, "ایجاد"),
        (ACTION_UPDATE, "ویرایش"),
        (ACTION_DELETE, "حذف"),
        (ACTION_LOGIN, "ورود"),
        (ACTION_LOGIN_FAILED, "ورود ناموفق"),
        (ACTION_LOGOUT, "خروج"),
        (ACTION_STATUS, "تغییر وضعیت"),
        (ACTION_APPROVE, "تایید"),
        (ACTION_REJECT, "رد"),
        (ACTION_EXPORT, "خروجی‌گیری"),
        (ACTION_DISPATCH, "ارسال به مدیریت"),
        (ACTION_VIEW, "مشاهده"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    user_label = models.CharField("عنوان کاربر", max_length=200, blank=True)
    action = models.CharField("عملیات", max_length=20, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField("موجودیت", max_length=100, blank=True, db_index=True)
    object_id = models.CharField("شناسه رکورد", max_length=64, blank=True)
    object_label = models.CharField("عنوان رکورد", max_length=250, blank=True)
    changes = models.JSONField("تغییرات", default=dict, blank=True)
    note = models.CharField("توضیح", max_length=300, blank=True)
    ip_address = models.GenericIPAddressField("نشانی IP", null=True, blank=True)
    user_agent = models.CharField("مرورگر", max_length=300, blank=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "رخداد ممیزی"
        verbose_name_plural = "لاگ ممیزی"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("model_name", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} — {self.object_label or self.model_name}"

    @property
    def jalali_created(self) -> str:
        return jalali.format_jalali(self.created_at, "Y/m/d H:M")


class Notification(models.Model):
    """اعلان داخلی (کارتابل کاربران)."""

    LEVEL_CHOICES = (
        ("info", "اطلاع"),
        ("success", "موفق"),
        ("warning", "هشدار"),
        ("danger", "بحرانی"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="گیرنده",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField("عنوان", max_length=200)
    message = models.TextField("متن", blank=True)
    url = models.CharField("پیوند", max_length=300, blank=True)
    level = models.CharField("سطح", max_length=10, choices=LEVEL_CHOICES, default="info")
    is_read = models.BooleanField("خوانده شده", default=False, db_index=True)
    read_at = models.DateTimeField("زمان خواندن", null=True, blank=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title

    def mark_read(self, save: bool = True):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=["is_read", "read_at"])

    @classmethod
    def push(cls, user, title, message="", url="", level="info"):
        if user is None:
            return None
        return cls.objects.create(
            user=user, title=title, message=message, url=url, level=level
        )

    @classmethod
    def push_many(cls, users, title, message="", url="", level="info"):
        created = []
        for user in users:
            created.append(cls.push(user, title, message, url, level))
        return created
