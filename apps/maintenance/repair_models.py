"""مدل‌های تعمیرکار مستقل، درخواست تعمیر، ارزیابی و ارجاع عمومی."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.validators import validate_document_file


def _repair_number():
    return f"RR-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _request_number():
    return f"IR-{timezone.localdate():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


class IndependentRepairer(TimeStampedModel):
    """فرد یا شرکت تعمیرکار مستقل؛ بدون نیاز به حساب کاربری."""

    KIND_INDIVIDUAL = "individual"
    KIND_COMPANY = "company"
    KIND_CHOICES = (
        (KIND_INDIVIDUAL, "شخص حقیقی"),
        (KIND_COMPANY, "شرکت"),
    )

    province = models.ForeignKey(
        "org.OrganizationalUnit", on_delete=models.PROTECT,
        related_name="independent_repairers", verbose_name="استان",
        limit_choices_to={"unit_type": "province"},
    )
    kind = models.CharField("نوع تعمیرکار", max_length=20, choices=KIND_CHOICES)
    name = models.CharField("نام تعمیرکار / شرکت", max_length=200)
    national_id = models.CharField("شناسه ملی / کد ملی", max_length=20, blank=True)
    phone = models.CharField("تلفن", max_length=30, blank=True)
    email = models.EmailField("رایانامه", blank=True)
    address = models.TextField("نشانی", blank=True)
    specialties = models.CharField("تخصص‌ها", max_length=300, blank=True)
    notes = models.TextField("یادداشت", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_independent_repairers", verbose_name="ثبت‌کننده",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="updated_independent_repairers", verbose_name="آخرین ویرایش‌کننده",
    )

    class Meta:
        verbose_name = "تعمیرکار مستقل"
        verbose_name_plural = "تعمیرکاران مستقل"
        ordering = ("name",)
        indexes = [models.Index(fields=("province", "is_active"), name="maint_repairer_prov_active_idx")]

    def __str__(self):
        return self.name


class RepairerProfileEvent(models.Model):
    """نسخه‌های قبلی و جدید مشخصات تعمیرکار برای ممیزی و حفظ تاریخچه."""

    repairer = models.ForeignKey(
        IndependentRepairer, on_delete=models.PROTECT, related_name="profile_events",
        verbose_name="تعمیرکار",
    )
    action = models.CharField("نوع تغییر", max_length=20, choices=(("created", "ایجاد"), ("updated", "ویرایش")))
    previous_values = models.JSONField("مقادیر پیشین", default=dict, blank=True)
    new_values = models.JSONField("مقادیر جدید", default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="repairer_profile_events", verbose_name="اقدام‌کننده",
    )
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "تاریخچه مشخصات تعمیرکار"
        verbose_name_plural = "تاریخچه مشخصات تعمیرکاران"
        ordering = ("-created_at",)


class RepairerStatusEvent(models.Model):
    """تاریخچه غیرقابل‌حذف فعال/غیرفعال شدن تعمیرکار."""

    repairer = models.ForeignKey(
        IndependentRepairer, on_delete=models.PROTECT, related_name="status_events",
        verbose_name="تعمیرکار",
    )
    previous_active = models.BooleanField("وضعیت قبلی")
    new_active = models.BooleanField("وضعیت جدید")
    reason = models.TextField("دلیل تغییر وضعیت")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="repairer_status_events", verbose_name="اقدام‌کننده",
    )
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "تاریخچه وضعیت تعمیرکار"
        verbose_name_plural = "تاریخچه وضعیت تعمیرکاران"
        ordering = ("-created_at",)


class RepairRequest(TimeStampedModel):
    """درخواست تعمیر سخت‌افزاری با تایید استانی و کنترل اختلاف هزینه."""

    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending_approval"
    STATUS_RETURNED = "returned"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed"
    STATUS_DISPUTED = "cost_disputed"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_PENDING, "در انتظار تایید مدیر استان"),
        (STATUS_RETURNED, "عودت برای اصلاح"),
        (STATUS_APPROVED, "مجاز به تعمیر"),
        (STATUS_REJECTED, "رد نهایی"),
        (STATUS_COMPLETED, "تعمیر انجام‌شده"),
        (STATUS_DISPUTED, "اختلاف هزینه"),
        (STATUS_RESOLVED, "مختومه پس از تعیین تکلیف"),
    )

    number = models.CharField("شماره درخواست", max_length=32, unique=True, default=_repair_number)
    center = models.ForeignKey(
        "org.Center", on_delete=models.PROTECT, related_name="repair_requests",
        verbose_name="مرکز",
    )
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.PROTECT, related_name="independent_repairs",
        verbose_name="دارایی",
    )
    repairer = models.ForeignKey(
        IndependentRepairer, on_delete=models.PROTECT, related_name="repair_requests",
        verbose_name="تعمیرکار مستقل",
    )
    repairer_name_snapshot = models.CharField("نام تعمیرکار هنگام ارجاع", max_length=200)
    fault_description = models.TextField("شرح خرابی")
    referral_reason = models.TextField("دلیل ارجاع")
    estimate_amount = models.DecimalField("برآورد هزینه", max_digits=14, decimal_places=2)
    estimate_attachment = models.FileField(
        "پیوست برآورد", upload_to="repairs/estimates/%Y/%m/",
        validators=[validate_document_file], blank=True,
    )
    status = models.CharField(
        "وضعیت", max_length=24, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_repair_requests", verbose_name="کارشناس ارجاع‌دهنده",
    )
    submitted_at = models.DateTimeField("زمان ارسال برای تایید", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_repair_requests", verbose_name="تاییدکننده استانی",
    )
    approved_at = models.DateTimeField("زمان تایید", null=True, blank=True)
    decision_note = models.TextField("توضیح تصمیم مدیر استان", blank=True)
    rejected_at = models.DateTimeField("زمان رد نهایی", null=True, blank=True)
    completed_at = models.DateTimeField("زمان ثبت نتیجه تعمیر", null=True, blank=True)
    outcome = models.TextField("نتیجه و اقدامات تعمیر", blank=True)
    final_cost = models.DecimalField(
        "هزینه نهایی", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    final_cost_reason = models.TextField("توضیح افزایش هزینه", blank=True)
    cost_dispute_resolution = models.TextField("نتیجه تعیین تکلیف اختلاف هزینه", blank=True)
    completion_attachment = models.FileField(
        "پیوست نتیجه تعمیر", upload_to="repairs/completion/%Y/%m/",
        validators=[validate_document_file], blank=True,
    )
    cost_increase_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_repair_cost_increases", verbose_name="تاییدکننده افزایش هزینه",
    )
    cost_increase_approved_at = models.DateTimeField("زمان تایید افزایش هزینه", null=True, blank=True)

    class Meta:
        verbose_name = "درخواست تعمیر مستقل"
        verbose_name_plural = "درخواست‌های تعمیر مستقل"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("center", "status"), name="maint_repair_center_status_idx"),
            models.Index(fields=("repairer", "created_at"), name="maint_repair_repairer_date_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.asset.asset_tag}"

    def get_absolute_url(self):
        return reverse("maintenance:repair_detail", args=[self.pk])

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.asset_id and self.center_id and self.asset.center_id != self.center_id:
            errors["asset"] = "دارایی باید متعلق به همان مرکز درخواست باشد."
        if self.repairer_id and self.center_id:
            province_id = getattr(
                getattr(self.center, "treatment_management", None), "province_id", None
            )
            if province_id and self.repairer.province_id != province_id:
                errors["repairer"] = "تعمیرکار باید متعلق به استان مرکز باشد."
        if self.estimate_amount is not None and self.estimate_amount < 0:
            errors["estimate_amount"] = "برآورد هزینه نمی‌تواند منفی باشد."
        if errors:
            raise ValidationError(errors)


class RepairRequestEvent(models.Model):
    """ردپای تغییر وضعیت و تصمیم‌های درخواست تعمیر."""

    repair_request = models.ForeignKey(
        RepairRequest, on_delete=models.PROTECT, related_name="events",
        verbose_name="درخواست تعمیر",
    )
    action = models.CharField("رویداد", max_length=40)
    previous_status = models.CharField("وضعیت قبلی", max_length=24, blank=True)
    new_status = models.CharField("وضعیت جدید", max_length=24, blank=True)
    note = models.TextField("شرح / دلیل")
    metadata = models.JSONField("اطلاعات تکمیلی", default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="repair_request_events", verbose_name="کاربر عامل",
    )
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "رخداد درخواست تعمیر"
        verbose_name_plural = "رخدادهای درخواست تعمیر"
        ordering = ("created_at",)


class RepairFeedback(TimeStampedModel):
    """سه امتیاز اجباری و نظر ثبت‌شده پس از تعمیر."""

    repair_request = models.OneToOneField(
        RepairRequest, on_delete=models.PROTECT, related_name="feedback",
        verbose_name="درخواست تعمیر",
    )
    repairer = models.ForeignKey(
        IndependentRepairer, on_delete=models.PROTECT, related_name="feedback",
        verbose_name="تعمیرکار",
    )
    center = models.ForeignKey(
        "org.Center", on_delete=models.PROTECT, related_name="repair_feedback",
        verbose_name="مرکز",
    )
    repairer_name_snapshot = models.CharField("نام تعمیرکار هنگام ارزیابی", max_length=200)
    work_quality = models.PositiveSmallIntegerField(
        "کیفیت کار", validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    completion_speed = models.PositiveSmallIntegerField(
        "سرعت انجام", validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    cost_fairness = models.PositiveSmallIntegerField(
        "منصفانه بودن هزینه", validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField("نظر تکمیلی", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="authored_repair_feedback", verbose_name="ثبت‌کننده ارزیابی",
    )

    class Meta:
        verbose_name = "ارزیابی تعمیرکار"
        verbose_name_plural = "ارزیابی تعمیرکاران"
        ordering = ("-created_at",)

    @property
    def average_score(self):
        return round((self.work_quality + self.completion_speed + self.cost_fairness) / 3, 2)


class RepairFeedbackReply(models.Model):
    """پاسخ/پیگیری رشته‌ای روی نظر اصلی؛ متن قبلی حذف یا بازنویسی نمی‌شود."""

    feedback = models.ForeignKey(
        RepairFeedback, on_delete=models.PROTECT, related_name="replies",
        verbose_name="ارزیابی",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="پاسخ به",
    )
    body = models.TextField("متن پاسخ")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="repair_feedback_replies", verbose_name="نویسنده",
    )
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "پاسخ ارزیابی تعمیرکار"
        verbose_name_plural = "پاسخ‌های ارزیابی تعمیرکار"
        ordering = ("created_at",)


class GeneralReferral(TimeStampedModel):
    """ارجاع عمومی ITAM برای پیگیری موضوعات بین واحدی و اختلاف‌ها."""

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = ((STATUS_OPEN, "باز"), (STATUS_RESOLVED, "تعیین تکلیف‌شده"))

    subject = models.CharField("موضوع", max_length=200)
    description = models.TextField("شرح و علت ارجاع")
    center = models.ForeignKey(
        "org.Center", on_delete=models.PROTECT, related_name="general_referrals",
        verbose_name="مرکز", null=True, blank=True,
    )
    repair_request = models.ForeignKey(
        RepairRequest, on_delete=models.PROTECT, related_name="referrals",
        verbose_name="درخواست تعمیر مرتبط", null=True, blank=True,
    )
    recipient_role = models.CharField("سمت / واحد گیرنده", max_length=120)
    recipient_name = models.CharField("نام گیرنده", max_length=150)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="received_itam_referrals", verbose_name="کاربر گیرنده",
    )
    status = models.CharField("وضعیت", max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    outcome = models.TextField("نتیجه پیگیری", blank=True)
    instruction = models.TextField("دستور / اقدام ثبت‌شده", blank=True)
    attachment = models.FileField(
        "مستند پیوست", upload_to="referrals/%Y/%m/",
        validators=[validate_document_file], blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_itam_referrals", verbose_name="ارجاع‌دهنده",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="resolved_itam_referrals", verbose_name="ثبت‌کننده نتیجه",
    )
    resolved_at = models.DateTimeField("زمان تعیین تکلیف", null=True, blank=True)

    class Meta:
        verbose_name = "ارجاع عمومی"
        verbose_name_plural = "ارجاع‌های عمومی"
        ordering = ("-created_at",)


class GeneralITRequest(TimeStampedModel):
    """درخواست عمومی تجهیزات/خدمات IT با تایید مدیر مرکزِ اختیاری و ثبت مسیر عبور."""

    TYPE_EQUIPMENT = "equipment"
    TYPE_REPLACEMENT = "replacement"
    TYPE_ISSUE = "issue"
    TYPE_CHOICES = (
        (TYPE_EQUIPMENT, "درخواست تامین تجهیز"),
        (TYPE_REPLACEMENT, "درخواست جایگزینی تجهیز"),
        (TYPE_ISSUE, "گزارش مسئله / کمبود"),
    )
    STATUS_NEW = "new"
    STATUS_ASSIGNED = "assigned"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_ESCALATED = "escalated"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = (
        (STATUS_NEW, "ثبت‌شده"),
        (STATUS_ASSIGNED, "ارجاع به کارشناس IT"),
        (STATUS_APPROVED, "تاییدشده"),
        (STATUS_REJECTED, "ردشده"),
        (STATUS_ESCALATED, "ارسال به استان"),
        (STATUS_RESOLVED, "مختومه"),
    )
    MANAGER_PENDING = "pending"
    MANAGER_APPROVED = "approved"
    MANAGER_REJECTED = "rejected"
    MANAGER_BYPASSED = "bypassed"
    MANAGER_NOT_REQUIRED = "not_required"
    MANAGER_CHOICES = (
        (MANAGER_PENDING, "در انتظار بررسی مدیر"),
        (MANAGER_APPROVED, "تایید مدیر"),
        (MANAGER_REJECTED, "رد مدیر"),
        (MANAGER_BYPASSED, "عبور با ثبت دلیل"),
        (MANAGER_NOT_REQUIRED, "نیازمند تایید نیست"),
    )

    number = models.CharField("شماره درخواست", max_length=32, unique=True, default=_request_number)
    request_type = models.CharField("نوع درخواست", max_length=20, choices=TYPE_CHOICES)
    center = models.ForeignKey(
        "org.Center", on_delete=models.PROTECT, related_name="it_requests", verbose_name="مرکز",
    )
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.PROTECT, null=True, blank=True,
        related_name="it_service_requests", verbose_name="دارایی مرتبط",
    )
    title = models.CharField("عنوان", max_length=200)
    description = models.TextField("شرح درخواست")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="submitted_it_requests", verbose_name="درخواست‌کننده",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="assigned_it_requests", verbose_name="کارشناس IT مسئول",
    )
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    manager_approval = models.CharField(
        "وضعیت تایید مدیر مرکز", max_length=20, choices=MANAGER_CHOICES, default=MANAGER_PENDING,
    )
    manager_bypass_reason = models.TextField("دلیل عبور از تایید مدیر", blank=True)
    manager_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_it_requests", verbose_name="مدیر بررسی‌کننده",
    )
    manager_reviewed_at = models.DateTimeField("زمان بررسی مدیر", null=True, blank=True)
    provincial_decision = models.TextField("تصمیم / دستور استانی", blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="resolved_it_requests", verbose_name="ثبت‌کننده نتیجه",
    )
    resolved_at = models.DateTimeField("زمان خاتمه", null=True, blank=True)

    class Meta:
        verbose_name = "درخواست عمومی فناوری اطلاعات"
        verbose_name_plural = "درخواست‌های عمومی فناوری اطلاعات"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("center", "status"), name="maint_itreq_center_status_idx")]

    def __str__(self):
        return f"{self.number} — {self.title}"


class GeneralITRequestEvent(models.Model):
    """تاریخچه غیرقابل‌حذف گردش درخواست عمومی IT."""

    request = models.ForeignKey(
        GeneralITRequest, on_delete=models.PROTECT, related_name="events",
        verbose_name="درخواست",
    )
    action = models.CharField("رویداد", max_length=40)
    note = models.TextField("شرح")
    metadata = models.JSONField("اطلاعات تکمیلی", default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="it_request_events", verbose_name="کاربر عامل",
    )
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "رخداد درخواست عمومی IT"
        verbose_name_plural = "رخدادهای درخواست عمومی IT"
        ordering = ("created_at",)
