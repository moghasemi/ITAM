"""گزارش‌ها و تحلیل‌های مدیریتی."""
from __future__ import annotations

from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import View

from apps.accounts.permissions import StaffRequiredMixin
from apps.assets.models import Asset, AssetCategory, HardwareSnapshot
from apps.assets.services import visible_assets
from apps.core import jalali
from apps.core.constants import (
    ASSET_STATUS_CHOICES,
    DIFF_REMOVED,
    PRIORITY_LABELS,
    TICKET_CLOSED_STATUSES,
    TICKET_OPEN_STATUSES,
    VISIT_DONE,
    VISIT_MISSED,
    VISIT_PLANNED,
    VISIT_IN_PROGRESS,
)
from apps.core.mixins import PageContextMixin
from apps.core.sla import get_calendar
from apps.core.utils import duration_fa, log_action
from apps.maintenance.models import MaintenanceVisit
from apps.maintenance.services import visible_visits
from apps.org.models import Contract, Contractor
from apps.tickets.models import Ticket
from apps.tickets.services import visible_tickets

from .exports import export_response
from .forms import ReportFilterForm, filter_tickets

REPORT_MENU = [
    {"key": "sla", "title": "گزارش SLA و زمان‌های پاسخ", "url": "/reports/sla/", "icon": "⏱"},
    {"key": "contractor", "title": "کارنامه پیمانکاران", "url": "/reports/contractors/", "icon": "🏢"},
    {"key": "inventory", "title": "فهرست و ارزش دارایی‌ها", "url": "/reports/inventory/", "icon": "🖥"},
    {"key": "visits", "title": "رعایت بازدیدهای دوره‌ای", "url": "/reports/visits/", "icon": "🗓"},
    {"key": "failures", "title": "تحلیل خرابی‌ها و MTTR", "url": "/reports/failures/", "icon": "📉"},
    {"key": "hardware", "title": "گزارش تغییر اقلام سخت‌افزاری", "url": "/assets/hardware/report/", "icon": "🔒"},
]


def _filter_form(request):
    form = ReportFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}
    return form, data


# ---------------------------------------------------------------------------
# صفحه اصلی گزارش‌ها
# ---------------------------------------------------------------------------
class ReportsHomeView(StaffRequiredMixin, PageContextMixin, View):
    template_name = "reports/home.html"
    page_title = "گزارش‌ها و داشبورد مدیریتی"
    active_menu = "reports"

    def get(self, request, *args, **kwargs):
        tickets = visible_tickets(request.user)
        assets = visible_assets(request.user)
        context = {
            "page_title": self.page_title,
            "active_menu": self.active_menu,
            "reports": REPORT_MENU,
            "tickets_total": tickets.count(),
            "assets_total": assets.count(),
            "contracts_active": Contract.objects.filter(
                status=Contract.STATUS_ACTIVE
            ).filter(
                Q(is_provincial=True) | Q(centers__in=request.user.get_scoped_centers())
            ).distinct().count(),
            "breached_total": tickets.filter(Q(response_met=False) | Q(resolve_met=False)).count(),
            "snapshots_total": HardwareSnapshot.objects.filter(asset__in=assets).count(),
            "diff_alarms": HardwareSnapshot.objects.filter(
                asset__in=assets, diff_data__has_key="removed"
            ).count(),
        }
        return render(request, self.template_name, context)


# ---------------------------------------------------------------------------
# گزارش SLA
# ---------------------------------------------------------------------------
class SlaReportView(StaffRequiredMixin, PageContextMixin, View):
    template_name = "reports/sla.html"
    page_title = "گزارش SLA و زمان‌های کلیدی"
    active_menu = "reports"

    def get(self, request, *args, **kwargs):
        form, data = _filter_form(request)
        tickets = filter_tickets(
            visible_tickets(request.user).filter(reported_at__isnull=False), data
        ).order_by("-reported_at")

        rows = []
        for ticket in tickets[:1000]:
            rows.append(
                {
                    "ticket": ticket,
                    "response_used": ticket.response_minutes_used,
                    "resolve_used": ticket.resolve_minutes_used,
                    "total_used": ticket.total_minutes_used,
                }
            )

        closed = tickets.filter(status__in=TICKET_CLOSED_STATUSES)
        aggregate = closed.aggregate(
            avg_response=Avg("response_minutes_used"),
            avg_resolve=Avg("resolve_minutes_used"),
            avg_total=Avg("total_minutes_used"),
        )
        evaluated = tickets.filter(response_met__isnull=False).count()
        response_ok = tickets.filter(response_met=True).count()
        resolve_evaluated = tickets.filter(resolve_met__isnull=False).count()
        resolve_ok = tickets.filter(resolve_met=True).count()

        summary = {
            "total": tickets.count(),
            "closed": closed.count(),
            "open": tickets.filter(status__in=TICKET_OPEN_STATUSES).count(),
            "avg_response": duration_fa(aggregate["avg_response"]),
            "avg_resolve": duration_fa(aggregate["avg_resolve"]),
            "avg_total": duration_fa(aggregate["avg_total"]),
            "response_compliance": (response_ok * 100 / evaluated) if evaluated else None,
            "resolve_compliance": (resolve_ok * 100 / resolve_evaluated) if resolve_evaluated else None,
            "breached": tickets.filter(Q(response_met=False) | Q(resolve_met=False)).count(),
            "paused_total": duration_fa(
                tickets.aggregate(total=Sum("paused_minutes"))["total"] or 0
            ),
        }

        if request.GET.get("export"):
            headers = [
                "شماره درخواست", "شماره اموال", "عنوان", "اولویت", "وضعیت",
                "زمان اعلام", "زمان حضور", "زمان اعلام رفع", "زمان بسته شدن",
                "دقیقه تا حضور", "سهمیه حضور", "رعایت پاسخ",
                "دقیقه تا رفع", "سهمیه رفع", "رعایت رفع", "دقیقه توقف",
            ]
            export_rows = []
            for ticket in tickets:
                policy = ticket.contract.sla_for(ticket.priority) if ticket.contract_id else None
                export_rows.append(
                    [
                        ticket.number,
                        ticket.asset.asset_tag,
                        ticket.title,
                        ticket.priority_label,
                        ticket.get_status_display(),
                        jalali.format_jalali(ticket.reported_at, "Y/m/d H:M", persian_digits=False),
                        jalali.format_jalali(ticket.arrived_at, "Y/m/d H:M", persian_digits=False),
                        jalali.format_jalali(ticket.resolved_declared_at, "Y/m/d H:M", persian_digits=False),
                        jalali.format_jalali(ticket.closed_at, "Y/m/d H:M", persian_digits=False),
                        ticket.response_minutes_used,
                        policy.response_minutes if policy else "",
                        "بله" if ticket.response_met else ("خیر" if ticket.response_met is False else ""),
                        ticket.resolve_minutes_used,
                        policy.resolve_minutes if policy else "",
                        "بله" if ticket.resolve_met else ("خیر" if ticket.resolve_met is False else ""),
                        ticket.paused_minutes,
                    ]
                )
            log_action("export", None, model_name="Ticket", object_label="گزارش SLA", user=request.user)
            filename = f"sla-report-{jalali.jalaali_today().isoformat().replace('/', '-')}"
            return export_response(
                request,
                filename=filename,
                sheet_title="گزارش SLA",
                headers=headers,
                rows=export_rows,
                title_rows=["گزارش SLA و زمان‌های کلیدی سامانه مدیریت دارایی"],
            )

        return render(
            request,
            self.template_name,
            {
                "page_title": self.page_title,
                "active_menu": self.active_menu,
                "filter_form": form,
                "rows": rows,
                "summary": summary,
                "calendar": get_calendar(),
            },
        )


# ---------------------------------------------------------------------------
# کارنامه پیمانکاران
# ---------------------------------------------------------------------------
class ContractorScorecardView(StaffRequiredMixin, PageContextMixin, View):
    template_name = "reports/contractors.html"
    page_title = "کارنامه عملکرد پیمانکاران"
    active_menu = "reports"

    def get(self, request, *args, **kwargs):
        form, data = _filter_form(request)
        tickets = filter_tickets(visible_tickets(request.user), data)
        visits = visible_visits(request.user)
        if data.get("contractor"):
            visits = visits.filter(contract__contractor=data["contractor"])
        if data.get("date_from"):
            visits = visits.filter(scheduled_date__gte=data["date_from"])
        if data.get("date_to"):
            visits = visits.filter(scheduled_date__lte=data["date_to"])

        rows = []
        visible_contractor_ids = set(tickets.values_list("assigned_contractor_id", flat=True))
        visible_contractor_ids.update(visits.values_list("contract__contractor_id", flat=True))
        visible_contractor_ids.discard(None)
        for contractor in Contractor.objects.filter(pk__in=visible_contractor_ids):
            contractor_tickets = tickets.filter(assigned_contractor=contractor)
            closed = contractor_tickets.filter(status__in=TICKET_CLOSED_STATUSES)
            evaluated = contractor_tickets.filter(response_met__isnull=False).count()
            met = contractor_tickets.filter(response_met=True).count()
            resolve_evaluated = contractor_tickets.filter(resolve_met__isnull=False).count()
            resolve_met = contractor_tickets.filter(resolve_met=True).count()
            contractor_visits = visits.filter(contract__contractor=contractor)
            planned = contractor_visits.count()
            done = contractor_visits.filter(status=VISIT_DONE).count()
            missed = contractor_visits.filter(status=VISIT_MISSED).count()
            late_done = contractor_visits.filter(
                status=VISIT_DONE,
                finished_at__date__gt=F("scheduled_end_date"),
            ).count()
            rows.append(
                {
                    "contractor": contractor,
                    "tickets_total": contractor_tickets.count(),
                    "tickets_open": contractor_tickets.filter(status__in=TICKET_OPEN_STATUSES).count(),
                    "tickets_closed": closed.count(),
                    "avg_response": duration_fa(closed.aggregate(value=Avg("response_minutes_used"))["value"]),
                    "avg_resolve": duration_fa(closed.aggregate(value=Avg("resolve_minutes_used"))["value"]),
                    "response_compliance": (met * 100 / evaluated) if evaluated else None,
                    "resolve_compliance": (resolve_met * 100 / resolve_evaluated) if resolve_evaluated else None,
                    "breached": contractor_tickets.filter(Q(response_met=False) | Q(resolve_met=False)).count(),
                    "visits_planned": planned,
                    "visits_done": done,
                    "visits_missed": missed,
                    "visit_compliance": (done * 100 / planned) if planned else None,
                    "hardware_diffs": HardwareSnapshot.objects.filter(
                        asset__contract__contractor=contractor
                    ).filter(diff_count__gt=0).count(),
                    "late_done": late_done,
                }
            )

        if request.GET.get("export"):
            headers = [
                "پیمانکار", "کل درخواست‌ها", "باز", "بسته‌شده", "میانگین زمان پاسخ",
                "میانگین زمان رفع", "رعایت SLA پاسخ (٪)", "رعایت SLA رفع (٪)",
                "نقض SLA", "بازدید برنامه‌ریزی‌شده", "بازدید انجام‌شده", "بازدید انجام‌نشده",
                "رعایت بازدید (٪)", "تغییرات سخت‌افزاری ثبت‌شده",
            ]
            export_rows = [
                [
                    row["contractor"].name, row["tickets_total"], row["tickets_open"],
                    row["tickets_closed"], row["avg_response"], row["avg_resolve"],
                    round(row["response_compliance"], 1) if row["response_compliance"] is not None else "",
                    round(row["resolve_compliance"], 1) if row["resolve_compliance"] is not None else "",
                    row["breached"], row["visits_planned"], row["visits_done"],
                    row["visits_missed"],
                    round(row["visit_compliance"], 1) if row["visit_compliance"] is not None else "",
                    row["hardware_diffs"],
                ]
                for row in rows
            ]
            log_action("export", None, model_name="Contractor", object_label="کارنامه پیمانکاران", user=request.user)
            return export_response(
                request,
                filename="contractor-scorecard",
                sheet_title="کارنامه پیمانکاران",
                headers=headers,
                rows=export_rows,
            )

        return render(
            request,
            self.template_name,
            {
                "page_title": self.page_title,
                "active_menu": self.active_menu,
                "filter_form": form,
                "rows": rows,
            },
        )


# ---------------------------------------------------------------------------
# گزارش دارایی‌ها
# ---------------------------------------------------------------------------
class InventoryReportView(StaffRequiredMixin, PageContextMixin, View):
    template_name = "reports/inventory.html"
    page_title = "فهرست و ارزش دارایی‌ها"
    active_menu = "reports"

    def get(self, request, *args, **kwargs):
        assets = visible_assets(request.user)
        category = request.GET.get("category")
        department = request.GET.get("department")
        status = request.GET.get("status")
        if category:
            assets = assets.filter(category_id=category)
        if department:
            assets = assets.filter(department_id=department)
        if status:
            assets = assets.filter(status=status)

        by_category = list(
            assets.values("category__name").annotate(total=Count("id"), value=Sum("price")).order_by("-total")
        )
        by_department = list(
            assets.values("department__name").annotate(total=Count("id"), value=Sum("price")).order_by("-total")
        )
        by_status = list(assets.values("status").annotate(total=Count("id")).order_by("-total"))
        by_location = list(
            assets.values("location__name", "location__building")
            .annotate(total=Count("id"))
            .order_by("-total")[:20]
        )
        totals = assets.aggregate(total=Count("id"), value=Sum("price"), tracked=Count("current_snapshot"))

        if request.GET.get("export"):
            headers = [
                "شماره اموال", "گونه", "عنوان", "برند", "مدل", "سریال",
                "واحد سازمانی", "محل", "امانت‌دار", "وضعیت",
                "تاریخ خرید", "پایان گارانتی", "ارزش (ریال)", "اقلام ثبت‌شده",
            ]
            rows = [
                [
                    asset.asset_tag,
                    asset.category.name,
                    asset.title,
                    asset.brand,
                    asset.model_name,
                    asset.serial_number,
                    asset.department.name if asset.department else "",
                    asset.location.full_label if asset.location else "",
                    asset.custodian.display_name if asset.custodian else "",
                    asset.get_status_display(),
                    jalali.format_jalali(asset.purchase_date, "Y/m/d", persian_digits=False) if asset.purchase_date else "",
                    jalali.format_jalali(asset.warranty_until, "Y/m/d", persian_digits=False) if asset.warranty_until else "",
                    int(asset.price) if asset.price else "",
                    asset.components_count,
                ]
                for asset in assets.select_related("category", "department", "location", "custodian")
            ]
            log_action("export", None, model_name="Asset", object_label="فهرست دارایی‌ها", user=request.user)
            return export_response(
                request,
                filename="assets-inventory",
                sheet_title="فهرست دارایی‌ها",
                headers=headers,
                rows=rows,
            )

        return render(
            request,
            self.template_name,
            {
                "page_title": self.page_title,
                "active_menu": self.active_menu,
                "by_category": by_category,
                "by_department": by_department,
                "by_status": by_status,
                "by_location": by_location,
                "totals": totals,
                "assets": assets.select_related("category", "department", "location")[:200],
                "categories": AssetCategory.objects.all(),
                "status_choices": ASSET_STATUS_CHOICES,
            },
        )


# ---------------------------------------------------------------------------
# گزارش بازدیدهای دوره‌ای
# ---------------------------------------------------------------------------
class VisitComplianceView(StaffRequiredMixin, PageContextMixin, View):
    template_name = "reports/visits.html"
    page_title = "رعایت بازدیدهای دوره‌ای"
    active_menu = "reports"

    def get(self, request, *args, **kwargs):
        form = ReportFilterForm(request.GET or None)
        data = form.cleaned_data if form.is_valid() else {}
        visits = visible_visits(request.user)
        if data.get("contract"):
            visits = visits.filter(contract=data["contract"])
        if data.get("contractor"):
            visits = visits.filter(contract__contractor=data["contractor"])
        if data.get("date_from"):
            visits = visits.filter(scheduled_date__gte=data["date_from"])
        if data.get("date_to"):
            visits = visits.filter(scheduled_date__lte=data["date_to"])

        rows = []
        for visit in visits.order_by("-scheduled_date")[:500]:
            rows.append(
                {
                    "visit": visit,
                    "deadline": visit.scheduled_end_date or visit.scheduled_date,
                    "is_late": visit.status not in (VISIT_DONE,) and visit.is_overdue,
                }
            )

        summary = {
            "planned": visits.filter(status=VISIT_PLANNED).count(),
            "in_progress": visits.filter(status=VISIT_IN_PROGRESS).count(),
            "done": visits.filter(status=VISIT_DONE).count(),
            "missed": visits.filter(status=VISIT_MISSED).count(),
            "total": visits.count(),
        }
        if summary["total"]:
            summary["compliance"] = summary["done"] * 100 / summary["total"]
        else:
            summary["compliance"] = None

        if request.GET.get("export"):
            headers = [
                "شماره بازدید", "قرارداد", "پیمانکار", "دوره", "تاریخ برنامه",
                "آخرین مهلت", "وضعیت", "کارشناس", "زمان پایان",
                "تعداد تجهیزات", "بازدیدشده", "تجهیزات دارای ایراد",
            ]
            export_rows = [
                [
                    row["visit"].number,
                    row["visit"].contract.number,
                    row["visit"].contract.contractor.name,
                    row["visit"].period_label,
                    jalali.format_jalali(row["visit"].scheduled_date, "Y/m/d", persian_digits=False),
                    jalali.format_jalali(row["deadline"], "Y/m/d", persian_digits=False),
                    row["visit"].get_status_display(),
                    row["visit"].technician.display_name if row["visit"].technician else "",
                    jalali.format_jalali(row["visit"].finished_at, "Y/m/d H:M", persian_digits=False),
                    row["visit"].checks_total,
                    row["visit"].checks_done,
                    row["visit"].faulty_count,
                ]
                for row in rows
            ]
            log_action("export", None, model_name="MaintenanceVisit", object_label="گزارش بازدیدها", user=request.user)
            return export_response(
                request,
                filename="visits-compliance",
                sheet_title="بازدیدهای دوره‌ای",
                headers=headers,
                rows=export_rows,
            )

        return render(
            request,
            self.template_name,
            {
                "page_title": self.page_title,
                "active_menu": self.active_menu,
                "filter_form": form,
                "rows": rows,
                "summary": summary,
            },
        )


# ---------------------------------------------------------------------------
# تحلیل خرابی‌ها
# ---------------------------------------------------------------------------
class FailureAnalysisView(StaffRequiredMixin, PageContextMixin, View):
    template_name = "reports/failures.html"
    page_title = "تحلیل خرابی‌ها و MTTR"
    active_menu = "reports"

    def get(self, request, *args, **kwargs):
        form, data = _filter_form(request)
        tickets = filter_tickets(visible_tickets(request.user), data)
        closed = tickets.filter(status__in=TICKET_CLOSED_STATUSES)

        top_assets = list(
            tickets.values("asset__asset_tag", "asset__title", "asset_id")
            .annotate(total=Count("id"), mttr=Avg("total_minutes_used"))
            .order_by("-total")[:15]
        )
        by_type = list(tickets.values("failure_type").annotate(total=Count("id")).order_by("-total"))
        by_priority = []
        for priority, label in PRIORITY_LABELS.items():
            subset = tickets.filter(priority=priority)
            by_priority.append(
                {
                    "priority": priority,
                    "label": label,
                    "total": subset.count(),
                    "open": subset.filter(status__in=TICKET_OPEN_STATUSES).count(),
                    "mttr": subset.aggregate(value=Avg("total_minutes_used"))["value"],
                    "breached": subset.filter(Q(response_met=False) | Q(resolve_met=False)).count(),
                }
            )
        by_category = list(
            tickets.values("asset__category__name").annotate(total=Count("id")).order_by("-total")
        )
        by_department = list(
            tickets.values("asset__department__name").annotate(total=Count("id")).order_by("-total")[:10]
        )

        summary = {
            "total": tickets.count(),
            "closed": closed.count(),
            "mttr": duration_fa(closed.aggregate(value=Avg("total_minutes_used"))["value"]),
            "avg_paused": duration_fa(closed.aggregate(value=Avg("paused_minutes"))["value"]),
        }

        if request.GET.get("export"):
            headers = ["شماره اموال", "عنوان تجهیز", "تعداد خرابی", "میانگین زمان رفع (دقیقه)"]
            export_rows = [
                [
                    row["asset__asset_tag"],
                    row["asset__title"] or "",
                    row["total"],
                    round(row["mttr"], 0) if row["mttr"] else "",
                ]
                for row in top_assets
            ]
            log_action("export", None, model_name="Ticket", object_label="تحلیل خرابی‌ها", user=request.user)
            return export_response(
                request,
                filename="failure-analysis",
                sheet_title="تحلیل خرابی‌ها",
                headers=headers,
                rows=export_rows,
            )

        return render(
            request,
            self.template_name,
            {
                "page_title": self.page_title,
                "active_menu": self.active_menu,
                "filter_form": form,
                "top_assets": top_assets,
                "by_type": by_type,
                "by_priority": by_priority,
                "by_category": by_category,
                "by_department": by_department,
                "summary": summary,
                "today": timezone.localdate(),
            },
        )
