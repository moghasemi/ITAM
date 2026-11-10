"""مدل‌های دارایی، اقلام سخت‌افزاری و اسنپ‌شات ضدسرقت."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.constants import (
    ASSET_ACTIVE,
    ASSET_STATUS_CHOICES,
    ITEM_CONDITION_CHOICES,
    ITEM_OK,
    SNAPSHOT_DRAFT,
    SNAPSHOT_LOCKED,
    SNAPSHOT_PENDING,
    SNAPSHOT_REJECTED,
    SNAPSHOT_STATUS_CHOICES,
)
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_image_file


class AssetCategory(TimeStampedModel):
    """گونه دارایی (کیس، پرینتر، مانیتور، ...)."""

    name = models.CharField("نام گونه", max_length=120, unique=True)
    code = models.CharField("کد", max_length=30, blank=True)
    icon = models.CharField("نماد", max_length=40, blank=True, default="💻")
    requires_component_tracking = models.BooleanField(
        "نیازمند ثبت اقلام داخلی (اسنپ‌شات)",
        default=False,
        help_text="برای کیس و لپ‌تاپ فعال شود تا اقلام داخلی ثبت و کنترل گردد",
    )
    is_computing_device = models.BooleanField(
        "تجهیز رایانه‌ای",
        default=False,
        help_text="برای رایانه رومیزی و لپ‌تاپ فعال شود تا مشخصات اختصاصی رایانه نمایش داده شود.",
    )
    is_portable = models.BooleanField("قابل حمل", default=False)
    description = models.CharField("توضیحات", max_length=250, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "گونه دارایی"
        verbose_name_plural = "گونه‌های دارایی"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class ComponentType(TimeStampedModel):
    """گونه قطعه سخت‌افزاری (پردازنده، حافظه، هارد، پاور، ...)."""

    name = models.CharField("نام قطعه", max_length=120, unique=True)
    code = models.CharField("کد", max_length=30, blank=True)
    is_serialized = models.BooleanField(
        "دارای شماره سریال", default=True, help_text="برای اقلامی که سریال یکتا دارند"
    )
    unit = models.CharField("واحد", max_length=20, default="عدد")
    sort_order = models.PositiveSmallIntegerField("ترتیب نمایش", default=100)
    is_key_item = models.BooleanField(
        "قلم کلیدی (کنترل سرقت)", default=False, help_text="اقلام پرارزش مانند حافظه و هارد"
    )
    description = models.CharField("توضیحات", max_length=250, blank=True)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "گونه قطعه"
        verbose_name_plural = "گونه‌های قطعه"
        ordering = ("sort_order", "name")

    def __str__(self) -> str:
        return self.name


class Asset(TimeStampedModel):
    """دارایی فناوری اطلاعات با شماره اموال."""

    asset_tag = models.CharField(
        "شماره اموال", max_length=60, unique=True, db_index=True,
        help_text="شماره اموال ثبت‌شده در دفاتر اداره",
    )
    title = models.CharField("عنوان/نام تجهیز", max_length=150, blank=True)
    category = models.ForeignKey(
        AssetCategory,
        verbose_name="گونه دارایی",
        on_delete=models.PROTECT,
        related_name="assets",
    )
    serial_number = models.CharField("شماره سریال", max_length=120, blank=True, db_index=True)
    brand = models.CharField("برند/سازنده", max_length=100, blank=True)
    model_name = models.CharField("مدل", max_length=120, blank=True)

    center = models.ForeignKey(
        "org.Center",
        verbose_name="مرکز",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        help_text="مرکز / شعبه مالک تجهیز",
    )
    contract = models.ForeignKey(
        "org.Contract",
        verbose_name="قرارداد پشتیبانی",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    department = models.ForeignKey(
        "org.Department",
        verbose_name="واحد سازمانی",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    location = models.ForeignKey(
        "org.Location",
        verbose_name="محل استقرار",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="امانت‌دار / کاربر",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodied_assets",
    )

    status = models.CharField(
        "وضعیت", max_length=20, choices=ASSET_STATUS_CHOICES, default=ASSET_ACTIVE, db_index=True
    )
    hostname = models.CharField("نام رایانه", max_length=80, blank=True)
    ip_address = models.GenericIPAddressField("نشانی IP", null=True, blank=True)
    mac_address = models.CharField("نشانی MAC", max_length=30, blank=True)
    os_name = models.CharField("سیستم‌عامل", max_length=120, blank=True)
    office_software = models.CharField("نرم‌افزارهای اداری", max_length=250, blank=True)
    spec_summary = models.TextField(
        "مشخصات کامل", blank=True, help_text="مشخصات فنی کامل تجهیز برای درج در شناسنامه"
    )

    purchase_date = models.DateField("تاریخ خرید", null=True, blank=True)
    warranty_until = models.DateField("پایان گارانتی", null=True, blank=True)
    price = models.DecimalField("ارزش (ریال)", max_digits=18, decimal_places=0, null=True, blank=True)
    supplier = models.CharField("تامین‌کننده", max_length=150, blank=True)

    qr_token = models.UUIDField("شناسه QR", default=uuid.uuid4, unique=True, editable=False)
    current_snapshot = models.ForeignKey(
        "assets.HardwareSnapshot",
        verbose_name="آخرین اسنپ‌شات سخت‌افزاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    baseline_locked_at = models.DateTimeField("زمان قفل اسنپ‌شات پایه", null=True, blank=True)
    is_quarantined = models.BooleanField(
        "وضعیت قرنطینه عدم انتساب",
        default=False,
        db_index=True,
        help_text="دارایی‌های بدون مرکز قطعی در حالت قرنطینه قرار می‌گیرند",
    )
    quarantine_notes = models.TextField("یادداشت قرنطینه", blank=True)
    notes = models.TextField("یادداشت", blank=True)

    class Meta:
        verbose_name = "دارایی"
        verbose_name_plural = "دارایی‌ها"
        ordering = ("asset_tag",)
        indexes = [
            models.Index(fields=("category", "status")),
            models.Index(fields=("department", "status")),
        ]

    def __str__(self) -> str:
        label = self.title or f"{self.category.name} {self.brand}".strip()
        return f"{self.asset_tag} — {label}"

    # -- دسترسی ------------------------------------------------------------
    def get_absolute_url(self):
        return reverse("assets:detail", args=[self.pk])

    def public_url(self) -> str:
        """نشانی کامل برای درج در QR."""
        from apps.core.models import SystemSetting

        path = reverse("assets:scan", args=[self.qr_token])
        base = SystemSetting.load().base_url()
        if base:
            return f"{base}{path}"
        return path

    def qr_svg(self, module_size: int = 6) -> str:
        from .qrgen import svg

        return svg(self.public_url(), module_size=module_size, title=str(self.asset_tag))

    # -- ویژگی‌ها -----------------------------------------------------------
    @property
    def display_name(self) -> str:
        return self.title or f"{self.category.name} {self.brand} {self.model_name}".strip()

    @property
    def requires_component_tracking(self) -> bool:
        return bool(self.category.requires_component_tracking)

    @property
    def has_baseline(self) -> bool:
        return self.baseline_locked_at is not None

    @property
    def is_under_contract(self) -> bool:
        return bool(self.contract_id and self.contract and self.contract.is_current)

    @property
    def status_css(self) -> str:
        from apps.core.constants import ASSET_STATUS_CSS

        return ASSET_STATUS_CSS.get(self.status, "neutral")

    @property
    def open_tickets_count(self) -> int:
        from apps.core.constants import TICKET_OPEN_STATUSES

        return self.tickets.filter(status__in=TICKET_OPEN_STATUSES).count()

    @property
    def components(self):
        """اقلام سخت‌افزاری جاری این دارایی."""
        if self.current_snapshot_id:
            return self.current_snapshot.items.select_related("component_type")
        return SnapshotItem.objects.none()

    @property
    def components_count(self) -> int:
        if not self.current_snapshot_id:
            return 0
        return self.current_snapshot.items.count()

    @property
    def warranty_state(self) -> str:
        if not self.warranty_until:
            return "نامشخص"
        if self.warranty_until < timezone.localdate():
            return "پایان‌یافته"
        return "معتبر"

    def hardware_summary_lines(self) -> list[str]:
        lines = []
        for item in self.components:
            text = item.display_label
            if item.serial_number:
                text += f" — سریال {item.serial_number}"
            lines.append(text)
        return lines


class AssetRelationship(TimeStampedModel):
    """رابطه ثبت‌شده میان دو دارایی؛ مانند اتصال چاپگر به رایانه."""

    RELATION_CONNECTED_TO = "connected_to"
    RELATION_DEPENDS_ON = "depends_on"
    RELATION_USES = "uses"
    RELATIONSHIP_TYPE_CHOICES = (
        (RELATION_CONNECTED_TO, "متصل به"),
        (RELATION_DEPENDS_ON, "وابسته به"),
        (RELATION_USES, "استفاده می‌کند از"),
    )

    CONNECTION_TYPE_USB = "usb"
    CONNECTION_TYPE_ETHERNET = "ethernet"
    CONNECTION_TYPE_WIFI = "wifi"
    CONNECTION_TYPE_SHARED = "shared"
    CONNECTION_TYPE_OTHER = "other"
    CONNECTION_TYPE_CHOICES = (
        (CONNECTION_TYPE_USB, "USB"),
        (CONNECTION_TYPE_ETHERNET, "شبکه کابلی"),
        (CONNECTION_TYPE_WIFI, "Wi-Fi"),
        (CONNECTION_TYPE_SHARED, "اشتراک‌گذاری شبکه‌ای"),
        (CONNECTION_TYPE_OTHER, "سایر"),
    )

    asset = models.ForeignKey(
        Asset, verbose_name="دارایی مبدأ", on_delete=models.CASCADE,
        related_name="outgoing_relationships",
    )
    related_asset = models.ForeignKey(
        Asset, verbose_name="دارایی مرتبط", on_delete=models.CASCADE,
        related_name="incoming_relationships",
    )
    relationship_type = models.CharField(
        "نوع ارتباط", max_length=20, choices=RELATIONSHIP_TYPE_CHOICES,
        default=RELATION_CONNECTED_TO,
    )
    connection_type = models.CharField(
        "روش اتصال", max_length=20, choices=CONNECTION_TYPE_CHOICES, blank=True,
    )
    is_active = models.BooleanField("ارتباط فعال", default=True)
    notes = models.CharField("توضیحات", max_length=250, blank=True)

    class Meta:
        verbose_name = "ارتباط دارایی"
        verbose_name_plural = "ارتباطات دارایی‌ها"
        ordering = ("asset__asset_tag", "related_asset__asset_tag")
        constraints = [
            models.UniqueConstraint(
                fields=("asset", "related_asset", "relationship_type"),
                name="unique_asset_relationship",
            ),
            models.CheckConstraint(
                condition=~models.Q(asset=models.F("related_asset")),
                name="asset_relationship_not_self",
            ),
        ]

    def clean(self):
        super().clean()
        if self.asset_id and self.related_asset_id:
            if self.asset_id == self.related_asset_id:
                raise ValidationError("یک دارایی نمی‌تواند با خودش ارتباط داشته باشد.")
            if not self.asset.center_id or self.asset.center_id != self.related_asset.center_id:
                raise ValidationError("ارتباط فقط بین دارایی‌های متعلق به یک مرکز مجاز است.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset.asset_tag} — {self.get_relationship_type_display()} — {self.related_asset.asset_tag}"


class HardwareSnapshot(TimeStampedModel):
    """اسنپ‌شات اقلام داخل کیس؛ پایه کنترل سرقت و ردیابی تغییرات."""

    asset = models.ForeignKey(
        Asset,
        verbose_name="دارایی",
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    version = models.PositiveIntegerField("نسخه", default=1)
    status = models.CharField(
        "وضعیت", max_length=20, choices=SNAPSHOT_STATUS_CHOICES, default=SNAPSHOT_DRAFT
    )
    is_baseline = models.BooleanField("اسنپ‌شات پایه", default=False)
    previous = models.ForeignKey(
        "self",
        verbose_name="مبنای مقایسه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_snapshots",
    )
    seal_number = models.CharField("شماره پلمب / برچسب امنیتی", max_length=60, blank=True)
    is_from_hwagent = models.BooleanField("ثبت شده از طریق HWAgent", default=False)
    agent_hashes = models.JSONField("هش‌های اعتبارسنجی HWAgent", default=dict, blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_snapshots",
    )
    recorded_at = models.DateTimeField("زمان ثبت", null=True, blank=True)
    technician_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تایید کارشناس",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technician_confirmed_snapshots",
    )
    technician_confirmed_at = models.DateTimeField("زمان تایید کارشناس", null=True, blank=True)
    it_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تایید کارشناس فناوری اطلاعات",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="it_confirmed_snapshots",
    )
    it_confirmed_at = models.DateTimeField("زمان تایید کارشناس IT", null=True, blank=True)
    locked_at = models.DateTimeField("زمان قفل شدن", null=True, blank=True)

    case_photo = models.FileField(
        "عکس کیس باز شده",
        upload_to="hardware/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    seal_photo = models.FileField(
        "عکس پلمب",
        upload_to="hardware/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_file],
    )

    diff_data = models.JSONField("نتیجه مقایسه", default=dict, blank=True)
    diff_count = models.PositiveIntegerField("تعداد تغییرات", default=0)
    note = models.TextField("توضیحات", blank=True)
    review_note = models.CharField("یادداشت بررسی", max_length=300, blank=True)

    class Meta:
        verbose_name = "اسنپ‌شات سخت‌افزاری"
        verbose_name_plural = "اسنپ‌شات‌های سخت‌افزاری"
        ordering = ("asset", "-version")
        constraints = [
            models.UniqueConstraint(fields=("asset", "version"), name="unique_snapshot_version"),
        ]

    def __str__(self) -> str:
        label = "پایه" if self.is_baseline else f"نسخه {self.version}"
        return f"{self.asset.asset_tag} — {label}"

    # -- دسترسی ------------------------------------------------------------
    def get_absolute_url(self):
        return reverse("assets:snapshot_detail", args=[self.pk])

    # -- وضعیت -------------------------------------------------------------
    @property
    def is_editable(self) -> bool:
        return self.status in (SNAPSHOT_DRAFT, SNAPSHOT_REJECTED)

    @property
    def is_locked(self) -> bool:
        return self.status == SNAPSHOT_LOCKED

    @property
    def status_css(self) -> str:
        from apps.core.constants import SNAPSHOT_STATUS_CSS

        return SNAPSHOT_STATUS_CSS.get(self.status, "neutral")

    @property
    def has_changes(self) -> bool:
        return self.diff_count > 0

    @property
    def changed_items(self):
        return [row for row in (self.diff_data or {}).get("rows", []) if row.get("state") != "unchanged"]

    def items_summary(self) -> str:
        return "، ".join(item.display_label for item in self.items.all())

    @classmethod
    def next_version(cls, asset) -> int:
        last = cls.objects.filter(asset=asset).order_by("-version").first()
        return (last.version + 1) if last else 1

    # -- گردش کار تایید -----------------------------------------------------
    def confirm_by_technician(self, user):
        if self.status not in (SNAPSHOT_DRAFT, SNAPSHOT_REJECTED):
            raise ValidationError("فقط اسنپ‌شات پیش‌نویس یا برگشت‌خورده قابل تایید و ارسال است.")
        self.technician_confirmed_by = user
        self.technician_confirmed_at = timezone.now()
        self.save(update_fields=["technician_confirmed_by", "technician_confirmed_at", "updated_at"])

    def submit_for_review(self, user):
        if self.status not in (SNAPSHOT_DRAFT, SNAPSHOT_REJECTED):
            raise ValidationError("این اسنپ‌شات قبلاً ارسال شده یا وضعیت نهایی دارد.")
        self.status = SNAPSHOT_PENDING
        if not self.recorded_at:
            self.recorded_at = timezone.now()
        if not self.recorded_by_id:
            self.recorded_by = user
        self.review_note = ""
        self.save(
            update_fields=["status", "recorded_at", "recorded_by", "review_note", "updated_at"]
        )

    def lock(self, user):
        from apps.core.models import SystemSetting

        setting = SystemSetting.load()
        if self.status != SNAPSHOT_PENDING:
            raise ValidationError("فقط اسنپ‌شات در انتظار بررسی قابل قفل‌شدن است.")
        if not getattr(user, "is_authenticated", False) or not user.has_role("admin_it"):
            raise ValidationError("قفل اسنپ‌شات فقط توسط کارشناس IT مجاز است.")
        if setting.baseline_requires_it_confirm:
            if not self.technician_confirmed_by_id:
                raise ValidationError("اسنپ‌شات باید ابتدا توسط ثبت‌کننده تایید و ارسال شود.")
            if self.technician_confirmed_by_id == user.pk:
                raise ValidationError("ثبت‌کننده و تاییدکننده اسنپ‌شات باید دو کاربر متفاوت باشند.")
        self.status = SNAPSHOT_LOCKED
        self.locked_at = timezone.now()
        if setting.baseline_requires_it_confirm:
            self.it_confirmed_by = user
            self.it_confirmed_at = self.locked_at
        if not self.technician_confirmed_at:
            self.technician_confirmed_by = user
            self.technician_confirmed_at = self.locked_at
        self.save(
            update_fields=[
                "status",
                "locked_at",
                "it_confirmed_by",
                "it_confirmed_at",
                "technician_confirmed_by",
                "technician_confirmed_at",
                "updated_at",
            ]
        )

    def reject(self, user, note=""):
        from apps.core.models import SystemSetting

        if self.status != SNAPSHOT_PENDING:
            raise ValidationError("فقط اسنپ‌شات در انتظار بررسی قابل رد است.")
        if not getattr(user, "is_authenticated", False) or not user.has_role("admin_it"):
            raise ValidationError("رد اسنپ‌شات فقط توسط کارشناس IT مجاز است.")
        if SystemSetting.load().baseline_requires_it_confirm:
            if not self.technician_confirmed_by_id or self.technician_confirmed_by_id == user.pk:
                raise ValidationError("ثبت‌کننده و بررسی‌کننده اسنپ‌شات باید دو کاربر متفاوت باشند.")
        self.status = SNAPSHOT_REJECTED
        self.review_note = note[:300]
        self.save(update_fields=["status", "review_note", "updated_at"])


class SnapshotItemQuerySet(models.QuerySet):
    def key_items(self):
        return self.filter(component_type__is_key_item=True)


class SnapshotItem(TimeStampedModel):
    """یک قلم سخت‌افزاری درون اسنپ‌شات."""

    snapshot = models.ForeignKey(
        HardwareSnapshot,
        verbose_name="اسنپ‌شات",
        on_delete=models.CASCADE,
        related_name="items",
    )
    component_type = models.ForeignKey(
        ComponentType,
        verbose_name="گونه قطعه",
        on_delete=models.PROTECT,
        related_name="snapshot_items",
    )
    brand = models.CharField("برند", max_length=100, blank=True)
    model_name = models.CharField("مدل", max_length=120, blank=True)
    serial_number = models.CharField("شماره سریال", max_length=120, blank=True, db_index=True)
    capacity = models.CharField("ظرفیت/مشخصه", max_length=120, blank=True)
    quantity = models.PositiveSmallIntegerField("تعداد", default=1)
    slot = models.CharField("محل نصب (اسلات)", max_length=80, blank=True)
    condition = models.CharField(
        "وضعیت قلم", max_length=20, choices=ITEM_CONDITION_CHOICES, default=ITEM_OK
    )
    photo = models.FileField(
        "عکس قلم",
        upload_to="hardware/items/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    notes = models.CharField("توضیحات", max_length=250, blank=True)

    objects = SnapshotItemQuerySet.as_manager()

    class Meta:
        verbose_name = "قلم سخت‌افزاری"
        verbose_name_plural = "اقلام سخت‌افزاری"
        ordering = ("component_type__sort_order", "component_type__name", "pk")

    def __str__(self) -> str:
        return self.display_label

    @property
    def display_label(self) -> str:
        parts = [self.component_type.name]
        detail = " ".join(part for part in (self.brand, self.model_name) if part)
        if detail:
            parts.append(detail)
        if self.capacity:
            parts.append(f"({self.capacity})")
        if self.quantity and self.quantity > 1:
            parts.append(f"× {self.quantity}")
        return " ".join(parts)

    @property
    def identity_key(self) -> tuple:
        """کلید شناسایی قلم برای مقایسه نسخه‌ها."""
        serial = (self.serial_number or "").strip().lower()
        if serial:
            return (self.component_type_id, serial)
        text = " ".join(
            part.strip().lower()
            for part in (self.brand, self.model_name, self.capacity)
            if part
        )
        return (self.component_type_id, f"~{text}")


class AssetAttachment(TimeStampedModel):
    """پیوست دارایی (عکس، فاکتور، سند)."""

    KIND_PHOTO = "photo"
    KIND_INVOICE = "invoice"
    KIND_DOCUMENT = "document"
    KIND_CHOICES = (
        (KIND_PHOTO, "عکس تجهیز"),
        (KIND_INVOICE, "فاکتور خرید"),
        (KIND_DOCUMENT, "سند / فرم"),
    )

    asset = models.ForeignKey(
        Asset, verbose_name="دارایی", on_delete=models.CASCADE, related_name="attachments"
    )
    kind = models.CharField("نوع", max_length=20, choices=KIND_CHOICES, default=KIND_PHOTO)
    title = models.CharField("عنوان", max_length=150, blank=True)
    file = models.FileField("فایل", upload_to="assets/%Y/%m/")
    description = models.CharField("توضیحات", max_length=250, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بارگذارنده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_asset_files",
    )

    class Meta:
        verbose_name = "پیوست دارایی"
        verbose_name_plural = "پیوست‌های دارایی"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title or self.file.name


class AgentCredential(TimeStampedModel):
    """اعتبارنامه امن و اختصاصی هر کلاینت فیزیکی HWAgent."""

    STATUS_ACTIVE = "active"
    STATUS_REVOKED = "revoked"
    STATUS_EXPIRED = "expired"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "فعال"),
        (STATUS_REVOKED, "ابطال‌شده"),
        (STATUS_EXPIRED, "منقضی"),
        (STATUS_SUSPENDED, "معلق"),
    )

    center = models.ForeignKey(
        "org.Center",
        verbose_name="مرکز خدمت متصل",
        on_delete=models.PROTECT,
        related_name="agent_credentials",
    )
    agent_uid = models.UUIDField("شناسه یکتای ایجنت", default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField("نام سیستم / کلاینت", max_length=150)
    hostname = models.CharField("نام رایانه (Hostname)", max_length=150, blank=True)
    token_prefix = models.CharField("پیشوند توکن", max_length=16, db_index=True)
    token_hash = models.CharField("هش رمزنگاری‌شده (SHA-256)", max_length=64, unique=True, db_index=True)
    status = models.CharField("وضعیت", max_length=20, default=STATUS_ACTIVE, choices=STATUS_CHOICES)
    last_sync_at = models.DateTimeField("آخرین همگام‌سازی", null=True, blank=True)
    last_ip = models.GenericIPAddressField("آخرین آدرس IP", null=True, blank=True)
    expires_at = models.DateTimeField("تاریخ انقضا", null=True, blank=True)
    revoked_at = models.DateTimeField("تاریخ ابطال", null=True, blank=True)
    revocation_reason = models.CharField("دلیل ابطال", max_length=250, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="صادرکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_agent_tokens",
    )

    class Meta:
        verbose_name = "اعتبارنامه ایجنت سخت‌افزار"
        verbose_name_plural = "اعتبارنامه‌های ایجنت‌ها"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.center.name}) [{self.get_status_display()}]"

    @classmethod
    def generate(
        cls,
        center,
        name: str,
        hostname: str = "",
        expires_in_days: int = 365,
        created_by=None,
    ) -> tuple[AgentCredential, str]:
        """تولید اعتبارنامه جدید با آنتروپی رمزنگاری‌شده بالا و ذخیره صرفاً هش در سرور."""
        raw_secret = secrets.token_urlsafe(36)
        raw_token = f"itam_agt_{raw_secret}"
        prefix = raw_token[:12]
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = timezone.now() + timezone.timedelta(days=expires_in_days) if expires_in_days else None

        cred = cls.objects.create(
            center=center,
            name=name,
            hostname=hostname,
            token_prefix=prefix,
            token_hash=token_hash,
            expires_at=expires_at,
            created_by=created_by,
        )
        return cred, raw_token

    @classmethod
    def verify_token(cls, raw_token: str) -> AgentCredential | None:
        """اعتبارسنجی توکن بدون ذخیره مقدار خام با الگوریتم Constant-Time."""
        if not raw_token or not raw_token.startswith("itam_agt_"):
            return None
        candidate_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        cred = cls.objects.filter(token_hash=candidate_hash, status=cls.STATUS_ACTIVE).first()
        if not cred:
            return None
        if not hmac.compare_digest(cred.token_hash, candidate_hash):
            return None
        if cred.expires_at and timezone.now() > cred.expires_at:
            cred.status = cls.STATUS_EXPIRED
            cred.save(update_fields=["status", "updated_at"])
            return None
        return cred

    def revoke(self, reason: str = "") -> None:
        """ابطال قطعی و فوری توکن ایجنت."""
        self.status = self.STATUS_REVOKED
        self.revoked_at = timezone.now()
        self.revocation_reason = reason
        self.save(update_fields=["status", "revoked_at", "revocation_reason", "updated_at"])

    def rotate(self, created_by=None) -> tuple[AgentCredential, str]:
        """چرخش ایمن توکن با ابطال توکن قبلی و صدور توکن جدید."""
        from django.db import transaction

        with transaction.atomic():
            self.revoke(reason="چرخش توکن (Token Rotation)")
            new_cred, raw_token = self.__class__.generate(
                center=self.center,
                name=self.name,
                hostname=self.hostname,
                created_by=created_by,
            )
            return new_cred, raw_token


class AgentNonce(TimeStampedModel):
    """نگهداری شناسه‌های یکتای درخواست جهت مقابله قطعی با حملات تکرار (Anti-Replay)."""

    agent = models.ForeignKey(AgentCredential, on_delete=models.CASCADE, related_name="nonces")
    nonce = models.CharField("شناسه یکتا", max_length=64, db_index=True)

    class Meta:
        verbose_name = "شناسه یکتای درخواست ایجنت"
        verbose_name_plural = "شناسه‌های یکتای درخواست ایجنت"
        constraints = [
            models.UniqueConstraint(fields=("agent", "nonce"), name="unique_agent_nonce")
        ]

    def __str__(self) -> str:
        return f"{self.agent.name}: {self.nonce}"


class AgentSyncAuditLog(TimeStampedModel):
    """ثبت ممیزی دقیق کلیه تلاش‌های همگام‌سازی HWAgent."""

    agent = models.ForeignKey(
        AgentCredential,
        verbose_name="اعتبارنامه ایجنت",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    center = models.ForeignKey(
        "org.Center",
        verbose_name="مرکز",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_audit_logs",
    )
    remote_ip = models.GenericIPAddressField("آدرس IP کلاینت", null=True, blank=True)
    http_status = models.PositiveSmallIntegerField("کد وضعیت HTTP", default=200)
    success = models.BooleanField("موفق", default=True)
    rejection_reason = models.CharField("علت رد / خطا", max_length=255, blank=True)
    payload_hash = models.CharField("هش SHA-256 بدنه درخواست", max_length=64, blank=True)
    execution_duration_ms = models.PositiveIntegerField("مدت اجرا (میلی‌ثانیه)", default=0)

    class Meta:
        verbose_name = "لاگ ممیزی ایجنت سخت‌افزار"
        verbose_name_plural = "لاگ‌های ممیزی ایجنت‌های سخت‌افزار"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        status_text = "موفق" if self.success else f"رد شد ({self.http_status})"
        return f"ایجنت {self.agent_id} — {status_text} در {self.created_at}"
