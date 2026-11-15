import os
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.core.middleware import client_ip


class ClientIpValidationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_ignores_forwarded_header_from_untrusted_remote(self):
        with patch.dict(os.environ, {"ITAM_TRUSTED_PROXY_IPS": ""}):
            request = self.factory.get(
                "/",
                HTTP_X_FORWARDED_FOR="203.0.113.10",
                REMOTE_ADDR="198.51.100.20",
            )
            self.assertEqual(client_ip(request), "198.51.100.20")

    def test_uses_forwarded_chain_only_from_trusted_proxy(self):
        with patch.dict(os.environ, {"ITAM_TRUSTED_PROXY_IPS": "10.0.0.0/8"}):
            request = self.factory.get(
                "/",
                HTTP_X_FORWARDED_FOR="192.0.2.99, 198.51.100.25, 10.0.0.8",
                REMOTE_ADDR="10.0.0.9",
            )
            self.assertEqual(client_ip(request), "198.51.100.25")

    def test_invalid_forwarded_entries_fall_back_to_trusted_proxy_address(self):
        with patch.dict(os.environ, {"ITAM_TRUSTED_PROXY_IPS": "10.0.0.0/8"}):
            request = self.factory.get(
                "/",
                HTTP_X_FORWARDED_FOR="not-an-ip",
                REMOTE_ADDR="10.0.0.5",
            )
            self.assertEqual(client_ip(request), "10.0.0.5")

    def test_validates_remote_addr_when_no_trusted_proxy_exists(self):
        request = self.factory.get("/", REMOTE_ADDR="2001:db8::1")
        self.assertEqual(client_ip(request), "2001:db8::1")

    def test_returns_none_for_invalid_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="not-an-ip")
        self.assertIsNone(client_ip(request))
