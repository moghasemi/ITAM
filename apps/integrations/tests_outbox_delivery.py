from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.integrations.models import OutboxDelivery, OutboxEvent, WebhookEndpoint
from apps.integrations.services import dispatch_pending


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
