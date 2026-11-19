from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Notification


class NotificationReadMethodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notification-reader", password="test-password",
            role=User.ROLE_ADMIN_IT,
        )
        self.notification = Notification.objects.create(
            user=self.user, title="اعلان آزمون", message="متن اعلان",
            url="/notifications-target/",
        )
        self.client.force_login(self.user)

    def test_get_does_not_mark_notification_as_read(self):
        response = self.client.get(
            reverse("core:notification_read", args=[self.notification.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)
        self.assertIsNone(self.notification.read_at)

    def test_post_marks_notification_as_read_and_redirects(self):
        response = self.client.post(
            reverse("core:notification_read", args=[self.notification.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/notifications-target/")
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)
