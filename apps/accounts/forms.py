"""فرم‌های کاربران و ورود به سامانه."""
from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from apps.core.forms import StyledModelForm, apply_widget_classes
from apps.org.models import Center, Contract, Contractor, Department, OrganizationalUnit

from .models import User


class LoginForm(AuthenticationForm):
    """فرم ورود با ظاهر فارسی."""

    username = forms.CharField(
        label="نام کاربری",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="گذرواژه",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "نام کاربری یا گذرواژه نادرست است.",
        "inactive": "این حساب کاربری غیرفعال است.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_widget_classes(self)

    def clean(self):
        username = self.cleaned_data.get("username")
        from apps.core.middleware import client_ip
        from .rate_limit import is_login_throttled

        if is_login_throttled(username, client_ip(self.request)):
            raise forms.ValidationError(
                "به دلیل چند تلاش ناموفق، ورود برای این نام کاربری موقتاً محدود شده است. ۱۵ دقیقه دیگر دوباره تلاش کنید."
            )
        return super().clean()


class UserForm(StyledModelForm):
    """ایجاد و ویرایش کاربر توسط کارشناس IT."""

    password1 = forms.CharField(
        label="گذرواژه",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="برای کاربر جدید الزامی است؛ در ویرایش خالی بگذارید تا تغییر نکند.",
    )
    password2 = forms.CharField(
        label="تکرار گذرواژه",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = [
            "username", "first_name", "last_name", "email", "role", "center",
            "personnel_code", "national_code", "phone", "job_title",
            "department", "contractor", "signature", "is_active",
        ]

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

        if self.current_user and not self.current_user.is_superuser and self.current_user.role != User.ROLE_ADMIN_COUNTRY:
            scoped_centers = self.current_user.get_scoped_centers().filter(is_active=True)
            self.fields["center"].queryset = scoped_centers
            if self.current_user.role == User.ROLE_ADMIN_IT:
                allowed_roles = [
                    (User.ROLE_REQUESTER, "کاربر / امانت‌دار"),
                    (User.ROLE_ADMIN_IT, "کارشناس فناوری اطلاعات مرکز"),
                    (User.ROLE_MANAGER, "مدیر و ناظر مرکز"),
                ]
                self.fields["role"].choices = allowed_roles
                if self.current_user.center:
                    self.fields["center"].initial = self.current_user.center
            elif self.current_user.role == User.ROLE_ADMIN_COUNTY:
                allowed_roles = [
                    (User.ROLE_REQUESTER, "کاربر / امانت‌دار"),
                    (User.ROLE_ADMIN_IT, "کارشناس فناوری اطلاعات مرکز"),
                    (User.ROLE_MANAGER, "مدیر و ناظر مرکز"),
                    (User.ROLE_ADMIN_COUNTY, "مدیر فناوری اطلاعات شهرستان"),
                ]
                self.fields["role"].choices = allowed_roles
            elif self.current_user.role == User.ROLE_ADMIN_PROVINCE:
                allowed_roles = [
                    (User.ROLE_REQUESTER, "کاربر / امانت‌دار"),
                    (User.ROLE_ADMIN_IT, "کارشناس فناوری اطلاعات مرکز"),
                    (User.ROLE_MANAGER, "مدیر و ناظر مرکز"),
                    (User.ROLE_ADMIN_COUNTY, "مدیر فناوری اطلاعات شهرستان"),
                    (User.ROLE_ADMIN_PROVINCE, "مدیر فناوری اطلاعات استان"),
                    (User.ROLE_TECHNICIAN, "کارشناس پیمانکار (پشتیبان استانی)"),
                ]
                self.fields["role"].choices = allowed_roles
        else:
            self.fields["center"].queryset = Center.objects.filter(is_active=True)

        departments = Department.objects.filter(is_active=True)
        if (
            self.current_user
            and not self.current_user.is_superuser
            and self.current_user.role != User.ROLE_ADMIN_COUNTRY
        ):
            departments = departments.filter(
                center__in=self.current_user.get_scoped_centers()
            )
        self.fields["department"].queryset = departments
        contractors = Contractor.objects.filter(is_active=True)
        if self.current_user and self.current_user.role == User.ROLE_ADMIN_PROVINCE:
            province = None
            if self.current_user.org_unit_id and self.current_user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE:
                province = self.current_user.org_unit
            elif self.current_user.center_id and self.current_user.center.treatment_management_id:
                province = self.current_user.center.treatment_management.province
            if province:
                today = timezone.localdate()
                active_contracts = Contract.objects.filter(
                    province=province,
                    status=Contract.STATUS_ACTIVE,
                    start_date__lte=today,
                    end_date__gte=today,
                )
                contractors = contractors.filter(contracts__in=active_contracts).distinct()
            else:
                contractors = contractors.none()
        self.fields["contractor"].queryset = contractors
        if not self.instance.pk:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError({"password2": "گذرواژه‌ها یکسان نیستند."})
            candidate = User(
                username=cleaned.get("username") or self.instance.username,
                first_name=cleaned.get("first_name") or "",
                last_name=cleaned.get("last_name") or "",
                email=cleaned.get("email") or "",
            )
            try:
                validate_password(password1, user=candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        role = cleaned.get("role")
        contractor = cleaned.get("contractor")
        if role == User.ROLE_TECHNICIAN and not contractor:
            raise forms.ValidationError({"contractor": "برای کارشناس پیمانکار، انتخاب شرکت الزامی است."})
        if (
            role == User.ROLE_TECHNICIAN
            and self.current_user
            and self.current_user.role == User.ROLE_ADMIN_PROVINCE
        ):
            province = None
            if self.current_user.org_unit_id and self.current_user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE:
                province = self.current_user.org_unit
            elif self.current_user.center_id and self.current_user.center.treatment_management_id:
                province = self.current_user.center.treatment_management.province
            today = __import__("django.utils.timezone", fromlist=["timezone"]).localdate()
            if not province or not contractor.contracts.filter(
                province=province,
                status=Contract.STATUS_ACTIVE,
                start_date__lte=today,
                end_date__gte=today,
            ).exists():
                self.add_error(
                    "contractor",
                    "پیمانکار باید در استان محل مسئولیت شما قرارداد فعال داشته باشد.",
                )

        if self.current_user and not self.current_user.is_superuser and self.current_user.role != User.ROLE_ADMIN_COUNTRY:
            if self.current_user.role == User.ROLE_ADMIN_IT and role in (
                User.ROLE_ADMIN_COUNTRY,
                User.ROLE_ADMIN_PROVINCE,
                User.ROLE_ADMIN_COUNTY,
            ):
                raise forms.ValidationError({"role": "شما مجاز به تخصیص نقش‌های فراتر از سطح کارشناس IT نیستید."})

            center = cleaned.get("center")
            if center and not self.current_user.get_scoped_centers().filter(pk=center.pk).exists():
                raise forms.ValidationError({"center": "مرکز انتخاب‌شده خارج از حوزه سازمانی مجاز شما است."})

        department = cleaned.get("department")
        center = cleaned.get("center")
        if department and center and department.center_id != center.pk:
            self.add_error("department", "واحد سازمانی باید متعلق به مرکز انتخاب‌شده باشد.")
        elif department and not center:
            self.add_error("center", "برای تخصیص واحد سازمانی، انتخاب مرکز الزامی است.")

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if (
            user.role == User.ROLE_TECHNICIAN
            and self.current_user
            and self.current_user.role == User.ROLE_ADMIN_PROVINCE
        ):
            if self.current_user.org_unit_id and self.current_user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE:
                user.org_unit = self.current_user.org_unit
            elif self.current_user.center_id and self.current_user.center.treatment_management_id:
                user.org_unit = self.current_user.center.treatment_management.province
        if commit:
            user.save()
        return user


class UserCreateForm(UserCreationForm):
    """فرم جایگزین برای سازگاری با جنگو."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "role"]


class ProfileForm(StyledModelForm):
    """ویرایش نمایه کاربر جاری."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "job_title", "signature"]


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_widget_classes(self)


class UserFilterForm(forms.Form):
    q = forms.CharField(label="جستجو", required=False)
    role = forms.ChoiceField(
        label="نقش", required=False, choices=[("", "همه")] + list(User.ROLE_CHOICES)
    )
    center = forms.ModelChoiceField(
        label="مرکز", required=False, queryset=Center.objects.all()
    )
    department = forms.ModelChoiceField(
        label="واحد سازمانی", required=False, queryset=Department.objects.all()
    )
    contractor = forms.ModelChoiceField(
        label="پیمانکار", required=False, queryset=Contractor.objects.all()
    )


class AdminSetPasswordForm(forms.Form):
    """تعیین گذرواژه جدید توسط کارشناس فناوری اطلاعات."""

    new_password1 = forms.CharField(
        label="گذرواژه جدید", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    new_password2 = forms.CharField(
        label="تکرار گذرواژه جدید", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        first = cleaned.get("new_password1")
        second = cleaned.get("new_password2")
        if first and second and first != second:
            raise forms.ValidationError({"new_password2": "گذرواژه‌ها یکسان نیستند."})
        if first:
            try:
                validate_password(first, user=self.user)
            except forms.ValidationError as exc:
                self.add_error("new_password1", exc)
        return cleaned
