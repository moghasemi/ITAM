"""Read-only audit for provincial contracts missing explicit center assignments."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.org.models import Contract, ContractCenterAssignment


class Command(BaseCommand):
    help = "ممیزی فقط‌خواندنی انتساب پیمانکاران رسمی به مراکز"

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        today = timezone.localdate()
        contracts = Contract.objects.filter(
            status=Contract.STATUS_ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        ).select_related("contractor", "province").prefetch_related("center_assignments", "centers")

        issues = []
        for contract in contracts.order_by("province__name", "number"):
            active_assignments = contract.center_assignments.filter(
                status=ContractCenterAssignment.STATUS_ACTIVE,
                start_date__lte=today,
            ).filter(
                models_q_end_date(today)
            )
            if active_assignments.exists():
                continue
            legacy_centers = list(contract.centers.values_list("code", flat=True))
            issues.append({
                "severity": "warning",
                "code": "active_contract_without_active_center_assignment",
                "contract": contract.number,
                "contractor": contract.contractor.name,
                "province": contract.province.name if contract.province_id else "",
                "legacy_center_count": len(legacy_centers),
                "legacy_center_codes": legacy_centers,
                "message": (
                    "قرارداد جاری به‌تنهایی دامنه دسترسی تکنسین ایجاد نمی‌کند؛ "
                    "انتساب فعال و صریح برای هر مرکز لازم است."
                ),
            })

        result = {
            "date": today.isoformat(),
            "active_contracts_checked": contracts.count(),
            "contracts_missing_active_assignment": len(issues),
            "issues": issues,
            "read_only": True,
        }
        if options["format"] == "json":
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            return
        self.stdout.write(self.style.MIGRATE_HEADING("ممیزی انتساب پیمانکار به مراکز"))
        self.stdout.write(f"قراردادهای جاری بررسی‌شده: {result['active_contracts_checked']}")
        self.stdout.write(f"قرارداد بدون انتساب فعال: {len(issues)}")
        for issue in issues:
            self.stdout.write(
                f"- {issue['contract']} | {issue['contractor']} | {issue['province']} "
                f"| مراکز قدیمی M2M: {issue['legacy_center_count']}"
            )
        self.stdout.write("این فرمان فقط گزارش می‌دهد و هیچ داده‌ای را تغییر نمی‌دهد.")


def models_q_end_date(today):
    from django.db.models import Q
    return Q(end_date__isnull=True) | Q(end_date__gte=today)
