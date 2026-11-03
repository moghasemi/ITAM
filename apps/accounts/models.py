"""مدل کاربر با نقش‌های سامانه."""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.validators import validate_image_file


class User(AbstractUser):
    """کاربر سامانه با نقش مشخص.

    نقش‌ها:
      * کارشناس فناوری اطلاعات مرکز — مدیریت کامل، تایید نهایی
      * کارشناس پیمانکار — ثبت بازدید، تعمیر و اسنپ‌شات سخت‌افزاری
      * کاربر / امانت‌دار — اعلام خرابی و تایید رفع
      * مدیر و ناظر — مشاهده و گزارش‌گیری
    """

    ROLE_ADMIN_IT = "admin_it"
    ROLE_TECHNICIAN = "technician"
    ROLE_REQUESTER = "requester"
    ROLE_MANAGER = "manager"
    ROLE_CHOICES = (
        (ROLE_ADMIN_IT, "کارشناس فناوری اطلاعات مرکز"),
        (ROLE_TECHNICIAN, "کارشناس پیمانکار"),
        (ROLE_REQUESTER, "کاربر / امانت‌دار"),
        (ROLE_MANAGER, "مدیر و ناظر"),
    )
    ROLE_LABELS = dict(ROLE_CHOICES)
    ROLE_CSS = {
        ROLE_ADMIN_IT: "success",
        ROLE_TECHNICIAN: "info",
        ROLE_REQUESTER: "neutral",
        ROLE_MANAGER: "warning",
    }

    role = models.CharField("نقش", max_length=20, choices=ROLE_CHOICES, default=ROLE_REQUESTER)
    personnel_code = models.CharField("کد پرسنلی", max_length=30, blank=True, db_index=True)
    national_code = models.CharField("کد ملی", max_length=10, blank=True)
    phone = models.CharField("تلفن همراه", max_length=20, blank=True)
    job_title = models.CharField("سمت", max_length=120, blank=True)
    department = models.ForeignKey(
        "org.Department",
        verbose_name="واحد سازمانی",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    contractor = models.ForeignKey(
        "org.Contractor",
        verbose_name="پیمانکار",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technicians",
        help_text="برای کارشناسان پیمانکار تکمیل شود",
    )
    signature = models.FileField(
        "نمونه امضا",
        upload_to="signatures/",
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    last_seen_at = models.DateTimeField("آخرین فعالیت", null=True, blank=True)

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"
        ordering = ("last_name", "first_name", "username")

    def __str__(self) -> str:
        return self.display_name

    # -- نام و نقش ---------------------------------------------------------
    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    @property
    def short_name(self) -> str:
        if self.first_name:
            return self.first_name
        return self.username

    @property
    def role_label(self) -> str:
        return self.ROLE_LABELS.get(self.role, self.role)

    @property
    def role_css(self) -> str:
        return self.ROLE_CSS.get(self.role, "neutral")

    def role_codes(self) -> list[str]:
        """فهرست نقش‌های کاربر (مدیر ارشد سامانه همه نقش‌ها را دارد)."""
        if self.is_superuser:
            return [code for code, _ in self.ROLE_CHOICES]
        return [self.role]

    def has_role(self, *roles: str) -> bool:
        return bool(set(roles) & set(self.role_codes()))

    @property
    def is_admin_it(self) -> bool:
        return self.has_role(self.ROLE_ADMIN_IT)

    @property
    def is_technician(self) -> bool:
        return self.has_role(self.ROLE_TECHNICIAN)

    @property
    def is_requester(self) -> bool:
        return self.has_role(self.ROLE_REQUESTER)

    @property
    def is_manager(self) -> bool:
        return self.has_role(self.ROLE_MANAGER)

    @property
    def can_manage_org(self) -> bool:
        """دسترسی به بخش‌های مدیریتی (قرارداد، دارایی، کاربران)."""
        return self.has_role(self.ROLE_ADMIN_IT)

    @property
    def can_view_reports(self) -> bool:
        return self.has_role(self.ROLE_ADMIN_IT, self.ROLE_MANAGER)

    @property
    def visible_contractor(self):
        """پیمانکار قابل مشاهده برای کارشناس پیمانکار."""
        if self.has_role(self.ROLE_TECHNICIAN):
            return self.contractor
        return None
