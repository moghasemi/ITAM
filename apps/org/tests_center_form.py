"""Regression tests for province-aware county selection in the center form."""

from django.test import TestCase

from apps.accounts.models import User
from apps.org.forms import CenterForm
from apps.org.models import Center, OrganizationalUnit


class CenterFormProvinceCountyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="ستاد آزمون فرم", code="CENTER-FORM-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        cls.province_a = OrganizationalUnit.objects.create(
            name="استان آزمایشی الف", code="CENTER-FORM-PROV-A",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        cls.province_b = OrganizationalUnit.objects.create(
            name="استان آزمایشی ب", code="CENTER-FORM-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        cls.county_a = OrganizationalUnit.objects.create(
            name="شهرستان الف", code="CENTER-FORM-COUNTY-A",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province_a,
        )
        cls.county_b = OrganizationalUnit.objects.create(
            name="شهرستان ب", code="CENTER-FORM-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province_b,
        )
        cls.country_admin = User.objects.create_user(
            username="center-form-country-admin",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_COUNTRY,
        )
        cls.province_admin = User.objects.create_user(
            username="center-form-province-admin",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=cls.province_a,
        )

    def test_county_choices_show_only_the_county_name(self):
        form = CenterForm(
            data={"province": str(self.province_a.pk)},
            user=self.country_admin,
        )

        self.assertEqual(
            form.fields["parent_unit"].label_from_instance(self.county_a),
            "شهرستان الف",
        )
        self.assertEqual(
            set(form.fields["parent_unit"].queryset.values_list("pk", flat=True)),
            {self.county_a.pk, self.county_b.pk},
        )
        rendered_counties = str(form["parent_unit"])
        self.assertIn(f'data-province-id="{self.province_a.pk}"', rendered_counties)
        self.assertIn(f'data-province-id="{self.province_b.pk}"', rendered_counties)

    def test_submitted_county_must_belong_to_submitted_province(self):
        form = CenterForm(
            data={
                "name": "مرکز خارج از استان",
                "code": "CENTER-FORM-CROSS-PROVINCE",
                "province": str(self.province_a.pk),
                "parent_unit": str(self.county_b.pk),
            },
            user=self.country_admin,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("parent_unit", form.errors)

    def test_province_admin_is_locked_to_own_province_and_counties(self):
        form = CenterForm(user=self.province_admin)

        self.assertTrue(form.fields["province"].disabled)
        self.assertEqual(
            list(form.fields["province"].queryset.values_list("pk", flat=True)),
            [self.province_a.pk],
        )
        self.assertEqual(
            list(form.fields["parent_unit"].queryset.values_list("pk", flat=True)),
            [self.county_a.pk],
        )

    def test_edit_form_preselects_the_centers_province(self):
        center = Center.objects.create(
            name="مرکز ویرایش آزمون",
            code="CENTER-FORM-EDIT",
            parent_unit=self.county_b,
        )

        form = CenterForm(instance=center, user=self.country_admin)

        self.assertEqual(form.fields["province"].initial, self.province_b.pk)
