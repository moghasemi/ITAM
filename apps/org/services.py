"""Scope-aware querysets for organization-domain records."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import Contract, ContractCenterAssignment, OrganizationalUnit


def visible_contracts(user):
    """Return contracts the authenticated user may inspect.

    Country administrators can inspect all contracts. Province administrators
    can inspect every contract owned by their active province. Other staff are
    limited to current contracts explicitly assigned to one of their scoped
    centers; a province relationship alone never grants center-level access.
    """
    if not getattr(user, "is_authenticated", False):
        return Contract.objects.none()

    if user.is_admin_country:
        return Contract.objects.all()

    if user.has_role("technician"):
        return user.get_active_contractor_contracts()

    if user.is_admin_province:
        if (
            user.org_unit_id
            and user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE
        ):
            if not user.org_unit.is_active:
                return Contract.objects.none()
            province_ids = [user.org_unit_id]
        else:
            province_ids = user.get_scoped_centers().values(
                "treatment_management__province_id"
            )
        return Contract.objects.filter(province_id__in=province_ids).distinct()

    today = timezone.localdate()
    assignments = ContractCenterAssignment.objects.filter(
        center__in=user.get_scoped_centers(),
        status=ContractCenterAssignment.STATUS_ACTIVE,
        start_date__lte=today,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today))

    return Contract.objects.filter(
        pk__in=assignments.values("contract_id"),
        status=Contract.STATUS_ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).distinct()
