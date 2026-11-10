"""Private user-signature delivery tests."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User


class UserSignatureAccessTests(TestCase):
    def test_signature_is_available_only_to_authenticated_owner(self):
        user = User.objects.create_user(
            username="signature-owner",
            password="Strong-Password-2026!",
            role=User.ROLE_REQUESTER,
        )
        user.signature = SimpleUploadedFile(
            "signature.png", b"private-signature", content_type="image/png"
        )
        user.save(update_fields=["signature"])

        anonymous = Client()
        response = anonymous.get(reverse("accounts:signature_file"))
        self.assertEqual(response.status_code, 302)

        client = Client()
        client.force_login(user)
        response = client.get(reverse("accounts:signature_file"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response.get("Content-Disposition", ""))
