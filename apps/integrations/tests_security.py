import os
import socket
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.integrations.services import _resolve_webhook_target


class WebhookTargetSecurityTests(SimpleTestCase):
    @patch("apps.integrations.services.socket.getaddrinfo")
    def test_private_address_is_rejected_without_explicit_allowlist(self, resolver):
        resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.30.40", 80))
        ]
        with patch.dict(os.environ, {"ITAM_WEBHOOK_ALLOWED_HOSTS": ""}):
            with self.assertRaises(ValueError):
                _resolve_webhook_target("http://internal.example/events")

    @patch("apps.integrations.services.socket.getaddrinfo")
    def test_private_address_requires_exact_allowlisted_hostname(self, resolver):
        resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.30.40", 8080))
        ]
        with patch.dict(
            os.environ, {"ITAM_WEBHOOK_ALLOWED_HOSTS": "internal.example"}
        ):
            parsed, pinned_ip, port = _resolve_webhook_target(
                "http://internal.example:8080/events"
            )
        self.assertEqual(parsed.hostname, "internal.example")
        self.assertEqual(pinned_ip, "10.20.30.40")
        self.assertEqual(port, 8080)


    @patch("apps.integrations.services.socket.getaddrinfo")
    def test_public_webhook_requires_https(self, resolver):
        resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))
        ]
        with patch.dict(os.environ, {"ITAM_WEBHOOK_ALLOWED_HOSTS": ""}):
            with self.assertRaises(ValueError):
                _resolve_webhook_target("http://events.example/api")

    @patch("apps.integrations.services.socket.getaddrinfo")
    def test_public_target_is_resolved_to_a_pinned_ip(self, resolver):
        resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        with patch.dict(os.environ, {"ITAM_WEBHOOK_ALLOWED_HOSTS": ""}):
            parsed, pinned_ip, port = _resolve_webhook_target(
                "https://events.example/api"
            )
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(pinned_ip, "93.184.216.34")
        self.assertEqual(port, 443)
