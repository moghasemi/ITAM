"""نماهای هسته: داشبورد، اعلان‌ها، تنظیمات، تعطیلات، لاگ ممیزی و جستجو."""
from __future__ import annotations

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, UpdateView

from apps.accounts.permissions import AdminItRequiredMixin, StaffRequiredMixin
from apps.assets.models import Asset, HardwareSnapshot
from apps.maintenance.models import MaintenanceVisit
from apps.tickets.models import Ticket, TicketEvent

from . import jalali
from .constants import (
    TICKET_CLOSED_STATUSES,
    TICKET_OPEN_STATUSES,
    VISIT_DONE,
    VISIT_MISSED,
    VISIT_PLANNED,
    VISIT_IN_PROGRESS,
)
from .forms import HolidayForm, SystemSettingForm
from .mixins import BaseListView, PageContextMixin, apply_search
from .models import AuditLog, Holiday, Notification, SystemSetting
from .sla import get_calendar
from .utils import duration_fa, log_action


# ---------------------------------------------------------------------------
# ابزارهای آماری
# ---------------------------------------------------------------------------
def jalali_month_series(queryset, field: str, months: int = 6):
    """سری ماهانه شمسی برای نمودارها."""
    today = jalali.jalaali_today()
    total = today.year * 12 + (today.month - 1)
    keys = []
    for offset in range(months - 1, -1, -1):
        value = total - offset
        year, month = divmod(value, 12)
        keys.append((year, month + 1))

    first_year, first_month = keys[0]
    start_date = jalali.jalali_to_gregorian(first_year, first_month, 1)
    start_dt = timezone.make_aware(
        dt.datetime.combine(start_date, dt.time.min), timezone.get_current_timezone()
    )

    counts: dict[tuple[int, int], int] = {key: 0 for key in keys}
    for value in queryset.filter(**{f"{field}__gte": start_dt}).values_list(field, flat=True):
        if value is None:
            continue
        jdate = jalali.to_jalali(timezone.localtime(value))
        key = (jdate.year, jdate.month)
        if key in counts:
            counts[key] += 1

    return [
        {
            "key": key,
            "label": jalali.jalaali_month_name(key[1]),
            "short_label": f"{jalali.jalaali_month_name(key[1])} {jalali.fa_digits(key[0] % 100)}",
            "value": counts[key],
        }
        for key in keys
    ]


def _ticket_scope(user):
    from apps.tickets.services import visible_tickets

    return visible_tickets(user)


def _asset_scope(user):
    from apps.assets.services import visible_assets

    return visible_assets(user)


# ---------------------------------------------------------------------------
# داشبورد
# ---------------------------------------------------------------------------
class DashboardView(PageContextMixin, ListView):
    template_name = "core/dashboard.html"
    context_object_name = "recent_tickets"
    page_title = "داشبورد"
    active_menu = "dashboard"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return _ticket_scope(self.request.user).order_by("-reported_at")[:8]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        tickets = _ticket_scope(user)
        assets = _asset_scope(user)
        now = timezone.now()
        setting = SystemSetting.load()

        open_tickets = tickets.filter(status__in=TICKET_OPEN_STATUSES)
        context.update(
            {
                "assets_total": assets.count(),
                "assets_by_status": list(
                    assets.values("status").annotate(total=Count("id")).order_by("-total")
                ),
                "assets_without_baseline": assets.filter(
                    baseline_locked_at__isnull=True, category__requires_component_tracking=True
                ).count(),
                "open_tickets": open_tickets.count(),
                "open_by_priority": list(
                    open_tickets.values("priority").annotate(total=Count("id"))
                ),
                "overdue_response": open_tickets.filter(
                    arrived_at__isnull=True, response_due_at__lt=now
                ).count(),
                "overdue_resolve": open_tickets.filter(
                    resolved_declared_at__isnull=True,
                    resolve_due_at__lt=now,
                    arrived_at__isnull=False,
                ).count(),
                "awaiting_user_confirm": tickets.filter(status="resolved").count(),
                "awaiting_it_confirm": tickets.filter(status="user_confirmed").count(),
                "closed_total": tickets.filter(status__in=TICKET_CLOSED_STATUSES).count(),
                "monthly_series": jalali_month_series(tickets, "reported_at", months=6),
                "recent_events": TicketEvent.objects.filter(
                    ticket__in=tickets.values("pk")
                ).select_related("ticket", "actor")[:10],
                "top_assets": list(
                    tickets.values("asset__asset_tag", "asset__title", "asset_id")
                    .annotate(total=Count("id"))
                    .order_by("-total")[:5]
                ),
                "pending_snapshots": HardwareSnapshot.objects.filter(
                    asset__in=assets, status="pending"
                ).select_related("asset", "recorded_by")[:6],
                "pending_snapshots_count": HardwareSnapshot.objects.filter(
                    asset__in=assets, status="pending"
                ).count(),
                "calendar": get_calendar(),
                "setting": setting,
                "sla_paused_count": open_tickets.filter(pauses__ended_at__isnull=True).distinct().count(),
            }
        )

        visits = MaintenanceVisit.objects.select_related("contract", "contract__contractor")
        if user.is_technician and user.contractor_id:
            visits = visits.filter(contract__contractor_id=user.contractor_id)
        elif not user.has_role("admin_it", "manager"):
            visits = visits.none()

        context.update(
            {
                "visits_planned": visits.filter(status=VISIT_PLANNED).count(),
                "visits_in_progress": visits.filter(status=VISIT_IN_PROGRESS).count(),
                "visits_done": visits.filter(status=VISIT_DONE).count(),
                "visits_missed": visits.filter(status=VISIT_MISSED).count(),
                "visits_overdue": visits.filter(
                    status__in=[VISIT_PLANNED, VISIT_IN_PROGRESS],
                    scheduled_end_date__lt=timezone.localdate(),
                ).count(),
                "upcoming_visits": visits.exclude(status__in=[VISIT_DONE]).order_by("scheduled_date")[:5],
                "my_visits": visits.filter(status__in=[VISIT_PLANNED, VISIT_IN_PROGRESS])[:5]
                if user.is_technician
                else [],
            }
        )
        return context


# ---------------------------------------------------------------------------
# اعلان‌ها
# ---------------------------------------------------------------------------
@login_required
def notification_list(request):
    queryset = Notification.objects.filter(user=request.user)
    unread_only = request.GET.get("unread") == "1"
    if unread_only:
        queryset = queryset.filter(is_read=False)
    return render(
        request,
        "core/notification_list.html",
        {
            "notifications": queryset[:200],
            "unread_only": unread_only,
            "page_title": "کارتابل اعلان‌ها",
            "active_menu": "notifications",
        },
    )


@login_required
def notification_read(request, pk: int):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_read()
    if notification.url:
        return redirect(notification.url)
    return redirect("core:notification_list")


@login_required
def notifications_read_all(request):
    if request.method == "POST":
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        messages.success(request, "همه اعلان‌ها خوانده‌شده علامت خوردند.")
    return redirect("core:notification_list")


# ---------------------------------------------------------------------------
# تنظیمات سامانه
# ---------------------------------------------------------------------------
class SettingUpdateView(AdminItRequiredMixin, PageContextMixin, UpdateView):
    model = SystemSetting
    form_class = SystemSettingForm
    template_name = "core/setting_form.html"
    page_title = "تنظیمات سامانه"
    active_menu = "settings"
    success_url = "/settings/"

    def get_object(self, queryset=None):
        return SystemSetting.load()

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action("update", self.object, note="ویرایش تنظیمات سامانه", user=self.request.user)
        messages.success(self.request, "تنظیمات ذخیره شد.")
        return response


class HolidayListView(AdminItRequiredMixin, BaseListView):
    model = Holiday
    template_name = "core/holiday_list.html"
    page_title = "تعطیلات رسمی"
    active_menu = "settings"
    paginate_by = 30


class HolidayUpdateView(AdminItRequiredMixin, PageContextMixin, UpdateView):
    """ویرایش تعطیلی رسمی."""

    model = Holiday
    form_class = HolidayForm
    template_name = "core/holiday_form.html"
    page_title = "ویرایش تعطیلی رسمی"
    active_menu = "settings"
    success_url = "/settings/holidays/"


@login_required
def holiday_create(request):
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    form = HolidayForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        holiday = form.save()
        log_action("create", holiday, user=request.user)
        messages.success(request, "تعطیلی ثبت شد.")
        return redirect("core:holiday_list")
    return render(
        request,
        "core/holiday_form.html",
        {"form": form, "page_title": "ثبت تعطیلی رسمی", "active_menu": "settings"},
    )


@login_required
def holiday_delete(request, pk: int):
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    holiday = get_object_or_404(Holiday, pk=pk)
    if request.method == "POST":
        label = str(holiday)
        holiday.delete()
        log_action(
            "delete", None, model_name="Holiday", object_id=pk, object_label=label, user=request.user
        )
        messages.success(request, "تعطیلی حذف شد.")
    return redirect("core:holiday_list")


# ---------------------------------------------------------------------------
# لاگ ممیزی
# ---------------------------------------------------------------------------
class AuditLogListView(StaffRequiredMixin, BaseListView):
    model = AuditLog
    template_name = "core/audit_list.html"
    page_title = "لاگ ممیزی سامانه"
    active_menu = "audit"
    paginate_by = 40

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("user")
        if not self.request.user.is_admin_province:
            # AuditLog has no center FK: fail closed for non-provincial roles.
            queryset = queryset.filter(user=self.request.user)
        term = (self.request.GET.get("q") or "").strip()
        action = (self.request.GET.get("action") or "").strip()
        model_name = (self.request.GET.get("model") or "").strip()
        if term:
            queryset = queryset.filter(
                Q(object_label__icontains=term)
                | Q(user_label__icontains=term)
                | Q(note__icontains=term)
                | Q(object_id__icontains=term)
            )
        if action:
            queryset = queryset.filter(action=action)
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_choices"] = AuditLog.ACTION_CHOICES
        context["model_choices"] = (
            self.get_queryset().exclude(model_name="")
            .values_list("model_name", flat=True)
            .distinct()
            .order_by("model_name")
        )
        context["current_action"] = self.request.GET.get("action", "")
        context["current_model"] = self.request.GET.get("model", "")
        return context


# ---------------------------------------------------------------------------
# جستجوی سراسری
# ---------------------------------------------------------------------------
@login_required
def global_search(request):
    term = (request.GET.get("q") or "").strip()
    assets = tickets = []
    if term:
        assets = apply_search(
            _asset_scope(request.user),
            term,
            ["asset_tag", "title", "serial_number", "brand", "model_name", "hostname", "ip_address"],
        )[:30]
        base_tickets = _ticket_scope(request.user)
        tickets = apply_search(
            base_tickets, term, ["number", "title", "description", "asset__asset_tag"]
        )[:30]
    return render(
        request,
        "core/search.html",
        {
            "term": term,
            "assets": assets,
            "tickets": tickets,
            "page_title": "جستجو",
        },
    )
