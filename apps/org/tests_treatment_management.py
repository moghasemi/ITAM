from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.org.models import Center, ContractCenterAssignment, OrganizationalUnit, TreatmentManagement


class TreatmentManagementSeparationTests(TestCase):
    def setUp(self):
        national = OrganizationalUnit.objects.create(
            name="ستاد کشوری", code="TM-NAT-TEST",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        self.province_a = OrganizationalUnit.objects.create(
            name="استان الف", code="TM-PROV-A",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        self.province_b = OrganizationalUnit.objects.create(
            name="استان ب", code="TM-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        self.county_a = OrganizationalUnit.objects.create(
            name="شهرستان الف", code="TM-COUNTY-A",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_a,
        )
        self.county_b = OrganizationalUnit.objects.create(
            name="شهرستان ب", code="TM-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_b,
        )

    def test_center_gets_separate_treatment_management_and_geography(self):
        center = Center.objects.create(
            name="مرکز آزمون الف", code="TM-CENTER-A", parent_unit=self.county_a
        )

        self.assertEqual(center.parent_unit_id, self.county_a.pk)
        self.assertEqual(center.treatment_management.province_id, self.province_a.pk)
        self.assertEqual(
            TreatmentManagement.objects.filter(province=self.province_a).count(), 1
        )

    def test_one_management_unit_per_province_is_reused(self):
        first = Center.objects.create(
            name="مرکز اول", code="TM-CENTER-1", parent_unit=self.county_a
        )
        second = Center.objects.create(
            name="مرکز دوم", code="TM-CENTER-2", parent_unit=self.county_a
        )

        self.assertEqual(first.treatment_management_id, second.treatment_management_id)
        self.assertEqual(TreatmentManagement.objects.filter(province=self.province_a).count(), 1)

    def test_center_cannot_be_assigned_to_another_provinces_management(self):
        center_a = Center.objects.create(
            name="مرکز استان الف", code="TM-CENTER-3", parent_unit=self.county_a
        )
        center_b = Center.objects.create(
            name="مرکز استان ب", code="TM-CENTER-4", parent_unit=self.county_b
        )
        center_a.treatment_management = center_b.treatment_management

        with self.assertRaises(ValidationError):
            center_a.full_clean()

    def test_contract_coverage_uses_treatment_management_province(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.org.models import Contract, Contractor

        center = Center.objects.create(
            name="مرکز قرارداد", code="TM-CENTER-5", parent_unit=self.county_a
        )
        contractor = Contractor.objects.create(name="پیمانکار مدیریت درمان")
        today = timezone.localdate()
        contract = Contract.objects.create(
            contractor=contractor,
            province=self.province_a,
            number="TM-CONTRACT-1",
            title="قرارداد آزمون",
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        actor = User.objects.create_user(
            username="tm-province-admin", password="TestPass!9382",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province_a,
        )
        ContractCenterAssignment.objects.create(
            contract=contract, center=center, start_date=today,
            status=ContractCenterAssignment.STATUS_ACTIVE, assigned_by=actor,
        )

        self.assertTrue(contract.covers_center(center))
        self.assertFalse(contract.covers_center(None))

    def test_contract_does_not_cover_orphan_center_with_owner_only(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.org.models import Contract, Contractor

        center = Center.objects.create(
            name="مرکز بدون شهرستان", code="TM-CENTER-ORPHAN", parent_unit=self.county_a
        )
        contractor = Contractor.objects.create(name="پیمانکار مرکز یتیم")
        today = timezone.localdate()
        contract = Contract.objects.create(
            contractor=contractor,
            province=self.province_a,
            number="TM-CONTRACT-ORPHAN",
            title="قرارداد مرکز یتیم",
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        actor = User.objects.create_user(
            username="tm-orphan-province-admin", password="TestPass!9382",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province_a,
        )
        ContractCenterAssignment.objects.create(
            contract=contract, center=center, start_date=today,
            status=ContractCenterAssignment.STATUS_ACTIVE, assigned_by=actor,
        )

        # Simulate a legacy orphan record without invoking Center.save().
        Center.objects.filter(pk=center.pk).update(parent_unit=None)
        center.refresh_from_db()

        self.assertIsNotNone(center.treatment_management_id)
        self.assertFalse(contract.covers_center(center))

    def test_county_cannot_move_while_its_centers_keep_old_treatment_owner(self):
        Center.objects.create(
            name="مرکز شهرستان در حال انتقال", code="TM-CENTER-MOVE",
            parent_unit=self.county_a,
        )
        self.county_a.parent = self.province_b

        with self.assertRaises(ValidationError):
            self.county_a.full_clean()

    def test_treatment_management_cannot_move_away_from_attached_centers(self):
        center = Center.objects.create(
            name="مرکز مدیریت درمان ثابت", code="TM-CENTER-TM-MOVE",
            parent_unit=self.county_a,
        )
        management = center.treatment_management
        management.province = self.province_b

        with self.assertRaises(ValidationError):
            management.full_clean()

    def test_scoped_center_access_fails_closed_on_geography_owner_mismatch(self):
        center_a = Center.objects.create(
            name="مرکز ناسازگاری دامنه", code="TM-CENTER-SCOPE-MISMATCH",
            parent_unit=self.county_a,
        )
        center_b = Center.objects.create(
            name="مرکز استان مقصد", code="TM-CENTER-SCOPE-DEST",
            parent_unit=self.county_b,
        )
        # Simulate a legacy/corrupted row that bypassed model validation.
        Center.objects.filter(pk=center_a.pk).update(
            treatment_management_id=center_b.treatment_management_id
        )
        center_user = User.objects.create_user(
            username="tm-scope-center-user", password="TestPass!9382",
            role=User.ROLE_ADMIN_IT, center=center_a,
        )

        self.assertNotIn(
            center_a.pk,
            center_user.get_scoped_centers().values_list("pk", flat=True),
        )
