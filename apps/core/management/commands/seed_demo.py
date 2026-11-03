"""ایجاد داده نمونه و کاربران پایه برای راه‌اندازی سریع سامانه.

نمونه اجرا:
    python manage.py seed_demo
    python manage.py seed_demo --admin-password 12345678
"""
from __future__ import annotations

import datetime as dt
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import (
    Asset,
    AssetCategory,
    ComponentType,
    HardwareSnapshot,
    SnapshotItem,
)
from apps.assets.services import approve_snapshot, create_snapshot, submit_snapshot
from apps.core.constants import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MEDIUM
from apps.core.models import Holiday, SystemSetting
from apps.maintenance.services import generate_visits
from apps.org.models import Contract, Contractor, Department, Location, SlaPolicy
from apps.tickets.models import Ticket, TicketPart
from apps.tickets.services import (
    acknowledge,
    declare_resolved,
    confirm_by_it,
    confirm_by_user,
    create_ticket,
    mark_arrived,
    pause_clock,
    resume_clock,
    start_work,
)

COMPONENT_TYPES = [
    ("پردازنده (CPU)", "CPU", True, 10, True),
    ("حافظه رم (RAM)", "RAM", True, 20, True),
    ("هارد دیسک / حافظه داخلی", "SSD", True, 30, True),
    ("کارت گرافیک", "GPU", True, 40, True),
    ("منبع تغذیه (پاور)", "PSU", True, 50, True),
    ("مادربرد", "MB", True, 60, True),
    ("درایو نوری", "ODD", False, 70, False),
    ("فن و خنک‌کننده", "FAN", False, 80, False),
    ("کارت شبکه", "NIC", True, 90, False),
    ("کیس و بدنه", "CASE", False, 100, False),
]

CATEGORIES = [
    ("کیس رایانه رومیزی", "PC", "🖥", True),
    ("لپ‌تاپ", "LAP", "💻", True),
    ("پرینتر", "PRN", "🖨", False),
    ("اسکنر", "SCN", "📠", False),
    ("مانیتور", "MON", "🖥", False),
    ("تجهیز شبکه", "NET", "🌐", False),
    ("تجهیز جانبی", "ACC", "🔌", False),
]


class Command(BaseCommand):
    help = "ایجاد داده نمونه، کاربران پایه و قرارداد نمونه برای شروع کار"

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", default="Admin@1403", help="گذرواژه کاربران نمونه")
        parser.add_argument("--assets", type=int, default=12, help="تعداد دارایی نمونه")
        parser.add_argument("--no-demo-tickets", action="store_true", help="بدون ساخت درخواست نمونه")
        parser.add_argument("--reset", action="store_true", help="پاک‌کردن داده‌های نمونه قبلی")

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["admin_password"]
        asset_count = options["assets"]

        self.stdout.write(self.style.MIGRATE_HEADING("۱) تنظیمات سامانه"))
        setting = SystemSetting.load()
        setting.org_name = setting.org_name or "اداره کل"
        setting.site_name = setting.site_name or "سامانه مدیریت دارایی و نگهداری فناوری اطلاعات"
        setting.public_base_url = setting.public_base_url or "http://127.0.0.1:8000"
        setting.work_days = setting.work_days or [5, 6, 0, 1, 2]
        setting.save()
        self.stdout.write(f"   سازمان: {setting.org_name}")

        self.stdout.write(self.style.MIGRATE_HEADING("۲) تعطیلات نمونه"))
        for title, month, day in [
            ("نوروز", 1, 1), ("نوروز", 1, 2), ("نوروز", 1, 3), ("نوروز", 1, 4),
            ("روز جمهوری اسلامی", 1, 12), ("سیزده‌بدر", 1, 13),
        ]:
            from apps.core import jalali

            jyear = jalali.jalaali_today().year
            date_value = jalali.jalali_to_gregorian(jyear, month, day)
            Holiday.objects.get_or_create(
                date=date_value,
                defaults={"title": title, "is_recurring_annual": True},
            )

        self.stdout.write(self.style.MIGRATE_HEADING("۳) واحدها و محل‌ها"))
        departments = {}
        for name, code, manager in [
            ("حوزه ریاست", "100", "محمد رضایی"),
            ("معاونت اداری و مالی", "200", "زهرا کریمی"),
            ("واحد فناوری اطلاعات", "210", "علی محمدی"),
            ("امور کارکنان", "300", "سارا احمدی"),
            ("دبیرخانه", "400", "حسین نوری"),
        ]:
            department, _ = Department.objects.get_or_create(
                name=name, defaults={"code": code, "manager_name": manager}
            )
            departments[code] = department

        locations = {}
        for building, floor, room in [
            ("ساختمان مرکزی", "همکف", "اتاق ۱۰۱"),
            ("ساختمان مرکزی", "طبقه اول", "اتاق ۲۰۳"),
            ("ساختمان مرکزی", "طبقه دوم", "اتاق ۳۰۵"),
            ("ساختمان معاونت", "همکف", "اتاق ۱۱۲"),
        ]:
            location, _ = Location.objects.get_or_create(
                name=room, building=building, floor=floor, room=room
            )
            locations[(building, room)] = location

        self.stdout.write(self.style.MIGRATE_HEADING("۴) پیمانکار و قرارداد"))
        contractor, _ = Contractor.objects.get_or_create(
            name="شرکت پشتیبان فناوری پارس",
            defaults={
                "code": "CN-1001",
                "contact_person": "رضا شریفی",
                "contact_phone": "021-88990011",
                "phone": "021-88990010",
                "email": "support@pars-it.example",
                "national_id": "10101010101",
                "address": "تهران، خیابان آزادی، پلاک ۱۲",
            },
        )

        today = timezone.localdate()
        contract, created = Contract.objects.get_or_create(
            number="1403/IT/07",
            defaults={
                "contractor": contractor,
                "title": "نگهداری و تعمیر تجهیزات رایانه‌ای و چاپگرها",
                "start_date": today - dt.timedelta(days=60),
                "end_date": today + dt.timedelta(days=305),
                "visit_interval_days": 90,
                "visit_scope": "بازدید دوره‌ای فصلی، سرویس و نظافت داخلی تجهیزات، بررسی سلامت قطعات",
                "repair_scope": "رفع خرابی سخت‌افزاری و نرم‌افزاری کیس‌ها و پرینترها، تامین قطعات",
                "status": Contract.STATUS_ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"   قرارداد {contract.number} ایجاد شد")
        for priority, response, resolve in [
            ("critical", 60, 480),
            ("high", 240, 1440),
            ("medium", 480, 2880),
            ("low", 960, 5760),
        ]:
            SlaPolicy.objects.get_or_create(
                contract=contract,
                priority=priority,
                defaults={"response_minutes": response, "resolve_minutes": resolve},
            )

        self.stdout.write(self.style.MIGRATE_HEADING("۵) کاربران"))
        admin_it, _ = User.objects.get_or_create(
            username="admin.it",
            defaults={
                "first_name": "علی",
                "last_name": "محمدی",
                "role": User.ROLE_ADMIN_IT,
                "department": departments["210"],
                "personnel_code": "21001",
                "phone": "09121112233",
                "job_title": "کارشناس فناوری اطلاعات",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_it.set_password(password)
        admin_it.save()

        technician, _ = User.objects.get_or_create(
            username="tech.pars",
            defaults={
                "first_name": "رضا",
                "last_name": "شریفی",
                "role": User.ROLE_TECHNICIAN,
                "contractor": contractor,
                "phone": "09123334455",
                "job_title": "کارشناس پشتیبانی",
            },
        )
        technician.set_password(password)
        technician.save()

        manager, _ = User.objects.get_or_create(
            username="manager",
            defaults={
                "first_name": "محمد",
                "last_name": "رضایی",
                "role": User.ROLE_MANAGER,
                "department": departments["100"],
                "job_title": "رئیس اداره",
            },
        )
        manager.set_password(password)
        manager.save()

        requester, _ = User.objects.get_or_create(
            username="user.karimi",
            defaults={
                "first_name": "زهرا",
                "last_name": "کریمی",
                "role": User.ROLE_REQUESTER,
                "department": departments["200"],
                "phone": "09127778899",
                "personnel_code": "20112",
            },
        )
        requester.set_password(password)
        requester.save()

        self.stdout.write(f"   کاربران ساخته شد (گذرواژه: {password})")

        self.stdout.write(self.style.MIGRATE_HEADING("۶) گونه‌ها و قطعات"))
        categories = {}
        for name, code, icon, tracking in CATEGORIES:
            category, _ = AssetCategory.objects.get_or_create(
                name=name,
                defaults={
                    "code": code,
                    "icon": icon,
                    "requires_component_tracking": tracking,
                },
            )
            categories[code] = category

        components = {}
        for name, code, serialized, order, key_item in COMPONENT_TYPES:
            component_type, _ = ComponentType.objects.get_or_create(
                name=name,
                defaults={
                    "code": code,
                    "is_serialized": serialized,
                    "sort_order": order,
                    "is_key_item": key_item,
                },
            )
            components[code] = component_type

        self.stdout.write(self.style.MIGRATE_HEADING("۷) دارایی‌ها"))
        random.seed(1403)
        brands = ["DELL", "HP", "ASUS", "Lenovo", "Acer"]
        created_assets = []
        department_list = list(departments.values())
        location_list = list(locations.values())

        for index in range(1, asset_count + 1):
            is_case = index / 2 != index // 2
            code = "PC" if is_case else "PRN"
            asset_tag = f"{'۱۰۲' if False else '102'}{index:05d}"
            asset, _ = Asset.objects.get_or_create(
                asset_tag=asset_tag,
                defaults={
                    "title": f"{'کیس اداری' if is_case else 'چاپگر لیزری'} شماره {index}",
                    "category": categories[code],
                    "brand": random.choice(brands) if is_case else "HP",
                    "model_name": "OptiPlex 3080" if is_case else "LaserJet P1102",
                    "serial_number": f"SN{random.randint(100000, 999999)}{index}",
                    "contract": contract,
                    "department": department_list[index % len(department_list)],
                    "location": location_list[index % len(location_list)],
                    "custodian": requester if index % 3 == 0 else None,
                    "status": "active",
                    "hostname": f"PC-{index:03d}" if is_case else "",
                    "ip_address": f"10.10.20.{100 + index}" if is_case else None,
                    "mac_address": f"00:1A:2B:3C:4D:{index:02X}" if is_case else "",
                    "os_name": "Windows 10 Pro" if is_case else "",
                    "office_software": "Office 2019" if is_case else "",
                    "spec_summary": (
                        "کیس اداری با مادربرد اختصاصی، پاور ۵۰۰ وات و فن خنک‌کننده"
                        if is_case
                        else "چاپگر لیزری تک‌کاره، اتصال USB"
                    ),
                    "purchase_date": today - dt.timedelta(days=random.randint(400, 1500)),
                    "warranty_until": today + dt.timedelta(days=random.randint(-200, 300)),
                    "price": random.choice([25_000_000, 38_500_000, 52_000_000]) if is_case else 9_800_000,
                    "supplier": "فروشگاه رایانه مرکزی",
                },
            )
            created_assets.append(asset)

        self.stdout.write(f"   {len(created_assets)} دارایی ثبت شد")

        self.stdout.write(self.style.MIGRATE_HEADING("۸) بازدیدهای دوره‌ای"))
        result = generate_visits(contract, user=admin_it)
        self.stdout.write(f"   {result['created']} نوبت بازدید ساخته شد")

        if not options["no_demo_tickets"]:
            self.stdout.write(self.style.MIGRATE_HEADING("۹) اسنپ‌شات سخت‌افزار و درخواست‌های نمونه"))
            self._demo_hardware(created_assets, admin_it, technician, components)
            self._demo_tickets(created_assets, admin_it, technician, requester)

        self.stdout.write(self.style.SUCCESS("\nراه‌اندازی نمونه با موفقیت انجام شد."))
        self.stdout.write(
            "ورود با یکی از حساب‌های زیر:\n"
            f"  • کارشناس فناوری اطلاعات مرکز: admin.it / {password}\n"
            f"   • کارشناس پیمانکار: tech.pars / {password}\n"
            f"   • مدیر و ناظر: manager / {password}\n"
            f"   • کاربر امانت‌دار: user.karimi / {password}\n"
        )

    # ------------------------------------------------------------------
    def _demo_hardware(self, assets, admin_it, technician, components):
        """ثبت اسنپ‌شات پایه و یک بازبینی با تغییر، برای نمایش کنترل سرقت."""
        cases = [asset for asset in assets if asset.requires_component_tracking]
        if not cases:
            return
        asset = cases[0]

        if asset.snapshots.exists():
            return

        snapshot = create_snapshot(asset, technician, note="ثبت اولیه اقلام داخل کیس")
        items = [
            ("CPU", "Intel", "Core i5-10400", "CPU-8842-11", "2.9GHz", "سوکت LGA1200"),
            ("RAM", "Kingston", "DDR4 2666", "RAM-5521-77", "8GB", "اسلات ۱"),
            ("RAM", "Kingston", "DDR4 2666", "RAM-5521-78", "8GB", "اسلات ۲"),
            ("SSD", "Samsung", "870 EVO", "SSD-3311-09", "500GB", "SATA 0"),
            ("PSU", "Green", "GP480A", "PSU-7781-33", "480W", "بالای کیس"),
            ("MB", "ASUS", "H510M-E", "MB-2211-45", "", "داخل کیس"),
            ("ODD", "LG", "DVD-RW", "", "", "درایو بالا"),
            ("FAN", "Green", "120mm", "", "", "پشت کیس"),
        ]
        for code, brand, model, serial, capacity, slot in items:
            SnapshotItem.objects.create(
                snapshot=snapshot,
                component_type=components[code],
                brand=brand,
                model_name=model,
                serial_number=serial,
                capacity=capacity,
                slot=slot,
            )
        submit_snapshot(snapshot, technician)
        approve_snapshot(snapshot, admin_it)
        self.stdout.write(f"   اسنپ‌شات پایه برای {asset.asset_tag} تایید و قفل شد")

        # بازبینی دوره‌ای با یک تعویض و یک مفقودی
        review = create_snapshot(asset, technician, note="بازبینی دوره‌ای اقلام")
        for item in review.items.all():
            if item.component_type.code == "SSD":
                item.serial_number = "SSD-9944-21"
                item.brand = "Western Digital"
                item.model_name = "Blue SN570"
                item.capacity = "1TB"
                item.save()
            elif item.component_type.code == "RAM" and item.slot == "اسلات ۲":
                item.delete()
        submit_snapshot(review, technician)
        self.stdout.write(
            f"   بازبینی {asset.asset_tag} با {review.diff_count} تغییر ثبت شد (در انتظار تایید کارشناس IT)"
        )

    def _demo_tickets(self, assets, admin_it, technician, requester):
        """ساخت درخواست‌های نمونه در وضعیت‌های مختلف."""
        if Ticket.objects.exists():
            return
        now = timezone.now()

        # ۱) درخواست بسته‌شده با رعایت SLA
        asset = assets[0]
        ticket = create_ticket(
            asset=asset,
            title="روشن نشدن کیس",
            description="کاربر اعلام کرد کیس پس از قطع برق روشن نمی‌شود و چراغ پاور چشمک می‌زند.",
            priority=PRIORITY_HIGH,
            user=requester,
            failure_type="power",
            reported_at=now - dt.timedelta(days=6),
        )
        acknowledge(ticket, technician, "درخواست دریافت شد؛ کارشناس اعزام می‌شود.")
        Ticket.objects.filter(pk=ticket.pk).update(
            arrived_at=now - dt.timedelta(days=6) + dt.timedelta(hours=3)
        )
        ticket.refresh_from_db()
        start_work(ticket, technician, "بررسی منبع تغذیه و مادربرد")
        pause_clock(ticket, technician, "awaiting_parts", "انتظار تامین پاور ۴۸۰ وات")
        from apps.tickets.models import TicketPause

        pause = TicketPause.objects.filter(ticket=ticket, ended_at__isnull=True).first()
        if pause:
            pause.started_at = now - dt.timedelta(days=5, hours=20)
            pause.save(update_fields=["started_at", "updated_at"])
        resume_clock(ticket, technician, "قطعه تامین و نصب شد.")
        if pause:
            pause.refresh_from_db()
            pause.ended_at = now - dt.timedelta(days=4, hours=10)
            pause.save(update_fields=["ended_at", "updated_at"])
        TicketPart.objects.create(
            ticket=ticket,
            name="منبع تغذیه ۴۸۰ وات",
            action="replaced",
            old_serial="PSU-7781-33",
            new_serial="PSU-9911-04",
            quantity=1,
        )
        declare_resolved(
            ticket, technician,
            root_cause="سوختن منبع تغذیه در اثر نوسان برق",
            action_taken="پاور معیوب تعویض و ولتاژ خروجی بررسی شد؛ سیستم تست و تحویل کاربر گردید.",
            parts_text="پاور ۴۸۰ وات",
        )
        Ticket.objects.filter(pk=ticket.pk).update(
            resolved_declared_at=now - dt.timedelta(days=4) + dt.timedelta(hours=2)
        )
        ticket.refresh_from_db()
        confirm_by_user(ticket, requester, "سیستم روشن شد و مشکلی ندارد.", satisfaction=5)
        confirm_by_it(ticket, admin_it, "تایید نهایی؛ رعایت SLA تایید می‌شود.")

        # ۲) درخواست باز در وضعیت انتظار قطعه
        asset2 = assets[1] if len(assets) > 1 else assets[0]
        ticket2 = create_ticket(
            asset=asset2,
            title="کیفیت پایین چاپ و خط افتادن روی کاغذ",
            description="چاپگر خطوط عمودی روی کاغذ ایجاد می‌کند و تونر زود تمام می‌شود.",
            priority=PRIORITY_MEDIUM,
            user=requester,
            failure_type="printer",
            reported_at=now - dt.timedelta(days=2),
        )
        acknowledge(ticket2, technician, "پذیرش و هماهنگی حضور")
        Ticket.objects.filter(pk=ticket2.pk).update(
            arrived_at=now - dt.timedelta(days=2) + dt.timedelta(hours=5)
        )
        ticket2.refresh_from_db()
        start_work(ticket2, technician, "بررسی درام و کارتریج")
        pause_clock(ticket2, technician, "awaiting_parts", "انتظار تامین کارتریج اصلی")

        # ۳) درخواست تازه بدون پذیرش
        asset3 = assets[2] if len(assets) > 2 else assets[0]
        create_ticket(
            asset=asset3,
            title="کندی شدید سیستم و ری‌استارت ناگهانی",
            description="سیستم هنگام کار با نرم‌افزار اداری ری‌استارت می‌شود و صدای فن زیاد است.",
            priority=PRIORITY_LOW,
            user=requester,
            failure_type="hardware",
            reported_at=now - dt.timedelta(hours=6),
        )
        self.stdout.write("   ۳ درخواست نمونه در وضعیت‌های مختلف ساخته شد")
