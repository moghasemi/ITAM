"""فرم‌های دارایی، اسنپ‌شات سخت‌افزاری و پیوست‌ها."""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import JalaliDateField, StyledForm, StyledModelForm
from apps.core.constants import ASSET_STATUS_CHOICES
from apps.org.models import Contract, Department, Location

from .models import Asset, AssetAttachment, AssetCategory, ComponentType, HardwareSnapshot, SnapshotItem


class AssetForm(StyledModelForm):
    """ثبت و ویرایش دارایی با شماره اموال و مشخصات کامل."""

    purchase_date = JalaliDateField(label="تاریخ خرید", required=False)
    warranty_until = JalaliDateField(label="پایان گارانتی", required=False)

    class Meta:
        model = Asset
        fields = [
            "asset_tag", "title", "category", "brand", "model_name", "serial_number",
            "contract", "department", "location", "custodian", "status",
            "hostname", "ip_address", "mac_address", "os_name", "office_software",
            "spec_summary", "purchase_date", "warranty_until", "price", "supplier", "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = AssetCategory.objects.filter(is_active=True)
        self.fields["contract"].queryset = Contract.objects.select_related("contractor").order_by("-start_date")
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["location"].queryset = Location.objects.filter(is_active=True)
        self.fields["custodian"].queryset = (
            self.fields["custodian"].queryset.filter(is_active=True).order_by("last_name", "first_name")
        )
        self.fields["custodian"].label_from_instance = lambda obj: obj.display_name
        self.fields["contract"].empty_label = "— بدون قرارداد —"
        self.fields["custodian"].empty_label = "— بدون امانت‌دار —"

    def clean_asset_tag(self):
        value = (self.cleaned_data.get("asset_tag") or "").strip()
        if not value:
            raise forms.ValidationError("شماره اموال الزامی است.")
        return value


class AssetFilterForm(StyledForm):
    """پالایه فهرست دارایی‌ها."""

    q = forms.CharField(label="جستجو", required=False)
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
            "name", "code", "icon", "requires_component_tracking", "is_portable",
            "is_active", "description",
        ]


class ComponentTypeForm(StyledModelForm):
    class Meta:
        model = ComponentType
        fields = [
            "name", "code", "is_serialized", "unit", "sort_order",
            "is_key_item", "is_active", "description",
        ]
