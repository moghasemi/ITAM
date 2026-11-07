"""Regression tests for organizational-data reconciliation safety."""

import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset, AssetCategory
from apps.org.models import Center, Location, OrganizationalUnit


class ReconciliationCommandRegressionTests(TestCase):
    def setUp(self):
        self.national = OrganizationalUnit.objects.create(
            name="Regression National", code="REG-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        self.province = OrganizationalUnit.objects.create(
            name="Regression Province", code="REG-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=self.national,
        )
        self.county = OrganizationalUnit.objects.create(
            name="Regression County", code="REG-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province,
        )
        self.center = Center.objects.create(
            name="Regression Center", code="REG-CENTER",
            parent_unit=self.county,
        )
        self.category = AssetCategory.objects.create(
            name="Regression Monitor", code="REG-MON",
        )

    def run_reconciliation(self, *args, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            report = str(Path(directory) / "reconciliation.csv")
            call_command("reconcile_organizational_data", *args, output=report, **kwargs)
            self.assertTrue(Path(report).exists())

    def test_apply_flag_really_assigns_high_confidence_asset(self):
        location = Location.objects.create(name="Known room", center=self.center)
        asset = Asset.objects.create(
            asset_tag="REG-ASSET-001", title="Known asset",
            category=self.category, location=location, center=None,
        )

        self.run_reconciliation(apply=True, dry_run=False)

        asset.refresh_from_db()
        self.assertEqual(asset.center_id, self.center.pk)
        self.assertFalse(asset.is_quarantined)

    def test_default_dry_run_does_not_change_asset(self):
        location = Location.objects.create(name="Preview room", center=self.center)
        asset = Asset.objects.create(
            asset_tag="REG-ASSET-002", title="Preview asset",
            category=self.category, location=location, center=None,
        )

        self.run_reconciliation()

        asset.refresh_from_db()
        self.assertIsNone(asset.center_id)

    def test_medium_confidence_asset_is_quarantined_in_apply_mode(self):
        from apps.org.models import Department

        department = Department.objects.create(name="Possible department", center=self.center)
        asset = Asset.objects.create(
            asset_tag="REG-ASSET-003", title="Ambiguous asset",
            category=self.category, department=department, center=None,
        )

        self.run_reconciliation(apply=True, dry_run=False)

        asset.refresh_from_db()
        self.assertIsNone(asset.center_id)
        self.assertTrue(asset.is_quarantined)
        self.assertIn("قرنطینه", asset.quarantine_notes)

    def test_center_reconciliation_uses_county_model_not_center_model(self):
        # A legacy center can have a missing parent; create it validly, then
        # reproduce the legacy database state without invoking model.save().
        legacy_center = Center.objects.create(
            name="Legacy exact-match center", code="REG-LEGACY",
            city=self.county.name, parent_unit=self.county,
        )
        Center.objects.filter(pk=legacy_center.pk).update(parent_unit=None)

        self.run_reconciliation(apply=True, dry_run=False)

        legacy_center.refresh_from_db()
        self.assertEqual(legacy_center.parent_unit_id, self.county.pk)

    def test_apply_and_dry_run_flags_are_mutually_exclusive(self):
        from django.core.management import load_command_class

        command = load_command_class("apps.org", "reconcile_organizational_data")
        parser = command.create_parser("manage.py", "reconcile_organizational_data")
        with self.assertRaises(SystemExit):
            parser.parse_args(["--apply", "--dry-run"])
