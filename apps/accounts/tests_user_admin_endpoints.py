"""Authentication and HTTP-method guards for account administration endpoints."""
from django.urls import reverse
from django.test import TestCase

from apps.accounts.models import User


class UserAdministrationEndpointSecurityTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            username="endpoint-requester",
            password="Strong-Endpoint-Password-2026!",
            role=User.ROLE_REQUESTER,
        )
        self.toggle_url = reverse("accounts:user_toggle", args=[self.requester.pk])
        self.password_url = reverse("accounts:user_password", args=[self.requester.pk])

    def test_anonymous_users_cannot_toggle_accounts(self):
        response = self.client.post(self.toggle_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_toggle_endpoint_rejects_get_requests(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.toggle_url)
        self.assertEqual(response.status_code, 405)

    def test_non_admin_cannot_toggle_accounts(self):
        self.client.force_login(self.requester)
        response = self.client.post(self.toggle_url)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_users_cannot_open_password_reset_form(self):
        response = self.client.get(self.password_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_non_admin_cannot_open_password_reset_form(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.password_url)
        self.assertEqual(response.status_code, 403)
