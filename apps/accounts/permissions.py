"""کنترل دسترسی مبتنی بر نقش."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import User

ADMIN_IT = User.ROLE_ADMIN_IT
TECHNICIAN = User.ROLE_TECHNICIAN
REQUESTER = User.ROLE_REQUESTER
MANAGER = User.ROLE_MANAGER

STAFF_ROLES = (ADMIN_IT, MANAGER)
ALL_ROLES = (ADMIN_IT, TECHNICIAN, REQUESTER, MANAGER)

ROLE_HOME = {
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


class AdminItRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ADMIN_IT,)


class StaffRequiredMixin(RoleRequiredMixin):
    """کارشناس فناوری اطلاعات مرکز یا مدیر/ناظر."""

    allowed_roles = STAFF_ROLES


class TechnicianRequiredMixin(RoleRequiredMixin):
    allowed_roles = (TECHNICIAN,)


class RepairStaffRequiredMixin(RoleRequiredMixin):
    """کارشناس IT یا کارشناس پیمانکار."""

    allowed_roles = (ADMIN_IT, TECHNICIAN)


class AnyRoleRequiredMixin(RoleRequiredMixin):
    allowed_roles = ALL_ROLES
