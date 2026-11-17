"""Safe inventory and reconciliation of records missing organizational centers.

The command is intentionally conservative: only unambiguous, single-source
matches are eligible for --apply. The CSV must be written successfully before
any database mutation begins.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.core.utils import log_action
from apps.maintenance.models import MaintenanceVisit
from apps.org.models import Center, Department, Location, OrganizationalUnit
from apps.tickets.models import Ticket


FIELDS = (
    "entity_type", "object_id", "identifier", "title_or_name",
    "current_center", "suggested_center_id", "suggested_center_name",
    "confidence", "heuristic_reason", "action",
)


def _center_evidence_signature(center):
    """Capture the center's operational ownership so stale reports cannot be applied."""
    if center is None:
        return None
    county = center.parent_unit if center.parent_unit_id else None
    province = county.parent if county and county.parent_id else None
    management = center.treatment_management if center.treatment_management_id else None
    return (
        center.pk,
        center.is_active,
        county.pk if county else None,
        county.is_active if county else None,
        province.pk if province else None,
        province.is_active if province else None,
        management.pk if management else None,
        management.is_active if management else None,
        management.province_id if management else None,
    )


class Command(BaseCommand):
    help = "Inventory and safely reconcile records missing organizational centers."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=False)
        mode.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--output", type=str, default="")

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        output = options.get("output") or (
            f"reconciliation_report_{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        centers = list(Center.objects.filter(parent_unit__isnull=True).select_related("treatment_management"))
        assets = list(
            Asset.objects.filter(center__isnull=True).select_related(
                "location__center", "custodian__center", "department__center"
            )
        )
        users = list(
            User.objects.filter(
                center__isnull=True, is_superuser=False,
                role__in=[User.ROLE_ADMIN_IT, User.ROLE_REQUESTER, User.ROLE_MANAGER],
            ).select_related("department__center")
        )
        tickets = list(
            Ticket.objects.filter(center__isnull=True).select_related(
                "asset__center", "reported_by__center"
            )
        )
        visits = list(MaintenanceVisit.objects.filter(center__isnull=True))
        departments = list(Department.objects.filter(center__isnull=True))
        locations = list(Location.objects.filter(center__isnull=True))

        rows = []
        plan = []
        counts = {
            "Center": len(centers), "Asset": len(assets), "User": len(users),
            "Ticket": len(tickets), "MaintenanceVisit": len(visits),
            "Department": len(departments), "Location": len(locations),
        }

        def add(entity, obj, identifier, title, suggestion=None, confidence="UNRESOLVED", reason="", evidence_signature=None):
            action = "DRY_RUN_PREVIEW"
            if apply_changes:
                action = "ASSIGN" if confidence == "HIGH" and suggestion else (
                    "QUARANTINE" if entity == "Asset" else "MANUAL_REVIEW"
                )
            rows.append({
                "entity_type": entity,
                "object_id": obj.pk,
                "identifier": identifier,
                "title_or_name": title,
                "current_center": "None",
                "suggested_center_id": suggestion.pk if suggestion else "",
                "suggested_center_name": suggestion.name if suggestion else "",
                "confidence": confidence,
                "heuristic_reason": reason,
                "action": action,
            })
            if apply_changes and action in {"ASSIGN", "QUARANTINE"}:
                plan.append((entity, obj.pk, suggestion.pk if suggestion else None, reason, evidence_signature))

        for asset in assets:
            evidence = []
            if asset.location_id and asset.location.center_id:
                evidence.append(("location", asset.location.center))
            if asset.custodian_id and asset.custodian.center_id:
                evidence.append(("custodian", asset.custodian.center))
            if asset.department_id and asset.department.center_id:
                evidence.append(("department", asset.department.center))

            centers_found = {item[1].pk: item[1] for item in evidence}
            suggestion = None
            confidence = "UNRESOLVED"
            if len(centers_found) > 1:
                reason = "تعارض شواهد: محل استقرار، امانت‌دار یا واحد سازمانی به مراکز متفاوت اشاره می‌کنند"
            elif len(centers_found) == 1:
                source, candidate = evidence[0]
                if source in {"location", "custodian"}:
                    suggestion, confidence = candidate, "HIGH"
                    reason = f"تنها شاهد معتبر از مسیر {source}"
                else:
                    reason = "تنها شاهد موجود واحد سازمانی است؛ برای انتساب قطعی کافی نیست"
            else:
                reason = "هیچ شاهد معتبر مرکز یافت نشد"
            signature = (
                "Asset", asset.location_id,
                _center_evidence_signature(asset.location.center) if asset.location_id and asset.location.center_id else None,
                asset.custodian_id,
                _center_evidence_signature(asset.custodian.center) if asset.custodian_id and asset.custodian.center_id else None,
                asset.department_id,
                _center_evidence_signature(asset.department.center) if asset.department_id and asset.department.center_id else None,
            )
            add("Asset", asset, asset.asset_tag, str(asset), suggestion, confidence, reason, signature)

        for user in users:
            suggestion = user.department.center if user.department_id and user.department.center_id else None
            add(
                "User", user, user.username, user.display_name, suggestion,
                "HIGH" if suggestion else "UNRESOLVED",
                "مرکز واحد سازمانی کاربر" if suggestion else "مرکز قطعی برای کاربر یافت نشد",
                ("User", user.department_id, _center_evidence_signature(user.department.center) if user.department_id and user.department.center_id else None),
            )

        for ticket in tickets:
            asset_center = ticket.asset.center if ticket.asset_id and ticket.asset.center_id else None
            reporter_center = ticket.reported_by.center if ticket.reported_by_id and ticket.reported_by.center_id else None
            if asset_center and reporter_center and asset_center.pk != reporter_center.pk:
                suggestion, confidence = None, "UNRESOLVED"
                reason = "تعارض مرکز دارایی و کاربر گزارش‌دهنده"
            elif asset_center or reporter_center:
                suggestion = asset_center or reporter_center
                confidence = "HIGH"
                reason = "مرکز دارایی مرتبط" if asset_center else "مرکز کاربر گزارش‌دهنده"
            else:
                suggestion, confidence, reason = None, "UNRESOLVED", "دارایی و گزارش‌دهنده مرکز مشخص ندارند"
            signature = (
                "Ticket", ticket.asset_id,
                _center_evidence_signature(ticket.asset.center) if ticket.asset_id and ticket.asset.center_id else None,
                ticket.reported_by_id,
                _center_evidence_signature(ticket.reported_by.center) if ticket.reported_by_id and ticket.reported_by.center_id else None,
            )
            add("Ticket", ticket, ticket.number, ticket.title, suggestion, confidence, reason, signature)

        for center in centers:
            matches = OrganizationalUnit.objects.filter(
                unit_type=OrganizationalUnit.UNIT_COUNTY,
                is_active=True,
                name__iexact=(center.city or "").strip(),
                parent__unit_type=OrganizationalUnit.UNIT_PROVINCE,
                parent__is_active=True,
            ) if center.city else OrganizationalUnit.objects.none()
            match_count = matches.count()
            suggestion = matches.first() if match_count == 1 else None
            if (
                suggestion
                and center.treatment_management_id
                and (
                    not center.treatment_management.is_active
                    or center.treatment_management.province_id != suggestion.parent_id
                )
            ):
                suggestion = None
            confidence = "HIGH" if suggestion else "UNRESOLVED"
            reason = (
                "تنها شهرستان فعال با نام منطبق و استان فعال؛ مالکیت مدیریت درمان نیز سازگار است"
                if suggestion else
                "تطبیق شهرستان یکتا و معتبر یافت نشد یا مالکیت مدیریت درمان مرکز با استان مقصد سازگار نیست؛ انتساب دستی لازم است"
            )
            signature = (
                "Center", (center.city or "").strip(), center.treatment_management_id,
                center.treatment_management.is_active if center.treatment_management_id else None,
                center.treatment_management.province_id if center.treatment_management_id else None,
            )
            add("Center", center, center.code or str(center.pk), center.name, suggestion, confidence, reason, signature)

        # These records are inventoried but never auto-assigned by this command.
        for entity, objects, identifier_fn, title_fn in (
            ("MaintenanceVisit", visits, lambda x: str(x.pk), lambda x: str(x)),
            ("Department", departments, lambda x: str(x.pk), lambda x: x.name),
            ("Location", locations, lambda x: str(x.pk), lambda x: x.name),
        ):
            for obj in objects:
                add(entity, obj, identifier_fn(obj), title_fn(obj), reason="این نوع رکورد در این فرمان به‌صورت خودکار منتسب نمی‌شود")

        # A complete report is a prerequisite for any apply operation.
        try:
            output_path = Path(output)
            with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
        except (OSError, csv.Error) as exc:
            raise CommandError(f"گزارش CSV ایجاد نشد؛ هیچ تغییری اعمال نشد: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"گزارش کامل ذخیره شد: {output_path}"))
        self.stdout.write("موجودی رکوردهای فاقد مرکز: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

        if not apply_changes:
            self.stdout.write(self.style.SUCCESS("Dry-run تمام شد؛ دیتابیس تغییر نکرد."))
            return

        applied = quarantined = 0
        try:
            with transaction.atomic():
                for entity, object_id, suggested_id, reason, expected_signature in plan:
                    if entity == "Center":
                        obj = Center.objects.select_for_update().get(pk=object_id)
                        current_signature = (
                            "Center", (obj.city or "").strip(), obj.treatment_management_id,
                            obj.treatment_management.is_active if obj.treatment_management_id else None,
                            obj.treatment_management.province_id if obj.treatment_management_id else None,
                        )
                        if obj.parent_unit_id is not None or current_signature != expected_signature:
                            raise CommandError(f"شواهد سازمانی مرکز {obj.pk} پس از تهیه گزارش تغییر کرده؛ عملیات لغو شد.")
                        current_matches = OrganizationalUnit.objects.filter(
                            unit_type=OrganizationalUnit.UNIT_COUNTY, is_active=True,
                            name__iexact=(obj.city or "").strip(),
                            parent__unit_type=OrganizationalUnit.UNIT_PROVINCE,
                            parent__is_active=True,
                        ) if obj.city else OrganizationalUnit.objects.none()
                        if current_matches.count() != 1 or current_matches.first().pk != suggested_id:
                            raise CommandError(f"تطبیق شهرستان مرکز {obj.pk} پس از تهیه گزارش تغییر کرده؛ عملیات لغو شد.")
                        unit = OrganizationalUnit.objects.select_for_update().get(
                            pk=suggested_id, unit_type=OrganizationalUnit.UNIT_COUNTY,
                            is_active=True, parent__is_active=True,
                        )
                        obj.parent_unit = unit
                        obj.province = unit.parent.name
                        obj.save(update_fields=["parent_unit", "province", "treatment_management", "updated_at"])
                        log_action("update", obj, note="تطبیق سازمانی: انتساب شهرستان بر اساس تطبیق یکتای نام شهر")
                        applied += 1
                        continue

                    if entity == "Asset":
                        obj = Asset.objects.select_for_update(of=("self",)).select_related(
                            "location__center", "custodian__center", "department__center"
                        ).get(pk=object_id)
                        current_signature = (
                            "Asset", obj.location_id,
                            _center_evidence_signature(obj.location.center) if obj.location_id and obj.location.center_id else None,
                            obj.custodian_id,
                            _center_evidence_signature(obj.custodian.center) if obj.custodian_id and obj.custodian.center_id else None,
                            obj.department_id,
                            _center_evidence_signature(obj.department.center) if obj.department_id and obj.department.center_id else None,
                        )
                        if obj.center_id is not None or current_signature != expected_signature:
                            raise CommandError(f"شواهد سازمانی دارایی {obj.pk} پس از تهیه گزارش تغییر کرده؛ عملیات لغو شد.")
                        if suggested_id:
                            obj.center_id = suggested_id
                            obj.is_quarantined = False
                            obj.quarantine_notes = ""
                            obj.save(update_fields=["center", "is_quarantined", "quarantine_notes", "updated_at"])
                            log_action("update", obj, note="تطبیق سازمانی: انتساب مرکز با شاهد یکتا")
                            applied += 1
                        else:
                            obj.is_quarantined = True
                            obj.quarantine_notes = (
                                f"قرنطینه تطبیق سازمانی در {timezone.now():%Y-%m-%d %H:%M}: {reason}"
                            )
                            obj.save(update_fields=["is_quarantined", "quarantine_notes", "updated_at"])
                            log_action("update", obj, note="قرنطینه به علت ابهام/تعارض در تطبیق سازمانی")
                            quarantined += 1
                        continue

                    if entity == "User":
                        obj = User.objects.select_for_update(of=("self",)).select_related("department__center").get(pk=object_id)
                        current_signature = (
                            "User", obj.department_id,
                            _center_evidence_signature(obj.department.center) if obj.department_id and obj.department.center_id else None,
                        )
                        if obj.center_id is not None or current_signature != expected_signature:
                            raise CommandError(f"شواهد سازمانی کاربر {obj.pk} پس از تهیه گزارش تغییر کرده؛ عملیات لغو شد.")
                        obj.center_id = suggested_id
                        obj.save(update_fields=["center"])
                    elif entity == "Ticket":
                        obj = Ticket.objects.select_for_update(of=("self",)).select_related(
                            "asset__center", "reported_by__center"
                        ).get(pk=object_id)
                        current_signature = (
                            "Ticket", obj.asset_id,
                            _center_evidence_signature(obj.asset.center) if obj.asset_id and obj.asset.center_id else None,
                            obj.reported_by_id,
                            _center_evidence_signature(obj.reported_by.center) if obj.reported_by_id and obj.reported_by.center_id else None,
                        )
                        if obj.center_id is not None or current_signature != expected_signature:
                            raise CommandError(f"شواهد سازمانی تیکت {obj.pk} پس از تهیه گزارش تغییر کرده؛ عملیات لغو شد.")
                        obj.center_id = suggested_id
                        obj.save(update_fields=["center", "updated_at"])
                    else:
                        continue
                    log_action("update", obj, note="تطبیق سازمانی: انتساب مرکز با شاهد یکتا")
                    applied += 1
        except Exception:
            # The atomic block rolls back all DB writes; the CSV remains as the
            # pre-apply inventory and can be inspected for diagnosis.
            raise

        self.stdout.write(self.style.SUCCESS(f"تطبیق‌های اعمال‌شده: {applied}"))
        self.stdout.write(self.style.WARNING(f"دارایی‌های قرنطینه‌شده: {quarantined}"))
