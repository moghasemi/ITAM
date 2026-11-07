"""کنترل دسترسی مبتنی بر نقش و دامنه سازمانی چهارسطحی."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import User

ADMIN_COUNTRY = User.ROLE_ADMIN_COUNTRY
ADMIN_PROVINCE = User.ROLE_ADMIN_PROVINCE
ADMIN_COUNTY = User.ROLE_ADMIN_COUNTY
ADMIN_IT = User.ROLE_ADMIN_IT
TECHNICIAN = User.ROLE_TECHNICIAN
REQUESTER = User.ROLE_REQUESTER
MANAGER = User.ROLE_MANAGER

STAFF_ROLES = (ADMIN_COUNTRY, ADMIN_PROVINCE, ADMIN_COUNTY, ADMIN_IT, MANAGER)
ALL_ROLES = (ADMIN_COUNTRY, ADMIN_PROVINCE, ADMIN_COUNTY, ADMIN_IT, TECHNICIAN, REQUESTER, MANAGER)

ROLE_HOME = {
    ADMIN_COUNTRY: "core:dashboard",
    ADMIN_PROVINCE: "core:dashboard",
    ADMIN_COUNTY: "core:dashboard",
    ADMIN_IT: "core:dashboard",
    MANAGER: "core:dashboard",
    TECHNICIAN: "maintenance:visit_list",
    REQUESTER: "tickets:my_tickets",
}


def user_has_any_role(user, roles) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return bool(set(roles) & set(user.role_codes()))


def landing_url_name(user) -> str:
    """صفحه فرود مناسب هر نقش."""
    if user.is_superuser:
        return "core:dashboard"
    for role in user.role_codes():
        if role in ROLE_HOME:
            return ROLE_HOME[role]
    return "core:dashboard"


class RoleRequiredMixin(LoginRequiredMixin):
    """محدودکردن نما به نقش‌های مشخص."""

    allowed_roles: tuple = ()
    permission_denied_message = "شما به این بخش دسترسی ندارید."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.allowed_roles and not user_has_any_role(request.user, self.allowed_roles):
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class CountryAdminRequiredMixin(RoleRequiredMixin):
    """دسترسی انحصاری مدیر فناوری اطلاعات کشوری یا Superuser."""
    allowed_roles = (ADMIN_COUNTRY,)


class ProvinceAdminRequiredMixin(RoleRequiredMixin):
    """دسترسی مدیر استانی یا کشوری."""
    allowed_roles = (ADMIN_COUNTRY, ADMIN_PROVINCE)


class CountyAdminRequiredMixin(RoleRequiredMixin):
    """دسترسی مدیر شهرستانی، استانی یا کشوری."""
    allowed_roles = (ADMIN_COUNTRY, ADMIN_PROVINCE, ADMIN_COUNTY)


class AdminItRequiredMixin(RoleRequiredMixin):
    """کارشناس IT مرکز یا مدیران بالادست (شهرستان، استان، کشور)."""
    allowed_roles = (ADMIN_COUNTRY, ADMIN_PROVINCE, ADMIN_COUNTY, ADMIN_IT)


class StaffRequiredMixin(RoleRequiredMixin):
    """کادر IT مرکز یا مدیران و ناظران."""
    allowed_roles = STAFF_ROLES


class TechnicianRequiredMixin(RoleRequiredMixin):
    allowed_roles = (TECHNICIAN,)


class RepairStaffRequiredMixin(RoleRequiredMixin):
    """کارشناس IT یا کارشناس پیمانکار."""
    allowed_roles = (ADMIN_COUNTRY, ADMIN_PROVINCE, ADMIN_COUNTY, ADMIN_IT, TECHNICIAN)


class AnyRoleRequiredMixin(RoleRequiredMixin):
    allowed_roles = ALL_ROLES
