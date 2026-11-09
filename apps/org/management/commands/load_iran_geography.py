"""Load Iran's province/county hierarchy into OrganizationalUnit records.

This command is additive and idempotent. It never deletes operational data.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.org.models import OrganizationalUnit


EXPECTED_PROVINCES = 31
EXPECTED_COUNTIES = 484
NATIONAL_CODE = "IR-NAT"
LEGACY_CODES = {
    "province": {100: "OU-PRV-MARKAZI"},
    "county": {
        1000001: "OU-CNTY-ARAK",
        1000004: "OU-CNTY-KHOMEIN",
        1000006: "OU-CNTY-SAVEH",
    },
}


class Command(BaseCommand):
    help = "بارگذاری سلسله‌مراتب ۳۱ استان و ۴۸۴ شهرستان ایران"

    def add_arguments(self, parser):
        data_dir = Path(settings.BASE_DIR) / "data" / "iran_admin"
        parser.add_argument(
            "--provinces-file",
            default=str(data_dir / "provinces.json"),
            help="مسیر فایل JSON استان‌ها",
        )
        parser.add_argument(
            "--counties-file",
            default=str(data_dir / "counties.json"),
            help="مسیر فایل JSON شهرستان‌ها",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="اعتبارسنجی فایل‌ها بدون تغییر پایگاه داده",
        )

    def _read_records(self, path: str, label: str) -> list[dict]:
        try:
            with Path(path).open("r", encoding="utf-8") as stream:
                records = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"خواندن فایل {label} ناموفق بود: {exc}") from exc

        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise CommandError(f"ساختار فایل {label} باید آرایه‌ای از اشیا باشد.")
        return records

    def _validate(self, provinces: list[dict], counties: list[dict]) -> None:
        if len(provinces) != EXPECTED_PROVINCES:
            raise CommandError(
                f"تعداد استان‌ها باید {EXPECTED_PROVINCES} باشد؛ مقدار فعلی: {len(provinces)}"
            )
        if len(counties) != EXPECTED_COUNTIES:
            raise CommandError(
                f"تعداد شهرستان‌ها باید {EXPECTED_COUNTIES} باشد؛ مقدار فعلی: {len(counties)}"
            )

        province_ids = set()
        for row in provinces:
            if not isinstance(row.get("id"), int) or not str(row.get("name", "")).strip():
                raise CommandError("هر استان باید شناسه عددی و نام غیرخالی داشته باشد.")
            if row["id"] in province_ids:
                raise CommandError(f"شناسه تکراری استان: {row['id']}")
            province_ids.add(row["id"])

        county_ids = set()
        for row in counties:
            if (
                not isinstance(row.get("id"), int)
                or not isinstance(row.get("province_id"), int)
                or not str(row.get("name", "")).strip()
            ):
                raise CommandError("هر شهرستان باید شناسه، شناسه استان و نام معتبر داشته باشد.")
            if row["id"] in county_ids:
                raise CommandError(f"شناسه تکراری شهرستان: {row['id']}")
            if row["province_id"] not in province_ids:
                raise CommandError(
                    f"شهرستان {row['name']} به استان ناشناخته {row['province_id']} متصل است."
                )
            county_ids.add(row["id"])

    def _root_unit(self) -> OrganizationalUnit:
        root = OrganizationalUnit.objects.filter(code=NATIONAL_CODE).first()
        if root:
            if root.unit_type != OrganizationalUnit.UNIT_NATIONAL or root.parent_id:
                raise CommandError(f"کد {NATIONAL_CODE} قبلاً برای واحد کشوری معتبر استفاده نشده است.")
            return root

        legacy_root = OrganizationalUnit.objects.filter(
            code="OU-NAT-MOH",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
            parent__isnull=True,
        ).first()
        if legacy_root:
            legacy_root.code = NATIONAL_CODE
            legacy_root.name = "ایران"
            legacy_root.save(update_fields=["code", "name", "updated_at"])
            return legacy_root

        # Do not repurpose an unrelated national unit. The importer owns only
        # its stable IR-* namespace and the explicitly known legacy demo code.
        return OrganizationalUnit.objects.create(
            code=NATIONAL_CODE,
            name="ایران",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )

    def _upsert_unit(
        self,
        *,
        code: str,
        name: str,
        unit_type: str,
        parent: OrganizationalUnit | None,
        legacy_code: str | None = None,
    ) -> tuple[OrganizationalUnit, bool]:
        unit = OrganizationalUnit.objects.filter(code=code).first()
        if unit is None and legacy_code:
            unit = OrganizationalUnit.objects.filter(code=legacy_code).first()
        if unit is None:
            matches = OrganizationalUnit.objects.filter(
                unit_type=unit_type,
                name=name,
                parent=parent,
            )
            if matches.count() > 1:
                raise CommandError(
                    f"چند واحد با نام «{name}» در یک سطح پیدا شد؛ تطبیق خودکار متوقف شد."
                )
            unit = matches.first()

        created = unit is None
        if created:
            unit = OrganizationalUnit(
                code=code,
                name=name,
                unit_type=unit_type,
                parent=parent,
                is_active=True,
            )
        else:
            if unit.unit_type != unit_type:
                raise CommandError(f"نوع واحد {unit.code} با نوع مورد انتظار سازگار نیست.")
            unit.code = code
            unit.name = name
            unit.parent = parent
            unit.is_active = True

        unit.save()
        return unit, created

    @transaction.atomic
    def handle(self, *args, **options):
        provinces = self._read_records(options["provinces_file"], "استان‌ها")
        counties = self._read_records(options["counties_file"], "شهرستان‌ها")
        self._validate(provinces, counties)

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"اعتبارسنجی موفق: {len(provinces)} استان و {len(counties)} شهرستان؛ هیچ تغییری اعمال نشد."
                )
            )
            return

        root = self._root_unit()
        province_units = {}
        created_provinces = 0
        updated_provinces = 0
        created_counties = 0
        updated_counties = 0

        for row in provinces:
            code = f"IR-PROV-{row['id']}"
            unit, created = self._upsert_unit(
                code=code,
                name=row["name"].strip(),
                unit_type=OrganizationalUnit.UNIT_PROVINCE,
                parent=root,
                legacy_code=LEGACY_CODES["province"].get(row["id"]),
            )
            province_units[row["id"]] = unit
            if created:
                created_provinces += 1
            else:
                updated_provinces += 1

        for row in counties:
            code = f"IR-COUNTY-{row['id']}"
            unit, created = self._upsert_unit(
                code=code,
                name=row["name"].strip(),
                unit_type=OrganizationalUnit.UNIT_COUNTY,
                parent=province_units[row["province_id"]],
                legacy_code=LEGACY_CODES["county"].get(row["id"]),
            )
            if created:
                created_counties += 1
            else:
                updated_counties += 1

        self.stdout.write(
            self.style.SUCCESS(
                "بارگذاری جغرافیای ایران کامل شد: "
                f"{len(province_units)} استان و {len(counties)} شهرستان."
            )
        )
        self.stdout.write(
            f"استان: {created_provinces} ایجاد، {updated_provinces} به‌روزرسانی | "
            f"شهرستان: {created_counties} ایجاد، {updated_counties} به‌روزرسانی"
        )
        self.stdout.write("هیچ مرکز عملیاتی یا رکورد موجودی حذف یا ایجاد نشد.")
