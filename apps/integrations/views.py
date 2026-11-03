"""نماهای یکپارچه‌سازی: پنل صف رخدادها و مقصدهای ارسال به مدیریت."""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView

from apps.accounts.permissions import AdminItRequiredMixin, StaffRequiredMixin
from apps.core.mixins import BaseCreateView, BaseListView, BaseUpdateView, PageContextMixin

from .forms import EventFilterForm, WebhookEndpointForm
from .models import ApiCallLog, OutboxEvent, WebhookEndpoint
from .services import build_envelope, dispatch_pending, outbox_statistics, requeue_dead_events


class OutboxListView(StaffRequiredMixin, BaseListView):
    model = OutboxEvent
    template_name = "integrations/outbox_list.html"
    page_title = "صف رخدادهای ارسالی به مدیریت"
    active_menu = "integrations"
    paginate_by = 30
    filter_form_class = EventFilterForm

    def get_queryset(self):
        queryset = OutboxEvent.objects.select_related("actor", "endpoint").order_by("-created_at")
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            data = form.cleaned_data
            term = (data.get("q") or "").strip()
            if term:
                queryset = queryset.filter(
                    Q(payload__icontains=term)
                    | Q(aggregate_id__icontains=term)
                    | Q(actor_label__icontains=term)
                )
            if data.get("event_type"):
                queryset = queryset.filter(event_type=data["event_type"])
            if data.get("status"):
                queryset = queryset.filter(status=data["status"])
            if data.get("aggregate_type"):
                queryset = queryset.filter(aggregate_type=data["aggregate_type"])
            if data.get("date_from"):
                queryset = queryset.filter(created_at__date__gte=data["date_from"])
            if data.get("date_to"):
                queryset = queryset.filter(created_at__date__lte=data["date_to"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = outbox_statistics()
        context["endpoints"] = WebhookEndpoint.objects.all()
        context["can_manage"] = self.request.user.has_role("admin_it")
        return context


class OutboxDetailView(StaffRequiredMixin, PageContextMixin, DetailView):
    model = OutboxEvent
    template_name = "integrations/outbox_detail.html"
    page_title = "جزئیات رخداد"
    active_menu = "integrations"

    def get_context_data(self, **kwargs):
        import json

        context = super().get_context_data(**kwargs)
        context["calls"] = self.object.calls.select_related("endpoint")[:20]
        context["can_manage"] = self.request.user.has_role("admin_it")
        context["envelope"] = build_envelope(self.object)
        context["envelope_json"] = json.dumps(
            context["envelope"], ensure_ascii=False, indent=2
        )
        return context


def dispatch_now(request):
    """ارسال دستی رخدادهای در انتظار به مقصدهای فعال."""
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    if request.method == "POST":
        summary = dispatch_pending(limit=200, user=request.user)
        if not summary["endpoints"]:
            messages.warning(
                request,
                "هیچ مقصد فعالی تعریف نشده است؛ رخدادها در صف باقی می‌مانند و گم نمی‌شوند.",
            )
        else:
            messages.success(
                request,
                f"پردازش‌شده: {summary['processed']} — موفق: {summary['sent']} — ناموفق: {summary['failed']}",
            )
    return redirect("integrations:outbox_list")


def requeue_event(request, pk: int):
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    event = get_object_or_404(OutboxEvent, pk=pk)
    if request.method == "POST":
        event.requeue()
        messages.success(request, "رخداد به صف ارسال بازگشت.")
    return redirect("integrations:outbox_detail", pk=pk)


def requeue_all(request):
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    if request.method == "POST":
        count = requeue_dead_events(user=request.user)
        messages.success(request, f"{count} رخداد متوقف‌شده به صف بازگشت.")
    return redirect("integrations:outbox_list")


class EndpointListView(AdminItRequiredMixin, BaseListView):
    model = WebhookEndpoint
    template_name = "integrations/endpoint_list.html"
    page_title = "مقصدهای ارسال رخداد"
    active_menu = "integrations"
    paginate_by = 30


class EndpointCreateView(AdminItRequiredMixin, BaseCreateView):
    model = WebhookEndpoint
    form_class = WebhookEndpointForm
    template_name = "integrations/endpoint_form.html"
    page_title = "افزودن مقصد ارسال"
    active_menu = "integrations"
    success_url = reverse_lazy("integrations:endpoint_list")
    success_message = "مقصد ارسال ثبت شد."


class EndpointUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = WebhookEndpoint
    form_class = WebhookEndpointForm
    template_name = "integrations/endpoint_form.html"
    page_title = "ویرایش مقصد ارسال"
    active_menu = "integrations"
    success_url = reverse_lazy("integrations:endpoint_list")


class ApiCallListView(StaffRequiredMixin, BaseListView):
    model = ApiCallLog
    template_name = "integrations/api_call_list.html"
    page_title = "لاگ ارسال به مدیریت"
    active_menu = "integrations"
    paginate_by = 40

    def get_queryset(self):
        return ApiCallLog.objects.select_related("endpoint", "event")
