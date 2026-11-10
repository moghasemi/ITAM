"""فرم‌های درخواست خرابی و اقدام‌های گردش کار."""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.assets.models import Asset
from apps.core.constants import (
    FAILURE_TYPE_CHOICES,
    PAUSE_REASON_CHOICES,
    PRIORITY_CHOICES,
    STATUS_ACKNOWLEDGED,
    STATUS_IN_PROGRESS,
    STATUS_REPORTED,
    STATUS_RESOLVED,
    STATUS_USER_CONFIRMED,
    TICKET_STATUS_CHOICES,
)
from apps.core.forms import JalaliDateTimeField, StyledForm, StyledModelForm
from apps.org.models import Contract, Contractor

from .models import Ticket, TicketAttachment, TicketPart


class TicketCreateForm(StyledModelForm):
    """اعلام خرابی توسط اداره (شروع ساعت SLA)."""

    reported_at = JalaliDateTimeField(
        label="زمان اعلام خرابی", required=False,
        help_text="خالی بگذارید تا زمان فعلی ثبت شود",
    )

    class Meta:
        model = Ticket
        fields = [
            "asset", "title", "description", "priority", "failure_type",
            "reporter_name", "reporter_phone", "reported_at",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        assets = kwargs.pop("assets", None)
        super().__init__(*args, **kwargs)
        if assets is None:
            assets = Asset.objects.select_related("category")
        self.fields["asset"].queryset = assets
        self.fields["asset"].label_from_instance = lambda obj: f"{obj.asset_tag} — {obj.display_name}"
        self.fields["asset"].empty_label = "— انتخاب تجهیز —"
        if self.user is not None and not self.user.is_admin_it:
            self.fields["reporter_name"].initial = self.user.display_name
            self.fields["reporter_phone"].initial = self.user.phone

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get("asset")
        if asset and asset.status in ("retired",):
            self.add_error("asset", "این تجهیز از رده خارج شده است.")
        description = cleaned.get("description")
        if not description or len(description.strip()) < 5:
            self.add_error("description", "شرح خرابی را کامل‌تر بنویسید.")
        return cleaned

    def save(self, commit=True):
        ticket = super().save(commit=False)
        if not ticket.reported_at:
            from django.utils import timezone

            ticket.reported_at = timezone.now()
        if self.user is not None and self.user.is_authenticated and not ticket.reported_by_id:
            ticket.reported_by = self.user
            if not ticket.reporter_name:
                ticket.reporter_name = self.user.display_name
            if not ticket.reporter_phone:
                ticket.reporter_phone = self.user.phone
        if commit:
            ticket.save()
        return ticket


class TicketFilterForm(StyledForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not user or not getattr(user, "is_authenticated", False):
            self.fields["contract"].queryset = Contract.objects.none()
            self.fields["contractor"].queryset = Contractor.objects.none()
        elif user.is_admin_country:
            pass
        else:
            province_ids = user.get_scoped_centers().values("parent_unit__parent_id")
            contracts = Contract.objects.filter(province_id__in=province_ids).distinct()
            self.fields["contract"].queryset = contracts
            self.fields["contractor"].queryset = Contractor.objects.filter(
                pk__in=contracts.values("contractor_id")
            )

    q = forms.CharField(label="جستجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت", required=False, choices=[("", "همه")] + list(TICKET_STATUS_CHOICES)
    )
    priority = forms.ChoiceField(
        label="اولویت", required=False, choices=[("", "همه")] + list(PRIORITY_CHOICES)
    )
    failure_type = forms.ChoiceField(
        label="نوع خرابی", required=False, choices=[("", "همه")] + list(FAILURE_TYPE_CHOICES)
    )
    contract = forms.ModelChoiceField(
        label="قرارداد", required=False, queryset=Contract.objects.select_related("contractor")
    )
    contractor = forms.ModelChoiceField(
        label="پیمانکار", required=False, queryset=Contractor.objects.all()
    )
    sla = forms.ChoiceField(
        label="وضعیت SLA",
        required=False,
        choices=(
            ("", "همه"),
            ("breached", "نقض‌شده"),
            ("met", "رعایت‌شده"),
            ("open", "در جریان"),
        ),
    )
    date_from = forms.DateField(label="از تاریخ", required=False, widget=forms.HiddenInput)
    date_to = forms.DateField(label="تا تاریخ", required=False, widget=forms.HiddenInput)
    open_only = forms.BooleanField(label="فقط درخواست‌های باز", required=False)


class AcknowledgeForm(StyledForm):
    note = forms.CharField(
        label="یادداشت پذیرش", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class ArriveForm(StyledForm):
    note = forms.CharField(
        label="توضیح حضور", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    parts_wait = forms.BooleanField(
        label="پس از حضور، ساعت SLA به دلیل انتظار قطعه متوقف شود", required=False
    )


class ResolveForm(StyledForm):
    root_cause = forms.CharField(
        label="علت خرابی", required=True, widget=forms.Textarea(attrs={"rows": 2})
    )
    action_taken = forms.CharField(
        label="اقدام انجام‌شده", required=True, widget=forms.Textarea(attrs={"rows": 3})
    )
    parts_text = forms.CharField(label="قطعات مصرف/تعویض‌شده", required=False, max_length=300)
    note = forms.CharField(
        label="توضیح تکمیلی", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class UserConfirmForm(StyledForm):
    note = forms.CharField(
        label="یادداشت تایید", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    satisfaction = forms.ChoiceField(
        label="میزان رضایت از خدمات",
        required=False,
        choices=(
            ("5", "بسیار خوب"),
            ("4", "خوب"),
            ("3", "متوسط"),
            ("2", "ضعیف"),
            ("1", "بسیار ضعیف"),
        ),
    )


class UserRejectForm(StyledForm):
    reason = forms.CharField(
        label="دلیل عدم تایید", required=True, widget=forms.Textarea(attrs={"rows": 3})
    )


class ItConfirmForm(StyledForm):
    note = forms.CharField(
        label="یادداشت کارشناس فناوری اطلاعات", required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class PauseForm(StyledForm):
    reason = forms.ChoiceField(label="دلیل توقف", choices=PAUSE_REASON_CHOICES)
    note = forms.CharField(
        label="توضیحات", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class ResumeForm(StyledForm):
    note = forms.CharField(
        label="توضیحات ادامه کار", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class CancelForm(StyledForm):
    reason = forms.CharField(
        label="دلیل لغو / رد", required=True, widget=forms.Textarea(attrs={"rows": 2})
    )


class TicketPartForm(StyledModelForm):
    class Meta:
        model = TicketPart
        fields = ["component_type", "name", "action", "old_serial", "new_serial", "quantity", "unit_price", "notes"]


TicketPartFormSet = inlineformset_factory(
    Ticket, TicketPart, form=TicketPartForm, extra=2, can_delete=True
)


class TicketAttachmentForm(StyledModelForm):
    class Meta:
        model = TicketAttachment
        fields = ["kind", "title", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update({"accept": "image/*,.pdf,.doc,.docx"})


class TicketNoteForm(StyledForm):
    """افزودن یادداشت به گردش کار درخواست."""

    note = forms.CharField(
        label="یادداشت", required=True, widget=forms.Textarea(attrs={"rows": 3})
    )
