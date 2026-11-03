"""فرم‌های ساختار سازمانی، پیمانکار و قرارداد."""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import JalaliDateField, StyledModelForm

from .models import Contract, Contractor, Department, Location, SlaPolicy


class DepartmentForm(StyledModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "manager_name", "phone", "is_active", "description"]


class LocationForm(StyledModelForm):
    class Meta:
        model = Location
        fields = ["name", "building", "floor", "room", "code", "is_active", "description"]


class ContractorForm(StyledModelForm):
    class Meta:
        model = Contractor
        fields = [
            "name", "code", "national_id", "economic_code", "contact_person",
            "contact_phone", "phone", "email", "is_active", "address", "notes",
        ]


class ContractForm(StyledModelForm):
    start_date = JalaliDateField(label="تاریخ شروع")
    end_date = JalaliDateField(label="تاریخ پایان")

    class Meta:
        model = Contract
        fields = [
            "contractor", "number", "title", "start_date", "end_date",
            "visit_interval_days", "status", "visit_scope", "repair_scope", "notes",
        ]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError({"end_date": "تاریخ پایان باید بعد از تاریخ شروع باشد."})
        return cleaned


class SlaPolicyForm(StyledModelForm):
    class Meta:
        model = SlaPolicy
        fields = [
            "priority", "response_minutes", "resolve_minutes", "pause_on_parts_wait", "description",
        ]


SlaPolicyFormSet = inlineformset_factory(
    Contract,
    SlaPolicy,
    form=SlaPolicyForm,
    extra=3,
    can_delete=True,
    validate_max=False,
)


class ContractFilterForm(forms.Form):
    """پالایه فهرست قراردادها."""

    q = forms.CharField(label="جستجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت", required=False, choices=[("", "همه")] + list(Contract.STATUS_CHOICES)
    )
    contractor = forms.ModelChoiceField(
        label="پیمانکار", required=False, queryset=Contractor.objects.all()
    )
