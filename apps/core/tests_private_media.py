import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.models import User
from apps.assets.models import Asset, AssetAttachment, AssetCategory
from apps.org.models import Center, OrganizationalUnit
from apps.core.views import private_media


class PrivateMediaAuthorizationTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        national = OrganizationalUnit.objects.create(
            name="ستاد رسانه", code="MEDIA-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        province = OrganizationalUnit.objects.create(
            name="استان رسانه", code="MEDIA-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_a = OrganizationalUnit.objects.create(
            name="شهرستان الف", code="MEDIA-COUNTY-A",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province,
        )
        county_b = OrganizationalUnit.objects.create(
            name="شهرستان ب", code="MEDIA-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province,
        )
        self.center_a = Center.objects.create(
            name="مرکز رسانه الف", code="MEDIA-CENTER-A", parent_unit=county_a
        )
        self.center_b = Center.objects.create(
            name="مرکز رسانه ب", code="MEDIA-CENTER-B", parent_unit=county_b
        )
        self.user_a = User.objects.create_user(
            username="media-a", password="test-password",
            role=User.ROLE_ADMIN_IT, center=self.center_a,
        )
        self.user_b = User.objects.create_user(
            username="media-b", password="test-password",
            role=User.ROLE_ADMIN_IT, center=self.center_b,
        )
        category = AssetCategory.objects.create(name="دارایی رسانه", code="MEDIA")
        asset = Asset.objects.create(
            asset_tag="MEDIA-0001", title="تجهیز آزمایشی",
            category=category, center=self.center_a,
        )
        self.attachment = AssetAttachment.objects.create(
            asset=asset,
            file=SimpleUploadedFile("evidence.txt", b"private-evidence"),
        )

    def test_same_center_staff_can_download_owned_asset_attachment(self):
        request = RequestFactory().get(f"/media/{self.attachment.file.name}")
        request.user = self.user_a
        response = private_media(request, self.attachment.file.name)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"private-evidence")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_other_center_staff_cannot_download_attachment(self):
        request = RequestFactory().get(f"/media/{self.attachment.file.name}")
        request.user = self.user_b
        with self.assertRaises(Http404):
            private_media(request, self.attachment.file.name)
