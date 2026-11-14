"""فرم‌های یکپارچه‌سازی و صف رخدادها."""
from __future__ import annotations

from django import forms

from apps.core.constants import EVENT_TYPE_CHOICES
from apps.core.forms import JalaliDateField, StyledForm, StyledModelForm

from .models import OutboxEvent, WebhookEndpoint


class WebhookEndpointForm(StyledModelForm):
    class Meta:
        model = WebhookEndpoint
        fields = [
            "name", "url", "method", "auth_type", "token", "secret",
            "extra_headers", "event_filter", "is_active", "timeout_seconds", "max_attempts",
        ]
        widgets = {
            "token": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
            "secret": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("token", "secret"):
            self.fields[name].required = False
            self.fields[name].help_text = (
                "برای حفظ محرمانگی مقدار فعلی نمایش داده نمی‌شود؛ "
                "برای جایگزینی، مقدار جدید وارد کنید."
                if self.instance.pk
                else "مقدار محرمانه فقط هنگام ذخیره دریافت می‌شود."
            )

    def clean_token(self):
        value = (self.cleaned_data.get("token") or "").strip()
        return value or (self.instance.token if self.instance.pk else "")

    def clean_secret(self):
        value = (self.cleaned_data.get("secret") or "").strip()
        return value or (self.instance.secret if self.instance.pk else "")

    def clean(self):
        cleaned = super().clean()
        auth_type = cleaned.get("auth_type")
        if auth_type == WebhookEndpoint.AUTH_TOKEN and not cleaned.get("token"):
            self.add_error("token", "برای احراز هویت توکنی، توکن الزامی است.")
        if auth_type == WebhookEndpoint.AUTH_HMAC and not cleaned.get("secret"):
            self.add_error("secret", "برای امضای HMAC، کلید محرمانه الزامی است.")
        return cleaned

    def clean_extra_headers(self):
        value = self.cleaned_data.get("extra_headers") or {}
        if not isinstance(value, dict):
            raise forms.ValidationError("سرآیندها باید به‌صورت شیء JSON باشند.")
        return value

    def clean_url(self):
        url = (self.cleaned_data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise forms.ValidationError("نشانی باید با http:// یا https:// آغاز شود.")
        return url


class EventFilterForm(StyledForm):
    q = forms.CharField(label="جستجو در داده رخداد", required=False)
    event_type = forms.ChoiceField(
        label="نوع رخداد", required=False, choices=[("", "همه")] + list(EVENT_TYPE_CHOICES)
    )
    status = forms.ChoiceField(
        label="وضعیت ارسال", required=False, choices=[("", "همه")] + list(OutboxEvent.STATUS_CHOICES)
    )
    aggregate_type = forms.ChoiceField(
        label="موجودیت",
        required=False,
        choices=(
            ("", "همه"),
            ("Ticket", "درخواست خرابی"),
            ("Asset", "دارایی"),
            ("HardwareSnapshot", "اسنپ‌شات سخت‌افزار"),
            ("MaintenanceVisit", "بازدید دوره‌ای"),
        ),
    )
    date_from = JalaliDateField(label="از تاریخ", required=False)
    date_to = JalaliDateField(label="تا تاریخ", required=False)
