"""آزمون‌های گردش کار درخواست خرابی، محاسبه SLA و کنترل دسترسی."""
from __future__ import annotations

import datetime as dt

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
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
from apps.org.models import Contract, Contractor, SlaPolicy

from .models import Ticket, TicketEvent, TicketPause
from .services import (
    acknowledge,
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
        cls.contractor = Contractor.objects.create(name="پیمانکار آزمون")
        cls.contract = Contract.objects.create(
            contractor=cls.contractor,
            number="C-100",
            title="قرارداد آزمون",
            start_date=timezone.localdate() - dt.timedelta(days=30),
            end_date=timezone.localdate() + dt.timedelta(days=330),
            visit_interval_days=90,
        )
        SlaPolicy.objects.create(
            contract=cls.contract, priority=PRIORITY_HIGH,
            response_minutes=60, resolve_minutes=480,
        )
        cls.category = AssetCategory.objects.create(name="کیس", code="PC")
        cls.asset = Asset.objects.create(
            asset_tag="A-1000", category=cls.category, contract=cls.contract, status="active"
        )
        cls.it_expert = User.objects.create_user(
            username="expert", password="pass12345", role=User.ROLE_ADMIN_IT
        )
        cls.technician = User.objects.create_user(
            username="tech", password="pass12345", role=User.ROLE_TECHNICIAN, contractor=cls.contractor
        )
        cls.requester = User.objects.create_user(
            username="user", password="pass12345", role=User.ROLE_REQUESTER
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
