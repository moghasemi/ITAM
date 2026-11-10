"""Tests for the Iran administrative geography loader."""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.org.models import OrganizationalUnit, TreatmentManagement


class IranGeographyLoaderTests(TestCase):
    def test_loads_all_provinces_and_counties_with_correct_hierarchy(self):
        call_command("load_iran_geography")

        national = OrganizationalUnit.objects.get(code="IR-NAT")
        provinces = OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=national,
            code__startswith="IR-PROV-",
        )
        counties = OrganizationalUnit.objects.filter(
            unit_type=OrganizationalUnit.UNIT_COUNTY,
            parent__in=provinces,
            code__startswith="IR-COUNTY-",
        )

        self.assertEqual(provinces.count(), 31)
        self.assertEqual(counties.count(), 484)
        self.assertEqual(TreatmentManagement.objects.count(), 31)
        self.assertEqual(
            TreatmentManagement.objects.values("province_id").distinct().count(), 31
        )
        active_provinces = list(
            provinces.filter(is_active=True).values_list("name", flat=True)
        )
        self.assertEqual(active_provinces, ["سیستان و بلوچستان"])
        self.assertFalse(
            counties.exclude(parent__name="سیستان و بلوچستان").filter(is_active=True).exists()
        )
        self.assertEqual(
            counties.filter(parent__name="سیستان و بلوچستان", is_active=True).count(),
            counties.filter(parent__name="سیستان و بلوچستان").count(),
        )
        self.assertEqual(
            OrganizationalUnit.objects.filter(
                unit_type=OrganizationalUnit.UNIT_COUNTY,
                parent__unit_type=OrganizationalUnit.UNIT_PROVINCE,
            ).count(),
            484,
        )

    def test_loader_is_idempotent(self):
        call_command("load_iran_geography")
        call_command("load_iran_geography")

        self.assertEqual(
            OrganizationalUnit.objects.filter(code__startswith="IR-PROV-").count(),
            31,
        )
        self.assertEqual(
            OrganizationalUnit.objects.filter(code__startswith="IR-COUNTY-").count(),
            484,
        )
        self.assertEqual(TreatmentManagement.objects.count(), 31)

    def test_loader_reuses_legacy_demo_hierarchy_and_keeps_center_link(self):
        national = OrganizationalUnit.objects.create(
            name="ستاد کشوری مدیریت فاوا",
            code="OU-NAT-MOH",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        province = OrganizationalUnit.objects.create(
            name="دانشگاه علوم پزشکی استان مرکزی",
            code="OU-PRV-MARKAZI",
            unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شبکه بهداشت و درمان شهرستان اراک",
            code="OU-CNTY-ARAK",
            unit_type=OrganizationalUnit.UNIT_COUNTY,
            parent=province,
        )
        from apps.org.models import Center

        center = Center.objects.create(
            name="مرکز قدیمی اراک",
            code="LEGACY-ARAK-CENTER",
            parent_unit=county,
            city="اراک",
        )

        call_command("load_iran_geography")

        national.refresh_from_db()
        province.refresh_from_db()
        county.refresh_from_db()
        center.refresh_from_db()
        self.assertEqual(national.code, "IR-NAT")
        self.assertEqual(province.code, "IR-PROV-100")
        self.assertEqual(province.name, "مرکزی")
        self.assertEqual(county.code, "IR-COUNTY-1000001")
        self.assertEqual(county.name, "اراک")
        self.assertEqual(center.parent_unit_id, county.pk)
        self.assertEqual(
            OrganizationalUnit.objects.filter(code="IR-COUNTY-1000001").count(),
            1,
        )

    def test_loader_preserves_unrelated_units(self):
        unrelated = OrganizationalUnit.objects.create(
            name="واحد آزمایشی مستقل",
            code="TEST-UNRELATED",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )

        call_command("load_iran_geography")

        self.assertTrue(OrganizationalUnit.objects.filter(pk=unrelated.pk).exists())

    def test_dry_run_does_not_write(self):
        call_command("load_iran_geography", dry_run=True)

        self.assertFalse(OrganizationalUnit.objects.exists())

    def test_invalid_record_count_fails_before_writing(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import json

        from django.conf import settings

        data_dir = Path(settings.BASE_DIR) / "data" / "iran_admin"
        provinces = json.loads((data_dir / "provinces.json").read_text(encoding="utf-8"))
        counties = json.loads((data_dir / "counties.json").read_text(encoding="utf-8"))

        with TemporaryDirectory() as directory:
            provinces_file = Path(directory) / "provinces.json"
            counties_file = Path(directory) / "counties.json"
            provinces_file.write_text(json.dumps(provinces[:-1], ensure_ascii=False), encoding="utf-8")
            counties_file.write_text(json.dumps(counties, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(CommandError):
                call_command(
                    "load_iran_geography",
                    provinces_file=str(provinces_file),
                    counties_file=str(counties_file),
                )

        self.assertFalse(OrganizationalUnit.objects.exists())
