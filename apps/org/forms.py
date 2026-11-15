"""فرم‌های ساختار سازمانی، مراکز استان، پیمانکار و قرارداد."""
from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import JalaliDateField, StyledModelForm
from .models import Center, Contract, ContractCenterAssignment, Contractor, Department, Location, OrganizationalUnit, SlaPolicy


class CountySelect(forms.Select):
    """Attach each county's province ID so the form can filter options client-side."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        county = getattr(value, "instance", None)
        if county is not None:
            option["attrs"]["data-province-id"] = str(county.parent_id)
        return option


class CountyChoiceField(forms.ModelChoiceField):
    """Show the concise county name, not the verbose organizational-unit label."""

    def label_from_instance(self, obj):
        return obj.name


class CenterForm(StyledModelForm):
    """فرم ثبت و ویرایش مرکز با انتخاب استان و شهرستان جغرافیایی."""

    province = forms.ModelChoiceField(
        label="استان",
        queryset=OrganizationalUnit.objects.none(),
        required=True,
        empty_label="استان را انتخاب کنید",
    )

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
        province_qs = OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_PROVINCE, is_active=True
        ).order_by("name")
        county_qs = OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_COUNTY, is_active=True
        ).select_related("parent").order_by("name")

        fixed_province_id = None
        if user and not user.is_superuser and user.role == "admin_province":
            if (
                getattr(user, "org_unit", None)
                and user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE
            ):
                fixed_province_id = user.org_unit_id
            elif (
                getattr(user, "center", None)
                and user.center.treatment_management_id
            ):
                fixed_province_id = user.center.treatment_management.province_id
            if fixed_province_id:
                province_qs = province_qs.filter(pk=fixed_province_id)
            else:
                province_qs = OrganizationalUnit.objects.none()

        if self.is_bound:
            selected_province_id = self.data.get(self.add_prefix("province"))
        elif self.instance.pk and self.instance.parent_unit_id:
            selected_province_id = self.instance.parent_unit.parent_id
        else:
            selected_province_id = fixed_province_id

        if selected_province_id:
            county_qs = county_qs.filter(parent_id=selected_province_id)
        else:
            county_qs = county_qs.none()

        province_field = self.fields["province"]
        province_field.queryset = province_qs
        if fixed_province_id:
            province_field.initial = fixed_province_id
            province_field.disabled = True
            province_field.help_text = "استان بر اساس محدوده دسترسی شما تعیین شده است."
        else:
            province_field.help_text = "ابتدا استان را انتخاب کنید تا شهرستان‌های همان استان نمایش داده شوند."

        self.fields["parent_unit"] = CountyChoiceField(
            label="شهرستان",
            queryset=county_qs,
            required=True,
            empty_label="شهرستان را انتخاب کنید",
            widget=CountySelect(attrs={"class": "form-select"}),
            help_text="فقط شهرستان‌های استان انتخاب‌شده قابل انتخاب هستند.",
        )
        self.order_fields([
            "name", "code", "province", "parent_unit", "city", "manager_name",
            "it_lead_name", "phone", "is_headquarters", "is_active", "address", "notes",
        ])

    def clean_parent_unit(self):
        parent_unit = self.cleaned_data.get("parent_unit")
        province = self.cleaned_data.get("province")
        if not parent_unit:
            raise forms.ValidationError("انتخاب شهرستان جغرافیایی الزامی است.")
        if parent_unit.unit_type != OrganizationalUnit.UNIT_COUNTY:
            raise forms.ValidationError("مرکز فقط می‌تواند به یک شهرستان جغرافیایی متصل شود.")
        if not province or parent_unit.parent_id != province.pk:
            raise forms.ValidationError("شهرستان انتخاب‌شده متعلق به استان انتخاب‌شده نیست.")
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
                    pk=user.center.treatment_management.province_id if user.center.treatment_management_id else None
                )
            else:
                self.fields["province"].queryset = OrganizationalUnit.objects.none()

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
        elif user.has_role("technician"):
            scoped_contracts = user.get_active_contractor_contracts()
            self.fields["contractor"].queryset = Contractor.objects.filter(
                pk__in=scoped_contracts.values("contractor_id")
            )
        elif not user.is_admin_country:
            province_ids = user.get_scoped_centers().values("treatment_management__province_id")
            scoped_contracts = Contract.objects.filter(province_id__in=province_ids).distinct()
            self.fields["contractor"].queryset = Contractor.objects.filter(
                pk__in=scoped_contracts.values("contractor_id")
            )

class ContractCenterAssignmentForm(StyledModelForm):
    start_date = JalaliDateField(label="تاریخ شروع انتساب")

    class Meta:
        model = ContractCenterAssignment
        fields = ["contract", "center", "start_date"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields["contract"].queryset = Contract.objects.none()
            self.fields["center"].queryset = Center.objects.none()
            return
        centers = user.get_scoped_centers()
        self.fields["center"].queryset = centers.order_by("name")
        if user.is_admin_country:
            contracts = Contract.objects.filter(is_provincial=True)
        else:
            province_id = getattr(user, "org_unit_id", None)
            contracts = Contract.objects.filter(
                province_id=province_id, is_provincial=True
            )
        self.fields["contract"].queryset = contracts.select_related("contractor").order_by("-start_date")

    def clean(self):
        cleaned = super().clean()
        contract = cleaned.get("contract")
        center = cleaned.get("center")
        if contract and center:
            province_id = center.treatment_management.province_id if center.treatment_management_id else None
            if not province_id or contract.province_id != province_id:
                self.add_error("contract", "قرارداد و مرکز باید متعلق به یک استان باشند.")
            if not contract.is_current:
                self.add_error("contract", "فقط قرارداد استانی جاری قابل انتساب است.")
        return cleaned


class ContractCenterAssignmentEndForm(forms.Form):
    end_date = JalaliDateField(label="تاریخ پایان", required=False)
    reason = forms.CharField(
        label="دلیل پایان انتساب",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
