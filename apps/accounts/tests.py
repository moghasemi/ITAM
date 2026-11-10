"""Regression tests for administrative password validation."""
from django.test import SimpleTestCase
from django.contrib.auth import get_user_model

from .forms import AdminSetPasswordForm


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
