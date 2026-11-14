"""Forms for the ITAM repair, referral and general request workflows."""
from __future__ import annotations

from django import forms
from django.db.models import Q

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.core.forms import StyledForm, StyledModelForm
from apps.org.models import Center, OrganizationalUnit

from .repair_models import (
    GeneralITRequest, GeneralReferral, IndependentRepairer, RepairFeedback,
    RepairFeedbackReply, RepairRequest,
)


RATING_CHOICES = [(value, str(value)) for value in range(1, 6)]


class IndependentRepairerForm(StyledModelForm):
    class Meta:
        model = IndependentRepairer
        fields = [
            "province", "kind", "name", "national_id", "phone", "email",
            "address", "specialties", "notes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not user:
            self.fields["province"].queryset = OrganizationalUnit.objects.none()
            return
        if user.is_admin_country:
            self.fields["province"].queryset = OrganizationalUnit.objects.filter(
                unit_type=OrganizationalUnit.UNIT_PROVINCE
            )
        else:
            province_id = user.org_unit_id if user.is_admin_province else (
                user.center.treatment_management.province_id
                if user.center_id and user.center.treatment_management_id else None
            )
            self.fields["province"].queryset = OrganizationalUnit.objects.filter(pk=province_id)
            self.fields["province"].initial = province_id
            self.fields["province"].disabled = True


class RepairRequestForm(StyledModelForm):
    class Meta:
        model = RepairRequest
        fields = [
            "center", "asset", "repairer", "fault_description",
            "referral_reason", "estimate_amount", "estimate_attachment",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not user:
            self.fields["center"].queryset = Center.objects.none()
            self.fields["asset"].queryset = Asset.objects.none()
            self.fields["repairer"].queryset = IndependentRepairer.objects.none()
            return
        centers = user.get_scoped_centers()
        self.fields["center"].queryset = centers
        self.fields["asset"].queryset = Asset.objects.filter(center__in=centers).select_related("center")
        province_ids = centers.values("treatment_management__province_id")
        self.fields["repairer"].queryset = IndependentRepairer.objects.filter(
            province_id__in=province_ids, is_active=True
        ).distinct()

    def clean(self):
        cleaned = super().clean()
        center = cleaned.get("center")
        asset = cleaned.get("asset")
        repairer = cleaned.get("repairer")
        if center and asset and asset.center_id != center.pk:
            self.add_error("asset", "دارایی باید متعلق به مرکز انتخاب‌شده باشد.")
        if center and repairer and center.treatment_management_id:
            if repairer.province_id != center.treatment_management.province_id:
                self.add_error("repairer", "تعمیرکار باید متعلق به استان مرکز باشد.")
        return cleaned


class RepairDecisionForm(StyledForm):
    decision = forms.ChoiceField(
        label="تصمیم",
        choices=(("approve", "تایید"), ("return", "عودت برای اصلاح"), ("reject", "رد نهایی")),
    )
    note = forms.CharField(label="توضیح تصمیم", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class RepairCompletionForm(StyledForm):
    outcome = forms.CharField(label="نتیجه و اقدامات تعمیر", widget=forms.Textarea(attrs={"rows": 4}))
    final_cost = forms.DecimalField(label="هزینه نهایی", min_value=0, max_digits=14, decimal_places=2)
    final_cost_reason = forms.CharField(
        label="توضیح افزایش هزینه", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    completion_attachment = forms.FileField(label="مستند نتیجه تعمیر", required=False)
    work_quality = forms.TypedChoiceField(label="کیفیت کار (۱ تا ۵)", choices=RATING_CHOICES, coerce=int)
    completion_speed = forms.TypedChoiceField(label="سرعت انجام (۱ تا ۵)", choices=RATING_CHOICES, coerce=int)
    cost_fairness = forms.TypedChoiceField(label="منصفانه بودن هزینه (۱ تا ۵)", choices=RATING_CHOICES, coerce=int)
    comment = forms.CharField(label="نظر تکمیلی", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class FeedbackReplyForm(StyledForm):
    body = forms.CharField(label="پاسخ / پیگیری", widget=forms.Textarea(attrs={"rows": 3}))


class ReferralCreateForm(StyledModelForm):
    class Meta:
        model = GeneralReferral
        fields = [
            "subject", "description", "center", "repair_request",
            "recipient_role", "recipient_name", "recipient_user", "attachment",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not user:
            self.fields["center"].queryset = Center.objects.none()
            self.fields["repair_request"].queryset = RepairRequest.objects.none()
            self.fields["recipient_user"].queryset = User.objects.none()
            return
        centers = user.get_scoped_centers()
        self.fields["center"].queryset = centers
        self.fields["repair_request"].queryset = RepairRequest.objects.filter(center__in=centers)
        recipients = User.objects.filter(is_active=True).exclude(pk=user.pk)
        if not user.is_admin_country:
            province_ids = centers.values_list(
                "treatment_management__province_id", flat=True
            ).distinct()
            recipients = recipients.filter(
                Q(org_unit_id__in=province_ids)
                | Q(org_unit__parent_id__in=province_ids)
                | Q(center__treatment_management__province_id__in=province_ids)
            )
        self.fields["recipient_user"].queryset = recipients


class ReferralResolveForm(StyledForm):
    outcome = forms.CharField(label="نتیجه پیگیری", widget=forms.Textarea(attrs={"rows": 3}))
    instruction = forms.CharField(label="دستور / اقدام ثبت‌شده", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    attachment = forms.FileField(label="مستند نتیجه / دستور", required=False)


class GeneralITRequestForm(StyledModelForm):
    class Meta:
        model = GeneralITRequest
        fields = ["request_type", "center", "asset", "title", "description"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not user:
            self.fields["center"].queryset = Center.objects.none()
            self.fields["asset"].queryset = Asset.objects.none()
            return
        centers = user.get_scoped_centers()
        if user.center_id:
            centers = centers.filter(pk=user.center_id) if user.role in (
                User.ROLE_REQUESTER, User.ROLE_MANAGER
            ) else centers
        self.fields["center"].queryset = centers
        self.fields["asset"].queryset = Asset.objects.filter(center__in=centers)

    def clean(self):
        cleaned = super().clean()
        center, asset = cleaned.get("center"), cleaned.get("asset")
        if center and asset and asset.center_id != center.pk:
            self.add_error("asset", "دارایی باید متعلق به مرکز درخواست باشد.")
        return cleaned


class GeneralITAssignForm(StyledForm):
    expert = forms.ModelChoiceField(label="کارشناس IT مسئول", queryset=User.objects.none())

    def __init__(self, *args, center=None, **kwargs):
        super().__init__(*args, **kwargs)
        if center:
            self.fields["expert"].queryset = User.objects.filter(
                role=User.ROLE_ADMIN_IT, center=center, is_active=True
            ).order_by("last_name", "first_name")


class GeneralITManagerDecisionForm(StyledForm):
    decision = forms.ChoiceField(label="تصمیم", choices=(("approve", "تایید"), ("reject", "رد")))
    note = forms.CharField(label="توضیح", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class GeneralITEscalateForm(StyledForm):
    bypass_reason = forms.CharField(
        label="دلیل عبور از تایید مدیر مرکز",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class GeneralITResolveForm(StyledForm):
    decision = forms.CharField(label="تصمیم / دستور استانی", widget=forms.Textarea(attrs={"rows": 4}))
