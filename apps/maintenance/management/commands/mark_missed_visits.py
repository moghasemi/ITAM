"""نشان‌دارکردن بازدیدهای دوره‌ای خارج از مهلت و اطلاع‌رسانی به کارشناسان IT."""
from django.core.management.base import BaseCommand

from apps.maintenance.services import mark_missed_visits


class Command(BaseCommand):
    help = "بازدیدهای دوره‌ای که مهلت آن‌ها گذشته و انجام نشده‌اند را نشان‌دار می‌کند"

    def handle(self, *args, **options):
        count = mark_missed_visits()
        self.stdout.write(self.style.SUCCESS(f"{count} بازدید خارج از مهلت نشان‌دار شد."))
