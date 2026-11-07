"""فرم‌های کاربران و ورود به سامانه."""
from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from apps.core.forms import StyledModelForm, apply_widget_classes
from apps.org.models import Center, Contractor, Department

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

        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["contractor"].queryset = Contractor.objects.filter(is_active=True)
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
            if len(password1) < 8:
                raise forms.ValidationError({"password1": "گذرواژه باید حداقل ۸ نویسه باشد."})
        role = cleaned.get("role")
        contractor = cleaned.get("contractor")
        if role == User.ROLE_TECHNICIAN and not contractor:
            raise forms.ValidationError({"contractor": "برای کارشناس پیمانکار، انتخاب شرکت الزامی است."})

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

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
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

    def clean(self):
        cleaned = super().clean()
        first = cleaned.get("new_password1")
        second = cleaned.get("new_password2")
        if first and second and first != second:
            raise forms.ValidationError({"new_password2": "گذرواژه‌ها یکسان نیستند."})
        if first and len(first) < 8:
            raise forms.ValidationError({"new_password1": "گذرواژه باید حداقل ۸ نویسه باشد."})
        return cleaned
