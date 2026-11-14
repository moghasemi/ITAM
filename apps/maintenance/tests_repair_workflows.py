import datetime as dt
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.maintenance.repair_models import (
    GeneralITRequest, IndependentRepairer, RepairFeedback, RepairerProfileEvent,
    RepairRequest, RepairerStatusEvent,
)
from apps.maintenance.repair_services import (
    add_feedback_reply,
    assign_contractor_to_center,
    assign_general_it_request,
    complete_repair_request,
    create_general_it_request,
    create_repair_request,
    decide_repair_request,
    end_contractor_assignment,
    escalate_general_it_request,
    manager_decide_general_it_request,
    resolve_general_it_request,
    resolve_repair_cost_dispute,
    resubmit_repair_request,
    set_repairer_active,
    visible_repair_feedback,
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

    def test_returned_request_can_be_resubmitted_but_final_rejection_cannot(self):
        repair = self._repair()
        repair = decide_repair_request(
            repair=repair, decision="return", note="برآورد را اصلاح کنید.",
            actor=self.province_admin,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_RETURNED)
        repair = resubmit_repair_request(
            repair=repair, actor=self.it_expert,
            estimate_amount=Decimal("1100000"),
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_PENDING)
        repair = decide_repair_request(
            repair=repair, decision="reject", note="درخواست فاقد توجیه است.",
            actor=self.province_admin,
        )
        self.assertEqual(repair.status, RepairRequest.STATUS_REJECTED)
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

    def test_provincial_it_experts_can_see_all_feedback_in_their_province(self):
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
        repair = create_repair_request(
            center=other_center, asset=other_asset, repairer=self.repairer,
            fault_description="خرابی نمونه", referral_reason="ارجاع نمونه",
            estimate_amount=Decimal("500000"), actor=other_expert,
        )
        repair = decide_repair_request(
            repair=repair, decision="approve", note="تایید", actor=self.province_admin,
        )
        complete_repair_request(
            repair=repair, actor=other_expert, outcome="تعمیر شد",
            final_cost=Decimal("500000"), work_quality=5,
            completion_speed=5, cost_fairness=5,
        )

        visible = visible_repair_feedback(self.it_expert)
        self.assertTrue(visible.filter(repair_request=repair).exists())

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
