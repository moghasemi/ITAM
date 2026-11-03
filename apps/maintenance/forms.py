"""فرم‌های بازدید دوره‌ای."""
from __future__ import annotations

from django import forms

from apps.assets.models import Asset
from apps.core.constants import CHECK_CONDITION_CHOICES, VISIT_STATUS_CHOICES
from apps.core.forms import JalaliDateField, StyledForm, StyledModelForm
from apps.org.models import Contract, Contractor

from .models import MaintenanceVisit, VisitAssetCheck


class VisitFilterForm(StyledForm):
    q = forms.CharField(label="جستجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت", required=False, choices=[("", "همه")] + list(VISIT_STATUS_CHOICES)
    )
    contract = forms.ModelChoiceField(
        label="قرارداد", required=False, queryset=Contract.objects.select_related("contractor")
    )
    contractor = forms.ModelChoiceField(
        label="پیمانکار", required=False, queryset=Contractor.objects.all()
    )
    date_from = JalaliDateField(label="از تاریخ", required=False)
    date_to = JalaliDateField(label="تا تاریخ", required=False)
    overdue_only = forms.BooleanField(label="فقط بازدیدهای خارج از مهلت", required=False)


class VisitForm(StyledModelForm):
    """ثبت/ویرایش نوبت بازدید."""

    scheduled_date = JalaliDateField(label="تاریخ برنامه‌ریزی‌شده")
    scheduled_end_date = JalaliDateField(label="آخرین مهلت انجام", required=False)

    class Meta:
        model = MaintenanceVisit
        fields = [
            "contract", "sequence_number", "period_label",
            "scheduled_date", "scheduled_end_date", "technician", "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contract"].queryset = Contract.objects.select_related("contractor").order_by("-start_date")


class VisitCheckForm(StyledModelForm):
    """ثبت نتیجه بازدید یک تجهیز."""

    next_due_date = JalaliDateField(label="تاریخ بازدید بعدی", required=False)

    class Meta:
        model = VisitAssetCheck
        fields = [
            "checked", "condition", "actions_taken", "parts_replaced",
            "next_due_date", "photo", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].widget.attrs.update({"accept": "image/*"})
        self.fields["condition"].choices = CHECK_CONDITION_CHOICES


class VisitCompleteForm(StyledForm):
    report_text = forms.CharField(
        label="گزارش بازدید", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    recommendation = forms.CharField(
        label="پیشنهادها و موارد نیازمند اقدام", required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    force = forms.BooleanField(
        label="پایان بازدید با برگه‌های تکمیل‌نشده", required=False
    )


class VisitConfirmForm(StyledForm):
    note = forms.CharField(
        label="یادداشت تایید", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class VisitCheckFilterForm(StyledForm):
    status = forms.ChoiceField(
        label="وضعیت بازدید",
        required=False,
        choices=(
            ("", "همه"),
            ("done", "بازدیدشده"),
            ("pending", "بازدید نشده"),
            ("faulty", "دارای ایراد"),
        ),
    )


class VisitAssetQuickForm(StyledForm):
    """افزودن تجهیز به فهرست بازدید."""

    asset = forms.ModelChoiceField(label="تجهیز", queryset=Asset.objects.all())
