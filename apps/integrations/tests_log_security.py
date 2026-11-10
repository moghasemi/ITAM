import json

from django.test import SimpleTestCase

from apps.integrations.services import (
    _redact_log_data,
    _safe_log_request_body,
    _safe_log_url,
)


class ApiCallLogSecurityTests(SimpleTestCase):

    def test_url_query_and_fragment_are_removed(self):
        url = (
            "https://example.com/webhook"
            "?access_token=secret123&tenant=42#section"
        )

        result = _safe_log_url(url)

        self.assertEqual(result, "https://example.com/webhook")
        self.assertNotIn("secret123", result)
        self.assertNotIn("tenant=42", result)

    def test_url_userinfo_is_not_logged(self):
        url = "https://user:password@example.com/webhook?token=abc"

        result = _safe_log_url(url)

        self.assertEqual(result, "https://example.com/webhook")
        self.assertNotIn("user", result)
        self.assertNotIn("password", result)
        self.assertNotIn("abc", result)

    def test_nested_sensitive_fields_are_redacted(self):
        data = {
            "event": "user.created",
            "token": "secret-token",
            "user": {
                "name": "Test User",
                "email": "user@example.com",
                "profile": {
                    "phone": "09120000000",
                },
            },
            "items": [
                {"client_secret": "hidden-secret"},
            ],
        }

        result = _redact_log_data(data)

        self.assertEqual(result["event"], "user.created")
        self.assertEqual(result["token"], "[REDACTED]")
        self.assertEqual(result["user"]["name"], "Test User")
        self.assertEqual(result["user"]["email"], "[REDACTED]")
        self.assertEqual(result["user"]["profile"]["phone"], "[REDACTED]")
        self.assertEqual(
            result["items"][0]["client_secret"],
            "[REDACTED]",
        )

    def test_request_body_is_redacted_before_logging(self):
        body = json.dumps(
            {
                "event": "ticket.created",
                "authorization": "Bearer secret-token",
                "data": {
                    "title": "Test ticket",
                    "api_key": "private-key",
                },
            }
        ).encode("utf-8")

        result = _safe_log_request_body(body)

        self.assertIn("ticket.created", result)
        self.assertIn("Test ticket", result)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret-token", result)
        self.assertNotIn("private-key", result)

    def test_non_json_request_body_is_not_logged(self):
        body = b"password=secret123"

        result = _safe_log_request_body(body)

        self.assertNotIn("secret123", result)
        self.assertIn("omitted", result)