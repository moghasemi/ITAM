from datetime import timedelta
from io import StringIO

from django.core.management import call_command

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.org.models import Center, Contract, Contractor, OrganizationalUnit
from apps.maintenance.repair_services import assign_contractor_to_center


class TechnicianProvinceContractScopeTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.today = today
        national = OrganizationalUnit.objects.create(
            name="ستاد", code="NAT-TEST", unit_type=OrganizationalUnit.UNIT_NATIONAL
        )
        self.province_a = OrganizationalUnit.objects.create(
            name="استان الف", code="PR-A-TEST",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        self.province_b = OrganizationalUnit.objects.create(
            name="استان ب", code="PR-B-TEST",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_a = OrganizationalUnit.objects.create(
            name="شهرستان الف", code="CO-A-TEST",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_a,
        )
        self.county_a = county_a
        county_b = OrganizationalUnit.objects.create(
            name="شهرستان ب", code="CO-B-TEST",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_b,
        )
        self.center_a1 = Center.objects.create(
            name="مرکز الف۱", code="C-A1-TEST", parent_unit=county_a
        )
        self.center_a2 = Center.objects.create(
            name="مرکز الف۲", code="C-A2-TEST", parent_unit=county_a
        )
        self.center_b = Center.objects.create(
            name="مرکز ب", code="C-B-TEST", parent_unit=county_b
        )
        self.contractor = Contractor.objects.create(name="پیمانکار آزمون")
        self.province_admin_a = User.objects.create_user(
            username="province-admin-a", password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province_a,
        )
        self.province_admin_b = User.objects.create_user(
            username="province-admin-b", password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province_b,
        )
        self.technician = User.objects.create_user(
            username="technician-province-test",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_TECHNICIAN,
            contractor=self.contractor,
        )
        self.start = today - timedelta(days=5)
        self.end = today + timedelta(days=30)

    def make_contract(self, number, province, **kwargs):
        defaults = {
            "contractor": self.contractor,
            "province": province,
            "number": number,
            "title": number,
            "start_date": self.start,
            "end_date": self.end,
            "status": Contract.STATUS_ACTIVE,
            "is_provincial": True,
        }
        defaults.update(kwargs)
        return Contract.objects.create(**defaults)

    def scoped_ids(self):
        return set(self.technician.get_scoped_centers().values_list("pk", flat=True))

    def assign(self, contract, center, province_admin=None):
        province_admin = province_admin or (
            self.province_admin_a if center.treatment_management.province_id == self.province_a.pk
            else self.province_admin_b
        )
        return assign_contractor_to_center(
            contract=contract, center=center, start_date=self.today, actor=province_admin,
        )

    def test_active_contract_grants_only_centers_in_its_province(self):
        contract = self.make_contract("CON-A-1", self.province_a)
        self.assign(contract, self.center_a1)
        self.assertEqual(self.scoped_ids(), {self.center_a1.pk})

    def test_multiple_active_contracts_in_same_province_are_supported(self):
        first = self.make_contract("CON-A-1", self.province_a)
        second = self.make_contract("CON-A-2", self.province_a)
        self.assign(first, self.center_a1)
        self.assign(second, self.center_a2)
        self.assertEqual(self.scoped_ids(), {self.center_a1.pk, self.center_a2.pk})

    def test_contracts_in_two_provinces_grant_only_those_two_provinces(self):
        contract_a = self.make_contract("CON-A-1", self.province_a)
        contract_b = self.make_contract("CON-B-1", self.province_b)
        self.assign(contract_a, self.center_a1, self.province_admin_a)
        self.assign(contract_b, self.center_b, self.province_admin_b)
        self.assertEqual(self.scoped_ids(), {self.center_a1.pk, self.center_b.pk})

    def test_suspended_contract_grants_no_access(self):
        self.make_contract("CON-SUSP", self.province_a, status=Contract.STATUS_SUSPENDED)
        self.assertEqual(self.scoped_ids(), set())

    def test_expired_contract_grants_no_access(self):
        self.make_contract(
            "CON-OLD", self.province_a,
            start_date=self.today - timedelta(days=60),
            end_date=self.today - timedelta(days=1),
        )
        self.assertEqual(self.scoped_ids(), set())

    def test_future_contract_grants_no_access_yet(self):
        self.make_contract(
            "CON-FUTURE", self.province_a,
            start_date=self.today + timedelta(days=1),
            end_date=self.today + timedelta(days=60),
        )
        self.assertEqual(self.scoped_ids(), set())

    def test_inactive_contractor_grants_no_access(self):
        self.contractor.is_active = False
        self.contractor.save(update_fields=["is_active"])
        self.make_contract("CON-INACTIVE", self.province_a)
        self.assertEqual(self.scoped_ids(), set())

    def test_unassigned_legacy_contract_grants_no_access(self):
        self.make_contract("CON-LEGACY", None)
        self.assertEqual(self.scoped_ids(), set())


    def test_inactive_province_grants_no_access_even_with_active_contract(self):
        self.province_a.is_active = False
        self.province_a.save(update_fields=["is_active"])
        self.make_contract("CON-INACTIVE-PROV", self.province_a)
        self.assertEqual(self.scoped_ids(), set())

    def test_inactive_county_centers_are_excluded(self):
        self.county_a.is_active = False
        self.county_a.save(update_fields=["is_active"])
        self.make_contract("CON-INACTIVE-COUNTY", self.province_a)
        self.assertEqual(self.scoped_ids(), set())

    def test_inactive_center_is_excluded_from_scope(self):
        self.center_a1.is_active = False
        self.center_a1.save(update_fields=["is_active"])
        contract = self.make_contract("CON-INACTIVE-CENTER", self.province_a)
        self.assign(contract, self.center_a1)
        self.assign(contract, self.center_a2)
        self.assertEqual(self.scoped_ids(), {self.center_a2.pk})

    def test_legacy_contract_assignment_audit_is_read_only(self):
        contract = self.make_contract("CON-LEGACY-AUDIT", self.province_a)
        contract.centers.add(self.center_a1)
        output = StringIO()

        call_command("audit_contract_center_assignments", stdout=output)

        self.assertIn("CON-LEGACY-AUDIT", output.getvalue())
        self.assertEqual(
            ContractCenterAssignment.objects.filter(contract=contract).count(), 0
        )

    def test_contract_cannot_cover_a_center_in_another_province(self):
        contract = self.make_contract("CON-COVER", self.province_a)
        self.assign(contract, self.center_a1)
        self.assertTrue(contract.covers_center(self.center_a1))
        self.assertFalse(contract.covers_center(self.center_b))
        self.assertFalse(contract.covers_center(None))

    def test_province_admin_cannot_open_foreign_contract_or_contractor_edit_pages(self):
        from django.urls import reverse
        from apps.org.models import Contractor

        admin = User.objects.create_user(
            username="province-admin-scope-test",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=self.province_a,
        )
        foreign_contractor = Contractor.objects.create(name="پیمانکار صرفاً استان ب")
        foreign_contract = self.make_contract(
            "CON-FOREIGN-EDIT", self.province_b, contractor=foreign_contractor
        )
        client = Client()
        client.force_login(admin)

        contract_response = client.get(
            reverse("org:contract_update", args=[foreign_contract.pk])
        )
        contractor_response = client.get(
            reverse("org:contractor_update", args=[foreign_contractor.pk])
        )
        self.assertEqual(contract_response.status_code, 404)
        self.assertEqual(contractor_response.status_code, 404)
