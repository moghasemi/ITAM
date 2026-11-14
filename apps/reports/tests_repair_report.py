from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.maintenance.repair_models import IndependentRepairer
from apps.maintenance.repair_services import create_repair_request
from apps.org.models import Center, OrganizationalUnit


class RepairPerformanceReportTests(TestCase):
    def setUp(self):
        national = OrganizationalUnit.objects.create(
            name="ستاد گزارش", code="RPT-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        self.province = OrganizationalUnit.objects.create(
            name="استان گزارش", code="RPT-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شهرستان گزارش", code="RPT-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province,
        )
        self.center = Center.objects.create(
            name="مرکز گزارش", code="RPT-CENTER", parent_unit=county,
        )
        self.province_admin = User.objects.create_user(
            username="rpt-province-admin", password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province,
        )
        self.expert = User.objects.create_user(
            username="rpt-center-it", password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT, center=self.center,
        )
        self.requester = User.objects.create_user(
            username="rpt-requester", password="Strong-Test-Password-2026!",
            role=User.ROLE_REQUESTER, center=self.center,
        )
        category = AssetCategory.objects.create(name="رایانه گزارش", code="RPT-PC")
        self.asset = Asset.objects.create(
            asset_tag="RPT-ASSET-001", title="کیس گزارش",
            category=category, center=self.center,
        )
        self.repairer = IndependentRepairer.objects.create(
            province=self.province,
            kind=IndependentRepairer.KIND_COMPANY,
            name="تعمیرکار گزارش نمونه",
            created_by=self.expert,
        )

    def test_report_aggregates_repair_costs_and_feedback_within_user_scope(self):
        repair = create_repair_request(
            center=self.center, asset=self.asset, repairer=self.repairer,
            fault_description="خرابی نمونه", referral_reason="ارجاع نمونه",
            estimate_amount=Decimal("1200000"), actor=self.expert,
        )

        self.client.force_login(self.province_admin)
        response = self.client.get(reverse("reports:repairs"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["total"], 1)
        self.assertEqual(response.context["rows"][0]["request_count"], 1)
        self.assertEqual(response.context["rows"][0]["estimate_total"], Decimal("1200000"))
        self.assertContains(response, "تعمیرکار گزارش نمونه")
        self.assertTrue(repair.pk)
