"""Regression tests for organizational scope assignment in UserForm."""

from django.test import TestCase

from apps.accounts.forms import UserForm
from apps.accounts.models import User
from apps.org.models import Center, OrganizationalUnit


class UserFormOrganizationalScopeTests(TestCase):
    def setUp(self):
        national = OrganizationalUnit.objects.create(
            name="National", code="USER-FORM-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        self.province_a = OrganizationalUnit.objects.create(
            name="Province A", code="USER-FORM-PROV-A",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        self.province_b = OrganizationalUnit.objects.create(
            name="Province B", code="USER-FORM-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        self.county_a = OrganizationalUnit.objects.create(
            name="County A", code="USER-FORM-COUNTY-A",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_a,
        )
        self.county_b = OrganizationalUnit.objects.create(
            name="County B", code="USER-FORM-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province_b,
        )
        self.center_a1 = Center.objects.create(
            name="Center A1", code="USER-FORM-CENTER-A1", parent_unit=self.county_a,
        )
        self.center_a2 = Center.objects.create(
            name="Center A2", code="USER-FORM-CENTER-A2", parent_unit=self.county_a,
        )
        self.center_b = Center.objects.create(
            name="Center B", code="USER-FORM-CENTER-B", parent_unit=self.county_b,
        )
        self.province_admin = User.objects.create_user(
            username="user-form-province-admin",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=self.province_a,
        )
        self.country_admin = User.objects.create_user(
            username="user-form-country-admin",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_COUNTRY,
        )

    def _data(self, **overrides):
        data = {
            "username": "new-county-admin",
            "first_name": "County",
            "last_name": "Admin",
            "email": "",
            "role": User.ROLE_ADMIN_COUNTY,
            "org_unit": str(self.county_a.pk),
            "center": "",
            "personnel_code": "",
            "national_code": "",
            "phone": "",
            "job_title": "",
            "department": "",
            "contractor": "",
            "signature": "",
            "is_active": "on",
            "password1": "Strong!Ridge-Quartz-2026",
            "password2": "Strong!Ridge-Quartz-2026",
        }
        data.update(overrides)
        return data

    def test_province_admin_can_create_county_admin_for_selected_county(self):
        form = UserForm(
            data=self._data(),
            current_user=self.province_admin,
        )

        self.assertTrue(form.is_valid(), form.errors)
        county_admin = form.save()

        self.assertEqual(county_admin.org_unit_id, self.county_a.pk)
        self.assertEqual(
            set(county_admin.get_scoped_centers().values_list("pk", flat=True)),
            {self.center_a1.pk, self.center_a2.pk},
        )

    def test_county_is_derived_from_selected_center_when_not_explicit(self):
        form = UserForm(
            data=self._data(org_unit="", center=str(self.center_a1.pk)),
            current_user=self.province_admin,
        )

        self.assertTrue(form.is_valid(), form.errors)
        county_admin = form.save()

        self.assertEqual(county_admin.org_unit_id, self.county_a.pk)
        self.assertEqual(
            set(county_admin.get_scoped_centers().values_list("pk", flat=True)),
            {self.center_a1.pk, self.center_a2.pk},
        )

    def test_county_admin_cannot_be_bound_to_another_province_county(self):
        form = UserForm(
            data=self._data(org_unit=str(self.county_b.pk)),
            current_user=self.province_admin,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("org_unit", form.errors)

    def test_center_must_match_explicit_county_assignment(self):
        form = UserForm(
            data=self._data(center=str(self.center_a1.pk), org_unit=str(self.county_b.pk)),
            current_user=self.country_admin,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("center", form.errors)

    def test_county_admin_can_edit_user_without_exposing_org_unit_field(self):
        county_admin = User.objects.create_user(
            username="existing-county-admin",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_COUNTY,
            org_unit=self.county_a,
        )
        form_data = self._data(
            username="existing-county-admin",
            role=User.ROLE_ADMIN_COUNTY,
            org_unit="",
            password1="",
            password2="",
        )
        form = UserForm(
            data=form_data,
            instance=county_admin,
            current_user=county_admin,
        )

        self.assertNotIn("org_unit", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        updated_user = form.save()
        self.assertEqual(updated_user.org_unit_id, self.county_a.pk)

    def test_country_admin_can_assign_county_admin_to_active_county(self):
        form = UserForm(
            data=self._data(),
            current_user=self.country_admin,
        )

        self.assertTrue(form.is_valid(), form.errors)
        county_admin = form.save()

        self.assertEqual(county_admin.org_unit_id, self.county_a.pk)
