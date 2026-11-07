"""فرم‌های دارایی، اسنپ‌شات سخت‌افزاری و پیوست‌ها."""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory
from django.db.models import Q

from apps.core.forms import JalaliDateField, StyledForm, StyledModelForm
from apps.core.constants import ASSET_STATUS_CHOICES
from apps.org.models import Center, Contract, Department, Location

from .models import Asset, AssetAttachment, AssetCategory, AssetRelationship, ComponentType, HardwareSnapshot, SnapshotItem


class AssetForm(StyledModelForm):
    """ثبت و ویرایش دارایی با شماره اموال و مشخصات کامل."""

    purchase_date = JalaliDateField(label="تاریخ خرید", required=False)
    warranty_until = JalaliDateField(label="پایان گارانتی", required=False)
    connected_computers = forms.ModelMultipleChoiceField(
        label="رایانه‌های متصل", required=False, queryset=Asset.objects.none(),
        help_text="برای چاپگرها و تجهیزات جانبی؛ فقط رایانه‌های ثبت‌شده در همان مرکز قابل انتخاب‌اند.",
        widget=forms.SelectMultiple(attrs={"size": 5}),
    )
    connection_type = forms.ChoiceField(
        label="روش اتصال", required=False,
        choices=(("", "— انتخاب روش اتصال —"),) + AssetRelationship.CONNECTION_TYPE_CHOICES,
    )

    class Meta:
        model = Asset
        fields = [
            "asset_tag", "title", "category", "brand", "model_name", "serial_number",
            "center", "contract", "department", "location", "custodian", "status",
            "hostname", "ip_address", "mac_address", "os_name", "office_software",
            "connected_computers", "connection_type",
            "spec_summary", "purchase_date", "warranty_until", "price", "supplier", "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        scoped_centers = (
            self.user.get_scoped_centers()
            if self.user and getattr(self.user, "is_authenticated", False)
            else Center.objects.none()
        )
        self.fields["center"].queryset = scoped_centers.filter(is_active=True)
        self.fields["center"].empty_label = "— انتخاب مرکز —"

        selected_center_id = self.instance.center_id if self.instance.pk else None
        if self.is_bound:
            raw_center_id = self.data.get(self.add_prefix("center"))
            if raw_center_id:
                try:
                    selected_center_id = int(raw_center_id)
                except (TypeError, ValueError):
                    selected_center_id = None
        elif self.user and getattr(self.user, "center_id", None):
            selected_center_id = self.user.center_id
            self.fields["center"].initial = self.user.center
        if self.user and getattr(self.user, "center_id", None) and self.user.has_role("admin_it", "manager"):
            self.fields["center"].required = True

        self.fields["category"].queryset = AssetCategory.objects.filter(is_active=True)
        self.fields["contract"].queryset = Contract.objects.filter(
            Q(centers__in=scoped_centers) | Q(is_provincial=True)
        ).select_related("contractor").distinct().order_by("-start_date")
        self.fields["department"].queryset = Department.objects.filter(center__in=scoped_centers, is_active=True)
        self.fields["location"].queryset = Location.objects.filter(center__in=scoped_centers, is_active=True)
        if selected_center_id:
            self.fields["department"].queryset = self.fields["department"].queryset.filter(center_id=selected_center_id)
            self.fields["location"].queryset = self.fields["location"].queryset.filter(center_id=selected_center_id)
            self.fields["contract"].queryset = self.fields["contract"].queryset.filter(
                Q(centers__pk=selected_center_id) | Q(is_provincial=True)
            ).distinct()

        self.fields["custodian"].queryset = self.fields["custodian"].queryset.filter(
            is_active=True, center__in=scoped_centers
        ).order_by("last_name", "first_name")
        self.fields["custodian"].label_from_instance = lambda obj: obj.display_name
        self.fields["contract"].empty_label = "— بدون قرارداد —"
        self.fields["custodian"].empty_label = "— بدون امانت‌دار —"

        computer_assets = Asset.objects.filter(
            center__in=scoped_centers, category__is_computing_device=True
        ).select_related("category", "center").exclude(pk=self.instance.pk)
        if selected_center_id:
            computer_assets = computer_assets.filter(center_id=selected_center_id)
        if self.instance.pk and self.instance.category.is_computing_device:
            computer_assets = Asset.objects.none()
        self.fields["connected_computers"].queryset = computer_assets.order_by("asset_tag")
        if self.instance.pk:
            self.fields["connected_computers"].initial = self.instance.outgoing_relationships.filter(
                relationship_type=AssetRelationship.RELATION_CONNECTED_TO,
                is_active=True,
            ).values_list("related_asset_id", flat=True)

        computing_ids = list(AssetCategory.objects.filter(
            is_active=True, is_computing_device=True
        ).values_list("pk", flat=True))
        self.fields["category"].widget.attrs["data-computing-category-ids"] = ",".join(map(str, computing_ids))
        for field_name in ("hostname", "os_name", "office_software"):
            self.fields[field_name].widget.attrs["data-computer-only"] = "true"
        self.fields["connected_computers"].widget.attrs["data-peripheral-only"] = "true"
        self.fields["connection_type"].widget.attrs["data-peripheral-only"] = "true"

    def clean(self):
        cleaned = super().clean()
        center = cleaned.get("center")
        category = cleaned.get("category")
        for field_name in ("department", "location"):
            related = cleaned.get(field_name)
            if related and center and related.center_id != center.pk:
                self.add_error(field_name, "این گزینه باید متعلق به مرکز انتخاب‌شده باشد.")
        contract = cleaned.get("contract")
        if contract and center and not contract.is_provincial and not contract.centers.filter(pk=center.pk).exists():
            self.add_error("contract", "قرارداد انتخاب‌شده به مرکز انتخاب‌شده تعلق ندارد.")
        custodian = cleaned.get("custodian")
        if custodian and center and custodian.center_id != center.pk:
            self.add_error("custodian", "امانت‌دار باید از کاربران همان مرکز باشد.")
        computers = cleaned.get("connected_computers")
        if category and category.is_computing_device and computers:
            self.add_error("connected_computers", "برای خود رایانه، انتخاب رایانه متصل در این فرم مجاز نیست.")
        elif computers and center and any(item.center_id != center.pk for item in computers):
            self.add_error("connected_computers", "رایانه‌های مرتبط باید متعلق به همان مرکز باشند.")
        if category and not category.is_computing_device:
            for field_name in ("hostname", "os_name", "office_software"):
                cleaned[field_name] = getattr(self.instance, field_name, "") or ""
        return cleaned

    def clean_asset_tag(self):
        value = (self.cleaned_data.get("asset_tag") or "").strip()
        if not value:
            raise forms.ValidationError("شماره اموال الزامی است.")
        return value


class AssetFilterForm(StyledForm):
    """پالایه فهرست دارایی‌ها با گزینه‌های محدود به دامنه مجاز کاربر."""

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        scoped = (
            user.get_scoped_centers()
            if user and getattr(user, "is_authenticated", False)
            else Center.objects.none()
        )
        self.fields["center"].queryset = scoped
        self.fields["department"].queryset = Department.objects.filter(center__in=scoped)
        self.fields["location"].queryset = Location.objects.filter(center__in=scoped)
        self.fields["contract"].queryset = Contract.objects.filter(
            Q(centers__in=scoped) | Q(is_provincial=True)
        ).distinct()

    q = forms.CharField(label="جستجو", required=False)
    center = forms.ModelChoiceField(label="مرکز", required=False, queryset=Center.objects.all())
    category = forms.ModelChoiceField(label="گونه", required=False, queryset=AssetCategory.objects.all())
    department = forms.ModelChoiceField(label="واحد", required=False, queryset=Department.objects.all())
    location = forms.ModelChoiceField(label="محل", required=False, queryset=Location.objects.all())
    contract = forms.ModelChoiceField(
        label="قرارداد", required=False, queryset=Contract.objects.select_related("contractor")
    )
    status = forms.ChoiceField(label="وضعیت", required=False, choices=[("", "همه")] + list(ASSET_STATUS_CHOICES))
    tracking = forms.ChoiceField(
        label="کنترل اقلام",
        required=False,
        choices=(
            ("", "همه"),
            ("with", "دارای اقلام ثبت‌شده"),
            ("without", "بدون اقلام ثبت‌شده"),
        ),
    )
    ordering = forms.ChoiceField(
        label="ترتیب",
        required=False,
        choices=(
            ("asset_tag", "شماره اموال"),
            ("-created_at", "تازه‌ترین"),
            ("department", "واحد سازمانی"),
            ("-open_tickets", "بیشترین خرابی"),
        ),
    )


class HardwareSnapshotForm(StyledModelForm):
    """اطلاعات کلی اسنپ‌شات."""

    class Meta:
        model = HardwareSnapshot
        fields = ["seal_number", "note", "case_photo", "seal_photo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["case_photo"].widget.attrs.update({"accept": "image/*"})
        self.fields["seal_photo"].widget.attrs.update({"accept": "image/*"})
        self.fields["case_photo"].help_text = "تصویر تجهیز در حالت باز، برای مستندسازی"
        self.fields["seal_photo"].help_text = "تصویر پلمب یا برچسب امنیتی نصب‌شده"


class SnapshotItemForm(StyledModelForm):
    """یک قلم سخت‌افزاری داخل کیس."""

    class Meta:
        model = SnapshotItem
        fields = [
            "component_type", "brand", "model_name", "serial_number",
            "capacity", "quantity", "slot", "condition", "photo", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["component_type"].queryset = ComponentType.objects.filter(is_active=True)
        self.fields["component_type"].empty_label = "— انتخاب قطعه —"
        self.fields["photo"].widget.attrs.update({"accept": "image/*"})

    def clean(self):
        cleaned = super().clean()
        component_type = cleaned.get("component_type")
        serial = (cleaned.get("serial_number") or "").strip()
        if component_type and component_type.is_serialized and not serial:
            self.add_error("serial_number", "برای این قطعه ثبت شماره سریال الزامی است.")
        return cleaned


SnapshotItemFormSet = inlineformset_factory(
    HardwareSnapshot,
    SnapshotItem,
    form=SnapshotItemForm,
    extra=4,
    can_delete=True,
)


class AssetAttachmentForm(StyledModelForm):
    class Meta:
        model = AssetAttachment
        fields = ["kind", "title", "file", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update({"accept": "image/*,.pdf,.doc,.docx,.xls,.xlsx"})


class AssetComponentForm(StyledModelForm):
    """افزودن سریع قلم به اسنپ‌شات جاری."""

    class Meta:
        model = SnapshotItem
        fields = [
            "component_type", "brand", "model_name", "serial_number",
            "capacity", "quantity", "slot", "condition", "notes",
        ]


class CategoryForm(StyledModelForm):
    class Meta:
        model = AssetCategory
        fields = [
            "name", "code", "icon", "requires_component_tracking", "is_computing_device", "is_portable",
            "is_active", "description",
        ]


class ComponentTypeForm(StyledModelForm):
    class Meta:
        model = ComponentType
        fields = [
            "name", "code", "is_serialized", "unit", "sort_order",
            "is_key_item", "is_active", "description",
        ]
