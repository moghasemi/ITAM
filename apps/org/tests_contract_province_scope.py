from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.org.models import Center, Contract, Contractor, OrganizationalUnit


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

    def test_active_contract_grants_only_centers_in_its_province(self):
        self.make_contract("CON-A-1", self.province_a)
        self.assertEqual(self.scoped_ids(), {self.center_a1.pk, self.center_a2.pk})

    def test_multiple_active_contracts_in_same_province_are_supported(self):
        self.make_contract("CON-A-1", self.province_a)
        self.make_contract("CON-A-2", self.province_a)
        self.assertEqual(self.scoped_ids(), {self.center_a1.pk, self.center_a2.pk})

    def test_contracts_in_two_provinces_grant_only_those_two_provinces(self):
        self.make_contract("CON-A-1", self.province_a)
        self.make_contract("CON-B-1", self.province_b)
        self.assertEqual(
            self.scoped_ids(),
            {self.center_a1.pk, self.center_a2.pk, self.center_b.pk},
        )

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
        self.make_contract("CON-INACTIVE-CENTER", self.province_a)
        self.assertEqual(self.scoped_ids(), {self.center_a2.pk})

    def test_contract_cannot_cover_a_center_in_another_province(self):
        contract = self.make_contract("CON-COVER", self.province_a)
        self.assertTrue(contract.covers_center(self.center_a1))
        self.assertFalse(contract.covers_center(self.center_b))
        self.assertFalse(contract.covers_center(None))
