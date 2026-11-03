"""ارسال رخدادهای در انتظار به سامانه مدیریت.

این فرمان را می‌توان از زمان‌بند ویندوز (Task Scheduler) هر چند دقیقه اجرا کرد:
    python manage.py dispatch_outbox --limit 200
"""
from django.core.management.base import BaseCommand

from apps.integrations.services import dispatch_pending, requeue_dead_events


class Command(BaseCommand):
    help = "ارسال رخدادهای صف Outbox به مقصدهای فعال سامانه مدیریت"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="حداکثر تعداد رخداد در هر اجرا")
        parser.add_argument("--requeue-dead", action="store_true", help="بازگردانی رخدادهای متوقف‌شده به صف")

    def handle(self, *args, **options):
        if options["requeue_dead"]:
            count = requeue_dead_events()
            self.stdout.write(f"بازگردانی‌شده به صف: {count}")

        summary = dispatch_pending(limit=options["limit"])
        if not summary["endpoints"]:
            self.stdout.write(
                self.style.WARNING(
                    "هیچ مقصد فعالی تعریف نشده است؛ رخدادها در صف داخلی باقی می‌مانند."
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"پردازش‌شده: {summary['processed']} — موفق: {summary['sent']} — "
                f"ناموفق: {summary['failed']} — بی‌مقصد: {summary['skipped']}"
            )
        )
