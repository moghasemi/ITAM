"""Regression tests for scope-aware report filters and dashboard totals."""
import datetime as dt

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory, HardwareSnapshot
from apps.org.models import (
    Center,
    Contract,
    ContractCenterAssignment,
    Contractor,
    OrganizationalUnit,
)
from apps.reports.forms import ReportFilterForm


class ReportContractScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="ستاد گزارش دامنه", code="RPT-SCOPE-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        cls.province = OrganizationalUnit.objects.create(
            name="استان گزارش دامنه", code="RPT-SCOPE-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شهرستان گزارش دامنه", code="RPT-SCOPE-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province,
        )
        cls.center_a = Center.objects.create(
            name="مرکز گزارش الف", code="RPT-SCOPE-A", parent_unit=county,
        )
        cls.center_b = Center.objects.create(
            name="مرکز گزارش ب", code="RPT-SCOPE-B", parent_unit=county,
        )
        cls.province_admin = User.objects.create_user(
            username="rpt-scope-province",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=cls.province,
        )
        cls.center_it = User.objects.create_user(
            username="rpt-scope-center",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
            center=cls.center_a,
        )
        today = timezone.localdate()
        contractor_a = Contractor.objects.create(name="پیمانکار گزارش الف")
        contractor_b = Contractor.objects.create(name="پیمانکار گزارش ب")
        cls.contract_a = Contract.objects.create(
            contractor=contractor_a,
            province=cls.province,
            number="RPT-SCOPE-001",
            title="قرارداد مرکز الف",
            start_date=today - dt.timedelta(days=1),
            end_date=today + dt.timedelta(days=90),
            visit_interval_days=30,
            visit_scope="بازدید دوره‌ای",
            repair_scope="تعمیر تجهیزات",
        )
        cls.contract_b = Contract.objects.create(
            contractor=contractor_b,
            province=cls.province,
            number="RPT-SCOPE-002",
            title="قرارداد مرکز ب",
            start_date=today - dt.timedelta(days=1),
            end_date=today + dt.timedelta(days=90),
            visit_interval_days=30,
            visit_scope="بازدید دوره‌ای",
            repair_scope="تعمیر تجهیزات",
        )
        ContractCenterAssignment.objects.create(
            contract=cls.contract_a,
            center=cls.center_a,
            start_date=today,
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=cls.province_admin,
        )
        ContractCenterAssignment.objects.create(
            contract=cls.contract_b,
            center=cls.center_b,
            start_date=today,
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=cls.province_admin,
        )
        category = AssetCategory.objects.create(
            name="گروه گزارش دامنه", code="RPT-SCOPE-CAT"
        )
        cls.asset = Asset.objects.create(
            asset_tag="RPT-SCOPE-ASSET",
            title="دارایی گزارش دامنه",
            category=category,
            center=cls.center_a,
        )
        HardwareSnapshot.objects.create(
            asset=cls.asset,
            version=1,
            diff_data={"removed": 0, "replaced": 0, "has_alarm": False},
        )
        HardwareSnapshot.objects.create(
            asset=cls.asset,
            version=2,
            diff_data={"removed": 1, "replaced": 0, "has_alarm": True},
        )

    def test_center_it_report_filters_only_include_explicitly_assigned_contracts(self):
        form = ReportFilterForm(user=self.center_it)
        contract_ids = set(
            form.fields["contract"].queryset.values_list("pk", flat=True)
        )
        contractor_ids = set(
            form.fields["contractor"].queryset.values_list("pk", flat=True)
        )
        self.assertEqual(contract_ids, {self.contract_a.pk})
        self.assertEqual(contractor_ids, {self.contract_a.contractor_id})

    def test_province_admin_retains_province_wide_report_contract_filters(self):
        form = ReportFilterForm(user=self.province_admin)
        contract_ids = set(
            form.fields["contract"].queryset.values_list("pk", flat=True)
        )
        self.assertEqual(contract_ids, {self.contract_a.pk, self.contract_b.pk})

    def test_dashboard_counts_only_visible_active_contracts_and_real_diff_alarms(self):
        self.client.force_login(self.center_it)
        response = self.client.get(reverse("reports:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["contracts_active"], 1)
        self.assertEqual(response.context["diff_alarms"], 1)
