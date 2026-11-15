"""Regression tests for read-only, center-scoped contract visibility."""

import datetime as dt

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.org.models import (
    Center,
    Contract,
    ContractCenterAssignment,
    Contractor,
    OrganizationalUnit,
)
from apps.org.views import _visible_contracts_for_user


class CenterContractReadOnlyAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="ستاد قرارداد", code="CONTRACT-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        cls.province = OrganizationalUnit.objects.create(
            name="استان قرارداد", code="CONTRACT-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شهرستان قرارداد", code="CONTRACT-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province,
        )
        cls.center = Center.objects.create(
            name="مرکز دارای قرارداد", code="CONTRACT-CENTER-1", parent_unit=county,
        )
        cls.other_center = Center.objects.create(
            name="مرکز دیگر استان", code="CONTRACT-CENTER-2", parent_unit=county,
        )
        cls.province_admin = User.objects.create_user(
            username="contract-province-admin",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=cls.province,
        )
        cls.center_it = User.objects.create_user(
            username="contract-center-it",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
            center=cls.center,
        )
        contractor = Contractor.objects.create(name="پیمانکار قرارداد آزمایشی")
        today = timezone.localdate()
        cls.assigned_contract = Contract.objects.create(
            contractor=contractor,
            province=cls.province,
            number="CONTRACT-001",
            title="قرارداد مرکز اول",
            start_date=today,
            end_date=today + dt.timedelta(days=90),
            visit_interval_days=30,
            visit_scope="بازدید دوره‌ای تجهیزات مرکز",
            repair_scope="تعمیر تجهیزات تحت پوشش",
        )
        cls.other_contract = Contract.objects.create(
            contractor=contractor,
            province=cls.province,
            number="CONTRACT-002",
            title="قرارداد مرکز دوم",
            start_date=today,
            end_date=today + dt.timedelta(days=90),
        )
        ContractCenterAssignment.objects.create(
            contract=cls.assigned_contract,
            center=cls.center,
            start_date=today,
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=cls.province_admin,
        )
        ContractCenterAssignment.objects.create(
            contract=cls.other_contract,
            center=cls.other_center,
            start_date=today,
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=cls.province_admin,
        )

    def test_center_it_sees_only_contracts_assigned_to_its_center(self):
        visible_ids = set(
            _visible_contracts_for_user(self.center_it).values_list("pk", flat=True)
        )
        self.assertEqual(visible_ids, {self.assigned_contract.pk})

    def test_center_it_can_read_assigned_contract_details_only(self):
        self.client.force_login(self.center_it)
        response = self.client.get(
            reverse("org:contract_detail", args=[self.assigned_contract.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "بازدید دوره‌ای تجهیزات مرکز")
        self.assertContains(response, "تعمیر تجهیزات تحت پوشش")

        out_of_scope = self.client.get(
            reverse("org:contract_detail", args=[self.other_contract.pk])
        )
        self.assertEqual(out_of_scope.status_code, 404)

    def test_center_it_cannot_create_edit_or_schedule_contracts(self):
        self.client.force_login(self.center_it)
        self.assertEqual(
            self.client.get(reverse("org:contract_create")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("org:contract_update", args=[self.assigned_contract.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("org:contract_update", args=[self.assigned_contract.pk]),
                {"title": "تغییر غیرمجاز"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("org:contract_generate_visits", args=[self.assigned_contract.pk])
            ).status_code,
            403,
        )

    def test_center_it_contract_pages_hide_write_controls(self):
        self.client.force_login(self.center_it)
        list_response = self.client.get(reverse("org:contract_list"))
        detail_response = self.client.get(
            reverse("org:contract_detail", args=[self.assigned_contract.pk])
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(list_response, "ثبت قرارداد")
        self.assertNotContains(list_response, "ویرایش")
        self.assertNotContains(detail_response, "ویرایش قرارداد")
        self.assertNotContains(detail_response, "برنامه‌ریزی بازدیدهای دوره‌ای")

    def test_province_admin_retains_province_wide_contract_access_and_management(self):
        visible_ids = set(
            _visible_contracts_for_user(self.province_admin).values_list("pk", flat=True)
        )
        self.assertEqual(
            visible_ids,
            {self.assigned_contract.pk, self.other_contract.pk},
        )
        self.client.force_login(self.province_admin)
        self.assertEqual(
            self.client.get(reverse("org:contract_create")).status_code, 200
        )
