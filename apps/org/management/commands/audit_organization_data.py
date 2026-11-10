"""Read-only audit for organizational/geographic center and contract mappings.

The command reports inconsistencies only. It never repairs, reassigns, or deletes
operational records; ambiguous legacy mappings must be reviewed by a human.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.org.models import Center, Contract, OrganizationalUnit, TreatmentManagement


class Command(BaseCommand):
    help = "ممیزی فقط‌خواندنی ارتباط جغرافیایی و مالکیت سازمانی مراکز"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="قالب گزارش خروجی",
        )

    def handle(self, *args, **options):
        issues: list[dict[str, str]] = []
        centers = Center.objects.select_related(
            "parent_unit__parent", "treatment_management__province"
        ).order_by("pk")

        center_count = centers.count()
        province_ids_with_management = set(
            TreatmentManagement.objects.values_list("province_id", flat=True)
        )
        for province in OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_PROVINCE
        ).only("pk", "name"):
            if province.pk not in province_ids_with_management:
                issues.append({
                    "severity": "error",
                    "code": "missing_province_treatment_management",
                    "object": f"Province:{province.pk}:{province.name}",
                    "message": "برای استان واحد مدیریت درمان تعریف نشده است.",
                })

        for center in centers.iterator():
            label = f"Center:{center.pk}:{center.code or center.name}"
            county = center.parent_unit
            province = county.parent if county else None

            if county is None:
                issues.append({
                    "severity": "error",
                    "code": "missing_geographic_county",
                    "object": label,
                    "message": "مرکز به شهرستان جغرافیایی متصل نیست.",
                })
            elif county.unit_type != OrganizationalUnit.UNIT_COUNTY:
                issues.append({
                    "severity": "error",
                    "code": "invalid_geographic_county",
                    "object": label,
                    "message": "واحد جغرافیایی مرکز از نوع شهرستان نیست.",
                })
            elif province is None or province.unit_type != OrganizationalUnit.UNIT_PROVINCE:
                issues.append({
                    "severity": "error",
                    "code": "invalid_geographic_province",
                    "object": label,
                    "message": "شهرستان مرکز به استان معتبر متصل نیست.",
                })

            management = center.treatment_management
            if management is None:
                issues.append({
                    "severity": "error",
                    "code": "missing_treatment_management",
                    "object": label,
                    "message": "مدیریت درمان سازمانی مرکز تعیین نشده است.",
                })
            elif province and management.province_id != province.pk:
                issues.append({
                    "severity": "error",
                    "code": "province_mismatch",
                    "object": label,
                    "message": "استان مدیریت درمان با استان جغرافیایی مرکز یکسان نیست.",
                })
            elif management and not management.is_active:
                issues.append({
                    "severity": "warning",
                    "code": "inactive_treatment_management",
                    "object": label,
                    "message": "مدیریت درمان متصل به مرکز غیرفعال است.",
                })

            if center.is_demo and not (center.code or "").startswith("DEMO-"):
                issues.append({
                    "severity": "warning",
                    "code": "demo_code_not_marked",
                    "object": label,
                    "message": "مرکز نمونه است اما کد آن با DEMO- آغاز نمی‌شود.",
                })
            elif (center.code or "").startswith("DEMO-") and not center.is_demo:
                issues.append({
                    "severity": "warning",
                    "code": "demo_code_without_flag",
                    "object": label,
                    "message": "کد مرکز نمونه است اما پرچم is_demo فعال نیست.",
                })

            if not center.city.strip():
                issues.append({
                    "severity": "warning",
                    "code": "missing_legacy_city",
                    "object": label,
                    "message": "فیلد متنی شهر خالی است؛ شهر نرمال‌شده هنوز در مدل وجود ندارد.",
                })

        contracts = Contract.objects.select_related("province").order_by("pk")
        contract_count = contracts.count()
        for contract in contracts.iterator():
            label = f"Contract:{contract.pk}:{contract.number}"
            if not contract.province_id:
                issues.append({
                    "severity": "error",
                    "code": "missing_contract_province",
                    "object": label,
                    "message": "استان قرارداد تعیین نشده است؛ دامنه دسترسی باید بسته بماند.",
                })
            elif contract.province.unit_type != OrganizationalUnit.UNIT_PROVINCE:
                issues.append({
                    "severity": "error",
                    "code": "invalid_contract_province",
                    "object": label,
                    "message": "استان قرارداد از نوع استان نیست.",
                })

        errors = sum(issue["severity"] == "error" for issue in issues)
        warnings = sum(issue["severity"] == "warning" for issue in issues)
        report = {
            "centers_checked": center_count,
            "contracts_checked": contract_count,
            "errors": errors,
            "warnings": warnings,
            "issues": issues,
        }

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(
                f"مراکز بررسی‌شده: {center_count} | قراردادهای بررسی‌شده: "
                f"{contract_count} | خطا: {errors} | هشدار: {warnings}"
            )
            for issue in issues:
                self.stdout.write(
                    f"[{issue['severity'].upper()}] {issue['code']} "
                    f"{issue['object']}: {issue['message']}"
                )

        if errors:
            raise CommandError(
                f"ممیزی با {errors} خطا و {warnings} هشدار پایان یافت؛ هیچ داده‌ای تغییر نکرد."
            )
        self.stdout.write(self.style.SUCCESS("ممیزی ساختار سازمانی/جغرافیایی بدون خطای بحرانی پایان یافت."))
