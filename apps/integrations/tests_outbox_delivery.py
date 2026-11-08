from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.integrations.models import OutboxDelivery, OutboxEvent, WebhookEndpoint
from apps.integrations.services import dispatch_event, dispatch_pending


class OutboxMultiDestinationTests(TestCase):
    def setUp(self):
        self.event = OutboxEvent.objects.create(
            event_type="ticket.reported",
            aggregate_type="Ticket",
            aggregate_id="T-100",
            payload={"ticket": "T-100"},
        )
        self.endpoint_a = WebhookEndpoint.objects.create(
            name="management-a", url="https://a.example/events"
        )
        self.endpoint_b = WebhookEndpoint.objects.create(
            name="management-b", url="https://b.example/events"
        )

    @staticmethod
    def _successful_delivery(event, endpoint, delivery):
        delivery.status = OutboxEvent.STATUS_SENT
        delivery.attempts += 1
        delivery.last_attempt_at = timezone.now()
        delivery.dispatched_at = delivery.last_attempt_at
        delivery.last_error = ""
        delivery.save()
        return True

    @patch("apps.integrations.services.dispatch_event")
    def test_event_is_delivered_to_every_matching_endpoint(self, dispatch):
        dispatch.side_effect = self._successful_delivery

        summary = dispatch_pending()

        self.assertEqual(dispatch.call_count, 2)
        self.assertEqual(summary["sent"], 2)
        self.assertEqual(
            set(self.event.deliveries.values_list("endpoint_id", flat=True)),
            {self.endpoint_a.pk, self.endpoint_b.pk},
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, OutboxEvent.STATUS_SENT)

    @patch("apps.integrations.services.dispatch_event")
    def test_retry_sends_only_failed_destination(self, dispatch):
        OutboxDelivery.objects.create(
            event=self.event, endpoint=self.endpoint_a,
            status=OutboxEvent.STATUS_SENT, attempts=1,
        )
        OutboxDelivery.objects.create(
            event=self.event, endpoint=self.endpoint_b,
            status=OutboxEvent.STATUS_FAILED, attempts=1,
            last_error="temporary network error",
        )
        self.event.status = OutboxEvent.STATUS_FAILED
        self.event.save(update_fields=["status"])
        dispatch.side_effect = self._successful_delivery

        summary = dispatch_pending()

        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(dispatch.call_args.args[1], self.endpoint_b)
        self.assertEqual(summary["sent"], 1)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, OutboxEvent.STATUS_SENT)

class OutboxHeaderSecurityTests(TestCase):
    def setUp(self):
        self.event = OutboxEvent.objects.create(
            event_type="ticket.reported",
            aggregate_type="Ticket",
            aggregate_id="T-200",
            payload={"ticket": "T-200"},
        )

    @patch("apps.integrations.services._resolve_webhook_target")
    def test_reserved_signature_header_cannot_be_overridden(self, resolver):
        endpoint = WebhookEndpoint.objects.create(
            name="header-test-signature",
            url="https://example.com/events",
            extra_headers={"x-itam-signature": "forged"},
        )

        result = dispatch_event(self.event, endpoint)

        self.assertFalse(result)
        resolver.assert_not_called()

        delivery = OutboxDelivery.objects.get(
            event=self.event, endpoint=endpoint
        )
        self.assertEqual(delivery.status, OutboxEvent.STATUS_FAILED)
        self.assertIn("رزروشده", delivery.last_error)

    @patch("apps.integrations.services._resolve_webhook_target")
    def test_reserved_idempotency_header_is_case_insensitive(self, resolver):
        endpoint = WebhookEndpoint.objects.create(
            name="header-test-idempotency",
            url="https://example.com/events",
            extra_headers={"X-ItAm-Idempotency-Key": "forged"},
        )

        result = dispatch_event(self.event, endpoint)

        self.assertFalse(result)
        resolver.assert_not_called()

    @patch("apps.integrations.services._resolve_webhook_target")
    def test_custom_header_rejects_crlf_injection(self, resolver):
        endpoint = WebhookEndpoint.objects.create(
            name="header-test-crlf",
            url="https://example.com/events",
            extra_headers={"X-Custom": "safe\r\nInjected: yes"},
        )

        result = dispatch_event(self.event, endpoint)

        self.assertFalse(result)
        resolver.assert_not_called()

    @patch("apps.integrations.services._resolve_webhook_target")
    def test_duplicate_custom_headers_are_rejected_case_insensitively(
        self, resolver
    ):
        endpoint = WebhookEndpoint.objects.create(
            name="header-test-duplicate",
            url="https://example.com/events",
            extra_headers={
                "X-Custom": "first",
                "x-custom": "second",
            },
        )

        result = dispatch_event(self.event, endpoint)

        self.assertFalse(result)
        resolver.assert_not_called()
class OutboxInactiveEndpointTests(TestCase):
    def setUp(self):
        self.event = OutboxEvent.objects.create(
            event_type="ticket.reported",
            aggregate_type="Ticket",
            aggregate_id="T-300",
            payload={"ticket": "T-300"},
        )
        self.inactive_endpoint = WebhookEndpoint.objects.create(
            name="inactive-endpoint",
            url="https://inactive.example/events",
            is_active=False,
        )
        self.active_endpoint = WebhookEndpoint.objects.create(
            name="active-endpoint",
            url="https://active.example/events",
        )

    @staticmethod
    def successful_delivery(event, endpoint, delivery):
        delivery.status = OutboxEvent.STATUS_SENT
        delivery.attempts += 1
        delivery.last_attempt_at = timezone.now()
        delivery.dispatched_at = delivery.last_attempt_at
        delivery.last_error = ""
        delivery.save()
        return True

    @patch("apps.integrations.services.dispatch_event")
    def test_inactive_failed_delivery_is_preserved(self, dispatch):
        inactive_delivery = OutboxDelivery.objects.create(
            event=self.event,
            endpoint=self.inactive_endpoint,
            status=OutboxEvent.STATUS_FAILED,
            attempts=1,
            last_error="previous delivery failed",
        )
        dispatch.side_effect = self.successful_delivery

        dispatch_pending()

        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(dispatch.call_args.args[1], self.active_endpoint)

        inactive_delivery.refresh_from_db()
        self.assertEqual(inactive_delivery.status, OutboxEvent.STATUS_FAILED)
        self.assertEqual(inactive_delivery.attempts, 1)

        self.event.refresh_from_db()
        self.assertEqual(self.event.status, OutboxEvent.STATUS_FAILED)

    @patch("apps.integrations.services.dispatch_event")
    def test_reactivated_endpoint_retries_failed_delivery(self, dispatch):
        OutboxDelivery.objects.create(
            event=self.event,
            endpoint=self.inactive_endpoint,
            status=OutboxEvent.STATUS_FAILED,
            attempts=1,
            last_error="previous delivery failed",
        )
        OutboxDelivery.objects.create(
            event=self.event,
            endpoint=self.active_endpoint,
            status=OutboxEvent.STATUS_SENT,
            attempts=1,
        )

        self.inactive_endpoint.is_active = True
        self.inactive_endpoint.save(update_fields=["is_active"])
        dispatch.side_effect = self.successful_delivery

        dispatch_pending()

        self.assertEqual(dispatch.call_count, 1)
        self.assertEqual(dispatch.call_args.args[1], self.inactive_endpoint)

        self.event.refresh_from_db()
        self.assertEqual(self.event.status, OutboxEvent.STATUS_SENT)
