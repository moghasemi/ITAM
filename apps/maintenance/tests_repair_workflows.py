import datetime as dt
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog, Notification
from apps.assets.models import Asset, AssetCategory
from apps.maintenance.repair_models import (
    GeneralITRequest, GeneralReferral, IndependentRepairer, RepairFeedback, RepairerProfileEvent,
    RepairRequest, RepairerStatusEvent,
)
from apps.maintenance.repair_services import (
    add_feedback_reply,
    assign_contractor_to_center,
    assign_general_it_request,
    complete_repair_request,
    create_general_it_request,
    create_referral,
    create_repair_request,
    decide_repair_request,
    end_contractor_assignment,
    escalate_general_it_request,
    manager_decide_general_it_request,
    resolve_general_it_request,
    resolve_referral,
    resolve_repair_cost_dispute,
    resubmit_repair_request,
    set_repairer_active,
    visible_repair_feedback,
    visible_repair_requests,
    visible_general_it_requests,
)
from apps.org.models import (
    Center, Contract, ContractCenterAssignment, Contractor,
    OrganizationalUnit,
)


class RepairAndReferralWorkflowTests(TestCase):
    def setUp(self):
        national = OrganizationalUnit.objects.create(
            name="ستاد نمونه", code="WF-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        self.province = OrganizationalUnit.objects.create(
            name="سیستان و بلوچستان", code="WF-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="زاهدان", code="WF-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province,
        )
        self.center = Center.objects.create(
            name="مرکز نمونه گردش کار", code="WF-CENTER", parent_unit=county, is_demo=True,
        )
        self.province_admin = User.objects.create_user(
            username="wf-province-admin", password="test-password",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=self.province,
        )
        self.it_expert = User.objects.create_user(
            username="wf-center-it", password="test-password",
            role=User.ROLE_ADMIN_IT, center=self.center,
        )
        self.requester = User.objects.create_user(
            username="wf-requester", password="test-password",
            role=User.ROLE_REQUESTER, center=self.center,
        )
        self.manager = User.objects.create_user(
            username="wf-manager", password="test-password",
            role=User.ROLE_MANAGER, center=self.center,
        )
        self.category = AssetCategory.objects.create(name="رایانه نمونه گردش", code="WF-PC")
        self.asset = Asset.objects.create(
            asset_tag="WF-ASSET-001", title="کیس نمونه",
            category=self.category, center=self.center,
        )
        self.repairer = IndependentRepairer.objects.create(
            province=self.province,
            kind=IndependentRepairer.KIND_COMPANY,
            name="تعمیرکار نمونه استان",
            created_by=self.it_expert,
        )

    def _repair(self, estimate="1000000"):
        return create_repair_request(
            center=self.center,
            asset=self.asset,
            repairer=self.repairer,
            fault_description="خرابی منبع تغذیه",
            referral_reason="عدم امکان تعمیر در مرکز",
            estimate_amount=Decimal(estimate),
            actor=self.it_expert,
        )

    def test_repair_requires_provincial_approval_and_records_cost_dispute(self):
        repair = self._repair()
        self.assertEqual(repair.status, RepairRequest.STATUS_PENDING)
        self.assertTrue(
            Notification.objects.filter(
                user=self.province_admin,
                title="درخواست تعمیر جدید در انتظار تایید",
            ).exists()
        )

        with self.assertRaises(PermissionDenied):
            decide_repair_request(
                repair=repair, decision="approve", note="", actor=self.it_expert,
            )

        repair = decide_repair_request(
            repair=repair, decision="approve", note="مجاز است.", actor=self.province_admin,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_APPROVED)

        repair = complete_repair_request(
            repair=repair, actor=self.it_expert,
            outcome="پاور تعویض و سیستم تست شد.",
            final_cost=Decimal("1250000"),
            final_cost_reason="افزایش قیمت قطعه نسبت به پیش‌فاکتور",
            work_quality=5, completion_speed=4, cost_fairness=3,
            comment="توضیح نمونه",
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_DISPUTED)
        self.assertEqual(RepairFeedback.objects.filter(repair_request=repair).count(), 1)

        feedback = repair.feedback
        reply = add_feedback_reply(
            feedback=feedback, body="پیگیری مدیر استان", actor=self.province_admin,
        )
        self.assertEqual(reply.body, "پیگیری مدیر استان")

        repair = resolve_repair_cost_dispute(
            repair=repair, decision="approve_increase",
            note="افزایش هزینه با مستندات تایید شد.", actor=self.province_admin,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_RESOLVED)
        self.assertEqual(repair.cost_increase_approved_by_id, self.province_admin.pk)

    def test_retired_assets_cannot_receive_new_independent_repair_requests(self):
        self.asset.status = "retired"
        self.asset.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            self._repair()

    def test_repair_can_be_completed_when_final_cost_is_unknown(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair,
            decision="approve",
            note="تایید برآورد",
            actor=self.province_admin,
        )
        repair = complete_repair_request(
            repair=repair,
            actor=self.it_expert,
            outcome="تعمیر انجام شد؛ مبلغ نهایی هنوز مشخص نیست.",
            final_cost=None,
            work_quality=4,
            completion_speed=4,
            cost_fairness=5,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_COMPLETED)
        self.assertIsNone(repair.final_cost)
        self.assertEqual(RepairFeedback.objects.filter(repair_request=repair).count(), 1)

    def test_rejected_cost_increase_keeps_repair_open_as_disputed(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair, decision="approve", note="تایید اولیه",
            actor=self.province_admin,
        )
        repair = complete_repair_request(
            repair=repair, actor=self.it_expert,
            outcome="تعمیر انجام شد",
            final_cost=Decimal("1250000"),
            final_cost_reason="افزایش قیمت قطعه",
            work_quality=4, completion_speed=4, cost_fairness=2,
        )
        repair = resolve_repair_cost_dispute(
            repair=repair, decision="reject_increase",
            note="افزایش هزینه تایید نشد؛ اختلاف مبلغ باید تعیین تکلیف مالی شود.",
            actor=self.province_admin,
            attachment=SimpleUploadedFile("cost-decision.pdf", b"%PDF-1.4\ndecision"),
        )
        repair.refresh_from_db()
        self.assertTrue(repair.cost_dispute_attachment.name.endswith("cost-decision.pdf"))
        self.assertEqual(repair.status, RepairRequest.STATUS_DISPUTED)
        self.assertEqual(repair.cost_dispute_resolution, "افزایش هزینه تایید نشد؛ اختلاف مبلغ باید تعیین تکلیف مالی شود.")
        self.assertIsNone(repair.cost_increase_approved_by_id)
        self.assertTrue(repair.events.filter(action="cost_increase_rejected").exists())

    def test_returned_request_can_be_resubmitted_but_final_rejection_cannot(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair, decision="return", note="برآورد را اصلاح کنید.",
            actor=self.province_admin,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_RETURNED)
        with self.assertRaises(ValidationError):
            decide_repair_request(
                repair=repair, decision="approve",
                note="تصمیم پیش از اصلاح درخواست", actor=self.province_admin,
            )
        repair = resubmit_repair_request(
            repair=repair, actor=self.it_expert,
            estimate_amount=Decimal("1100000"),
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_PENDING)
        self.assertTrue(
            Notification.objects.filter(
                user=self.province_admin,
                title="درخواست تعمیر اصلاح‌شده در انتظار تایید",
            ).exists()
        )
        repair = decide_repair_request(
            repair=repair, decision="reject", note="درخواست فاقد توجیه است.",
            actor=self.province_admin,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_REJECTED)
        with self.assertRaises(ValidationError):
            resubmit_repair_request(repair=repair, actor=self.it_expert)

    def test_inactive_repairer_cannot_be_approved_or_resubmitted(self):
        repair = self._repair()
        set_repairer_active(
            repairer=self.repairer,
            active=False,
            reason="پایان همکاری",
            actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            decide_repair_request(
                repair=repair,
                decision="approve",
                note="تایید",
                actor=self.province_admin,
            )
        repair = decide_repair_request(
            repair=repair,
            decision="return",
            note="تعمیرکار غیرفعال شده است.",
            actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            resubmit_repair_request(repair=repair, actor=self.it_expert)

    def test_repairer_deactivation_requires_reason_and_preserves_history(self):
        with self.assertRaises(ValidationError):
            set_repairer_active(
                repairer=self.repairer, active=False, reason="", actor=self.it_expert,
            )
        set_repairer_active(
            repairer=self.repairer, active=False,
            reason="پایان همکاری", actor=self.it_expert,
        )
        self.repairer.refresh_from_db()
        self.assertFalse(self.repairer.is_active)
        event = RepairerStatusEvent.objects.get(repairer=self.repairer)
        self.assertTrue(event.previous_active)
        self.assertFalse(event.new_active)
        self.assertEqual(event.reason, "پایان همکاری")
        with self.assertRaises(ValidationError):
            self._repair()

    def test_general_request_bypass_requires_reason_and_is_audited(self):
        request = create_general_it_request(
            center=self.center, request_type=GeneralITRequest.TYPE_EQUIPMENT,
            title="درخواست رایانه", description="تامین رایانه برای واحد",
            actor=self.requester,
        )
        assign_general_it_request(
            request=request, expert=self.it_expert, actor=self.it_expert,
        )
        with self.assertRaises(ValidationError):
            escalate_general_it_request(request=request, actor=self.it_expert)
        request = escalate_general_it_request(
            request=request, actor=self.it_expert,
            bypass_reason="فوریت تامین تجهیز و عدم دسترسی مدیر مرکز",
        )
        self.assertEqual(request.manager_approval, GeneralITRequest.MANAGER_BYPASSED)
        self.assertTrue(request.manager_bypass_reason)
        request = resolve_general_it_request(
            request=request, decision="تامین تجهیز از محل اعتبارات استانی",
            actor=self.province_admin,
        )
        self.assertEqual(request.status, GeneralITRequest.STATUS_RESOLVED)

    def test_center_it_can_escalate_after_manager_rejection_with_reason(self):
        request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_EQUIPMENT,
            title="درخواست تجهیز ردشده",
            description="درخواست نیازمند بررسی مدیر",
            actor=self.requester,
        )
        request = manager_decide_general_it_request(
            request=request, decision="reject",
            note="در حال حاضر امکان تامین وجود ندارد.",
            actor=self.manager,
        )
        with self.assertRaises(ValidationError):
            escalate_general_it_request(request=request, actor=self.it_expert)
        escalated = escalate_general_it_request(
            request=request, actor=self.it_expert,
            bypass_reason="نیاز عملیاتی مرکز و ضرورت بررسی استانی",
        )
        self.assertEqual(escalated.status, GeneralITRequest.STATUS_ESCALATED)
        self.assertEqual(
            escalated.manager_approval,
            GeneralITRequest.MANAGER_BYPASSED,
        )
        self.assertEqual(
            escalated.manager_bypass_reason,
            "نیاز عملیاتی مرکز و ضرورت بررسی استانی",
        )
        self.assertTrue(
            escalated.events.filter(
                action="escalated",
                note="نیاز عملیاتی مرکز و ضرورت بررسی استانی",
            ).exists()
        )

    def test_manager_approval_is_optional_when_bypass_reason_is_recorded(self):
        request = create_general_it_request(
            center=self.center, request_type=GeneralITRequest.TYPE_REPLACEMENT,
            title="جایگزینی چاپگر", description="تجهیز قابل تعمیر نیست",
            actor=self.requester,
        )
        assign_general_it_request(request=request, expert=self.it_expert, actor=self.it_expert)
        request = manager_decide_general_it_request(
            request=request, decision="approve", note="مورد تایید است.",
            actor=self.manager,
        )
        self.assertEqual(request.manager_approval, GeneralITRequest.MANAGER_APPROVED)
        request = escalate_general_it_request(request=request, actor=self.it_expert)
        self.assertEqual(request.status, GeneralITRequest.STATUS_ESCALATED)

    def test_province_admin_cannot_complete_repair_for_a_center(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair, decision="approve", note="تایید برآورد",
            actor=self.province_admin,
        )

        with self.assertRaises(PermissionDenied):
            complete_repair_request(
                repair=repair, actor=self.province_admin,
                outcome="تعمیر انجام شد", final_cost=Decimal("500000"),
                work_quality=5, completion_speed=5, cost_fairness=5,
            )

        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.STATUS_APPROVED)
        self.assertFalse(RepairFeedback.objects.filter(repair_request=repair).exists())

    def test_center_it_repairer_list_statistics_are_center_scoped(self):
        own_repair = self._repair()
        own_repair = decide_repair_request(
            repair=own_repair, decision="approve", note="تایید",
            actor=self.province_admin,
        )
        complete_repair_request(
            repair=own_repair, actor=self.it_expert, outcome="تعمیر مرکز خود",
            final_cost=Decimal("500000"), work_quality=4,
            completion_speed=3, cost_fairness=2,
        )

        other_county = OrganizationalUnit.objects.create(
            name="شهرستان دیگر", code="WF-COUNTY-STATS-OTHER",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province,
        )
        other_center = Center.objects.create(
            name="مرکز دیگر برای آمار", code="WF-CENTER-STATS-OTHER",
            parent_unit=other_county, is_demo=True,
        )
        other_expert = User.objects.create_user(
            username="wf-other-center-stats", password="test-password",
            role=User.ROLE_ADMIN_IT, center=other_center,
        )
        other_asset = Asset.objects.create(
            asset_tag="WF-ASSET-STATS-OTHER", title="کیس مرکز دیگر",
            category=self.category, center=other_center,
        )
        other_repair = create_repair_request(
            center=other_center, asset=other_asset, repairer=self.repairer,
            fault_description="خرابی مرکز دیگر", referral_reason="ارجاع نمونه",
            estimate_amount=Decimal("500000"), actor=other_expert,
        )
        other_repair = decide_repair_request(
            repair=other_repair, decision="approve", note="تایید",
            actor=self.province_admin,
        )
        complete_repair_request(
            repair=other_repair, actor=other_expert, outcome="تعمیر مرکز دیگر",
            final_cost=Decimal("500000"), work_quality=1,
            completion_speed=1, cost_fairness=1,
        )

        self.client.force_login(self.it_expert)
        response = self.client.get(reverse("maintenance:repairer_list"))
        self.assertEqual(response.status_code, 200)
        row = response.context["rows"].get(pk=self.repairer.pk)
        self.assertEqual(row.repair_count, 1)
        self.assertAlmostEqual(row.average_quality, 4.0)
        self.assertAlmostEqual(row.average_speed, 3.0)
        self.assertAlmostEqual(row.average_cost_fairness, 2.0)

    def test_center_it_only_sees_feedback_for_its_own_center(self):
        own_repair = self._repair()
        own_repair = decide_repair_request(
            repair=own_repair, decision="approve", note="تایید", actor=self.province_admin,
        )
        complete_repair_request(
            repair=own_repair, actor=self.it_expert, outcome="تعمیر شد",
            final_cost=Decimal("500000"), work_quality=5,
            completion_speed=5, cost_fairness=5,
        )

        other_county = OrganizationalUnit.objects.create(
            name="زابل", code="WF-COUNTY-OTHER",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province,
        )
        other_center = Center.objects.create(
            name="مرکز دیگر استان", code="WF-CENTER-OTHER", parent_unit=other_county,
        )
        other_expert = User.objects.create_user(
            username="wf-other-center-it", password="test-password",
            role=User.ROLE_ADMIN_IT, center=other_center,
        )
        other_asset = Asset.objects.create(
            asset_tag="WF-ASSET-OTHER", title="کیس مرکز دیگر",
            category=self.category, center=other_center,
        )
        other_repair = create_repair_request(
            center=other_center, asset=other_asset, repairer=self.repairer,
            fault_description="خرابی نمونه", referral_reason="ارجاع نمونه",
            estimate_amount=Decimal("500000"), actor=other_expert,
        )
        other_repair = decide_repair_request(
            repair=other_repair, decision="approve", note="تایید", actor=self.province_admin,
        )
        complete_repair_request(
            repair=other_repair, actor=other_expert, outcome="تعمیر شد",
            final_cost=Decimal("500000"), work_quality=5,
            completion_speed=5, cost_fairness=5,
        )

        center_visible = visible_repair_feedback(self.it_expert)
        self.assertTrue(center_visible.filter(repair_request=own_repair).exists())
        self.assertFalse(center_visible.filter(repair_request=other_repair).exists())

        province_visible = visible_repair_feedback(self.province_admin)
        self.assertTrue(province_visible.filter(repair_request=other_repair).exists())

    def test_repairer_profile_changes_are_audited_by_the_ui(self):
        from django.urls import reverse

        self.client.force_login(self.it_expert)
        response = self.client.post(
            reverse("maintenance:repairer_update", args=[self.repairer.pk]),
            {
                "kind": self.repairer.kind,
                "name": "تعمیرکار نمونه ویرایش‌شده",
                "national_id": "",
                "phone": "",
                "email": "",
                "address": "",
                "specialties": "تعمیر سخت‌افزار",
                "notes": "ویرایش آزمایشی",
            },
        )
        self.assertEqual(response.status_code, 302)
        event = RepairerProfileEvent.objects.get(repairer=self.repairer, action="updated")
        self.assertEqual(event.previous_values["name"], "تعمیرکار نمونه استان")
        self.assertEqual(event.new_values["name"], "تعمیرکار نمونه ویرایش‌شده")

    def test_general_referral_creation_and_resolution_are_audited(self):
        referral = create_referral(
            subject="ارجاع نمونه برای تامین قطعه",
            description="نیازمند بررسی مالی استان",
            recipient_role="مسئول مالی استان",
            recipient_name="مسئول مالی نمونه",
            center=self.center,
            actor=self.province_admin,
            attachment=SimpleUploadedFile("initial.pdf", b"%PDF-1.4\ninitial"),
        )
        self.assertTrue(AuditLog.objects.filter(
            model_name="GeneralReferral", object_id=str(referral.pk), action="create"
        ).exists())

        with self.assertRaises(PermissionDenied):
            resolve_referral(
                referral=referral, outcome="تعیین تکلیف توسط کارشناس مرکز",
                instruction="", actor=self.it_expert,
            )
        resolve_referral(
            referral=referral,
            outcome="اعتبار تامین قطعه تایید شد.",
            instruction="پرداخت پس از ارائه فاکتور رسمی انجام شود.",
            actor=self.province_admin,
            attachment=SimpleUploadedFile("decision.pdf", b"%PDF-1.4\ndecision"),
        )
        referral.refresh_from_db()
        self.assertTrue(referral.resolution_attachment.name.endswith("decision.pdf"))
        self.assertEqual(referral.status, GeneralReferral.STATUS_RESOLVED)
        self.assertTrue(AuditLog.objects.filter(
            model_name="GeneralReferral", object_id=str(referral.pk), action="resolve"
        ).exists())
        with self.assertRaises(ValidationError):
            resolve_referral(
                referral=referral, outcome="تلاش برای بازنویسی",
                instruction="", actor=self.province_admin,
            )

    def test_province_admin_can_resolve_centerless_province_referral(self):
        referral = create_referral(
            subject="ارجاع استانی بدون مرکز مشخص",
            description="موضوع مربوط به کل استان است.",
            recipient_role="مسئول مالی استان",
            recipient_name="مسئول مالی نمونه",
            recipient_user=self.manager,
            actor=self.province_admin,
        )
        self.assertEqual(referral.province_id, self.province.pk)
        resolve_referral(
            referral=referral,
            outcome="نتیجه استانی ثبت شد.",
            instruction="اقدام طبق دستور مدیر استان انجام شود.",
            actor=self.province_admin,
        )
        referral.refresh_from_db()
        self.assertEqual(referral.status, GeneralReferral.STATUS_RESOLVED)

    def test_center_it_sees_center_and_province_level_referrals(self):
        own_referral = create_referral(
            subject="ارجاع مرکز خود",
            description="پیگیری برای مرکز خود",
            recipient_role="مسئول استان",
            recipient_name="مسئول نمونه",
            center=self.center,
            actor=self.it_expert,
            attachment=SimpleUploadedFile("own-referral.pdf", b"%PDF-1.4\\nown"),
        )
        province_referral = create_referral(
            subject="ارجاع عمومی استان",
            description="موضوع مربوط به کل استان",
            recipient_role="مسئول استان",
            recipient_name="مسئول نمونه",
            actor=self.province_admin,
            attachment=SimpleUploadedFile("province-referral.pdf", b"%PDF-1.4\\nprovince"),
        )
        assigned_referral = create_referral(
            subject="ارجاع خطاب به کارشناس مرکز",
            description="ارجاع صریح به کارشناس مرکز",
            recipient_role="کارشناس IT مرکز",
            recipient_name=self.it_expert.display_name,
            recipient_user=self.it_expert,
            actor=self.province_admin,
        )

        other_county = OrganizationalUnit.objects.create(
            name="شهرستان دیگر ارجاع", code="WF-REF-COUNTY-OTHER",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=self.province,
        )
        other_center = Center.objects.create(
            name="مرکز دیگر ارجاع", code="WF-REF-CENTER-OTHER",
            parent_unit=other_county, is_demo=True,
        )
        other_expert = User.objects.create_user(
            username="wf-ref-other-center", password="test-password",
            role=User.ROLE_ADMIN_IT, center=other_center,
        )
        other_referral = create_referral(
            subject="ارجاع مرکز دیگر",
            description="موضوع متعلق به مرکز دیگر",
            recipient_role="مسئول استان",
            recipient_name="مسئول نمونه",
            center=other_center,
            actor=other_expert,
        )

        self.client.force_login(self.it_expert)
        response = self.client.get(reverse("maintenance:referral_list"))
        self.assertEqual(response.status_code, 200)
        visible_ids = {row.pk for row in response.context["rows"]}
        self.assertIn(own_referral.pk, visible_ids)
        self.assertIn(assigned_referral.pk, visible_ids)
        self.assertIn(province_referral.pk, visible_ids)
        self.assertNotIn(other_referral.pk, visible_ids)

        own_file = self.client.get(f"/media/{own_referral.attachment.name}")
        province_file = self.client.get(f"/media/{province_referral.attachment.name}")
        self.assertEqual(own_file.status_code, 200)
        self.assertEqual(province_file.status_code, 200)

    def test_province_referral_can_only_be_resolved_by_recipient_or_province_manager(self):
        referral = create_referral(
            subject="ارجاع سراسری نمونه",
            description="ارجاع به مسئول مشخص استانی",
            recipient_role="مسئول مالی",
            recipient_name="مدیر نمونه",
            recipient_user=self.manager,
            actor=self.province_admin,
        )
        with self.assertRaises(PermissionDenied):
            resolve_referral(
                referral=referral, outcome="نتیجه غیرمجاز",
                instruction="", actor=self.it_expert,
            )
        resolve_referral(
            referral=referral, outcome="نتیجه ثبت‌شده توسط گیرنده",
            instruction="", actor=self.manager,
        )
        referral.refresh_from_db()
        self.assertEqual(referral.status, "resolved")

    def test_contractor_assignment_is_unique_and_history_is_retained(self):
        contractor = Contractor.objects.create(name="پیمانکار رسمی گردش")
        today = timezone.localdate()
        contract = Contract.objects.create(
            contractor=contractor, province=self.province,
            number="WF-CONTRACT-1", title="قرارداد سخت‌افزار",
            start_date=today - dt.timedelta(days=1),
            end_date=today + dt.timedelta(days=90),
            is_provincial=True,
        )
        assignment = assign_contractor_to_center(
            contract=contract, center=self.center, start_date=today,
            actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            assign_contractor_to_center(
                contract=contract, center=self.center, start_date=today,
                actor=self.province_admin,
            )
        assignment = end_contractor_assignment(
            assignment=assignment, reason="پایان دوره آزمایشی",
            actor=self.province_admin,
        )
        self.assertEqual(assignment.status, ContractCenterAssignment.STATUS_ENDED)
        self.assertTrue(ContractCenterAssignment.objects.filter(pk=assignment.pk).exists())

    def test_stale_repair_decision_cannot_overwrite_a_newer_decision(self):
        stale_repair = self._repair()
        decide_repair_request(
            repair=stale_repair, decision="approve",
            note="تایید اولیه", actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            decide_repair_request(
                repair=stale_repair, decision="reject",
                note="تلاش برای تغییر تصمیم قبلی", actor=self.province_admin,
            )
        stale_repair.refresh_from_db()
        self.assertEqual(stale_repair.status, RepairRequest.STATUS_APPROVED)
        self.assertEqual(stale_repair.events.count(), 2)

    def test_stale_completion_cannot_create_duplicate_feedback(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair, decision="approve",
            note="تایید اولیه", actor=self.province_admin,
        )
        stale_repair = RepairRequest.objects.get(pk=repair.pk)
        complete_repair_request(
            repair=repair, actor=self.it_expert,
            outcome="تعمیر انجام شد", final_cost=Decimal("900000"),
            work_quality=5, completion_speed=4, cost_fairness=4,
        )
        with self.assertRaises(ValidationError):
            complete_repair_request(
                repair=stale_repair, actor=self.it_expert,
                outcome="ارسال تکراری", final_cost=Decimal("900000"),
                work_quality=1, completion_speed=1, cost_fairness=1,
            )
        self.assertEqual(RepairFeedback.objects.filter(repair_request_id=repair.pk).count(), 1)
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.STATUS_COMPLETED)

    def test_stale_cost_dispute_decision_cannot_overwrite_resolution(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair, decision="approve",
            note="تایید اولیه", actor=self.province_admin,
        )
        repair = complete_repair_request(
            repair=repair, actor=self.it_expert,
            outcome="تعمیر انجام شد", final_cost=Decimal("1200000"),
            final_cost_reason="افزایش قیمت قطعه",
            work_quality=4, completion_speed=4, cost_fairness=3,
        )
        stale_repair = RepairRequest.objects.get(pk=repair.pk)
        resolve_repair_cost_dispute(
            repair=repair, decision="settled",
            note="اختلاف با توافق طرفین تسویه شد.", actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            resolve_repair_cost_dispute(
                repair=stale_repair, decision="reject_increase",
                note="تلاش برای بازنویسی تصمیم", actor=self.province_admin,
            )
        repair.refresh_from_db()
        self.assertEqual(repair.status, RepairRequest.STATUS_RESOLVED)
        self.assertEqual(repair.cost_dispute_resolution, "اختلاف با توافق طرفین تسویه شد.")

    def test_stale_referral_resolution_cannot_overwrite_recorded_outcome(self):
        referral = create_referral(
            subject="ارجاع برای بررسی", description="شرح موضوع",
            recipient_role="مسئول مالی", recipient_name="مسئول نمونه",
            center=self.center, actor=self.province_admin,
        )
        stale_referral = GeneralReferral.objects.get(pk=referral.pk)
        resolve_referral(
            referral=referral, outcome="نتیجه اول", instruction="دستور اول",
            actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            resolve_referral(
                referral=stale_referral, outcome="نتیجه بازنویسی‌شده",
                instruction="دستور بازنویسی‌شده", actor=self.province_admin,
            )
        referral.refresh_from_db()
        self.assertEqual(referral.outcome, "نتیجه اول")
        self.assertEqual(referral.status, GeneralReferral.STATUS_RESOLVED)

    def test_stale_general_request_resolution_cannot_overwrite_decision(self):
        request = create_general_it_request(
            center=self.center, request_type=GeneralITRequest.TYPE_EQUIPMENT,
            title="درخواست تجهیز", description="شرح درخواست", actor=self.requester,
        )
        request = manager_decide_general_it_request(
            request=request, decision="approve",
            note="تایید مدیر مرکز", actor=self.manager,
        )
        assign_general_it_request(
            request=request, expert=self.it_expert, actor=self.it_expert,
        )
        request = escalate_general_it_request(
            request=request, actor=self.it_expert,
        )
        stale_request = GeneralITRequest.objects.get(pk=request.pk)
        resolve_general_it_request(
            request=request, decision="تامین تجهیز تایید شد.",
            actor=self.province_admin,
        )
        with self.assertRaises(ValidationError):
            resolve_general_it_request(
                request=stale_request, decision="تغییر نتیجه قبلی",
                actor=self.province_admin,
            )
        request.refresh_from_db()
        self.assertEqual(request.status, GeneralITRequest.STATUS_RESOLVED)
        self.assertEqual(request.provincial_decision, "تامین تجهیز تایید شد.")

    def test_requester_can_create_general_it_request_through_the_view(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("maintenance:it_request_create"),
            {
                "request_type": GeneralITRequest.TYPE_ISSUE,
                "center": self.center.pk,
                "asset": "",
                "title": "درخواست عمومی از سمت درخواست‌کننده",
                "description": "شرح مشکل ثبت‌شده توسط کاربر مرکز",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GeneralITRequest.objects.filter(
                requested_by=self.requester,
                title="درخواست عمومی از سمت درخواست‌کننده",
            ).exists()
        )

    def test_general_it_request_creation_notifies_and_assignment_is_state_guarded(self):
        request = create_general_it_request(
            center=self.center,
            request_type="equipment",
            title="درخواست تجهیز جدید",
            description="نیاز به تجهیز جدید",
            actor=self.requester,
        )
        self.assertTrue(request.events.filter(action="created").exists())
        self.assertEqual(
            request.manager_approval,
            GeneralITRequest.MANAGER_PENDING,
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.manager,
                title="درخواست جدید برای بررسی مدیر مرکز",
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.it_expert,
                title="درخواست جدید فناوری اطلاعات",
            ).exists()
        )

        second_expert = User.objects.create_user(
            username="wf-second-center-it",
            password="test-password",
            role=User.ROLE_ADMIN_IT,
            center=self.center,
        )
        with self.assertRaises(ValidationError):
            assign_general_it_request(
                request=request, expert=second_expert, actor=self.it_expert,
            )
        request = manager_decide_general_it_request(
            request=request, decision="approve",
            note="تایید مدیر مرکز", actor=self.manager,
        )
        assign_general_it_request(
            request=request, expert=second_expert, actor=self.it_expert,
        )
        request.refresh_from_db()
        self.assertEqual(request.status, GeneralITRequest.STATUS_ASSIGNED)
        self.assertEqual(request.assigned_to_id, second_expert.pk)
        self.assertTrue(
            Notification.objects.filter(
                user=second_expert,
                title="درخواست IT جدید به شما ارجاع شد",
            ).exists()
        )

        request.status = GeneralITRequest.STATUS_ESCALATED
        request.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            assign_general_it_request(
                request=request, expert=self.it_expert, actor=self.it_expert,
            )

    def test_equipment_request_skips_manager_approval_when_center_has_no_active_manager(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_EQUIPMENT,
            title="درخواست تجهیز بدون مدیر فعال",
            description="مرکز در حال حاضر مدیر فعال ندارد.",
            actor=self.requester,
        )
        self.assertEqual(
            request.manager_approval,
            GeneralITRequest.MANAGER_NOT_REQUIRED,
        )
        self.assertFalse(
            Notification.objects.filter(
                user=self.manager,
                title="درخواست جدید برای بررسی مدیر مرکز",
            ).exists()
        )
        assigned = assign_general_it_request(
            request=request, expert=self.it_expert, actor=self.it_expert,
        )
        self.assertEqual(assigned.status, GeneralITRequest.STATUS_ASSIGNED)

    def test_manager_requester_cannot_self_approve_when_another_manager_exists(self):
        second_manager = User.objects.create_user(
            username="wf-second-manager",
            password="test-password",
            role=User.ROLE_MANAGER,
            center=self.center,
        )
        request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_EQUIPMENT,
            title="درخواست مدیر با مدیر دوم",
            description="باید مدیر دیگری بررسی کند.",
            actor=self.manager,
        )
        self.assertEqual(
            request.manager_approval,
            GeneralITRequest.MANAGER_PENDING,
        )
        with self.assertRaises(PermissionDenied):
            manager_decide_general_it_request(
                request=request, decision="approve",
                note="تلاش برای تایید خود", actor=self.manager,
            )
        approved = manager_decide_general_it_request(
            request=request, decision="approve",
            note="تایید توسط مدیر دوم", actor=second_manager,
        )
        self.assertEqual(
            approved.manager_approval,
            GeneralITRequest.MANAGER_APPROVED,
        )

    def test_manager_who_submits_equipment_request_does_not_self_approve(self):
        request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_EQUIPMENT,
            title="درخواست تجهیز توسط مدیر",
            description="مدیر مرکز خودش درخواست را ثبت کرده است.",
            actor=self.manager,
        )
        self.assertEqual(
            request.manager_approval,
            GeneralITRequest.MANAGER_NOT_REQUIRED,
        )
        self.assertFalse(
            Notification.objects.filter(
                user=self.manager,
                title="درخواست جدید برای بررسی مدیر مرکز",
            ).exists()
        )

    def test_issue_request_can_escalate_without_manager_bypass(self):
        request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_ISSUE,
            title="کمبود تجهیز",
            description="شرح کمبود",
            actor=self.requester,
        )
        self.assertEqual(
            request.manager_approval,
            GeneralITRequest.MANAGER_NOT_REQUIRED,
        )
        escalated = escalate_general_it_request(
            request=request,
            actor=self.it_expert,
        )
        self.assertEqual(escalated.status, GeneralITRequest.STATUS_ESCALATED)
        self.assertEqual(
            escalated.manager_approval,
            GeneralITRequest.MANAGER_NOT_REQUIRED,
        )

    def test_technicians_cannot_view_center_repair_requests_or_other_general_it_requests(self):
        repair = self._repair()
        technician = User.objects.create_user(
            username="wf-technician-scope",
            password="test-password",
            role=User.ROLE_TECHNICIAN,
            center=self.center,
        )
        self.assertFalse(
            visible_repair_requests(technician).filter(pk=repair.pk).exists()
        )
        self.assertTrue(
            visible_repair_requests(self.it_expert).filter(pk=repair.pk).exists()
        )

        own_request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_ISSUE,
            title="درخواست متعلق به تکنسین",
            description="شرح درخواست خود تکنسین",
            actor=technician,
        )
        other_request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_ISSUE,
            title="درخواست متعلق به کاربر دیگر",
            description="شرح درخواست دیگر",
            actor=self.requester,
        )
        visible = visible_general_it_requests(technician)
        self.assertTrue(visible.filter(pk=own_request.pk).exists())
        self.assertFalse(visible.filter(pk=other_request.pk).exists())

    def test_stale_manager_review_cannot_replace_first_decision(self):
        request = create_general_it_request(
            center=self.center, request_type=GeneralITRequest.TYPE_REPLACEMENT,
            title="جایگزینی تجهیز", description="شرح درخواست", actor=self.requester,
        )
        stale_request = GeneralITRequest.objects.get(pk=request.pk)
        manager_decide_general_it_request(
            request=request, decision="approve",
            note="تایید مدیر مرکز", actor=self.manager,
        )
        assign_general_it_request(
            request=request, expert=self.it_expert, actor=self.it_expert,
        )
        with self.assertRaises(ValidationError):
            manager_decide_general_it_request(
                request=stale_request, decision="reject",
                note="تلاش برای تغییر تصمیم", actor=self.manager,
            )
        request.refresh_from_db()
        self.assertEqual(request.manager_approval, GeneralITRequest.MANAGER_APPROVED)
        self.assertEqual(request.status, GeneralITRequest.STATUS_APPROVED)

    def test_new_general_request_notifies_active_center_it_experts(self):
        request = create_general_it_request(
            center=self.center,
            request_type=GeneralITRequest.TYPE_ISSUE,
            title="اختلال در سامانه",
            description="کاربر امکان استفاده از سامانه را ندارد.",
            actor=self.requester,
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.it_expert,
                title="درخواست جدید فناوری اطلاعات",
                url=f"/maintenance/requests/{request.pk}/",
            ).exists()
        )
