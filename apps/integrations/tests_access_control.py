"""Regression tests for center-level Outbox read-only access."""

from django.test import TestCase

from apps.accounts.models import User


class CenterItOutboxAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.center_it = User.objects.create_user(
            username="center-it-outbox",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
        )
        cls.country_admin = User.objects.create_user(
            username="country-admin-outbox",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_COUNTRY,
        )

    def test_center_it_can_open_outbox_as_read_only(self):
        self.client.login(username="center-it-outbox", password="Strong-Test-Password-2026!")
        response = self.client.get("/integrations/outbox/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_manage"])
        self.assertFalse(response.context["endpoints"].exists())
        self.assertNotContains(response, "ارسال رخدادهای در انتظار")
        self.assertNotContains(response, "بازگردانی رخدادهای متوقف")
        self.assertNotContains(response, "مقصدهای ارسال")
        self.assertNotContains(response, "تنظیمات سامانه")
        self.assertNotContains(response, "گونه‌های دارایی و قطعه")

    def test_center_it_cannot_dispatch_or_requeue_outbox_events(self):
        self.client.login(username="center-it-outbox", password="Strong-Test-Password-2026!")
        paths = (
            "/integrations/dispatch/",
            "/integrations/outbox/requeue-all/",
            "/integrations/outbox/999/requeue/",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 403)

    def test_dispatch_endpoint_rejects_get_requests(self):
        self.client.login(username="center-it-outbox", password="Strong-Test-Password-2026!")
        self.assertEqual(self.client.get("/integrations/dispatch/").status_code, 405)

    def test_country_admin_retains_outbox_management_controls(self):
        self.client.login(username="country-admin-outbox", password="Strong-Test-Password-2026!")
        response = self.client.get("/integrations/outbox/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_manage"])
