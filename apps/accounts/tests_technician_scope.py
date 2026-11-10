import datetime as dt

from django.test import TestCase
from django.utils import timezone

from apps.accounts.forms import UserForm
from apps.accounts.models import User
from apps.org.models import Center, Contract, Contractor, OrganizationalUnit


class TechnicianProvinceScopeTests(TestCase):
    def setUp(self):
        national = OrganizationalUnit.objects.create(
            name="National Scope", code="TECH-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        self.province_a = OrganizationalUnit.objects.create(
            name="Province A", code="TECH-PROV-A",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        self.province_b = OrganizationalUnit.objects.create(
            name="Province B", code="TECH-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_a = OrganizationalUnit.objects.create(
            name="County A", code="TECH-COUNTY-A",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_a,
        )
        county_b = OrganizationalUnit.objects.create(
            name="County B", code="TECH-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_b,
        )
        self.center_a = Center.objects.create(
            name="Center A", code="TECH-CENTER-A", parent_unit=county_a,
        )
        self.center_b = Center.objects.create(
            name="Center B", code="TECH-CENTER-B", parent_unit=county_b,
        )
        self.contractor = Contractor.objects.create(name="Multi Province Contractor")
        today = timezone.localdate()
        self.contract_a = Contract.objects.create(
            contractor=self.contractor, province=self.province_a,
            number="TECH-CONTRACT-A", title="Province A support",
            start_date=today - dt.timedelta(days=10),
            end_date=today + dt.timedelta(days=100),
        )
        self.contract_b = Contract.objects.create(
            contractor=self.contractor, province=self.province_b,
            number="TECH-CONTRACT-B", title="Province B support",
            start_date=today - dt.timedelta(days=10),
            end_date=today + dt.timedelta(days=100),
        )
        self.contract_a.centers.add(self.center_a)
        self.contract_b.centers.add(self.center_b)
        self.province_admin = User.objects.create_user(
            username="province-admin-a", password="test-password",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province_a,
        )

    def test_technician_scope_is_limited_to_assigned_province(self):
        technician = User.objects.create_user(
            username="technician-a", password="test-password",
            role=User.ROLE_TECHNICIAN, contractor=self.contractor,
            org_unit=self.province_a,
        )
        self.assertEqual(
            set(technician.get_active_contractor_contracts().values_list("pk", flat=True)),
            {self.contract_a.pk},
        )
        self.assertEqual(
            set(technician.get_scoped_centers().values_list("pk", flat=True)),
            {self.center_a.pk},
        )

    def test_legacy_unbound_technician_with_multi_province_contractor_fails_closed(self):
        technician = User.objects.create_user(
            username="legacy-technician", password="test-password",
            role=User.ROLE_TECHNICIAN, contractor=self.contractor,
        )
        self.assertFalse(technician.get_active_contractor_contracts().exists())
        self.assertFalse(technician.get_scoped_centers().exists())

    def test_province_admin_form_binds_new_technician_to_own_province(self):
        form = UserForm(
            data={
                "username": "created-technician",
                "first_name": "Test",
                "last_name": "Technician",
                "email": "",
                "role": User.ROLE_TECHNICIAN,
                "center": "",
                "personnel_code": "",
                "national_code": "",
                "phone": "",
                "job_title": "Technician",
                "department": "",
                "contractor": str(self.contractor.pk),
                "signature": "",
                "is_active": "on",
                "password1": "Strong!Ridge-Quartz-2026",
                "password2": "Strong!Ridge-Quartz-2026",
            },
            current_user=self.province_admin,
        )
        self.assertTrue(form.is_valid(), form.errors)
        technician = form.save()
        self.assertEqual(technician.org_unit_id, self.province_a.pk)
        self.assertEqual(
            set(technician.get_active_contractor_contracts().values_list("pk", flat=True)),
            {self.contract_a.pk},
        )
