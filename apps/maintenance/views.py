"""نماهای بازدیدهای دوره‌ای."""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.permissions import AnyRoleRequiredMixin, RepairStaffRequiredMixin
from apps.core.constants import CHECK_HEALTHY, VISIT_DONE, VISIT_PLANNED, VISIT_IN_PROGRESS, VISIT_MISSED
from apps.core.mixins import BaseListView, PageContextMixin, apply_search
from apps.core.utils import log_action

from .forms import (
    VisitCheckForm,
    VisitCompleteForm,
    VisitConfirmForm,
    VisitFilterForm,
    VisitForm,
)
from .models import MaintenanceVisit, VisitAssetCheck
from .services import (
    can_manage_visit,
    complete_visit,
    confirm_visit,
    populate_checks,
    save_check,
    start_visit,
    visible_checks,
    visible_visits,
    visit_statistics,
)


# ---------------------------------------------------------------------------
# فهرست‌ها
# ---------------------------------------------------------------------------
class VisitListView(AnyRoleRequiredMixin, BaseListView):
    model = MaintenanceVisit
    template_name = "maintenance/visit_list.html"
    page_title = "بازدیدهای دوره‌ای"
    active_menu = "visits"
    paginate_by = 25
    filter_form_class = VisitFilterForm

    def get_queryset(self):
        queryset = visible_visits(self.request.user).annotate(
            checks_count=Count("checks", distinct=True)
        ).order_by("-scheduled_date")
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            data = form.cleaned_data
            queryset = apply_search(
                queryset, data.get("q"), ["number", "period_label", "contract__number", "contract__contractor__name"]
            )
            if data.get("status"):
                queryset = queryset.filter(status=data["status"])
            if data.get("contract"):
                queryset = queryset.filter(contract=data["contract"])
            if data.get("contractor"):
                queryset = queryset.filter(contract__contractor=data["contractor"])
            if data.get("date_from"):
                queryset = queryset.filter(scheduled_date__gte=data["date_from"])
            if data.get("date_to"):
                queryset = queryset.filter(scheduled_date__lte=data["date_to"])
            if data.get("overdue_only"):
                from django.utils import timezone

                queryset = queryset.filter(
                    status__in=[VISIT_PLANNED, VISIT_IN_PROGRESS],
                    scheduled_end_date__lt=timezone.localdate(),
                )
        return queryset.order_by("-scheduled_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        base = visible_visits(user)
        context["counts"] = {
            "planned": base.filter(status=VISIT_PLANNED).count(),
            "in_progress": base.filter(status=VISIT_IN_PROGRESS).count(),
            "done": base.filter(status=VISIT_DONE).count(),
            "missed": base.filter(status=VISIT_MISSED).count(),
        }
        context["can_create"] = user.has_role("admin_it")
        return context


class MyVisitsView(VisitListView):
    template_name = "maintenance/my_visits.html"
    page_title = "کارتابل بازدیدهای من"
    active_menu = "my_visits"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.exclude(status=VISIT_DONE)


# ---------------------------------------------------------------------------
# نمایش و گردش کار
# ---------------------------------------------------------------------------
class VisitDetailView(AnyRoleRequiredMixin, PageContextMixin, DetailView):
    model = MaintenanceVisit
    template_name = "maintenance/visit_detail.html"
    page_title = "برگه بازدید دوره‌ای"
    active_menu = "visits"

    def get_queryset(self):
        return visible_visits(self.request.user).select_related("contract", "contract__contractor", "technician")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visit = self.object
        scoped_checks = visible_checks(self.request.user, visit)
        context["checks"] = scoped_checks.select_related("asset", "asset__category", "asset__location")
        context["stats"] = visit_statistics(visit, checks=scoped_checks)
        context["can_manage"] = can_manage_visit(self.request.user, visit)
        context["complete_form"] = VisitCompleteForm(
            initial={"report_text": visit.report_text, "recommendation": visit.recommendation}
        )
        context["confirm_form"] = VisitConfirmForm()
        return context


class VisitCreateView(RepairStaffRequiredMixin, PageContextMixin, CreateView):
    model = MaintenanceVisit
    form_class = VisitForm
    template_name = "maintenance/visit_form.html"
    page_title = "ثبت نوبت بازدید"
    active_menu = "visits"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def _bind_visit_center(self, visit):
        contract = visit.contract
        if contract.is_provincial:
            if not self.request.user.is_admin_province:
                raise PermissionDenied("برنامه‌ریزی بازدید قرارداد استانی فقط توسط مدیر استان مجاز است.")
            visit.center = None
            return
        centers = list(contract.centers.all())
        if len(centers) != 1:
            raise ValidationError("قرارداد غیر استانی باید دقیقاً به یک مرکز متصل باشد.")
        if not self.request.user.is_admin_province and not self.request.user.get_scoped_centers().filter(pk=centers[0].pk).exists():
            raise PermissionDenied("قرارداد خارج از دامنه مراکز مجاز شماست.")
        visit.center = centers[0]

    def form_valid(self, form):
        try:
            self._bind_visit_center(form.instance)
        except ValidationError as exc:
            form.add_error("contract", exc)
            return self.form_invalid(form)
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        populate_checks(self.object)
        log_action("create", self.object, note="ثبت نوبت بازدید دستی", user=self.request.user)
        messages.success(self.request, "نوبت بازدید ثبت و برگه‌های تجهیزات ساخته شد.")
        return response

    def get_success_url(self):
        return reverse("maintenance:visit_detail", args=[self.object.pk])


class VisitUpdateView(RepairStaffRequiredMixin, PageContextMixin, UpdateView):
    model = MaintenanceVisit
    form_class = VisitForm
    template_name = "maintenance/visit_form.html"
    page_title = "ویرایش نوبت بازدید"
    active_menu = "visits"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        return visible_visits(self.request.user)

    def form_valid(self, form):
        contract = form.cleaned_data["contract"]
        try:
            if contract.is_provincial:
                if not self.request.user.is_admin_province:
                    raise PermissionDenied("ویرایش بازدید قرارداد استانی فقط توسط مدیر استان مجاز است.")
                form.instance.center = None
            else:
                centers = list(contract.centers.all())
                if len(centers) != 1:
                    raise ValidationError("قرارداد غیر استانی باید دقیقاً به یک مرکز متصل باشد.")
                if not self.request.user.is_admin_province and not self.request.user.get_scoped_centers().filter(pk=centers[0].pk).exists():
                    raise PermissionDenied("قرارداد خارج از دامنه مراکز مجاز شماست.")
                form.instance.center = centers[0]
        except ValidationError as exc:
            form.add_error("contract", exc)
            return self.form_invalid(form)
        response = super().form_valid(form)
        log_action("update", self.object, note="ویرایش نوبت بازدید", user=self.request.user)
        messages.success(self.request, "نوبت بازدید ذخیره شد.")
        return response

    def get_success_url(self):
        return reverse("maintenance:visit_detail", args=[self.object.pk])


def _run_visit_action(request, pk, handler, success_message):
    visit = get_object_or_404(visible_visits(request.user), pk=pk)
    if request.method != "POST":
        return redirect("maintenance:visit_detail", pk=visit.pk)
    try:
        handler(visit)
        messages.success(request, success_message)
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:visit_detail", pk=visit.pk)


def visit_start(request, pk: int):
    return _run_visit_action(
        request, pk,
        lambda visit: start_visit(visit, request.user),
        "بازدید آغاز شد.",
    )


def visit_complete(request, pk: int):
    form = VisitCompleteForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "اطلاعات فرم پایان بازدید ناقص است.")
        return redirect("maintenance:visit_detail", pk=pk)
    return _run_visit_action(
        request, pk,
        lambda visit: complete_visit(
            visit, request.user,
            report_text=form.cleaned_data.get("report_text", ""),
            recommendation=form.cleaned_data.get("recommendation", ""),
            force=form.cleaned_data.get("force", False),
        ),
        "بازدید پایان یافت و برای تایید کارشناس IT ارسال شد.",
    )


def visit_confirm(request, pk: int):
    form = VisitConfirmForm(request.POST or None)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    return _run_visit_action(
        request, pk,
        lambda visit: confirm_visit(visit, request.user, note),
        "بازدید تایید شد.",
    )


def visit_bulk_healthy(request, pk: int):
    """ثبت گروهی وضعیت سالم برای برگه‌های بازدیدشده‌نشده."""

    def handler(visit):
        if not can_manage_visit(request.user, visit):
            raise PermissionDenied("اجازه ثبت این بازدید را ندارید.")
        pending = visit.checks.filter(checked=False)
        count = pending.count()
        for check in pending:
            save_check(check, request.user, condition=CHECK_HEALTHY, checked=True)
        log_action(
            "update", visit,
            note=f"ثبت گروهی وضعیت سالم برای {count} تجهیز",
            user=request.user,
        )

    return _run_visit_action(
        request, pk, handler, "برگه‌های باقی‌مانده با وضعیت «سالم» ثبت شدند."
    )


def check_edit(request, pk: int):
    """ثبت نتیجه بازدید یک تجهیز."""
    check = get_object_or_404(
        VisitAssetCheck.objects.select_related("visit", "visit__contract", "asset"), pk=pk
    )
    if not can_manage_visit(request.user, check.visit):
        raise PermissionDenied("اجازه ثبت این برگه بازدید را ندارید.")

    form = VisitCheckForm(request.POST or None, request.FILES or None, instance=check)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.checked = True
        from django.utils import timezone

        obj.checked_at = timezone.now()
        obj.checked_by = request.user
        obj.save()
        log_action("update", obj, note="ثبت نتیجه بازدید تجهیز", user=request.user)
        messages.success(request, "برگه بازدید ذخیره شد.")
        return redirect("maintenance:visit_detail", pk=check.visit_id)

    return render(
        request,
        "maintenance/check_form.html",
        {
            "form": form,
            "check": check,
            "visit": check.visit,
            "asset": check.asset,
            "page_title": f"برگه بازدید {check.asset.asset_tag}",
            "active_menu": "visits",
        },
    )


def visit_print(request, pk: int):
    """نسخه چاپی برگه بازدید."""
    visit = get_object_or_404(visible_visits(request.user), pk=pk)
    return render(
        request,
        "maintenance/visit_print.html",
        {
            "visit": visit,
            "checks": visible_checks(request.user, visit).select_related(
                "asset", "asset__location", "asset__category"
            ),
            "stats": visit_statistics(visit, checks=visible_checks(request.user, visit)),
        },
    )
