"""فرم‌های پایه: فیلد تاریخ شمسی، ویجت‌ها و ظاهر یکدست."""
from __future__ import annotations

import datetime as dt

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import jalali
from .utils import log_action

TEXT_WIDGETS = (
    forms.TextInput,
    forms.NumberInput,
    forms.EmailInput,
    forms.URLInput,
    forms.PasswordInput,
    forms.DateInput,
    forms.DateTimeInput,
    forms.TimeInput,
)
SELECT_WIDGETS = (forms.Select, forms.SelectMultiple)


class JalaliDateInput(forms.TextInput):
    """ورودی تاریخ شمسی."""

    def __init__(self, attrs=None):
        default_attrs = {
            "class": "input jalali-date",
            "placeholder": "۱۴۰۳/۰۵/۱۲",
            "autocomplete": "off",
            "inputmode": "numeric",
            "dir": "ltr",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class JalaliDateTimeInput(forms.TextInput):
    """ورودی تاریخ و ساعت شمسی."""

    def __init__(self, attrs=None):
        default_attrs = {
            "class": "input jalali-datetime",
            "placeholder": "۱۴۰۳/۰۵/۱۲ ۰۸:۳۰",
            "autocomplete": "off",
            "dir": "ltr",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class JalaliDateField(forms.DateField):
    """فیلد تاریخ که ورودی شمسی می‌گیرد و تاریخ میلادی ذخیره می‌کند."""

    widget = JalaliDateInput

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        try:
            return jalali.parse_jalali(value)
        except ValueError as exc:
            raise ValidationError(str(exc))

    def prepare_value(self, value):
        if isinstance(value, dt.datetime):
            value = value.date()
        if isinstance(value, dt.date):
            return jalali.format_jalali(value, "Y/m/d")
        return value


class JalaliDateTimeField(forms.DateTimeField):
    """فیلد تاریخ و ساعت شمسی."""

    widget = JalaliDateTimeInput

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, dt.datetime):
            return value if timezone.is_aware(value) else timezone.make_aware(value)
        try:
            return jalali.parse_jalali_datetime(value)
        except ValueError as exc:
            raise ValidationError(str(exc))

    def prepare_value(self, value):
        if isinstance(value, dt.datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return jalali.format_jalali(value, "Y/m/d H:M")
        return value


def apply_widget_classes(form) -> None:
    """افزودن کلاس‌های ظاهری به همه ویجت‌های فرم."""
    for field in form.fields.values():
        widget = field.widget
        existing = widget.attrs.get("class", "")
        if isinstance(widget, forms.CheckboxInput):
            css = "checkbox"
        elif isinstance(widget, SELECT_WIDGETS):
            css = "select"
        elif isinstance(widget, forms.Textarea):
            css = "textarea"
        elif isinstance(widget, forms.ClearableFileInput):
            css = "file"
        elif isinstance(widget, TEXT_WIDGETS):
            css = "input"
        else:
            css = "input"
        if "jalali" in existing:
            css = ""
        widget.attrs["class"] = f"{existing} {css}".strip()
        if isinstance(widget, forms.Textarea) and "rows" not in widget.attrs:
            widget.attrs["rows"] = 3
        if field.required:
            widget.attrs.setdefault("required", "required")


class StyledFormMixin:
    """ظاهر یکدست و ثبت خودکار خطاها."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_widget_classes(self)


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass


class StyledForm(StyledFormMixin, forms.Form):
    pass


class SearchForm(StyledForm):
    """فرم جستجوی عمومی."""

    q = forms.CharField(
        label="جستجو",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "شماره اموال، سریال، عنوان…"}),
    )

    def clean_q(self):
        return (self.cleaned_data.get("q") or "").strip()


class DateRangeForm(StyledForm):
    """بازه تاریخ شمسی برای گزارش‌ها."""

    date_from = JalaliDateField(label="از تاریخ", required=False)
    date_to = JalaliDateField(label="تا تاریخ", required=False)

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise ValidationError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
        return cleaned


def save_with_audit(form, *, user, action="update", note=""):
    """ذخیره فرم همراه با ثبت در لاگ ممیزی."""
    obj = form.save()
    log_action(action, obj, note=note, user=user)
    return obj


class SystemSettingForm(StyledModelForm):
    """تنظیمات سراسری سامانه."""

    class Meta:
        from .models import SystemSetting

        model = SystemSetting
        fields = [
            "org_name", "site_name", "public_base_url", "counting_mode",
            "work_start", "work_end", "work_days", "exclude_holidays",
            "default_response_minutes", "default_resolve_minutes",
            "pause_clock_on_parts_wait", "require_user_confirmation",
            "require_it_confirmation", "baseline_requires_it_confirm",
            "hardware_diff_alerts", "logo", "footer_note",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["work_days"].help_text = (
            "روزهای کاری هفته به‌صورت فهرست شماره روز؛ پیش‌فرض [5, 6, 0, 1, 2] "
            "یعنی شنبه تا چهارشنبه (شنبه=۵، یک‌شنبه=۶، دوشنبه=۰ …)"
        )
        self.fields["work_start"].widget.attrs.update({"type": "time"})
        self.fields["work_end"].widget.attrs.update({"type": "time"})
        self.fields["logo"].widget.attrs.update({"accept": "image/*"})

    def clean_work_days(self):
        value = self.cleaned_data.get("work_days")
        if isinstance(value, str):
            import json

            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValidationError("قالب روزهای کاری نامعتبر است؛ نمونه: [5, 6, 0, 1, 2]")
        if not isinstance(value, list):
            raise ValidationError("روزهای کاری باید فهرست باشند.")
        return [int(day) for day in value]


class HolidayForm(StyledModelForm):
    date = JalaliDateField(label="تاریخ")

    class Meta:
        from .models import Holiday

        model = Holiday
        fields = ["title", "date", "is_recurring_annual", "is_active", "note"]
