"""مدل کاربر با نقش‌های سامانه و پشتیبانی از ساختار چند مرکزی."""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.validators import validate_image_file


class User(AbstractUser):
    """کاربر سامانه با نقش مشخص در سلسله‌مراتب استانی.
    نقش‌ها:
      * مدیر فناوری اطلاعات استان — مدیریت کامل، نظارت استانی بر تمام مراکز
      * کارشناس فناوری اطلاعات مرکز — مدیریت کامل و تایید نهایی در مرکز خود
      * کارشناس پیمانکار — ثبت بازدید، تعمیر و اسنپ‌شات (پوشش قرارداد استانی)
      * کاربر / امانت‌دار — اعلام خرابی و تایید رفع در مرکز خود
      * مدیر و ناظر مرکز — مشاهده و گزارش‌گیری مرکز
    """

    ROLE_ADMIN_COUNTRY = "admin_country"
    ROLE_ADMIN_PROVINCE = "admin_province"
    ROLE_ADMIN_COUNTY = "admin_county"
    ROLE_ADMIN_IT = "admin_it"
    ROLE_TECHNICIAN = "technician"
    ROLE_REQUESTER = "requester"
    ROLE_MANAGER = "manager"

    ROLE_CHOICES = (
        (ROLE_ADMIN_COUNTRY, "مدیر فناوری اطلاعات کشوری (ستاد)"),
        (ROLE_ADMIN_PROVINCE, "مدیر فناوری اطلاعات استان"),
        (ROLE_ADMIN_COUNTY, "مدیر فناوری اطلاعات شهرستان"),
        (ROLE_ADMIN_IT, "کارشناس فناوری اطلاعات مرکز"),
        (ROLE_TECHNICIAN, "کارشناس پیمانکار (پشتیبان استانی)"),
        (ROLE_REQUESTER, "کاربر / امانت‌دار"),
        (ROLE_MANAGER, "مدیر و ناظر مرکز"),
    )
    ROLE_LABELS = dict(ROLE_CHOICES)
    ROLE_CSS = {
        ROLE_ADMIN_COUNTRY: "danger",
        ROLE_ADMIN_PROVINCE: "primary",
        ROLE_ADMIN_COUNTY: "info",
        ROLE_ADMIN_IT: "success",
        ROLE_TECHNICIAN: "secondary",
        ROLE_REQUESTER: "neutral",
        ROLE_MANAGER: "warning",
    }
    role = models.CharField("نقش", max_length=20, choices=ROLE_CHOICES, default=ROLE_REQUESTER)
    org_unit = models.ForeignKey(
        "org.OrganizationalUnit",
        verbose_name="واحد سازمانی کلان",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="واحد سازمانی کشوری، استانی یا شهرستانی تحت مدیریت کاربر",
    )
    center = models.ForeignKey(
        "org.Center",
        verbose_name="مرکز خدمت",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="مرکزی که کاربر یا کارشناس در آن مستقر است (برای مدیر استان می‌تواند خالی یا ستاد باشد)",
    )
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
        if self.is_superuser:
            return [code for code, _ in self.ROLE_CHOICES]
        codes = [self.role]
        if self.role == self.ROLE_ADMIN_COUNTRY:
            codes.extend([self.ROLE_ADMIN_PROVINCE, self.ROLE_ADMIN_COUNTY, self.ROLE_ADMIN_IT, self.ROLE_MANAGER])
        elif self.role == self.ROLE_ADMIN_PROVINCE:
            codes.extend([self.ROLE_ADMIN_COUNTY, self.ROLE_ADMIN_IT, self.ROLE_MANAGER])
        elif self.role == self.ROLE_ADMIN_COUNTY:
            codes.extend([self.ROLE_ADMIN_IT, self.ROLE_MANAGER])
        return codes

    def has_role(self, *roles: str) -> bool:
        return bool(set(roles) & set(self.role_codes()))

    @property
    def is_admin_country(self) -> bool:
        return self.is_superuser or self.role == self.ROLE_ADMIN_COUNTRY

    @property
    def is_admin_province(self) -> bool:
        return self.is_superuser or self.role in (self.ROLE_ADMIN_COUNTRY, self.ROLE_ADMIN_PROVINCE)

    @property
    def is_admin_county(self) -> bool:
        return self.is_superuser or self.role in (self.ROLE_ADMIN_COUNTRY, self.ROLE_ADMIN_PROVINCE, self.ROLE_ADMIN_COUNTY)

    @property
    def is_admin_it(self) -> bool:
        return self.is_superuser or self.has_role(self.ROLE_ADMIN_COUNTRY, self.ROLE_ADMIN_PROVINCE, self.ROLE_ADMIN_COUNTY, self.ROLE_ADMIN_IT)

    def get_scoped_centers(self):
        """محاسبه دقیق دامنه مراکز مجاز کاربر (Fail-Closed)."""
        from apps.org.models import Center
        if not getattr(self, "is_authenticated", False):
            return Center.objects.none()
        if self.is_superuser or self.role == self.ROLE_ADMIN_COUNTRY:
            return Center.objects.all()
        if self.role == self.ROLE_ADMIN_PROVINCE:
            if self.org_unit:
                return Center.objects.filter(parent_unit__parent=self.org_unit)
            if self.center:
                if self.center.parent_unit and self.center.parent_unit.parent:
                    return Center.objects.filter(parent_unit__parent=self.center.parent_unit.parent)
                # مسیر سازگار موقت منحصراً برای مراکزی که هنوز به شهرستان متصل نشده‌اند
                return Center.objects.filter(province=self.center.province)
            return Center.objects.none()
        if self.role == self.ROLE_ADMIN_COUNTY:
            if self.org_unit:
                return Center.objects.filter(parent_unit=self.org_unit)
            if self.center:
                return Center.objects.filter(pk=self.center_id)
            return Center.objects.none()
        if self.role in (self.ROLE_ADMIN_IT, self.ROLE_MANAGER):
            if self.center_id:
                return Center.objects.filter(pk=self.center_id)
            return Center.objects.none()
        if self.role == self.ROLE_TECHNICIAN:
            if self.contractor_id:
                from apps.org.models import Contract
                active_contracts = self.contractor.contracts.filter(status=Contract.STATUS_ACTIVE)
                if active_contracts.filter(is_provincial=True).exists():
                    return Center.objects.all()
                return Center.objects.filter(contracts__in=active_contracts).distinct()
            return Center.objects.none()
        if self.role == self.ROLE_REQUESTER:
            if self.center_id:
                return Center.objects.filter(pk=self.center_id)
            return Center.objects.none()
        return Center.objects.none()

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
    def can_manage_all_centers(self) -> bool:
        return self.is_admin_province

    @property
    def can_manage_org(self) -> bool:
        return self.has_role(self.ROLE_ADMIN_PROVINCE, self.ROLE_ADMIN_IT)

    @property
    def can_view_reports(self) -> bool:
        return self.has_role(self.ROLE_ADMIN_PROVINCE, self.ROLE_ADMIN_IT, self.ROLE_MANAGER)

    @property
    def visible_contractor(self):
        if self.has_role(self.ROLE_TECHNICIAN):
            return self.contractor
        return None
