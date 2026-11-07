"""آزمون‌های جامع انطباق حاکمیت معماری و امنیت سامانه ITAM."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import (
    AgentCredential,
    AgentNonce,
    AgentSyncAuditLog,
    Asset,
    AssetCategory,
)
from apps.org.models import Center, Contract, Contractor, Department, Location, OrganizationalUnit


class HWAgentSecurityTests(TestCase):
    """آزمون‌های امنیتی احراز هویت، انقیاد مرکز و جلوگیری از تکرار در اندپوینت HWAgent."""

    @classmethod
    def setUpTestData(cls):
        cls.category = AssetCategory.objects.create(name="رایانه رومیزی", code="PC", requires_component_tracking=True)
        cls.center_a = Center.objects.create(name="مرکز درمانی سینا", code="C-SINA", province="مرکزی")
        cls.center_b = Center.objects.create(name="مرکز درمانی امام رضا", code="C-REZA", province="مرکزی")

        cls.asset_a = Asset.objects.create(
            asset_tag="TAG-A01",
            title="کیس حسابداری سینا",
            category=cls.category,
            center=cls.center_a,
            hostname="PC-SINA-01",
            serial_number="MB-SINA-001",
            mac_address="AA:BB:CC:DD:EE:01",
        )
        cls.asset_b = Asset.objects.create(
            asset_tag="TAG-B01",
            title="کیس داروخانه رضا",
            category=cls.category,
            center=cls.center_b,
            hostname="PC-REZA-01",
            serial_number="MB-REZA-001",
            mac_address="AA:BB:CC:DD:EE:02",
        )

        cls.cred_a, cls.raw_token_a = AgentCredential.generate(cls.center_a, name="PC-SINA-01-Agent")

    def setUp(self):
        self.client = Client()
        self.payload = {
            "computerName": "PC-SINA-01",
            "os": "Windows 11 Pro",
            "baseboard": {"manufacturer": "ASUS", "product": "PRIME-B660", "serial": "MB-SINA-001"},
            "cpu": {"name": "Intel Core i7-12700", "cores": 12, "threads": 20, "speed": 2100},
            "ram": [{"slot": "DIMM 1", "capacityGB": 16, "speedMHz": 3200, "manufacturer": "Corsair", "partNumber": "CMK16G", "serial": "RAM-01"}],
            "disks": [{"name": "Samsung 980 1TB", "mediaType": "NVMe", "sizeGB": 1000, "serial": "SAMS-001"}],
            "network": [{"name": "Ethernet", "mac": "AA:BB:CC:DD:EE:01"}],
        }

    def _auth_headers(self, token, timestamp=None, nonce=None):
        ts = timestamp or timezone.now().isoformat()
        nc = nonce or str(uuid.uuid4())
        return {
            "HTTP_AUTHORIZATION": f"Bearer {token}",
            "HTTP_X_ITAM_TIMESTAMP": ts,
            "HTTP_X_ITAM_NONCE": nc,
        }

    def test_unauthenticated_request_rejected_401(self):
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("error", resp.json())

    def test_invalid_token_rejected_401(self):
        headers = self._auth_headers("itam_agt_invalid_dummy_token_99999999999999999")
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 401)

    def test_revoked_token_rejected_401(self):
        self.cred_a.revoke(reason="تست ابطال")
        headers = self._auth_headers(self.raw_token_a)
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 401)

    def test_expired_token_rejected_401(self):
        self.cred_a.expires_at = timezone.now() - timedelta(days=1)
        self.cred_a.save()
        headers = self._auth_headers(self.raw_token_a)
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 401)

    def test_missing_timestamp_rejected_401(self):
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {self.raw_token_a}",
            "HTTP_X_ITAM_NONCE": str(uuid.uuid4()),
        }
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 401)

    def test_timestamp_skew_rejected_401(self):
        skewed_time = (timezone.now() - timedelta(seconds=350)).isoformat()
        headers = self._auth_headers(self.raw_token_a, timestamp=skewed_time)
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Clock skew", resp.json()["error"])

    def test_replayed_nonce_rejected_401(self):
        nonce = str(uuid.uuid4())
        headers = self._auth_headers(self.raw_token_a, nonce=nonce)

        # درخواست اول باید موفق باشد
        resp1 = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp1.status_code, 200)

        # درخواست دوم با همان Nonce باید به عنوان حمله تکرار مسدود شود
        resp2 = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp2.status_code, 401)
        self.assertIn("Replay attack", resp2.json()["error"])

    def test_cross_center_matching_prevented(self):
        """ایجنت مرکز A با ارسال تگ و سریال دارایی مرکز B نباید دارایی مرکز B را بیابد یا تغییر دهد."""
        cross_payload = dict(self.payload)
        cross_payload["computerName"] = "PC-REZA-01"
        cross_payload["baseboard"] = {"serial": "MB-REZA-001"}
        cross_payload["network"] = [{"name": "Ethernet", "mac": "AA:BB:CC:DD:EE:02"}]

        headers = self._auth_headers(self.raw_token_a)
        resp = self.client.post(
            "/api/v1/hardware/agent-sync/?asset_tag=TAG-B01",
            data=json.dumps(cross_payload),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(resp.status_code, 404)

        # دارایی مرکز B باید دست‌نخورده باقی بماند
        self.asset_b.refresh_from_db()
        self.assertIsNone(self.asset_b.current_snapshot)

    def test_client_supplied_center_ignored(self):
        """شناسه center ارسالی در Payload نادیده گرفته شده و مرکز اختصاصی ایجنت اعمال می‌شود."""
        tampered_payload = dict(self.payload)
        tampered_payload["center"] = self.center_b.pk
        tampered_payload["center_id"] = self.center_b.pk

        headers = self._auth_headers(self.raw_token_a)
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(tampered_payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 200)

        # دارایی به‌روزرسانی‌شده متعلق به مرکز A است
        self.asset_a.refresh_from_db()
        self.assertEqual(self.asset_a.center, self.center_a)
        self.assertEqual(self.asset_a.snapshots.count(), 1)
        self.assertEqual(self.asset_a.snapshots.first().status, "pending")

    def test_audit_log_recorded(self):
        headers = self._auth_headers(self.raw_token_a)
        self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)

        log = AgentSyncAuditLog.objects.filter(agent=self.cred_a).first()
        self.assertIsNotNone(log)
        self.assertTrue(log.success)
        self.assertEqual(log.http_status, 200)
        self.assertTrue(len(log.payload_hash) == 64)

    def test_token_rotation(self):
        old_hash = self.cred_a.token_hash
        new_cred, new_raw_token = self.cred_a.rotate()

        self.cred_a.refresh_from_db()
        self.assertEqual(self.cred_a.status, AgentCredential.STATUS_REVOKED)

        self.assertEqual(new_cred.status, AgentCredential.STATUS_ACTIVE)
        self.assertNotEqual(new_cred.token_hash, old_hash)

        # توکن جدید باید کار کند
        headers = self._auth_headers(new_raw_token)
        resp = self.client.post("/api/v1/hardware/agent-sync/", data=json.dumps(self.payload), content_type="application/json", **headers)
        self.assertEqual(resp.status_code, 200)


class OrganizationalHierarchyTests(TestCase):
    """آزمون‌های ساختار سازمانی چهارسطحی و روابط سلسله‌مراتبی."""

    def test_valid_four_level_hierarchy(self):
        # ۱. سطح کشوری
        national = OrganizationalUnit.objects.create(name="ستاد مرکزی وزارت", code="OU-NAT-01", unit_type=OrganizationalUnit.UNIT_NATIONAL)
        national.clean()

        # ۲. سطح استانی
        province = OrganizationalUnit.objects.create(name="دانشگاه علوم پزشکی مرکزی", code="OU-PRV-MARKAZI", unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national)
        province.clean()

        # ۳. سطح شهرستانی
        county = OrganizationalUnit.objects.create(name="شبکه بهداشت شهرستان اراک", code="OU-CNTY-ARAK", unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province)
        county.clean()

        # ۴. مرکز عملیاتی تابعه
        center = Center.objects.create(name="بیمارستان حضرت ولی‌عصر (عج)", code="C-VALIASR", parent_unit=county, province="مرکزی")
        center.clean()

        self.assertEqual(center.province_name, "دانشگاه علوم پزشکی مرکزی")
        self.assertEqual(center.county_name, "شبکه بهداشت شهرستان اراک")

    def test_circular_parent_rejected(self):
        ou1 = OrganizationalUnit.objects.create(name="واحد اول", code="OU-01", unit_type=OrganizationalUnit.UNIT_NATIONAL)
        ou2 = OrganizationalUnit.objects.create(name="واحد دوم", code="OU-02", unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=ou1)

        # تلاش برای تبدیل ou1 به فرزند ou2
        ou1.parent = ou2
        with self.assertRaises(ValidationError):
            ou1.clean()

    def test_invalid_parent_unit_type_rejected(self):
        national = OrganizationalUnit.objects.create(name="ستاد کشوری", code="OU-N1", unit_type=OrganizationalUnit.UNIT_NATIONAL)

        # تلاش برای اتصال مستقیم شهرستان به کشوری بدون استان
        county = OrganizationalUnit.objects.create(name="شهرستان بدون استان", code="OU-C1", unit_type=OrganizationalUnit.UNIT_COUNTY, parent=national)
        with self.assertRaises(ValidationError):
            county.clean()

    def test_center_parent_unit_must_be_county(self):
        province = OrganizationalUnit.objects.create(name="استان", code="OU-P1", unit_type=OrganizationalUnit.UNIT_PROVINCE)
        center = Center.objects.create(name="مرکز با والد غیرشهرستانی", code="C-ERR", parent_unit=province)
        with self.assertRaises(ValidationError):
            center.clean()


class RBACAndDataIsolationTests(TestCase):
    """آزمون‌های جداسازی داده‌ها بین مراکز، سطوح استانی و جلوگیری از ترفیع امتیاز."""

    @classmethod
    def setUpTestData(cls):
        cls.category = AssetCategory.objects.create(name="سرور", code="SRV")

        cls.national_unit = OrganizationalUnit.objects.create(name="ستاد کشوری", code="OU-NAT", unit_type=OrganizationalUnit.UNIT_NATIONAL)
        cls.province_markazi = OrganizationalUnit.objects.create(name="استان مرکزی", code="OU-PRV-MKZ", unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=cls.national_unit)
        cls.county_arak = OrganizationalUnit.objects.create(name="شهرستان اراک", code="OU-CNTY-ARK", unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province_markazi)

        cls.province_tehran = OrganizationalUnit.objects.create(name="استان تهران", code="OU-PRV-TEH", unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=cls.national_unit)
        cls.county_shemiran = OrganizationalUnit.objects.create(name="شهرستان شمیرانات", code="OU-CNTY-SHM", unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province_tehran)

        cls.center_arak = Center.objects.create(name="مرکز بهداشت اراک", code="C-ARAK", parent_unit=cls.county_arak, province="مرکزی")
        cls.center_tehran = Center.objects.create(name="بیمارستان تجریش", code="C-TAJRISH", parent_unit=cls.county_shemiran, province="تهران")

        # کاربران
        cls.user_country_admin = User.objects.create_user(
            username="admin_country", password="password123", role=User.ROLE_ADMIN_COUNTRY
        )
        cls.user_province_markazi = User.objects.create_user(
            username="admin_prv_mkz", password="password123", role=User.ROLE_ADMIN_PROVINCE, org_unit=cls.province_markazi
        )
        cls.user_it_arak = User.objects.create_user(
            username="it_arak", password="password123", role=User.ROLE_ADMIN_IT, center=cls.center_arak
        )
        cls.user_it_tehran = User.objects.create_user(
            username="it_tehran", password="password123", role=User.ROLE_ADMIN_IT, center=cls.center_tehran
        )
        cls.user_requester_arak = User.objects.create_user(
            username="req_arak", password="password123", role=User.ROLE_REQUESTER, center=cls.center_arak
        )

        cls.asset_arak = Asset.objects.create(asset_tag="SRV-ARAK-01", title="سرور شبکه اراک", category=cls.category, center=cls.center_arak)
        cls.asset_tehran = Asset.objects.create(asset_tag="SRV-TEH-01", title="سرور بیمارستان تجریش", category=cls.category, center=cls.center_tehran)

    def test_center_it_cannot_view_other_center_asset_returns_404(self):
        self.client.login(username="it_arak", password="password123")
        resp = self.client.get(f"/assets/{self.asset_tehran.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_center_it_cannot_update_other_center_asset_returns_404(self):
        self.client.login(username="it_arak", password="password123")
        resp = self.client.get(f"/assets/{self.asset_tehran.pk}/edit/")
        self.assertEqual(resp.status_code, 404)

        post_resp = self.client.post(f"/assets/{self.asset_tehran.pk}/edit/", {"title": "تغییر غیرمجاز"})
        self.assertEqual(post_resp.status_code, 404)

    def test_center_it_cannot_view_other_center_user_returns_404(self):
        self.client.login(username="it_arak", password="password123")
        resp = self.client.get(f"/accounts/users/{self.user_it_tehran.pk}/edit/")
        self.assertEqual(resp.status_code, 404)

    def test_center_it_cannot_reset_password_of_other_center_user(self):
        self.client.login(username="it_arak", password="password123")
        resp = self.client.get(f"/accounts/users/{self.user_it_tehran.pk}/password/")
        self.assertEqual(resp.status_code, 404)

    def test_center_it_cannot_escalate_user_role(self):
        """کارشناس IT مرکز نباید بتواند کاربر را به مدیر استان یا کشور ارتقا دهد."""
        self.client.login(username="it_arak", password="password123")
        resp = self.client.post(
            f"/accounts/users/{self.user_requester_arak.pk}/edit/",
            {
                "username": self.user_requester_arak.username,
                "first_name": "کاربر",
                "last_name": "تست",
                "role": User.ROLE_ADMIN_PROVINCE,  # تلاش برای ارتقا به مدیر استان
                "center": self.center_arak.pk,
            },
        )
        self.assertEqual(resp.status_code, 200)  # فرم با خطا بازگردانده می‌شود
        self.user_requester_arak.refresh_from_db()
        self.assertNotEqual(self.user_requester_arak.role, User.ROLE_ADMIN_PROVINCE)

    def test_province_admin_cannot_access_other_province_center_returns_404(self):
        self.client.login(username="admin_prv_mkz", password="password123")
        resp = self.client.get(f"/org/centers/{self.center_tehran.pk}/edit/")
        self.assertEqual(resp.status_code, 404)

    def test_unauthorized_user_cannot_create_center_returns_403(self):
        """کارشناس مرکز یا کاربر متقاضی نباید بتوانند مرکز جدید ایجاد کنند."""
        self.client.login(username="it_arak", password="password123")
        resp = self.client.get("/org/centers/add/")
        self.assertEqual(resp.status_code, 403)

    def test_unauthorized_user_cannot_create_contract_returns_403(self):
        self.client.login(username="it_arak", password="password123")
        resp = self.client.get("/org/contracts/add/")
        self.assertEqual(resp.status_code, 403)


class DataReconciliationCommandTests(TestCase):
    """آزمون‌های فرمان تطبیق داده‌های فاقد مرکز و حفظ ثبات داده‌ها."""

    def test_dry_run_makes_no_db_changes(self):
        from django.core.management import call_command

        category = AssetCategory.objects.create(name="مانیتور", code="MON")
        center = Center.objects.create(name="مرکز نمونه", code="C-SMP", province="مرکزی")
        loc = Location.objects.create(name="اتاق سرور", center=center)

        # ایجاد دارایی بدون مرکز با لوکیشن دارای مرکز
        asset = Asset.objects.create(asset_tag="MON-001", title="مانیتور بدون مرکز", category=category, location=loc, center=None)

        call_command("reconcile_organizational_data", dry_run=True)

        asset.refresh_from_db()
        self.assertIsNone(asset.center)  # در حالت dry-run نباید تغییر کند

    def test_orphaned_records_inventory_and_quarantine(self):
        from django.core.management import call_command

        category = AssetCategory.objects.create(name="پرینتر", code="PRN")
        asset = Asset.objects.create(asset_tag="PRN-001", title="پرینتر بدون هیچ رابطه", category=category, center=None)

        call_command("reconcile_organizational_data", apply=True, dry_run=False)

        asset.refresh_from_db()
        self.assertTrue(asset.is_quarantined)
        self.assertIn("قرنطینه", asset.quarantine_notes)
