"""Regression tests for maintenance access boundaries."""
import datetime as dt

from django.core.exceptions import PermissionDenied
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.org.models import Center, Contract, Contractor, OrganizationalUnit

from .models import MaintenanceVisit, VisitAssetCheck
from .services import save_check, visible_checks


class ProvincialMaintenanceScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="Test National", code="MNT-NAT", unit_type=OrganizationalUnit.UNIT_NATIONAL
        )
        cls.province = OrganizationalUnit.objects.create(
            name="Province One", code="MNT-P1",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        other_province = OrganizationalUnit.objects.create(
            name="Province Two", code="MNT-P2",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_one = OrganizationalUnit.objects.create(
            name="County One", code="MNT-C1",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province,
        )
        county_two = OrganizationalUnit.objects.create(
            name="County Two", code="MNT-C2",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=other_province,
        )
        cls.center = Center.objects.create(
            name="Maintenance Center One", code="MNT-CENTER1", parent_unit=county_one
        )
        cls.other_center = Center.objects.create(
            name="Maintenance Center Two", code="MNT-CENTER2", parent_unit=county_two
        )
        cls.contractor = Contractor.objects.create(name="Maintenance Test Contractor")
        cls.contract = Contract.objects.create(
            contractor=cls.contractor, number="MNT-CONTRACT-1", title="Provincial contract",
            is_provincial=True,
            start_date=timezone.localdate() - dt.timedelta(days=10),
            end_date=timezone.localdate() + dt.timedelta(days=100),
            visit_interval_days=30,
        )
        cls.contract.centers.add(cls.center, cls.other_center)
        category = AssetCategory.objects.create(name="Maintenance Test Category", code="MNT")
        cls.asset = Asset.objects.create(
            asset_tag="MNT-ASSET-1", category=category, contract=cls.contract,
            center=cls.center, status="active",
        )
        cls.other_asset = Asset.objects.create(
            asset_tag="MNT-ASSET-2", category=category, contract=cls.contract,
            center=cls.other_center, status="active",
        )
        cls.visit = MaintenanceVisit.objects.create(
            number="MNT-VISIT-1", contract=cls.contract, contractor=cls.contractor,
            center=None, sequence_number=1,
            scheduled_date=timezone.localdate(),
        )
        cls.own_check = VisitAssetCheck.objects.create(visit=cls.visit, asset=cls.asset)
        cls.foreign_check = VisitAssetCheck.objects.create(visit=cls.visit, asset=cls.other_asset)
        cls.provincial_admin = User.objects.create_user(
            username="maintenance-provincial-admin", password="TestPass!9382",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=cls.province,
        )

    def test_provincial_admin_only_sees_checks_for_scoped_assets(self):
        checks = visible_checks(self.provincial_admin, self.visit)
        self.assertEqual(set(checks.values_list("pk", flat=True)), {self.own_check.pk})

    def test_provincial_admin_cannot_save_check_for_foreign_asset(self):
        with self.assertRaises(PermissionDenied):
            save_check(self.foreign_check, self.provincial_admin, notes="unauthorized change")
        self.foreign_check.refresh_from_db()
        self.assertEqual(self.foreign_check.notes, "")

    def test_check_edit_endpoint_hides_foreign_asset_check(self):
        client = Client()
        client.force_login(self.provincial_admin)
        response = client.get(reverse("maintenance:check_edit", args=[self.foreign_check.pk]))
        self.assertEqual(response.status_code, 404)
