from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset
from apps.maintenance.repair_models import GeneralITRequest, GeneralReferral, RepairRequest
from apps.org.models import Center, ContractCenterAssignment
from apps.tickets.models import Ticket


class SistanBaluchestanDemoSeedTests(TestCase):
    def test_seed_creates_complete_synthetic_province_fixture_and_is_idempotent(self):
        password = "Demo-Only-Password-2026!Strong"
        call_command("seed_sistan_demo", admin_password=password, assets_per_center=4)

        self.assertEqual(Center.objects.filter(code__startswith="DEMO-SB-").count(), 10)
        self.assertEqual(Asset.objects.filter(asset_tag__startswith="DEMO-SB-").count(), 40)
        self.assertEqual(
            ContractCenterAssignment.objects.filter(
                center__code__startswith="DEMO-SB-",
                status=ContractCenterAssignment.STATUS_ACTIVE,
            ).count(),
            9,
        )
        self.assertEqual(RepairRequest.objects.filter(number__startswith="DEMO-RR-").count(), 4)
        self.assertEqual(GeneralITRequest.objects.filter(number__startswith="DEMO-ITR-").count(), 2)
        self.assertEqual(GeneralReferral.objects.filter(subject="اختلاف هزینه تعمیر نمونه").count(), 1)
        self.assertEqual(Ticket.objects.filter(title="[DEMO] خرابی سخت‌افزاری نمونه").count(), 1)

        call_command("seed_sistan_demo", admin_password=password, assets_per_center=4)

        self.assertEqual(Center.objects.filter(code__startswith="DEMO-SB-").count(), 10)
        self.assertEqual(Asset.objects.filter(asset_tag__startswith="DEMO-SB-").count(), 40)
        self.assertEqual(RepairRequest.objects.filter(number__startswith="DEMO-RR-").count(), 4)
        self.assertEqual(GeneralITRequest.objects.filter(number__startswith="DEMO-ITR-").count(), 2)
