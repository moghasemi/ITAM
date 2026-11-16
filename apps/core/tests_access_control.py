"""Regression tests for global administration and audit-log authorization."""

from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.views import visible_users
from apps.core.models import AuditLog, SystemSetting
from apps.org.models import OrganizationalUnit


class GlobalSettingsAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.center_it = User.objects.create_user(
            username="center-it-settings",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
        )
        cls.country_admin = User.objects.create_user(
            username="country-admin-settings",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_COUNTRY,
        )

    def test_center_it_cannot_access_global_settings_or_holidays(self):
        self.client.login(username="center-it-settings", password="Strong-Test-Password-2026!")
        paths = (
            "/settings/",
            "/settings/holidays/",
            "/settings/holidays/add/",
            "/settings/holidays/1/edit/",
            "/settings/holidays/1/delete/",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_center_it_cannot_mutate_global_settings_or_holidays(self):
        self.client.login(username="center-it-settings", password="Strong-Test-Password-2026!")
        settings_response = self.client.post("/settings/", {"org_name": "تغییر غیرمجاز"})
        holiday_response = self.client.post(
            "/settings/holidays/add/",
            {"title": "تعطیلی غیرمجاز", "date": "2026-12-01"},
        )
        delete_response = self.client.post("/settings/holidays/1/delete/")

        self.assertEqual(settings_response.status_code, 403)
        self.assertEqual(holiday_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertFalse(SystemSetting.objects.exists())

    def test_country_admin_can_access_global_settings(self):
        self.client.login(username="country-admin-settings", password="Strong-Test-Password-2026!")
        self.assertEqual(self.client.get("/settings/").status_code, 200)
        self.assertEqual(self.client.get("/settings/holidays/").status_code, 200)


class AuditLogOrganizationalScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="National Audit Test",
            code="AUD-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        cls.province_a = OrganizationalUnit.objects.create(
            name="Province A",
            code="AUD-PROV-A",
            unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=national,
        )
        cls.province_b = OrganizationalUnit.objects.create(
            name="Province B",
            code="AUD-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=national,
        )
        cls.province_admin = User.objects.create_user(
            username="province-admin-audit",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=cls.province_a,
        )
        cls.county_a = OrganizationalUnit.objects.create(
            name="County A", code="AUD-COUNTY-A",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province_a,
        )
        cls.county_admin = User.objects.create_user(
            username="county-admin-audit",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_COUNTY,
            org_unit=cls.county_a,
        )
        cls.county_actor = User.objects.create_user(
            username="county-actor-audit",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_REQUESTER,
            org_unit=cls.county_a,
        )
        actor_a = User.objects.create_user(
            username="actor-province-a",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
            org_unit=cls.province_a,
        )
        actor_b = User.objects.create_user(
            username="actor-province-b",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
            org_unit=cls.province_b,
        )
        cls.log_a = AuditLog.objects.create(
            user=actor_a,
            action=AuditLog.ACTION_UPDATE,
            model_name="Asset",
            object_label="Province A asset",
        )
        cls.log_b = AuditLog.objects.create(
            user=actor_b,
            action=AuditLog.ACTION_UPDATE,
            model_name="Asset",
            object_label="Province B asset",
        )
        cls.county_log = AuditLog.objects.create(
            user=cls.county_actor,
            action=AuditLog.ACTION_UPDATE,
            model_name="Asset",
            object_label="County A asset",
        )

    def test_province_admin_sees_only_audit_logs_in_own_scope(self):
        self.client.login(username="province-admin-audit", password="Strong-Test-Password-2026!")
        response = self.client.get("/audit/")

        self.assertEqual(response.status_code, 200)
        visible_ids = set(response.context["object_list"].values_list("pk", flat=True))
        self.assertIn(self.log_a.pk, visible_ids)
        self.assertNotIn(self.log_b.pk, visible_ids)

    def test_inactive_province_hides_users_and_audit_logs(self):
        self.province_a.is_active = False
        self.province_a.save(update_fields=["is_active"])

        self.assertFalse(visible_users(self.province_admin).exists())
        self.client.force_login(self.province_admin)
        response = self.client.get("/audit/")
        self.assertEqual(response.status_code, 200)
        visible_ids = set(response.context["object_list"].values_list("pk", flat=True))
        self.assertNotIn(self.log_a.pk, visible_ids)
        self.assertNotIn(self.county_log.pk, visible_ids)

    def test_inactive_county_hides_county_users_and_audit_logs(self):
        self.county_a.is_active = False
        self.county_a.save(update_fields=["is_active"])

        self.assertFalse(visible_users(self.county_admin).exists())
        self.client.force_login(self.county_admin)
        response = self.client.get("/audit/")
        self.assertEqual(response.status_code, 200)
        visible_ids = set(response.context["object_list"].values_list("pk", flat=True))
        self.assertNotIn(self.county_log.pk, visible_ids)

    def test_province_admin_does_not_see_users_in_inactive_counties(self):
        self.county_a.is_active = False
        self.county_a.save(update_fields=["is_active"])

        visible_ids = set(visible_users(self.province_admin).values_list("pk", flat=True))
        self.assertNotIn(self.county_admin.pk, visible_ids)
        self.assertNotIn(self.county_actor.pk, visible_ids)
