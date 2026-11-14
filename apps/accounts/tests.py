"""Regression tests for administrative password validation."""
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model

from .forms import AdminSetPasswordForm
from .models import LoginAttempt, User
from .rate_limit import LOGIN_FAILURE_LIMIT, LOGIN_IP_FAILURE_LIMIT, is_login_throttled, record_login_failure


class AdminSetPasswordFormTests(SimpleTestCase):
    def test_common_password_is_rejected(self):
        user = get_user_model()(username="test-account")
        form = AdminSetPasswordForm(
            data={"new_password1": "password", "new_password2": "password"},
            user=user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("new_password1", form.errors)

    def test_strong_matching_password_is_accepted(self):
        user = get_user_model()(username="test-account")
        password = "R3d!Pine-Quartz-82"
        form = AdminSetPasswordForm(
            data={"new_password1": password, "new_password2": password},
            user=user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_mismatched_passwords_are_rejected(self):
        form = AdminSetPasswordForm(
            data={"new_password1": "R3d!Pine-Quartz-82", "new_password2": "Other!Password-83"},
            user=get_user_model()(username="test-account"),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("new_password2", form.errors)

class LoginThrottlingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="throttle-user",
            password="Str0ng-Login-Password-2026!",
            role=User.ROLE_REQUESTER,
        )

    def test_repeated_failed_passwords_temporarily_block_valid_login(self):
        from django.urls import reverse

        url = reverse("accounts:login")
        for _ in range(LOGIN_FAILURE_LIMIT):
            response = self.client.post(
                url, {"username": self.user.username, "password": "wrong-password"}
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(LoginAttempt.objects.count(), LOGIN_FAILURE_LIMIT)
        response = self.client.post(
            url, {"username": self.user.username, "password": "Str0ng-Login-Password-2026!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ورود برای این نام کاربری موقتاً محدود شده است")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_successful_login_clears_username_failures(self):
        from django.urls import reverse

        for _ in range(2):
            self.client.post(
                reverse("accounts:login"),
                {"username": self.user.username, "password": "wrong-password"},
            )
        self.assertEqual(LoginAttempt.objects.count(), 2)

        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": "Str0ng-Login-Password-2026!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.get("_auth_user_id"))
        self.assertFalse(
            LoginAttempt.objects.exists()
        )

    def test_ip_failure_limit_blocks_password_spraying(self):
        for index in range(LOGIN_IP_FAILURE_LIMIT):
            record_login_failure(f"unknown-user-{index}", "192.0.2.10")
        self.assertTrue(is_login_throttled("another-user", "192.0.2.10"))
        self.assertFalse(is_login_throttled("another-user", "192.0.2.11"))

