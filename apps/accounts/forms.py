"""فرم‌های کاربران و ورود به سامانه."""
from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from apps.core.forms import StyledModelForm, apply_widget_classes
from apps.org.models import Contractor, Department

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
            "username", "first_name", "last_name", "email", "role",
            "personnel_code", "national_code", "phone", "job_title",
            "department", "contractor", "signature", "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
