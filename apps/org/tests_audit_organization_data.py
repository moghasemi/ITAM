from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.org.models import Center, OrganizationalUnit, TreatmentManagement


class AuditOrganizationDataCommandTests(TestCase):
    def setUp(self):
        self.national = OrganizationalUnit.objects.create(
            name="ستاد", code="AUD-NAT", unit_type=OrganizationalUnit.UNIT_NATIONAL
        )
        self.province_a = OrganizationalUnit.objects.create(
            name="استان الف", code="AUD-PA",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=self.national,
        )
        self.province_b = OrganizationalUnit.objects.create(
            name="استان ب", code="AUD-PB",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=self.national,
        )
        self.county_a = OrganizationalUnit.objects.create(
            name="شهرستان الف", code="AUD-CA",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_a,
        )
        self.center = Center.objects.create(
            name="مرکز ممیزی", code="AUD-C-01", city="شهر الف", parent_unit=self.county_a
        )
        self.management_b, _ = TreatmentManagement.objects.get_or_create(
            province=self.province_b,
            defaults={"name": "مدیریت درمان استان ب", "code": "AUD-TM-PB"},
        )

    def test_valid_center_passes_read_only_audit(self):
        output = StringIO()
        call_command("audit_organization_data", stdout=output)

        self.assertIn("مراکز بررسی‌شده: 1", output.getvalue())
        self.assertIn("بدون خطای بحرانی", output.getvalue())

    def test_province_mismatch_fails_without_repairing_data(self):
        Center.objects.filter(pk=self.center.pk).update(
            treatment_management=self.management_b
        )
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command("audit_organization_data", stdout=output)

        self.assertIn("province_mismatch", output.getvalue())
        self.center.refresh_from_db()
        self.assertEqual(
            self.center.treatment_management.province_id, self.province_b.pk
        )

    def test_orphaned_geography_is_reported(self):
        Center.objects.filter(pk=self.center.pk).update(parent_unit=None)
        output = StringIO()

        with self.assertRaises(CommandError):
            call_command("audit_organization_data", stdout=output)

        self.assertIn("missing_geographic_county", output.getvalue())
