"""فرم‌های ساختار سازمانی، مراکز استان، پیمانکار و قرارداد."""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import JalaliDateField, StyledModelForm
from .models import Center, Contract, Contractor, Department, Location, OrganizationalUnit, SlaPolicy


class CenterForm(StyledModelForm):
    """فرم ثبت و ویرایش مرکز اداری / شهرستان با الزام اتصال به واحد شهرستانی."""

    class Meta:
        model = Center
        fields = [
            "name",
            "code",
            "parent_unit",
            "city",
            "manager_name",
            "it_lead_name",
            "phone",
            "is_headquarters",
            "is_active",
            "address",
            "notes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        county_qs = OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_COUNTY, is_active=True
        ).select_related("parent")

        if user and not user.is_superuser:
            if getattr(user, "org_unit", None) and user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE:
                county_qs = county_qs.filter(parent=user.org_unit)
            elif getattr(user, "center", None) and user.center.parent_unit and user.center.parent_unit.parent:
                county_qs = county_qs.filter(parent=user.center.parent_unit.parent)

        self.fields["parent_unit"].queryset = county_qs
        self.fields["parent_unit"].required = True
        self.fields["parent_unit"].help_text = "انتخاب واحد سازمانی شهرستانی (County) بالادست الزامی است."

    def clean_parent_unit(self):
        parent_unit = self.cleaned_data.get("parent_unit")
        if not parent_unit:
            raise forms.ValidationError("اتصال مرکز به واحد سازمانی شهرستانی الزامی است.")
        if parent_unit.unit_type != OrganizationalUnit.UNIT_COUNTY:
            raise forms.ValidationError("مرکز فقط می‌تواند به یک واحد سازمانی از نوع شهرستانی (County) متصل شود.")
        return parent_unit







class _CenterScopedFormMixin:
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and getattr(user, "is_authenticated", False):
            self.fields["center"].queryset = user.get_scoped_centers().filter(is_active=True)
            if getattr(user, "center_id", None) and user.has_role("admin_it", "manager"):
                self.fields["center"].initial = user.center
                self.fields["center"].required = True
        else:
            self.fields["center"].queryset = Center.objects.none()


class DepartmentForm(_CenterScopedFormMixin, StyledModelForm):
    class Meta:
        model = Department
        fields = ["center", "name", "code", "manager_name", "phone", "is_active", "description"]


class LocationForm(_CenterScopedFormMixin, StyledModelForm):
    class Meta:
        model = Location
        fields = ["center", "name", "building", "floor", "room", "code", "is_active", "description"]


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
            "contractor", "province", "number", "title", "start_date", "end_date",
            "visit_interval_days", "status", "visit_scope", "repair_scope", "notes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["province"].queryset = OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_PROVINCE, is_active=True
        ).order_by("name")
        if user and user.role == "admin_province" and not user.is_superuser:
            if user.org_unit_id:
                self.fields["province"].queryset = self.fields["province"].queryset.filter(
                    pk=user.org_unit_id
                )
            elif user.center_id and user.center.parent_unit_id:
                self.fields["province"].queryset = self.fields["province"].queryset.filter(
                    pk=user.center.parent_unit.parent_id
                )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        province = cleaned.get("province")
        if not province:
            self.add_error("province", "انتخاب استان قرارداد الزامی است.")
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields["contractor"].queryset = Contractor.objects.none()
        elif not user.is_admin_province:
            province_ids = user.get_scoped_centers().values("parent_unit__parent_id")
            scoped_contracts = Contract.objects.filter(province_id__in=province_ids).distinct()
            self.fields["contractor"].queryset = Contractor.objects.filter(
                pk__in=scoped_contracts.values("contractor_id")
            )