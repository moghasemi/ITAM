"""نماهای کاربران: ورود، نمایه و مدیریت کاربران."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from apps.core.mixins import BaseListView, PageContextMixin, apply_search
from apps.core.utils import log_action

from .forms import (
    AdminSetPasswordForm,
    LoginForm,
    ProfileForm,
    StyledPasswordChangeForm,
    UserFilterForm,
    UserForm,
)
from .models import User
from .permissions import AdminItRequiredMixin, landing_url_name


class ItamLoginView(LoginView):
    """ورود به سامانه با هدایت بر اساس نقش."""

    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        target = self.get_redirect_url()
        if target:
            return target
        return reverse(landing_url_name(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "ورود به سامانه"
        return context


class ItamLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class ProfileView(LoginRequiredMixin, PageContextMixin, DetailView):
    template_name = "accounts/profile.html"
    page_title = "نمایه کاربری"
    active_menu = "profile"

    def get_object(self, queryset=None):
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, PageContextMixin, UpdateView):
    form_class = ProfileForm
    template_name = "accounts/profile_form.html"
    page_title = "ویرایش نمایه"
    active_menu = "profile"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action("update", self.object, note="ویرایش نمایه کاربری", user=self.request.user)
        messages.success(self.request, "نمایه شما به‌روزرسانی شد.")
        return response


class ItamPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "تغییر گذرواژه"
        context["active_menu"] = "profile"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action("update", self.request.user, note="تغییر گذرواژه", user=self.request.user)
        messages.success(self.request, "گذرواژه تغییر کرد.")
        return response


class UserListView(AdminItRequiredMixin, BaseListView):
    model = User
    template_name = "accounts/user_list.html"
    page_title = "کاربران سامانه"
    active_menu = "users"
    paginate_by = 25
    filter_form_class = UserFilterForm

    def get_queryset(self):
        queryset = User.objects.select_related("department", "contractor").order_by("last_name", "first_name")
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            data = form.cleaned_data
            queryset = apply_search(queryset, data.get("q"), ["username", "first_name", "last_name", "personnel_code", "phone"])
            if data.get("role"):
                queryset = queryset.filter(role=data["role"])
            if data.get("department"):
                queryset = queryset.filter(department=data["department"])
            if data.get("contractor"):
                queryset = queryset.filter(contractor=data["contractor"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_labels"] = User.ROLE_LABELS
        return context


class UserCreateView(AdminItRequiredMixin, PageContextMixin, CreateView):
    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    page_title = "افزودن کاربر"
    active_menu = "users"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action("create", self.object, note="ایجاد کاربر", user=self.request.user)
        messages.success(self.request, "کاربر ایجاد شد.")
        return response


class UserUpdateView(AdminItRequiredMixin, PageContextMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    page_title = "ویرایش کاربر"
    active_menu = "users"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action("update", self.object, note="ویرایش کاربر", user=self.request.user)
        messages.success(self.request, "تغییرات کاربر ذخیره شد.")
        return response


class UserDetailView(AdminItRequiredMixin, PageContextMixin, DetailView):
    model = User
    template_name = "accounts/user_detail.html"
    page_title = "پرونده کاربر"
    active_menu = "users"


def user_toggle_active(request, pk: int):
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if user.pk == request.user.pk:
            messages.error(request, "نمی‌توانید حساب کاربری خود را غیرفعال کنید.")
        else:
            user.is_active = not user.is_active
            user.save(update_fields=["is_active"])
            log_action(
                "update",
                user,
                note=f"تغییر وضعیت فعال بودن به {'فعال' if user.is_active else 'غیرفعال'}",
                user=request.user,
            )
            messages.success(request, "وضعیت کاربر تغییر کرد.")
    return redirect("accounts:user_list")


def user_set_password(request, pk: int):
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    user = get_object_or_404(User, pk=pk)
    form = AdminSetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password1"])
        user.save(update_fields=["password"])
        log_action("update", user, note="تعیین گذرواژه جدید توسط کارشناس IT", user=request.user)
        messages.success(request, "گذرواژه کاربر تغییر کرد.")
        return redirect("accounts:user_list")
    return render(
        request,
        "accounts/user_password.html",
        {
            "form": form,
            "object": user,
            "page_title": f"تعیین گذرواژه برای {user.display_name}",
            "active_menu": "users",
        },
    )
