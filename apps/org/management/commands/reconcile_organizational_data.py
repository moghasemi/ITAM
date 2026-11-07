"""فرمان تطبیق، موجودی‌برداری و تعیین تکلیف داده‌های فاقد مرکز سازمانی."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any, Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.maintenance.models import MaintenanceVisit
from apps.org.models import Center, Department, Location
from apps.tickets.models import Ticket


class Command(BaseCommand):
    help = "موجودی‌برداری و تطبیق ساختار سازمانی داده‌های فاقد مرکز با پشتیبانی از Dry-Run و گزارش CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="اجرای آزمایشی بدون اعمال هرگونه تغییر در پایگاه داده (پیش‌فرض).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="اعمال قطعی تطبیق‌های با قطعیت بالا در پایگاه داده.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="مسیر دلخواه ذخیره فایل گزارش CSV (اختیاری).",
        )

    def handle(self, *args, **options):
        is_apply = options.get("apply", False)
        is_dry_run = not is_apply or options.get("dry_run", True)
        output_file = options.get("output") or f"reconciliation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("   ITAM — موجودی‌برداری و تطبیق داده‌های فاقد مرکز سازمانی"))
        mode_str = "اجرای آزمایشی (DRY-RUN — بدون تغییر در دیتابیس)" if is_dry_run else "اعمال قطعی تغییرات (APPLY MODE)"
        self.stdout.write(self.style.WARNING(f"   وضعیت اجرا: {mode_str}"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        # موجودی‌برداری
        orphaned_assets = list(Asset.objects.filter(center__isnull=True).select_related("location", "custodian", "department"))
        orphaned_users = list(User.objects.filter(center__isnull=True, is_superuser=False, role__in=[User.ROLE_ADMIN_IT, User.ROLE_REQUESTER, User.ROLE_MANAGER]))
        orphaned_tickets = list(Ticket.objects.filter(center__isnull=True).select_related("asset", "reported_by"))
        orphaned_visits = list(MaintenanceVisit.objects.filter(center__isnull=True).prefetch_related("checks__asset"))
        orphaned_departments = list(Department.objects.filter(center__isnull=True))
        orphaned_locations = list(Location.objects.filter(center__isnull=True))

        total_orphaned = (
            len(orphaned_assets)
            + len(orphaned_users)
            + len(orphaned_tickets)
            + len(orphaned_visits)
            + len(orphaned_departments)
            + len(orphaned_locations)
        )

        self.stdout.write(f"\n📊 آمار اقلام فاقد مرکز شناسایی‌شده در سامانه:")
        self.stdout.write(f"  * دارایی‌ها (Assets): {len(orphaned_assets)}")
        self.stdout.write(f"  * کاربران (Users): {len(orphaned_users)}")
        self.stdout.write(f"  * درخواست‌های خرابی (Tickets): {len(orphaned_tickets)}")
        self.stdout.write(f"  * نوبت‌های بازدید دوره‌ای (Visits): {len(orphaned_visits)}")
        self.stdout.write(f"  * واحدهای سازمانی (Departments): {len(orphaned_departments)}")
        self.stdout.write(f"  * محل‌های استقرار (Locations): {len(orphaned_locations)}")
        self.stdout.write(self.style.NOTICE(f"  مجموع کل رکوردهای نیازمند تعیین تکلیف: {total_orphaned}\n"))

        report_rows: List[Dict[str, Any]] = []
        high_confidence_count = 0
        quarantine_count = 0

        # ۱) بررسی دارایی‌ها
        for asset in orphaned_assets:
            suggested_center = None
            confidence = "UNRESOLVED"
            reason = "هیچ شواهد قطعی رابطه‌ای یافت نشد"

            if asset.location and asset.location.center:
                suggested_center = asset.location.center
                confidence = "HIGH"
                reason = f"تطبیق بر اساس مرکز محل استقرار ({asset.location.name})"
            elif asset.custodian and asset.custodian.center:
                suggested_center = asset.custodian.center
                confidence = "HIGH"
                reason = f"تطبیق بر اساس مرکز امانت‌دار ({asset.custodian.display_name})"
            elif asset.department and asset.department.center:
                suggested_center = asset.department.center
                confidence = "MEDIUM"
                reason = f"تطبیق احتمالی بر اساس واحد سازمانی ({asset.department.name})"

            status = "RESOLVED" if confidence == "HIGH" else "QUARANTINED"
            if status == "RESOLVED":
                high_confidence_count += 1
            else:
                quarantine_count += 1

            report_rows.append({
                "entity_type": "Asset",
                "object_id": asset.pk,
                "identifier": asset.asset_tag,
                "title_or_name": str(asset),
                "current_center": "None",
                "suggested_center_id": suggested_center.pk if suggested_center else "",
                "suggested_center_name": suggested_center.name if suggested_center else "",
                "confidence": confidence,
                "heuristic_reason": reason,
                "action": "ASSIGN" if (status == "RESOLVED" and not is_dry_run) else ("QUARANTINE" if not is_dry_run else "DRY_RUN_PREVIEW"),
            })

        # ۲) بررسی کاربران
        for user in orphaned_users:
            suggested_center = None
            confidence = "UNRESOLVED"
            reason = "هیچ مرکز قطعی برای کاربر یافت نشد"

            if user.department and user.department.center:
                suggested_center = user.department.center
                confidence = "HIGH"
                reason = f"تطبیق بر اساس واحد سازمانی کاربر ({user.department.name})"

            status = "RESOLVED" if confidence == "HIGH" else "QUARANTINED"
            if status == "RESOLVED":
                high_confidence_count += 1
            else:
                quarantine_count += 1

            report_rows.append({
                "entity_type": "User",
                "object_id": user.pk,
                "identifier": user.username,
                "title_or_name": user.display_name,
                "current_center": "None",
                "suggested_center_id": suggested_center.pk if suggested_center else "",
                "suggested_center_name": suggested_center.name if suggested_center else "",
                "confidence": confidence,
                "heuristic_reason": reason,
                "action": "ASSIGN" if (status == "RESOLVED" and not is_dry_run) else ("QUARANTINE" if not is_dry_run else "DRY_RUN_PREVIEW"),
            })

        # ۳) بررسی تیکت‌ها
        for ticket in orphaned_tickets:
            suggested_center = None
            confidence = "UNRESOLVED"
            reason = "عدم ارتباط با دارایی یا کاربر دارای مرکز"

            if ticket.asset and ticket.asset.center:
                suggested_center = ticket.asset.center
                confidence = "HIGH"
                reason = f"تطبیق مستقیم با مرکز دارایی مرتبط ({ticket.asset.asset_tag})"
            elif ticket.reported_by and ticket.reported_by.center:
                suggested_center = ticket.reported_by.center
                confidence = "HIGH"
                reason = f"تطبیق با مرکز کاربر اعلام‌کننده ({ticket.reported_by.display_name})"

            status = "RESOLVED" if confidence == "HIGH" else "QUARANTINED"
            if status == "RESOLVED":
                high_confidence_count += 1
            else:
                quarantine_count += 1

            report_rows.append({
                "entity_type": "Ticket",
                "object_id": ticket.pk,
                "identifier": ticket.number,
                "title_or_name": ticket.title,
                "current_center": "None",
                "suggested_center_id": suggested_center.pk if suggested_center else "",
                "suggested_center_name": suggested_center.name if suggested_center else "",
                "confidence": confidence,
                "heuristic_reason": reason,
                "action": "ASSIGN" if (status == "RESOLVED" and not is_dry_run) else ("QUARANTINE" if not is_dry_run else "DRY_RUN_PREVIEW"),
            })

        # تولید گزارش CSV
        fieldnames = [
            "entity_type",
            "object_id",
            "identifier",
            "title_or_name",
            "current_center",
            "suggested_center_id",
            "suggested_center_name",
            "confidence",
            "heuristic_reason",
            "action",
        ]

        try:
            with open(output_file, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in report_rows:
                    writer.writerow(row)
            self.stdout.write(self.style.SUCCESS(f"✅ فایل گزارش مشروح تطبیق تولید شد: {output_file}"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"خطا در ایجاد فایل CSV: {exc}"))

        # اعمال در پایگاه داده در صورت فعال بودن flag --apply
        if not is_dry_run:
            self.stdout.write(self.style.WARNING("\n⏳ در حال اعمال تطبیق‌های با قطعیت بالا در تراکنش اتمیک..."))
            applied_count = 0
            with transaction.atomic():
                for row in report_rows:
                    if row["confidence"] == "HIGH" and row["suggested_center_id"]:
                        center_obj = Center.objects.get(pk=row["suggested_center_id"])
                        if row["entity_type"] == "Asset":
                            Asset.objects.filter(pk=row["object_id"]).update(center=center_obj, is_quarantined=False)
                            applied_count += 1
                        elif row["entity_type"] == "User":
                            User.objects.filter(pk=row["object_id"]).update(center=center_obj)
                            applied_count += 1
                        elif row["entity_type"] == "Ticket":
                            Ticket.objects.filter(pk=row["object_id"]).update(center=center_obj)
                            applied_count += 1
                    elif row["confidence"] == "UNRESOLVED":
                        if row["entity_type"] == "Asset":
                            Asset.objects.filter(pk=row["object_id"]).update(
                                is_quarantined=True,
                                quarantine_notes=f"قرنطینه شده در تاریخ {timezone.now():%Y-%m-%d}: نیازمند بررسی حضوری جهت تعیین مرکز",
                            )

            self.stdout.write(self.style.SUCCESS(f"✅ با موفقیت {applied_count} رکورد با قطعیت بالا به مراکز مربوطه منتسب شدند."))
            self.stdout.write(self.style.WARNING(f"⚠️ تعداد {quarantine_count} رکورد مبهم جهت حفظ یکپارچگی حقوقی در قرنطینه نگهداری شدند."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ اجرای آزمایشی (Dry-Run) با موفقیت به پایان رسید. هیچ تغییری در پایگاه داده اعمال نشد."))
            self.stdout.write(f"   - تطبیق‌های با قطعیت بالا: {high_confidence_count}")
            self.stdout.write(f"   - موارد مبهم / قرنطینه‌شده: {quarantine_count}")
            self.stdout.write(self.style.NOTICE("   برای اعمال تغییرات با قطعیت بالا، فرمان را با آرگومان --apply اجرا کنید.\n"))
