"""آزمون‌های گردش کار درخواست خرابی، محاسبه SLA و کنترل دسترسی."""
from __future__ import annotations

import datetime as dt

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.core import jalali
from apps.core.constants import (
    PRIORITY_HIGH,
    STATUS_ACKNOWLEDGED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_REPORTED,
    STATUS_RESOLVED,
    STATUS_USER_CONFIRMED,
    STATUS_WAITING_PARTS,
)
from apps.core.models import SystemSetting
from apps.integrations.models import OutboxEvent
from apps.org.models import (
    Center, Contract, ContractCenterAssignment, Contractor, OrganizationalUnit, SlaPolicy,
)

from .models import Ticket, TicketAttachment, TicketEvent, TicketPause
from .services import (
    acknowledge,
    can_confirm_as_it,
    can_confirm_as_user,
    can_manage_ticket,
    visible_tickets,
    confirm_by_it,
    confirm_by_user,
    create_ticket,
    declare_resolved,
    mark_arrived,
    pause_clock,
    recalculate_sla,
    reject_by_user,
    resume_clock,
    sla_state,
    start_work,
)


class TicketWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="ستاد کشور", code="TEST-NAT", unit_type=OrganizationalUnit.UNIT_NATIONAL
        )
        province = OrganizationalUnit.objects.create(
            name="استان آزمون", code="TEST-PROV", unit_type=OrganizationalUnit.UNIT_PROVINCE,
            parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شهرستان آزمون", code="TEST-COUNTY", unit_type=OrganizationalUnit.UNIT_COUNTY,
            parent=province,
        )
        cls.center = Center.objects.create(
            name="مرکز آزمون", code="TEST-CENTER", parent_unit=county
        )
        cls.contractor = Contractor.objects.create(name="پیمانکار آزمون")
        cls.contract = Contract.objects.create(
            contractor=cls.contractor,
            province=province,
            number="C-100",
            title="قرارداد آزمون",
            start_date=timezone.localdate() - dt.timedelta(days=30),
            end_date=timezone.localdate() + dt.timedelta(days=330),
            visit_interval_days=90,
        )
        cls.contract.centers.add(cls.center)
        SlaPolicy.objects.create(
            contract=cls.contract, priority=PRIORITY_HIGH,
            response_minutes=60, resolve_minutes=480,
        )
        cls.category = AssetCategory.objects.create(name="کیس", code="PC")
        cls.asset = Asset.objects.create(
            asset_tag="A-1000", category=cls.category, contract=cls.contract,
            center=cls.center, status="active"
        )
        cls.it_expert = User.objects.create_user(
            username="expert", password="pass12345", role=User.ROLE_ADMIN_IT,
            center=cls.center
        )
        province_admin = User.objects.create_user(
            username="ticket-province-admin", password="pass12345",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=province,
        )
        cls.technician = User.objects.create_user(
            username="tech", password="pass12345", role=User.ROLE_TECHNICIAN,
            contractor=cls.contractor, org_unit=province,
        )
        ContractCenterAssignment.objects.create(
            contract=cls.contract, center=cls.center,
            start_date=timezone.localdate(),
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=province_admin,
        )
        cls.requester = User.objects.create_user(
            username="user", password="pass12345", role=User.ROLE_REQUESTER,
            center=cls.center
        )

    def setUp(self):
        cache.clear()
        setting = SystemSetting.load()
        setting.counting_mode = SystemSetting.COUNTING_WORK_HOURS
        setting.work_start = dt.time(0, 0)
        setting.work_end = dt.time(23, 59)
        setting.work_days = [0, 1, 2, 3, 4, 5, 6]
        setting.exclude_holidays = False
        setting.require_user_confirmation = True
        setting.require_it_confirmation = True
        setting.save()
        cache.clear()

    def _create(self, **kwargs):
        defaults = {
            "asset": self.asset,
            "title": "روشن نشدن کیس",
            "description": "کیس پس از قطع برق روشن نمی‌شود.",
            "priority": PRIORITY_HIGH,
            "user": self.requester,
            "failure_type": "power",
        }
        defaults.update(kwargs)
        return create_ticket(**defaults)

    # ------------------------------------------------------------------
    def test_number_format(self):
        ticket = self._create()
        year = jalali.jalaali_today().year
        self.assertTrue(ticket.number.startswith(f"TK-{year}-"))
        self.assertEqual(ticket.number, f"TK-{year}-0001")

    def test_creation_sets_sla_deadlines_and_events(self):
        ticket = self._create()
        self.assertEqual(ticket.status, STATUS_REPORTED)
        self.assertIsNotNone(ticket.reported_at)
        self.assertIsNotNone(ticket.response_due_at)
        self.assertIsNotNone(ticket.resolve_due_at)
        self.assertEqual(ticket.contract_id, self.contract.pk)
        self.assertEqual(ticket.assigned_contractor_id, self.contractor.pk)
        self.assertEqual(ticket.events.count(), 1)
        self.assertEqual(ticket.events.first().event_type, TicketEvent.EVENT_CREATED)
        self.assertTrue(
            OutboxEvent.objects.filter(event_type="ticket.reported", aggregate_id=ticket.pk).exists()
        )


    def test_ticket_notifications_do_not_cross_center_boundaries(self):
        county = self.center.parent_unit
        other_center = Center.objects.create(
            name="مرکز دوم اعلان", code="NOTIFY-CENTER-2", parent_unit=county,
        )
        other_it = User.objects.create_user(
            username="other-center-it", password="pass12345",
            role=User.ROLE_ADMIN_IT, center=other_center,
        )
        self._create()
        self.assertTrue(self.it_expert.notifications.exists())
        self.assertFalse(other_it.notifications.exists())


    def test_ticket_sla_start_cannot_be_backdated_by_service_caller(self):
        requested_past = timezone.now() - dt.timedelta(days=365)
        before_create = timezone.now()
        ticket = self._create(reported_at=requested_past)
        self.assertGreaterEqual(ticket.reported_at, before_create)
        self.assertNotEqual(ticket.reported_at, requested_past)

    def test_requester_cannot_spoof_reporter_identity_in_create_form(self):
        from apps.tickets.forms import TicketCreateForm

        form = TicketCreateForm(
            data={
                "asset": str(self.asset.pk),
                "title": "خرابی ثبت‌شده",
                "description": "شرح کامل خرابی برای آزمون",
                "priority": PRIORITY_HIGH,
                "failure_type": "power",
                "reporter_name": "کاربر جعلی",
                "reporter_phone": "09120000000",
                "reported_at": "1400/01/01 00:00",
            },
            user=self.requester,
            assets=Asset.objects.filter(pk=self.asset.pk),
        )
        self.assertTrue(form.is_valid(), form.errors)
        ticket = form.save(commit=False)
        self.assertEqual(ticket.reporter_name, self.requester.display_name)
        self.assertEqual(ticket.reporter_phone, self.requester.phone)
        self.assertEqual(ticket.reported_by_id, self.requester.pk)

    def test_technician_cannot_manage_ticket_when_asset_is_bound_to_foreign_contract_province(self):
        national = self.center.parent_unit.parent.parent
        province_b = OrganizationalUnit.objects.create(
            name="استان دوم آزمون", code="TEST-PROV-SECOND",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_b = OrganizationalUnit.objects.create(
            name="شهرستان دوم استان دوم", code="TEST-COUNTY-SECOND",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province_b,
        )
        center_b = Center.objects.create(
            name="مرکز استان دوم", code="TEST-CENTER-SECOND", parent_unit=county_b,
        )
        Contract.objects.create(
            contractor=self.contractor,
            province=province_b,
            number="C-200",
            title="قرارداد فعال استان دوم",
            start_date=timezone.localdate() - dt.timedelta(days=5),
            end_date=timezone.localdate() + dt.timedelta(days=30),
            visit_interval_days=90,
        )
        # The asset is physically in province B but references province A's contract.
        foreign_asset = Asset.objects.create(
            asset_tag="A-FOREIGN-CONTRACT-PROVINCE",
            category=self.category,
            contract=self.contract,
            center=center_b,
            status="active",
        )
        ticket = self._create(asset=foreign_asset)
        self.assertFalse(visible_tickets(self.technician).filter(pk=ticket.pk).exists())
        self.assertFalse(can_manage_ticket(self.technician, ticket))

    def test_acknowledge_permission(self):
        ticket = self._create()
        with self.assertRaises(PermissionDenied):
            acknowledge(ticket, self.requester)

    def test_acknowledge_only_from_reported(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_ACKNOWLEDGED)
        with self.assertRaises(ValidationError):
            acknowledge(ticket, self.technician)

    def test_it_confirmation_is_center_scoped(self):
        other_county = OrganizationalUnit.objects.create(
            name="شهرستان دوم", code="TEST-COUNTY-2",
            unit_type=OrganizationalUnit.UNIT_COUNTY,
            parent=self.center.parent_unit.parent,
        )
        other_center = Center.objects.create(
            name="مرکز دوم", code="TEST-CENTER-2", parent_unit=other_county
        )
        other_it = User.objects.create_user(
            username="other-expert", password="pass12345",
            role=User.ROLE_ADMIN_IT, center=other_center,
        )
        ticket = self._create()
        ticket.status = STATUS_USER_CONFIRMED
        ticket.save(update_fields=["status"])
        self.assertFalse(can_confirm_as_it(other_it, ticket))
        with self.assertRaises(PermissionDenied):
            confirm_by_it(ticket, other_it, "تایید خارج از مرکز")

    def test_full_workflow(self):
        ticket = self._create()
        acknowledge(ticket, self.technician, "پذیرش")
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.acknowledged_at)

        mark_arrived(ticket, self.technician, "در محل حاضر شدم")
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.arrived_at)
        self.assertIsNotNone(ticket.response_minutes_used)
        self.assertTrue(ticket.response_met)

        start_work(ticket, self.technician)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_IN_PROGRESS)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "in_repair")

        declare_resolved(
            ticket, self.technician,
            root_cause="سوختن منبع تغذیه",
            action_taken="تعویض پاور و تست سیستم",
            parts_text="پاور ۴۸۰ وات",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_RESOLVED)
        self.assertIsNotNone(ticket.resolved_declared_at)
        self.assertIsNotNone(ticket.resolve_minutes_used)

        confirm_by_user(ticket, self.requester, "تایید کاربر", satisfaction=5)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_USER_CONFIRMED)
        self.assertIsNotNone(ticket.user_confirmed_at)
        self.assertEqual(ticket.satisfaction, 5)

        confirm_by_it(ticket, self.it_expert, "تایید نهایی")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_CLOSED)
        self.assertIsNotNone(ticket.it_confirmed_at)
        self.assertIsNotNone(ticket.closed_at)
        self.assertIsNotNone(ticket.total_minutes_used)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "active")

        event_types = list(ticket.events.values_list("event_type", flat=True))
        for expected in (
            TicketEvent.EVENT_CREATED,
            TicketEvent.EVENT_ACKNOWLEDGED,
            TicketEvent.EVENT_ARRIVED,
            TicketEvent.EVENT_WORK_STARTED,
            TicketEvent.EVENT_RESOLVED,
            TicketEvent.EVENT_USER_CONFIRMED,
            TicketEvent.EVENT_IT_CONFIRMED,
        ):
            self.assertIn(expected, event_types)
        self.assertTrue(
            OutboxEvent.objects.filter(event_type="ticket.closed", aggregate_id=ticket.pk).exists()
        )

    def test_pause_and_resume_updates_metrics(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        mark_arrived(ticket, self.technician)
        pause_clock(ticket, self.technician, "awaiting_parts", "انتظار قطعه")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_WAITING_PARTS)
        self.assertTrue(ticket.is_sla_paused)

        with self.assertRaises(ValidationError):
            pause_clock(ticket, self.technician, "awaiting_parts")

        pause = TicketPause.objects.get(ticket=ticket, ended_at__isnull=True)
        pause.started_at = timezone.now() - dt.timedelta(hours=3)
        pause.save(update_fields=["started_at"])

        resume_clock(ticket, self.technician, "قطعه رسید")
        ticket.refresh_from_db()
        self.assertFalse(ticket.is_sla_paused)
        self.assertGreaterEqual(ticket.paused_minutes, 170)

    def test_reject_by_user_returns_to_progress(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        mark_arrived(ticket, self.technician)
        declare_resolved(ticket, self.technician, root_cause="علت", action_taken="اقدام")
        reject_by_user(ticket, self.requester, "مشکل باقی است")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, STATUS_IN_PROGRESS)
        self.assertIsNone(ticket.resolved_declared_at)


    def test_it_role_cannot_impersonate_requester_for_user_confirmation(self):
        ticket = self._create()
        Ticket.objects.filter(pk=ticket.pk).update(status=STATUS_RESOLVED)
        ticket.refresh_from_db()
        self.assertFalse(can_confirm_as_user(self.it_expert, ticket))
        with self.assertRaises(PermissionDenied):
            confirm_by_user(ticket, self.it_expert, "تایید به جای کاربر")

    def test_province_admin_cannot_confirm_user_step_for_another_province(self):
        national = self.center.parent_unit.parent.parent
        province_b = OrganizationalUnit.objects.create(
            name="استان تایید دوم", code="TEST-CONFIRM-PROV-B",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_b = OrganizationalUnit.objects.create(
            name="شهرستان تایید دوم", code="TEST-CONFIRM-COUNTY-B",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province_b,
        )
        center_b = Center.objects.create(
            name="مرکز تایید دوم", code="TEST-CONFIRM-CENTER-B", parent_unit=county_b,
        )
        contract_b = Contract.objects.create(
            contractor=self.contractor, province=province_b,
            number="C-CONFIRM-B", title="قرارداد استان دوم",
            start_date=timezone.localdate() - dt.timedelta(days=5),
            end_date=timezone.localdate() + dt.timedelta(days=30),
        )
        asset_b = Asset.objects.create(
            asset_tag="A-CONFIRM-B", category=self.category,
            contract=contract_b, center=center_b, status="active",
        )
        ticket_b = self._create(asset=asset_b)
        Ticket.objects.filter(pk=ticket_b.pk).update(status=STATUS_RESOLVED)
        ticket_b.refresh_from_db()
        province_admin = User.objects.create_user(
            username="province-admin-confirm-test", password="pass12345",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=self.center.parent_unit.parent,
        )
        self.assertFalse(can_confirm_as_user(province_admin, ticket_b))
        with self.assertRaises(PermissionDenied):
            confirm_by_user(ticket_b, province_admin, "تایید خارج از استان")

    def test_it_cannot_bypass_required_user_confirmation(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        mark_arrived(ticket, self.technician)
        declare_resolved(ticket, self.technician, root_cause="علت", action_taken="اقدام")
        with self.assertRaises(PermissionDenied):
            confirm_by_it(ticket, self.it_expert)

    def test_user_and_it_approvals_must_be_different_actors(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        mark_arrived(ticket, self.technician)
        declare_resolved(ticket, self.technician, root_cause="علت", action_taken="اقدام")
        confirm_by_user(ticket, self.requester, "تایید")
        with self.assertRaises(PermissionDenied):
            confirm_by_it(ticket, self.requester)
        confirm_by_it(ticket, self.it_expert, "تایید مستقل IT")

    def test_only_it_can_confirm_final(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        mark_arrived(ticket, self.technician)
        declare_resolved(ticket, self.technician, root_cause="علت", action_taken="اقدام")
        with self.assertRaises(PermissionDenied):
            confirm_by_it(ticket, self.technician)

    def test_sla_breach_detection(self):
        ticket = self._create()
        Ticket.objects.filter(pk=ticket.pk).update(
            reported_at=timezone.now() - dt.timedelta(days=5),
            response_due_at=timezone.now() - dt.timedelta(days=4),
            resolve_due_at=timezone.now() - dt.timedelta(days=3),
        )
        ticket.refresh_from_db()
        state = sla_state(ticket)
        self.assertEqual(state["response_state"], "breached")
        self.assertEqual(state["resolve_state"], "breached")

        from .services import detect_sla_breach

        detect_sla_breach(ticket)
        detect_sla_breach(ticket)  # نباید رخداد تکراری ثبت شود
        breaches = ticket.events.filter(meta__flag__startswith="sla_breach_logged")
        self.assertEqual(breaches.count(), 1)

    def test_sla_met_flags(self):
        ticket = self._create()
        acknowledge(ticket, self.technician)
        mark_arrived(ticket, self.technician)
        ticket.refresh_from_db()
        self.assertTrue(ticket.response_met)
        metrics = recalculate_sla(ticket)
        self.assertEqual(metrics["response_target"], 60)
        self.assertLessEqual(metrics["response_minutes"], 5)

    def test_workflow_steps(self):
        ticket = self._create()
        steps = ticket.workflow_steps()
        self.assertEqual(len(steps), 7)
        self.assertTrue(steps[0]["active"])
        self.assertFalse(steps[0]["done"])

    def test_provincial_ticket_scope_is_limited_to_own_province(self):
        from .services import visible_tickets

        national = self.center.parent_unit.parent.parent
        other_province = OrganizationalUnit.objects.create(
            name="استان دوم", code="TEST-PROV-2",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        other_county = OrganizationalUnit.objects.create(
            name="شهرستان استان دوم", code="TEST-COUNTY-2",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=other_province,
        )
        other_center = Center.objects.create(
            name="مرکز استان دوم", code="TEST-CENTER-2", parent_unit=other_county,
        )
        other_asset = Asset.objects.create(
            asset_tag="A-OTHER", category=self.category, center=other_center, status="active"
        )
        self._create()
        misbound_ticket = self._create(asset=other_asset)
        # A stale/incorrect Ticket.center must never override the asset's real center.
        Ticket.objects.filter(pk=misbound_ticket.pk).update(center=self.center)
        provincial_admin = User.objects.create_user(
            username="provincial-admin", password="pass12345",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=self.center.parent_unit.parent,
        )
        visible_centers = set(
            visible_tickets(provincial_admin).values_list("asset__center_id", flat=True)
        )
        self.assertEqual(visible_centers, {self.center.pk})
        self.assertFalse(visible_tickets(provincial_admin).filter(
            pk=misbound_ticket.pk
        ).exists())

    def test_center_admin_without_center_sees_no_tickets(self):
        from .services import visible_tickets

        self._create()
        unscoped_admin = User.objects.create_user(
            username="unscoped-it", password="pass12345", role=User.ROLE_ADMIN_IT
        )
        self.assertFalse(visible_tickets(unscoped_admin).exists())
    def test_requester_scope(self):
        from .services import visible_tickets

        self._create()
        other = User.objects.create_user(
            username="other", password="pass12345", role=User.ROLE_REQUESTER
        )
        self.assertEqual(visible_tickets(other).count(), 0)
        self.assertEqual(visible_tickets(self.requester).count(), 1)
        self.assertEqual(visible_tickets(self.it_expert).count(), 1)
        self.assertEqual(visible_tickets(self.technician).count(), 1)


    def test_ticket_attachment_download_respects_ticket_visibility(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse

        own_ticket = self._create()
        own_attachment = TicketAttachment.objects.create(
            ticket=own_ticket,
            file=SimpleUploadedFile("own-ticket.txt", b"own ticket"),
            uploaded_by=self.requester,
        )
        other_center = Center.objects.create(
            name="مرکز دیگر آزمون",
            code="TEST-CENTER-2",
            parent_unit=self.center.parent_unit,
        )
        other_asset = Asset.objects.create(
            asset_tag="A-2000",
            category=self.category,
            contract=self.contract,
            center=other_center,
            status="active",
        )
        other_requester = User.objects.create_user(
            username="other-requester",
            password="pass12345",
            role=User.ROLE_REQUESTER,
            center=other_center,
        )
        other_ticket = create_ticket(
            asset=other_asset,
            title="درخواست مرکز دیگر",
            description="آزمون دسترسی پیوست",
            priority=PRIORITY_HIGH,
            user=other_requester,
            failure_type="power",
        )
        foreign_attachment = TicketAttachment.objects.create(
            ticket=other_ticket,
            file=SimpleUploadedFile("foreign-ticket.txt", b"foreign ticket"),
            uploaded_by=other_requester,
        )

        client = Client()
        client.force_login(self.it_expert)
        own_response = client.get(
            reverse("tickets:attachment_download", args=[own_attachment.pk])
        )
        foreign_response = client.get(
            reverse("tickets:attachment_download", args=[foreign_attachment.pk])
        )
        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(foreign_response.status_code, 403)

