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
