from django.test import RequestFactory, SimpleTestCase

from apps.core.middleware import client_ip


class ClientIpValidationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_uses_first_valid_forwarded_ip(self):
        request = self.factory.get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.5",
            REMOTE_ADDR="10.0.0.5",
        )
        self.assertEqual(client_ip(request), "203.0.113.10")

    def test_rejects_invalid_forwarded_ip_instead_of_persisting_untrusted_text(self):
        request = self.factory.get(
            "/",
            HTTP_X_FORWARDED_FOR="not-an-ip, 10.0.0.5",
            REMOTE_ADDR="10.0.0.5",
        )
        self.assertIsNone(client_ip(request))

    def test_validates_remote_addr_when_no_forwarded_header_exists(self):
        request = self.factory.get("/", REMOTE_ADDR="2001:db8::1")
        self.assertEqual(client_ip(request), "2001:db8::1")

    def test_returns_none_for_invalid_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="not-an-ip")
        self.assertIsNone(client_ip(request))
