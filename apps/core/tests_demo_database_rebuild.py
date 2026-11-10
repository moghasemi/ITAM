"""Safety checks for the destructive local demo database rebuild command."""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class RebuildDemoDatabaseSafetyTests(SimpleTestCase):
    def test_requires_explicit_confirmation(self):
        with self.assertRaises(CommandError):
            call_command(
                "rebuild_demo_database",
                admin_password="test-only-password",
            )

    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_is_disabled(self):
        with self.assertRaises(CommandError):
            call_command(
                "rebuild_demo_database",
                admin_password="test-only-password",
                confirm_reset=True,
            )
