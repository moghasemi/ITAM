import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from apps.accounts.models import User
from apps.assets.models import Asset, AssetAttachment, AssetCategory, HardwareSnapshot
from apps.maintenance.models import (GeneralReferral, IndependentRepairer, MaintenanceVisit, RepairRequest, VisitAssetCheck)
from apps.org.models import Center, Contract, Contractor, OrganizationalUnit
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
        self.asset = Asset.objects.create(
            asset_tag="MEDIA-0001", title="تجهیز آزمایشی",
            category=category, center=self.center_a,
        )
        self.attachment = AssetAttachment.objects.create(
            asset=self.asset,
            file=SimpleUploadedFile("evidence.txt", b"private-evidence"),
        )
        repairer = IndependentRepairer.objects.create(
            province=province, kind=IndependentRepairer.KIND_COMPANY,
            name="تعمیرکار خصوصی رسانه", created_by=self.user_a,
        )
        self.repair = RepairRequest.objects.create(
            center=self.center_a, asset=self.asset, repairer=repairer,
            repairer_name_snapshot=repairer.name,
            fault_description="خرابی نمونه", referral_reason="ارجاع نمونه",
            estimate_amount="1000000", requested_by=self.user_a,
            status=RepairRequest.STATUS_COMPLETED,
            estimate_attachment=SimpleUploadedFile("estimate.pdf", b"%PDF-1.4\nestimate"),
            completion_attachment=SimpleUploadedFile("completion.pdf", b"%PDF-1.4\ncompletion"),
            cost_dispute_attachment=SimpleUploadedFile("decision.pdf", b"%PDF-1.4\ndecision"),
        )
        self.referral = GeneralReferral.objects.create(
            subject="ارجاع خصوصی رسانه", description="شرح خصوصی",
            center=self.center_a, province=province, recipient_role="مدیر استان",
            recipient_name="مسئول نمونه", created_by=self.user_a,
            attachment=SimpleUploadedFile("referral.pdf", b"%PDF-1.4\nreferral"),
            resolution_attachment=SimpleUploadedFile("resolution.pdf", b"%PDF-1.4\nresolution"),
            status=GeneralReferral.STATUS_RESOLVED, outcome="نتیجه خصوصی",
        )
        self.province_referral = GeneralReferral.objects.create(
            subject="ارجاع استانی رسانه", description="موضوع در سطح استان",
            province=province, recipient_role="مسئول مالی استان",
            recipient_name="مسئول مالی", recipient_user=self.user_a,
            created_by=self.user_a,
            resolution_attachment=SimpleUploadedFile("province-decision.pdf", b"%PDF-1.4\nprovince"),
            status=GeneralReferral.STATUS_RESOLVED, outcome="نتیجه استانی",
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


    def test_same_center_staff_can_download_repair_and_referral_documents(self):
        paths = [
            self.repair.estimate_attachment.name,
            self.repair.completion_attachment.name,
            self.repair.cost_dispute_attachment.name,
            self.referral.attachment.name,
            self.referral.resolution_attachment.name,
        ]
        for path in paths:
            request = RequestFactory().get(f"/media/{path}")
            request.user = self.user_a
            response = private_media(request, path)
            self.assertEqual(response.status_code, 200, path)
            response.close()

    def test_other_center_staff_cannot_download_repair_or_referral_documents(self):
        paths = [
            self.repair.estimate_attachment.name,
            self.repair.completion_attachment.name,
            self.repair.cost_dispute_attachment.name,
            self.referral.attachment.name,
            self.referral.resolution_attachment.name,
        ]
        for path in paths:
            request = RequestFactory().get(f"/media/{path}")
            request.user = self.user_b
            with self.assertRaises(Http404, msg=path):
                private_media(request, path)

    def test_same_province_staff_can_download_centerless_province_referral_document(self):
        path = self.province_referral.resolution_attachment.name
        request = RequestFactory().get(f"/media/{path}")
        request.user = self.user_b
        response = private_media(request, path)
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_technician_cannot_download_misbound_hardware_or_visit_photos(self):
        import datetime as dt
        from django.utils import timezone

        province_b = OrganizationalUnit.objects.create(
            name="استان رسانه دوم", code="MEDIA-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=self.center_a.parent_unit.parent.parent,
        )
        county_b = OrganizationalUnit.objects.create(
            name="شهرستان رسانه دوم", code="MEDIA-COUNTY-C",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province_b,
        )
        center_c = Center.objects.create(
            name="مرکز رسانه ج", code="MEDIA-CENTER-C", parent_unit=county_b
        )
        contractor = Contractor.objects.create(name="پیمانکار رسانه")
        today = timezone.localdate()
        contract_a = Contract.objects.create(
            contractor=contractor, province=self.center_a.parent_unit.parent,
            number="MEDIA-CONTRACT-A", title="قرارداد استان الف",
            start_date=today - dt.timedelta(days=5),
            end_date=today + dt.timedelta(days=30),
        )
        Contract.objects.create(
            contractor=contractor, province=province_b,
            number="MEDIA-CONTRACT-B", title="قرارداد استان ب",
            start_date=today - dt.timedelta(days=5),
            end_date=today + dt.timedelta(days=30),
        )
        technician = User.objects.create_user(
            username="media-multi-province-tech", password="test-password",
            role=User.ROLE_TECHNICIAN, contractor=contractor,
        )
        misbound_asset = Asset.objects.create(
            asset_tag="MEDIA-MISBOUND", title="دارایی با قرارداد استان دیگر",
            category=self.attachment.asset.category,
            center=center_c, contract=contract_a,
        )
        snapshot = HardwareSnapshot.objects.create(
            asset=misbound_asset,
            case_photo=SimpleUploadedFile("case.jpg", b"private-case-photo"),
        )
        visit = MaintenanceVisit.objects.create(
            number="MEDIA-VISIT-A", contract=contract_a, contractor=contractor,
            scheduled_date=today,
        )
        check = VisitAssetCheck.objects.create(
            visit=visit, asset=misbound_asset,
            photo=SimpleUploadedFile("visit.jpg", b"private-visit-photo"),
        )

        for path in [snapshot.case_photo.name, check.photo.name]:
            request = RequestFactory().get(f"/media/{path}")
            request.user = technician
            with self.assertRaises(Http404):
                private_media(request, path)

    def test_province_admin_cannot_download_signature_from_another_province(self):
        province_a = self.center_a.parent_unit.parent
        province_b = OrganizationalUnit.objects.create(
            name="استان امضای دوم", code="MEDIA-SIGN-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=province_a.parent,
        )
        county_b = OrganizationalUnit.objects.create(
            name="شهرستان امضای دوم", code="MEDIA-SIGN-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province_b,
        )
        center_b = Center.objects.create(
            name="مرکز امضای دوم", code="MEDIA-SIGN-CENTER-B", parent_unit=county_b
        )
        province_admin = User.objects.create_user(
            username="media-province-admin", password="test-password",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=province_a,
        )
        owner = User.objects.create_user(
            username="media-signature-owner", password="test-password",
            role=User.ROLE_REQUESTER, center=center_b,
        )
        owner.signature = SimpleUploadedFile("signature.png", b"private-signature")
        owner.save(update_fields=["signature"])

        request = RequestFactory().get(f"/media/{owner.signature.name}")
        request.user = province_admin
        with self.assertRaises(Http404):
            private_media(request, owner.signature.name)
