"""Create an idempotent, clearly synthetic Sistan & Baluchestan demo dataset.

This command never resets or deletes data. It is restricted to DEBUG + SQLite.
Run after migrations:
    python manage.py seed_sistan_demo --admin-password "<unique-demo-password>"
"""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.core.constants import PRIORITY_HIGH
from apps.maintenance.repair_models import (
    GeneralITRequest, GeneralReferral, IndependentRepairer, RepairRequest,
)
from apps.maintenance.repair_services import (
    assign_general_it_request,
    complete_repair_request,
    create_general_it_request,
    create_referral,
    create_repair_request,
    decide_repair_request,
    escalate_general_it_request,
    manager_decide_general_it_request,
)
from apps.org.models import (
    Center, Contract, ContractCenterAssignment, Contractor, Department,
    Location, OrganizationalUnit, SlaPolicy,
)
from apps.tickets.models import Ticket
from apps.tickets.services import create_ticket


class Command(BaseCommand):
    help = "ساخت داده نمونه و قابل‌تکرار ITAM برای استان سیستان و بلوچستان"

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", required=True, help="گذرواژه قوی حساب‌های نمونه")
        parser.add_argument("--assets-per-center", type=int, default=6)
        parser.add_argument(
            "--centers-file",
            default=str(Path(settings.BASE_DIR) / "data" / "demo" / "sistan_baluchestan_centers.json"),
        )

    def _load_centers(self, path):
        try:
            rows = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"خواندن فهرست مراکز نمونه ناموفق بود: {exc}") from exc
        if not isinstance(rows, list) or len(rows) != 10:
            raise CommandError("فهرست نمونه باید دقیقاً ۱۰ مرکز/واحد آزمایشی داشته باشد.")
        if any(not row.get("code", "").startswith("DEMO-SB-") for row in rows):
            raise CommandError("تمام کدهای مراکز نمونه باید با DEMO-SB- آغاز شوند.")
        if len({row["code"] for row in rows}) != len(rows):
            raise CommandError("کد مرکز نمونه تکراری است.")
        return rows

    def _user(self, username, password, role, *, center=None, province=None,
              contractor=None, first_name="کاربر", last_name="نمونه", staff=False):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "role": role, "center": center, "org_unit": province,
                "contractor": contractor, "first_name": first_name,
                "last_name": last_name, "is_staff": staff, "is_superuser": False,
            },
        )
        user.role = role
        user.center = center
        user.org_unit = province
        user.contractor = contractor
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.is_staff = staff
        user.is_superuser = False
        user.set_password(password)
        user.save()
        return user

    def _demo_repair(self, *, number, center, asset, repairer, expert, province_admin,
                     state, estimate=Decimal("8000000")):
        existing = RepairRequest.objects.filter(number=number).first()
        if existing:
            return existing
        repair = create_repair_request(
            center=center, asset=asset, repairer=repairer,
            fault_description="خرابی سخت‌افزاری نمونه؛ روشن نشدن یا اختلال قطعه",
            referral_reason="تعمیر تخصصی خارج از توان تعمیرگاه داخلی مرکز",
            estimate_amount=estimate, actor=expert,
        )
        repair.number = number
        repair.save(update_fields=["number", "updated_at"])
        if state in {"approved", "completed", "disputed"}:
            decide_repair_request(
                repair=repair, decision="approve",
                note="تایید آزمایشی مدیر فناوری اطلاعات استان",
                actor=province_admin,
            )
            repair.refresh_from_db()
        if state in {"completed", "disputed"}:
            complete_repair_request(
                repair=repair, actor=expert,
                outcome="قطعه معیوب تعویض، اتصالات بررسی و تجهیز تحت آزمون قرار گرفت.",
                final_cost=estimate if state == "completed" else estimate + Decimal("1500000"),
                final_cost_reason=(
                    "اختلاف عمدی نمونه برای نمایش گردش تعیین تکلیف هزینه."
                    if state == "disputed" else ""
                ),
                work_quality=4, completion_speed=5, cost_fairness=3,
                comment="ارزیابی نمونه؛ داده واقعی عملکرد پیمانکار نیست.",
            )
        elif state == "returned":
            decide_repair_request(
                repair=repair, decision="return",
                note="لطفاً برآورد و شرح خرابی را تکمیل کنید.",
                actor=province_admin,
            )
        return repair

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            raise CommandError("این فرمان فقط در محیط توسعه DEBUG=True و پایگاه SQLite مجاز است.")
        password = options["admin_password"]
        if len(password) < 12:
            raise CommandError("گذرواژه نمونه باید حداقل ۱۲ نویسه داشته باشد.")
        try:
            validate_password(password)
        except Exception as exc:
            raise CommandError(f"گذرواژه نمونه معیارهای امنیتی را ندارد: {exc}") from exc
        assets_per_center = options["assets_per_center"]
        if assets_per_center < 2 or assets_per_center > 50:
            raise CommandError("--assets-per-center باید بین ۲ و ۵۰ باشد.")
        rows = self._load_centers(options["centers_file"])

        self.stdout.write(self.style.MIGRATE_HEADING("۱) بارگذاری جغرافیا و مدیریت درمان"))
        call_command("load_iran_geography")
        province = OrganizationalUnit.objects.get(code="IR-PROV-111")
        if province.name != "سیستان و بلوچستان":
            raise CommandError("کد استان ۱۱۱ با داده مورد انتظار مطابقت ندارد.")
        management = province.treatment_management
        if not province.is_active or not management.is_active:
            raise CommandError("استان یا مدیریت درمان سیستان و بلوچستان غیرفعال است؛ فرمان seed وضعیت عملیاتی را تغییر نمی‌دهد.")
        counties = {
            row["id"]: OrganizationalUnit.objects.get(code=f"IR-COUNTY-{row['id']}")
            for row in rows
        }

        self.stdout.write(self.style.MIGRATE_HEADING("۲) ایجاد مراکز کاملاً آزمایشی"))
        centers = {}
        for row in rows:
            county = OrganizationalUnit.objects.get(code=f"IR-COUNTY-{row['county_id']}")
            center, created = Center.objects.get_or_create(
                code=row["code"],
                defaults={
                    "name": row["name"], "parent_unit": county,
                    "treatment_management": management,
                    "province": province.name, "city": row["city"],
                    "is_headquarters": row["headquarters"], "is_demo": True,
                    "is_active": True,
                    "notes": "رکورد کاملاً آزمایشی ITAM؛ نام و اطلاعات تماس، مرکز واقعی را معرفی نمی‌کند.",
                },
            )
            if not center.is_demo:
                raise CommandError(f"کد {row['code']} قبلاً برای رکورد غیرآزمایشی استفاده شده است.")
            center.name = row["name"]
            center.parent_unit = county
            center.treatment_management = management
            center.province = province.name
            center.city = row["city"]
            center.is_headquarters = row["headquarters"]
            center.is_active = True
            center.notes = "رکورد کاملاً آزمایشی ITAM؛ نام و اطلاعات تماس، مرکز واقعی را معرفی نمی‌کند."
            center.save()
            centers[row["code"]] = center
        headquarters = centers["DEMO-SB-HQ"]

        self.stdout.write(self.style.MIGRATE_HEADING("۳) پیمانکاران و قراردادهای سخت‌افزاری"))
        contractor_a, _ = Contractor.objects.get_or_create(
            name="شرکت نمونه پشتیبانی سخت‌افزار الف",
            defaults={"code": "DEMO-SB-CON-A", "phone": "0000000000", "is_active": True,
                      "notes": "شرکت کاملاً فرضی برای داده آزمایشی؛ بدون قرارداد واقعی."},
        )
        contractor_b, _ = Contractor.objects.get_or_create(
            name="شرکت نمونه پشتیبانی سخت‌افزار ب",
            defaults={"code": "DEMO-SB-CON-B", "phone": "0000000000", "is_active": True,
                      "notes": "شرکت کاملاً فرضی برای داده آزمایشی؛ بدون قرارداد واقعی."},
        )
        today = timezone.localdate()
        contracts = {}
        for contractor, number in (
            (contractor_a, "DEMO-SB-CONTRACT-A"),
            (contractor_b, "DEMO-SB-CONTRACT-B"),
        ):
            contract, _ = Contract.objects.get_or_create(
                number=number,
                defaults={
                    "contractor": contractor, "province": province,
                    "title": "قرارداد نمونه پشتیبانی تجهیزات سخت‌افزاری",
                    "start_date": today - dt.timedelta(days=30),
                    "end_date": today + dt.timedelta(days=335),
                    "visit_interval_days": 90,
                    "visit_scope": "بازدید سخت‌افزاری، بررسی سلامت کیس، چاپگر و قطعات جانبی.",
                    "repair_scope": "تعمیر سخت‌افزار رایانه، چاپگر و قطعات؛ نرم‌افزار و شبکه خارج از دامنه.",
                    "is_provincial": True, "status": Contract.STATUS_ACTIVE,
                },
            )
            contract.contractor = contractor
            contract.province = province
            contract.start_date = today - dt.timedelta(days=30)
            contract.end_date = today + dt.timedelta(days=335)
            contract.status = Contract.STATUS_ACTIVE
            contract.is_provincial = True
            contract.save()
            contracts[contractor.pk] = contract
            for priority, response, resolution in (
                ("critical", 60, 480), ("high", 240, 1440),
                ("medium", 480, 2880), ("low", 960, 5760),
            ):
                SlaPolicy.objects.get_or_create(
                    contract=contract, priority=priority,
                    defaults={"response_minutes": response, "resolve_minutes": resolution},
                )

        self.stdout.write(self.style.MIGRATE_HEADING("۴) حساب‌های آزمایشی و انتساب پیمانکار"))
        province_admin = self._user(
            "demo.sistan.admin", password, User.ROLE_ADMIN_PROVINCE,
            center=headquarters, province=province,
            first_name="مدیر", last_name="نمونه استان", staff=True,
        )
        center_experts = {}
        managers = {}
        requesters = {}
        for code, center in centers.items():
            suffix = code.lower().replace("-", "_")
            center_experts[code] = self._user(
                f"demo.it.{suffix}", password, User.ROLE_ADMIN_IT,
                center=center, first_name="کارشناس", last_name=f"نمونه {center.city}", staff=True,
            )
            managers[code] = self._user(
                f"demo.manager.{suffix}", password, User.ROLE_MANAGER,
                center=center, first_name="مدیر", last_name=f"نمونه {center.city}",
            )
            requesters[code] = self._user(
                f"demo.user.{suffix}", password, User.ROLE_REQUESTER,
                center=center, first_name="کاربر", last_name=f"نمونه {center.city}",
            )

        technician_a = self._user(
            "demo.tech.hardware.a", password, User.ROLE_TECHNICIAN,
            province=province, contractor=contractor_a,
            first_name="تکنسین", last_name="نمونه الف",
        )
        technician_b = self._user(
            "demo.tech.hardware.b", password, User.ROLE_TECHNICIAN,
            province=province, contractor=contractor_b,
            first_name="تکنسین", last_name="نمونه ب",
        )

        assignment_map = {}
        contractor_a_codes = {
            "DEMO-SB-HQ", "DEMO-SB-ZAH-HOSP-01", "DEMO-SB-ZAB-HOSP-01",
            "DEMO-SB-IRH-HOSP-01", "DEMO-SB-SAR-HOSP-01",
        }
        contractor_b_codes = {
            "DEMO-SB-ZAH-HOSP-02", "DEMO-SB-ZAH-CLINIC-01",
            "DEMO-SB-KHA-HOSP-01", "DEMO-SB-CHA-HOSP-01",
        }
        for code, center in centers.items():
            contract = (
                contracts[contractor_a.pk] if code in contractor_a_codes
                else contracts[contractor_b.pk] if code in contractor_b_codes
                else None
            )
            if contract is None:
                continue  # Medical records office intentionally has no official contractor.
            assignment = ContractCenterAssignment.objects.filter(
                center=center, status=ContractCenterAssignment.STATUS_ACTIVE
            ).first()
            if assignment is None:
                from apps.maintenance.repair_services import assign_contractor_to_center
                assignment = assign_contractor_to_center(
                    contract=contract, center=center, start_date=today, actor=province_admin,
                )
            assignment_map[code] = assignment

        self.stdout.write(self.style.MIGRATE_HEADING("۵) واحدها، محل‌ها و دارایی‌ها"))
        categories = {}
        for name, code, icon, tracking, computing in (
            ("کیس رایانه رومیزی نمونه", "DEMO-PC", "🖥", True, True),
            ("لپ‌تاپ نمونه", "DEMO-LAP", "💻", True, True),
            ("چاپگر نمونه", "DEMO-PRN", "🖨", False, False),
            ("مانیتور نمونه", "DEMO-MON", "🖥", False, False),
            ("اسکنر نمونه", "DEMO-SCN", "📠", False, False),
        ):
            category, _ = AssetCategory.objects.get_or_create(
                name=name,
                defaults={"code": code, "icon": icon,
                          "requires_component_tracking": tracking,
                          "is_computing_device": computing},
            )
            categories[code] = category

        assets_by_center = {}
        for center_index, (code, center) in enumerate(centers.items(), start=1):
            department, _ = Department.objects.get_or_create(
                center=center, name="واحد فناوری اطلاعات نمونه",
                defaults={"code": f"{code}-IT", "manager_name": "مسئول نمونه"},
            )
            location, _ = Location.objects.get_or_create(
                center=center, name="اتاق تجهیزات", building="ساختمان نمونه",
                floor="همکف", room="اتاق ۱۰۱",
            )
            assignment = assignment_map.get(code)
            contract = assignment.contract if assignment else None
            assets = []
            for index in range(1, assets_per_center + 1):
                category_code = ("DEMO-PC", "DEMO-PC", "DEMO-PRN", "DEMO-MON", "DEMO-LAP", "DEMO-SCN")[(index - 1) % 6]
                asset_tag = f"{code}-{index:03d}"
                asset, _ = Asset.objects.get_or_create(
                    asset_tag=asset_tag,
                    defaults={
                        "title": f"{categories[category_code].name} {index}",
                        "category": categories[category_code],
                        "center": center, "contract": contract,
                        "department": department, "location": location,
                        "custodian": requesters[code],
                        "brand": "سازنده نمونه",
                        "model_name": "مدل آزمایشی",
                        "serial_number": f"DEMO-SERIAL-{center_index:02d}-{index:03d}",
                        "status": "active",
                        "hostname": f"DEMO-{center_index:02d}-{index:03d}" if category_code in {"DEMO-PC", "DEMO-LAP"} else "",
                        "os_name": "Windows 11 Pro (Demo)" if category_code in {"DEMO-PC", "DEMO-LAP"} else "",
                        "spec_summary": "مشخصات ساختگی صرفاً برای تست عملکرد سامانه؛ داده واقعی سخت‌افزار نیست.",
                        "purchase_date": today - dt.timedelta(days=500 + index),
                        "price": 250000000 if category_code in {"DEMO-PC", "DEMO-LAP"} else 65000000,
                        "supplier": "تامین‌کننده فرضی",
                        "notes": "DEMO DATA — رکورد ساختگی",
                    },
                )
                assets.append(asset)
            assets_by_center[code] = assets

        self.stdout.write(self.style.MIGRATE_HEADING("۶) تعمیرکاران مستقل و گردش تعمیر"))
        repairer_company, _ = IndependentRepairer.objects.get_or_create(
            province=province, name="تعمیرگاه نمونه سخت‌افزار جنوب شرق",
            defaults={
                "kind": IndependentRepairer.KIND_COMPANY,
                "phone": "0000000000", "specialties": "تعمیر کیس، مادربرد، پاور و چاپگر",
                "notes": "هویت کاملاً فرضی؛ داده آزمایشی.", "created_by": province_admin,
            },
        )
        repairer_person, _ = IndependentRepairer.objects.get_or_create(
            province=province, name="تعمیرکار حقیقی نمونه",
            defaults={
                "kind": IndependentRepairer.KIND_INDIVIDUAL,
                "phone": "0000000000", "specialties": "تعمیر قطعات رایانه",
                "notes": "هویت کاملاً فرضی؛ داده آزمایشی.", "created_by": province_admin,
            },
        )
        hospital_code = "DEMO-SB-ZAH-HOSP-01"
        hospital_assets = assets_by_center[hospital_code]
        pending = self._demo_repair(
            number="DEMO-RR-PENDING-001", center=centers[hospital_code],
            asset=hospital_assets[0], repairer=repairer_company,
            expert=center_experts[hospital_code], province_admin=province_admin,
            state="pending",
        )
        completed = self._demo_repair(
            number="DEMO-RR-COMPLETED-001", center=centers[hospital_code],
            asset=hospital_assets[1], repairer=repairer_person,
            expert=center_experts[hospital_code], province_admin=province_admin,
            state="completed",
        )
        disputed = self._demo_repair(
            number="DEMO-RR-DISPUTED-001", center=centers[hospital_code],
            asset=hospital_assets[2], repairer=repairer_company,
            expert=center_experts[hospital_code], province_admin=province_admin,
            state="disputed",
        )
        returned = self._demo_repair(
            number="DEMO-RR-RETURNED-001", center=centers[hospital_code],
            asset=hospital_assets[3], repairer=repairer_person,
            expert=center_experts[hospital_code], province_admin=province_admin,
            state="returned",
        )

        self.stdout.write(self.style.MIGRATE_HEADING("۷) درخواست‌های عمومی، ارجاع‌ها و تیکت"))
        requester = requesters[hospital_code]
        expert = center_experts[hospital_code]
        if not GeneralITRequest.objects.filter(number="DEMO-ITR-BYPASS-001").exists():
            req = create_general_it_request(
                center=centers[hospital_code], request_type=GeneralITRequest.TYPE_EQUIPMENT,
                title="درخواست تامین رایانه برای واحد پذیرش",
                description="درخواست نمونه برای نمایش گردش تامین تجهیز.",
                actor=requester,
            )
            req.number = "DEMO-ITR-BYPASS-001"
            req.save(update_fields=["number", "updated_at"])
            assign_general_it_request(request=req, expert=expert, actor=expert)
            escalate_general_it_request(
                request=req, actor=expert,
                bypass_reason="فوریت تامین و عدم دسترسی مدیر مرکز در بازه ثبت درخواست.",
            )
        if not GeneralITRequest.objects.filter(number="DEMO-ITR-MANAGER-001").exists():
            req = create_general_it_request(
                center=centers[hospital_code], request_type=GeneralITRequest.TYPE_REPLACEMENT,
                title="درخواست جایگزینی چاپگر",
                description="تجهیز نمونه قابل تعمیر نیست و نیازمند جایگزینی است.",
                actor=requester,
            )
            req.number = "DEMO-ITR-MANAGER-001"
            req.save(update_fields=["number", "updated_at"])
            assign_general_it_request(request=req, expert=expert, actor=expert)
            manager_decide_general_it_request(
                request=req, decision="approve", note="تایید آزمایشی مدیر مرکز.",
                actor=managers[hospital_code],
            )
            escalate_general_it_request(request=req, actor=expert)

        if not GeneralReferral.objects.filter(subject="اختلاف هزینه تعمیر نمونه", center=centers[hospital_code]).exists():
            create_referral(
                subject="اختلاف هزینه تعمیر نمونه",
                description="ارجاع آزمایشی برای تعیین تکلیف مبلغ مازاد هزینه تعمیر.",
                recipient_role="مسئول مالی و اداری مدیریت درمان",
                recipient_name="مسئول مالی نمونه",
                center=centers[hospital_code], repair_request=disputed,
                actor=province_admin,
            )

        if not Ticket.objects.filter(title="[DEMO] خرابی سخت‌افزاری نمونه").exists():
            create_ticket(
                asset=hospital_assets[0],
                title="[DEMO] خرابی سخت‌افزاری نمونه",
                description="تیکت نمونه برای نمایش چرخه اعلام خرابی و SLA.",
                priority=PRIORITY_HIGH,
                user=requester,
                failure_type="hardware",
            )

        self.stdout.write(self.style.SUCCESS("داده نمونه استان با موفقیت ایجاد/تکمیل شد."))
        self.stdout.write(f"مراکز نمونه: {len(centers)} | دارایی‌ها: {len(centers) * assets_per_center}")
        self.stdout.write("کاربران نمونه: demo.sistan.admin و حساب‌های demo.it.* / demo.manager.* / demo.user.*")
        self.stdout.write("گذرواژه همه حساب‌های نمونه همان گذرواژه‌ای است که در --admin-password وارد کردید.")
        self.stdout.write("هیچ رکورد واقعی حذف یا بازنویسی نشده است؛ تمام مراکز با کد DEMO-SB- و is_demo مشخص‌اند.")
