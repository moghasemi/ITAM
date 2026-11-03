"""نماهای ساختار سازمانی، پیمانکاران، قراردادها و SLA."""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.core.constants import TICKET_OPEN_STATUSES
from apps.core.mixins import (
    BaseCreateView,
    BaseDetailView,
    BaseListView,
    BaseUpdateView,
    PageContextMixin,
    apply_search,
)
from apps.core.utils import log_action

from .forms import (
    ContractFilterForm,
    ContractForm,
    ContractorForm,
    DepartmentForm,
    LocationForm,
    SlaPolicyFormSet,
)
from .models import Contract, Contractor, Department, Location


# ---------------------------------------------------------------------------
# واحدهای سازمانی
# ---------------------------------------------------------------------------
class DepartmentListView(BaseListView):
    model = Department
    template_name = "org/department_list.html"
    page_title = "واحدهای سازمانی"
    active_menu = "org"

    def get_queryset(self):
        queryset = Department.objects.annotate(assets_total=Count("assets", distinct=True)).order_by("name")
        return apply_search(queryset, self.request.GET.get("q"), ["name", "code", "manager_name"])


class DepartmentCreateView(BaseCreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "org/simple_form.html"
    page_title = "افزودن واحد سازمانی"
    active_menu = "org"
    success_url = reverse_lazy("org:department_list")
    success_message = "واحد سازمانی ثبت شد."


class DepartmentUpdateView(BaseUpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "org/simple_form.html"
    page_title = "ویرایش واحد سازمانی"
    active_menu = "org"
    success_url = reverse_lazy("org:department_list")


# ---------------------------------------------------------------------------
# محل‌های استقرار
# ---------------------------------------------------------------------------
class LocationListView(BaseListView):
    model = Location
    template_name = "org/location_list.html"
    page_title = "محل‌های استقرار"
    active_menu = "org"

    def get_queryset(self):
        queryset = Location.objects.annotate(assets_total=Count("assets", distinct=True)).order_by(
            "building", "floor", "name"
        )
        return apply_search(queryset, self.request.GET.get("q"), ["name", "building", "floor", "room", "code"])


class LocationCreateView(BaseCreateView):
    model = Location
    form_class = LocationForm
    template_name = "org/simple_form.html"
    page_title = "افزودن محل استقرار"
    active_menu = "org"
    success_url = reverse_lazy("org:location_list")
    success_message = "محل استقرار ثبت شد."


class LocationUpdateView(BaseUpdateView):
    model = Location
    form_class = LocationForm
    template_name = "org/simple_form.html"
    page_title = "ویرایش محل استقرار"
    active_menu = "org"
    success_url = reverse_lazy("org:location_list")


# ---------------------------------------------------------------------------
# پیمانکاران
# ---------------------------------------------------------------------------
class ContractorListView(BaseListView):
    model = Contractor
    template_name = "org/contractor_list.html"
    page_title = "پیمانکاران"
    active_menu = "org"

    def get_queryset(self):
        queryset = Contractor.objects.annotate(
            contracts_total=Count("contracts", distinct=True),
            technicians_total=Count("technicians", distinct=True),
        ).order_by("name")
        return apply_search(queryset, self.request.GET.get("q"), ["name", "code", "contact_person", "phone"])


class ContractorCreateView(BaseCreateView):
    model = Contractor
    form_class = ContractorForm
    template_name = "org/contractor_form.html"
    page_title = "افزودن پیمانکار"
    active_menu = "org"
    success_url_name = "org:contractor_detail"
    success_message = "پیمانکار ثبت شد."


class ContractorUpdateView(BaseUpdateView):
    model = Contractor
    form_class = ContractorForm
    template_name = "org/contractor_form.html"
    page_title = "ویرایش پیمانکار"
    active_menu = "org"
    success_url_name = "org:contractor_detail"


class ContractorDetailView(BaseDetailView):
    model = Contractor
    template_name = "org/contractor_detail.html"
    page_title = "پرونده پیمانکار"
    active_menu = "org"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contractor = self.object
        context["contracts"] = contractor.contracts.select_related("contractor").order_by("-start_date")
        context["technicians"] = contractor.technicians.all()
        tickets = contractor.tickets.all()
        context["tickets_total"] = tickets.count()
        context["tickets_open"] = tickets.filter(status__in=TICKET_OPEN_STATUSES).count()
        context["visits"] = contractor.visits.select_related("contract").order_by("-scheduled_date")[:10]
        return context


# ---------------------------------------------------------------------------
# قراردادها
# ---------------------------------------------------------------------------
class ContractListView(BaseListView):
    model = Contract
    template_name = "org/contract_list.html"
    page_title = "قراردادهای نگهداری و تعمیرات"
    active_menu = "contracts"
    filter_form_class = ContractFilterForm

    def get_queryset(self):
        queryset = Contract.objects.select_related("contractor").annotate(
            assets_total=Count("assets", distinct=True),
            tickets_total=Count("tickets", distinct=True),
        ).order_by("-start_date")
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            data = form.cleaned_data
            queryset = apply_search(queryset, data.get("q"), ["number", "title", "contractor__name"])
            if data.get("status"):
                queryset = queryset.filter(status=data["status"])
            if data.get("contractor"):
                queryset = queryset.filter(contractor=data["contractor"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = timezone.localdate()
        return context


class ContractFormMixin:
    """ذخیره هم‌زمان قرارداد و سیاست‌های SLA."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["sla_formset"] = SlaPolicyFormSet(self.request.POST, instance=self.object)
        else:
            context["sla_formset"] = SlaPolicyFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["sla_formset"]
        if not formset.is_valid():
            messages.error(self.request, "سیاست‌های SLA را بررسی کنید.")
            return self.form_invalid(form)
        self.object = form.save()
        formset.instance = self.object
        formset.save()
        log_action(
            "create" if self.creating else "update",
            self.object,
            note="ثبت/ویرایش قرارداد و سیاست‌های SLA",
            user=self.request.user,
        )
        messages.success(self.request, "قرارداد ذخیره شد.")
        return redirect(self.get_success_url())


class ContractCreateView(ContractFormMixin, BaseCreateView):
    model = Contract
    form_class = ContractForm
    template_name = "org/contract_form.html"
    page_title = "ثبت قرارداد جدید"
    active_menu = "contracts"
    success_url_name = "org:contract_detail"
    creating = True


class ContractUpdateView(ContractFormMixin, BaseUpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "org/contract_form.html"
    page_title = "ویرایش قرارداد"
    active_menu = "contracts"
    success_url_name = "org:contract_detail"
    creating = False


class ContractDetailView(BaseDetailView):
    model = Contract
    template_name = "org/contract_detail.html"
    page_title = "پرونده قرارداد"
    active_menu = "contracts"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self.object
        tickets = contract.tickets.all()
        context["sla_policies"] = contract.sla_table()
        context["visits"] = contract.visits.select_related("technician").order_by("sequence_number")
        context["assets"] = contract.assets.select_related("category", "location")[:50]
        context["assets_total"] = contract.assets.count()
        context["tickets_total"] = tickets.count()
        context["tickets_open"] = tickets.filter(status__in=TICKET_OPEN_STATUSES).count()
        context["tickets_closed"] = tickets.exclude(status__in=TICKET_OPEN_STATUSES).count()
        context["breached_count"] = tickets.filter(Q(response_met=False) | Q(resolve_met=False)).count()
        context["planned_visits"] = contract.planned_visit_count()
        context["sla_minutes_to_hours"] = True
        return context


def contract_generate_visits(request, pk: int):
    """برنامه‌ریزی بازدیدهای دوره‌ای یک قرارداد."""
    contract = get_object_or_404(Contract, pk=pk)
    if not request.user.has_role("admin_it"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("فقط کارشناس فناوری اطلاعات مرکز می‌تواند بازدیدها را برنامه‌ریزی کند.")
    if request.method == "POST":
        from apps.maintenance.services import generate_visits

        try:
            result = generate_visits(contract, user=request.user)
            messages.success(
                request,
                f"{result['created']} نوبت بازدید جدید برنامه‌ریزی شد "
                f"(از مجموع {result['planned']} نوبت مورد انتظار).",
            )
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"برنامه‌ریزی بازدید انجام نشد: {exc}")
    return redirect("org:contract_detail", pk=pk)
