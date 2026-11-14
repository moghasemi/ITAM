from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.integrations.forms import WebhookEndpointForm
from apps.integrations.models import WebhookEndpoint


class WebhookAdministrationSecurityTests(TestCase):
    def setUp(self):
        self.endpoint = WebhookEndpoint.objects.create(
            name="secure-endpoint",
            url="https://management.example.test/events",
            auth_type=WebhookEndpoint.AUTH_HMAC,
            secret="super-secret-value",
            token="private-token-value",
        )
        self.center_it = User.objects.create_user(
            username="webhook-center-it", password="test-password",
            role=User.ROLE_ADMIN_IT,
        )
        self.province_admin = User.objects.create_user(
            username="webhook-province-admin", password="test-password",
            role=User.ROLE_ADMIN_PROVINCE,
        )
        self.country_admin = User.objects.create_user(
            username="webhook-country-admin", password="test-password",
            role=User.ROLE_ADMIN_COUNTRY,
        )

    def test_only_country_admin_can_list_create_or_edit_webhook_endpoints(self):
        url = reverse("integrations:endpoint_list")
        for user in (self.center_it, self.province_admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.get(reverse("integrations:endpoint_update", args=[self.endpoint.pk])).status_code, 403)

        self.client.force_login(self.country_admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("integrations:endpoint_update", args=[self.endpoint.pk])).status_code,
            200,
        )

    def test_secret_fields_are_never_rendered_and_blank_edit_preserves_values(self):
        form = WebhookEndpointForm(instance=self.endpoint)
        self.assertNotIn("super-secret-value", str(form["secret"]))
        self.assertNotIn("private-token-value", str(form["token"]))

        bound = WebhookEndpointForm(
            data={
                "name": self.endpoint.name,
                "url": self.endpoint.url,
                "method": self.endpoint.method,
                "auth_type": WebhookEndpoint.AUTH_HMAC,
                "token": "",
                "secret": "",
                "extra_headers": "{}",
                "event_filter": "",
                "is_active": "on",
                "timeout_seconds": str(self.endpoint.timeout_seconds),
                "max_attempts": str(self.endpoint.max_attempts),
            },
            instance=self.endpoint,
        )
        self.assertTrue(bound.is_valid(), bound.errors)
        saved = bound.save()
        self.assertEqual(saved.secret, "super-secret-value")
        self.assertEqual(saved.token, "private-token-value")
