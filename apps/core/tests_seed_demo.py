"""Regression tests for the Sistan and Baluchestan demo seed."""
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.org.models import Center, Contract, ContractCenterAssignment, OrganizationalUnit


class DemoSeedProvinceTests(TestCase):
    def test_demo_seed_uses_only_the_active_rollout_province(self):
        call_command(
            "seed_demo",
            admin_password="Local-Demo-Only-Strong-Password-2026!",
            assets=1,
            no_demo_tickets=True,
        )

        province = OrganizationalUnit.objects.get(code="IR-PROV-111")
        self.assertEqual(province.name, "سیستان و بلوچستان")
        self.assertTrue(province.is_active)

        contract = Contract.objects.get(number="1403/IT/07")
        self.assertEqual(contract.province_id, province.pk)
        self.assertTrue(contract.is_provincial)

        demo_centers = Center.objects.filter(code__in=["DEMO-HQ-01", "DEMO-C-02", "DEMO-C-03"])
        self.assertEqual(demo_centers.count(), 3)
        self.assertTrue(demo_centers.filter(is_demo=True).count() == 3)
        self.assertFalse(
            demo_centers.exclude(parent_unit__parent=province).exists()
        )
        self.assertFalse(Center.objects.filter(is_demo=True).exclude(parent_unit__parent=province).exists())
        self.assertFalse(Center.objects.filter(is_demo=False, code__startswith="DEMO-").exists())

        province_admin = User.objects.get(username="admin.province")
        self.assertEqual(province_admin.org_unit_id, province.pk)
        self.assertTrue(province_admin.get_scoped_centers().filter(pk__in=demo_centers).count() == 3)

        technician = User.objects.get(username="tech.pars")
        for center in demo_centers:
            ContractCenterAssignment.objects.create(
                contract=contract, center=center,
                start_date=contract.start_date,
                status=ContractCenterAssignment.STATUS_ACTIVE,
                assigned_by=province_admin,
            )
        self.assertEqual(
            set(technician.get_scoped_centers().values_list("pk", flat=True)),
            set(demo_centers.values_list("pk", flat=True)),
        )

    def test_demo_seed_is_blocked_when_debug_is_disabled(self):
        from django.test import override_settings
        from django.core.management.base import CommandError

        with override_settings(DEBUG=False, RUNNING_TESTS=False):
            with self.assertRaises(CommandError):
                call_command(
                    "seed_demo",
                    admin_password="Local-Demo-Only-Strong-Password-2026!",
                    assets=1,
                    no_demo_tickets=True,
                )
