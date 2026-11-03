"""مدل‌های دارایی، اقلام سخت‌افزاری و اسنپ‌شات ضدسرقت."""
from __future__ import annotations

import uuid

from django.conf import settings
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
        self.technician_confirmed_by = user
        self.technician_confirmed_at = timezone.now()
        self.save(update_fields=["technician_confirmed_by", "technician_confirmed_at", "updated_at"])

    def submit_for_review(self, user):
        self.status = SNAPSHOT_PENDING
        if not self.recorded_at:
            self.recorded_at = timezone.now()
        if not self.recorded_by_id:
            self.recorded_by = user
        self.save(
            update_fields=["status", "recorded_at", "recorded_by", "updated_at"]
        )

    def lock(self, user):
        from apps.core.models import SystemSetting

        setting = SystemSetting.load()
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
