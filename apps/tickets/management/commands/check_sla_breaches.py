"""نشان‌دارکردن درخواست‌های دارای نقض SLA و ثبت رخداد آن.

اجرای دوره‌ای پیشنهادی: هر ۳۰ دقیقه از زمان‌بند ویندوز.
    python manage.py check_sla_breaches
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.constants import TICKET_OPEN_STATUSES
from apps.tickets.models import Ticket
from apps.tickets.services import detect_sla_breach, recalculate_sla, sla_state


class Command(BaseCommand):
    help = "بررسی درخواست‌های باز و ثبت رخداد نقض SLA"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        now = timezone.now()
        queryset = (
            Ticket.objects.filter(status__in=TICKET_OPEN_STATUSES)
            .select_related("asset", "contract")
            .order_by("reported_at")[: options["limit"]]
        )
        checked = 0
        breached = 0
        for ticket in queryset:
            checked += 1
            recalculate_sla(ticket)
            state = sla_state(ticket)
            before = ticket.events.filter(meta__flag__startswith="sla_breach_logged").count()
            detect_sla_breach(ticket)
            after = ticket.events.filter(meta__flag__startswith="sla_breach_logged").count()
            if after > before:
                breached += 1
                self.stdout.write(
                    f"نقض SLA — {ticket.number} | {ticket.asset.asset_tag} | "
                    f"پاسخ: {state['response_state']} | رفع: {state['resolve_state']}"
                )
        self.stdout.write(
            self.style.SUCCESS(f"بررسی‌شده: {checked} درخواست — نقض تازه ثبت‌شده: {breached}")
        )
