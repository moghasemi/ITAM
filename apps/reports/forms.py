"""فیلترهای گزارش‌گیری."""
from __future__ import annotations

from django import forms

from apps.core.constants import FAILURE_TYPE_CHOICES, PRIORITY_CHOICES, TICKET_STATUS_CHOICES
from apps.core.forms import JalaliDateField, StyledForm
from apps.org.models import Contract, Contractor, Department


class ReportFilterForm(StyledForm):
    """فیلتر مشترک گزارش‌ها."""

    contract = forms.ModelChoiceField(
        label="قرارداد", required=False, queryset=Contract.objects.select_related("contractor")
    )
    contractor = forms.ModelChoiceField(
        label="پیمانکار", required=False, queryset=Contractor.objects.all()
    )
    department = forms.ModelChoiceField(
        label="واحد سازمانی", required=False, queryset=Department.objects.all()
    )
    priority = forms.ChoiceField(
        label="اولویت", required=False, choices=[("", "همه")] + list(PRIORITY_CHOICES)
    )
    status = forms.ChoiceField(
        label="وضعیت درخواست", required=False, choices=[("", "همه")] + list(TICKET_STATUS_CHOICES)
    )
    failure_type = forms.ChoiceField(
        label="نوع خرابی", required=False, choices=[("", "همه")] + list(FAILURE_TYPE_CHOICES)
    )
    date_from = JalaliDateField(label="از تاریخ", required=False)
    date_to = JalaliDateField(label="تا تاریخ", required=False)
    open_only = forms.BooleanField(label="فقط درخواست‌های باز", required=False)


def filter_tickets(queryset, data: dict):
    """اعمال فیلتر گزارش روی مجموعه درخواست‌ها."""
    if data.get("contract"):
        queryset = queryset.filter(contract=data["contract"])
    if data.get("contractor"):
        queryset = queryset.filter(assigned_contractor=data["contractor"])
    if data.get("department"):
        queryset = queryset.filter(asset__department=data["department"])
    if data.get("priority"):
        queryset = queryset.filter(priority=data["priority"])
    if data.get("status"):
        queryset = queryset.filter(status=data["status"])
    if data.get("failure_type"):
        queryset = queryset.filter(failure_type=data["failure_type"])
    if data.get("date_from"):
        queryset = queryset.filter(reported_at__date__gte=data["date_from"])
    if data.get("date_to"):
        queryset = queryset.filter(reported_at__date__lte=data["date_to"])
    if data.get("open_only"):
        from apps.core.constants import TICKET_OPEN_STATUSES

        queryset = queryset.filter(status__in=TICKET_OPEN_STATUSES)
    return queryset
