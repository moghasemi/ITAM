"""بررسی سریع سلامت همه صفحات سامانه (مناسب پیش از تحویل و پس از هر تغییر).

نمونه اجرا:
    python manage.py smoke_test
    python manage.py smoke_test --user tech.pars
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.accounts.models import User
from apps.assets.models import Asset, HardwareSnapshot
from apps.assets.services import visible_assets
from apps.maintenance.models import MaintenanceVisit, VisitAssetCheck
from apps.org.models import Contract, Contractor, Department, Location
from apps.tickets.models import Ticket

#: (نام مسیر، پارامترها، کدهای قابل قبول)
ADMIN_ROUTES = [
    ("core:dashboard", None, (200,)),
    ("core:search", None, (200,)),
    ("core:notification_list", None, (200,)),
    ("core:setting_update", None, (200,)),
    ("core:holiday_list", None, (200,)),
    ("core:holiday_create", None, (200,)),
    ("core:audit_list", None, (200,)),
    ("accounts:profile", None, (200,)),
    ("accounts:profile_edit", None, (200,)),
    ("accounts:password_change", None, (200,)),
    ("accounts:user_list", None, (200,)),
    ("accounts:user_create", None, (200,)),
    ("org:department_list", None, (200,)),
    ("org:department_create", None, (200,)),
    ("org:location_list", None, (200,)),
    ("org:location_create", None, (200,)),
    ("org:contractor_list", None, (200,)),
    ("org:contractor_create", None, (200,)),
    ("org:contract_list", None, (200,)),
    ("org:contract_create", None, (200,)),
    ("assets:list", None, (200,)),
    ("assets:create", None, (200,)),
    ("assets:label_print", None, (200,)),
    ("assets:hardware_report", None, (200,)),
    ("assets:snapshot_pending", None, (200,)),
    ("assets:category_list", None, (200,)),
    ("assets:category_create", None, (200,)),
    ("assets:component_type_list", None, (200,)),
    ("assets:component_type_create", None, (200,)),
    ("tickets:list", None, (200,)),
    ("tickets:my_tickets", None, (200,)),
    ("tickets:create", None, (200,)),
    ("maintenance:visit_list", None, (200,)),
    ("maintenance:my_visits", None, (200,)),
    ("maintenance:visit_create", None, (200,)),
    ("integrations:outbox_list", None, (200,)),
    ("integrations:endpoint_list", None, (200,)),
    ("integrations:endpoint_create", None, (200,)),
    ("integrations:api_call_list", None, (200,)),
    ("reports:home", None, (200,)),
    ("reports:sla", None, (200,)),
    ("reports:sla", None, (200,)),
    ("reports:contractors", None, (200,)),
    ("reports:inventory", None, (200,)),
    ("reports:visits", None, (200,)),
    ("reports:failures", None, (200,)),
]

OBJECT_ROUTES = [
    ("accounts:user_detail", "user", (200,)),
    ("accounts:user_update", "user", (200,)),
    ("accounts:user_password", "user", (200,)),
    ("org:contractor_detail", "contractor", (200,)),
    ("org:contractor_update", "contractor", (200,)),
    ("org:department_update", "department", (200,)),
    ("org:location_update", "location", (200,)),
    ("org:contract_detail", "contract", (200,)),
    ("org:contract_update", "contract", (200,)),
    ("assets:detail", "asset", (200,)),
    ("assets:update", "asset", (200,)),
    ("assets:qr_image", "asset", (200,)),
    ("assets:snapshot_start", "asset", (200,)),
    ("assets:snapshot_detail", "snapshot", (200,)),
    ("assets:attachment_create", "asset", (200,)),
    ("tickets:detail", "ticket", (200,)),
    ("tickets:print", "ticket", (200,)),
    ("maintenance:visit_detail", "visit", (200,)),
    ("maintenance:visit_update", "visit", (200,)),
    ("maintenance:visit_print", "visit", (200,)),
    ("maintenance:check_edit", "check", (200,)),
    ("integrations:outbox_detail", "outbox", (200,)),
]

TECHNICIAN_ROUTES = [
    ("core:dashboard", None),
    ("tickets:list", None),
    ("tickets:create", None),
    ("maintenance:my_visits", None),
    ("maintenance:visit_list", None),
    ("assets:list", None),
    ("assets:detail", "asset"),
]

REQUESTER_ROUTES = [
    ("core:dashboard", None),
    ("tickets:my_tickets", None),
    ("tickets:create", None),
    ("tickets:detail", "ticket"),
    ("assets:list", None),
]


class Command(BaseCommand):
    help = "بررسی سلامت صفحات سامانه با درخواست‌های واقعی HTTP روی همه نقش‌ها"

    def add_arguments(self, parser):
        parser.add_argument("--user", help="نام کاربری برای آزمایش (پیش‌فرض: نخستین کارشناس IT)")

    def handle(self, *args, **options):
        client = Client()
        user = None
        if options.get("user"):
            user = User.objects.filter(username=options["user"]).first()
        if user is None:
            user = User.objects.filter(role=User.ROLE_ADMIN_PROVINCE, is_active=True).first() or User.objects.filter(role=User.ROLE_ADMIN_IT, is_active=True).first()
        if user is None:
            self.stderr.write(self.style.ERROR("کاربری برای آزمایش یافت نشد. ابتدا seed_demo را اجرا کنید."))
            return

        objects = {
            "user": User.objects.first(),
            "contractor": Contractor.objects.first(),
            "department": Department.objects.first(),
            "location": Location.objects.first(),
            "contract": Contract.objects.first(),
            "asset": Asset.objects.first(),
            "snapshot": HardwareSnapshot.objects.first(),
            "ticket": Ticket.objects.filter(asset__in=visible_assets(user)).first() or Ticket.objects.first(),
            "visit": MaintenanceVisit.objects.first(),
            "check": VisitAssetCheck.objects.first(),
            "outbox": self._first_outbox(),
        }

        client.force_login(user)
        failures = []
        checked = 0

        self.stdout.write(self.style.MIGRATE_HEADING(f"آزمایش با نقش {user.role_label} ({user.username})"))
        for name, arg_key, codes in ADMIN_ROUTES:
            checked += 1
            result = self._check(client, name, None, codes)
            if result:
                failures.append(result)

        for name, arg_key, codes in OBJECT_ROUTES:
            target = objects.get(arg_key)
            if target is None:
                continue
            checked += 1
            result = self._check(client, name, [target.pk], codes)
            if result:
                failures.append(result)

        # نقش‌های دیگر
        for username, routes in self._role_routes():
            actor = User.objects.filter(username=username).first()
            if actor is None:
                continue
            other_client = Client()
            other_client.force_login(actor)
            self.stdout.write(self.style.MIGRATE_HEADING(f"آزمایش با نقش {actor.role_label} ({username})"))
            for name, arg_key in routes:
                args = None
                if arg_key:
                    target = objects.get(arg_key)
                    if target is None:
                        continue
                    args = [target.pk]
                checked += 1
                result = self._check(other_client, name, args, (200,))
                if result:
                    failures.append(result)

        # صفحات خطا
        checked += 2
        for path, expected in (("/this-page-does-not-exist/", 404),):
            response = client.get(path)
            if response.status_code != expected:
                failures.append(f"{path} → کد {response.status_code} (انتظار {expected})")

        self.stdout.write("")
        if failures:
            self.stdout.write(self.style.ERROR(f"❌ {len(failures)} خطا از {checked} صفحه بررسی‌شده:"))
            for item in failures:
                self.stdout.write(self.style.ERROR(f"   • {item}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"✅ همه {checked} صفحه با موفقیت پاسخ دادند."))

    # ------------------------------------------------------------------
    def _role_routes(self):
        return [
            ("tech.pars", TECHNICIAN_ROUTES),
            ("user.karimi", REQUESTER_ROUTES),
            ("manager", [("core:dashboard", None), ("reports:home", None), ("reports:sla", None), ("org:contract_list", None)]),
        ]

    def _first_outbox(self):
        from apps.integrations.models import OutboxEvent

        return OutboxEvent.objects.first()

    def _check(self, client, name, args, codes):
        try:
            url = reverse(name, args=args) if args else reverse(name)
        except NoReverseMatch as exc:
            return f"{name} → مسیر یافت نشد ({exc})"
        try:
            response = client.get(url)
        except Exception as exc:  # noqa: BLE001
            return f"{name} ({url}) → خطای اجرا: {exc.__class__.__name__}: {exc}"
        if response.status_code not in codes:
            return f"{name} ({url}) → کد {response.status_code} (انتظار {codes})"
        return None
