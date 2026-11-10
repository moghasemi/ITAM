"""نماهای ساختار سازمانی، پیمانکاران، قراردادها و SLA."""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.core.constants import TICKET_OPEN_STATUSES
from apps.accounts.permissions import (
    AdminItRequiredMixin,
    ProvinceAdminRequiredMixin,
    CountryAdminRequiredMixin,
)
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
    CenterForm,
    ContractFilterForm,
    ContractForm,
    ContractorForm,
    DepartmentForm,
    LocationForm,
    SlaPolicyFormSet,
)
from .models import Center, Contract, Contractor, Department, Location


def _visible_contracts_for_user(user):
    if user.is_admin_country:
        return Contract.objects.all()
    if user.has_role("technician"):
        return user.get_active_contractor_contracts()
    province_ids = user.get_scoped_centers().values("parent_unit__parent_id")
    return Contract.objects.filter(province_id__in=province_ids).distinct()


# ---------------------------------------------------------------------------
# مراکز استان
# ---------------------------------------------------------------------------
class CenterListView(AdminItRequiredMixin, BaseListView):
    model = Center
    template_name = "org/center_list.html"
    page_title = "مراکز استان و مدیریت ستادی"
    active_menu = "org"

    def get_queryset(self):
        scoped = self.request.user.get_scoped_centers()
        queryset = scoped.annotate(
            assets_total=Count("assets", distinct=True),
            users_total=Count("users", distinct=True),
        ).order_by("-is_headquarters", "name")
        return apply_search(queryset, self.request.GET.get("q"), ["name", "code", "city", "manager_name"])


class CenterCreateView(ProvinceAdminRequiredMixin, BaseCreateView):
    model = Center
    form_class = CenterForm
    template_name = "org/simple_form.html"
    page_title = "افزودن مرکز جدید"
    active_menu = "org"
    success_url = reverse_lazy("org:center_list")
    success_message = "مرکز جدید با موفقیت ثبت شد."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class CenterUpdateView(ProvinceAdminRequiredMixin, BaseUpdateView):
    model = Center
    form_class = CenterForm
    template_name = "org/simple_form.html"
    page_title = "ویرایش مشخصات مرکز"
    active_menu = "org"
    success_url = reverse_lazy("org:center_list")
    success_message = "تغییرات مرکز ذخیره شد."

    def get_queryset(self):
        return self.request.user.get_scoped_centers()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


# ---------------------------------------------------------------------------
# واحدهای سازمانی
# ---------------------------------------------------------------------------
class DepartmentListView(AdminItRequiredMixin, BaseListView):
    model = Department
    template_name = "org/department_list.html"
    page_title = "واحدهای سازمانی"
    active_menu = "org"

    def get_queryset(self):
        scoped = self.request.user.get_scoped_centers()
        queryset = Department.objects.filter(center__in=scoped).annotate(assets_total=Count("assets", distinct=True)).order_by("name")
        return apply_search(queryset, self.request.GET.get("q"), ["name", "code", "manager_name"])


class DepartmentCreateView(AdminItRequiredMixin, BaseCreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "org/simple_form.html"
    page_title = "افزودن واحد سازمانی"
    active_menu = "org"
    success_url = reverse_lazy("org:department_list")
    success_message = "واحد سازمانی ثبت شد."


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

class DepartmentUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "org/simple_form.html"
    page_title = "ویرایش واحد سازمانی"
    active_menu = "org"
    success_url = reverse_lazy("org:department_list")

    def get_queryset(self):
        scoped = self.request.user.get_scoped_centers()
        return Department.objects.filter(center__in=scoped)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


# ---------------------------------------------------------------------------
# محل‌های استقرار
# ---------------------------------------------------------------------------
class LocationListView(AdminItRequiredMixin, BaseListView):
    model = Location
    template_name = "org/location_list.html"
    page_title = "محل‌های استقرار"
    active_menu = "org"

    def get_queryset(self):
        scoped = self.request.user.get_scoped_centers()
        queryset = Location.objects.filter(center__in=scoped).annotate(assets_total=Count("assets", distinct=True)).order_by(
            "building", "floor", "name"
        )
        return apply_search(queryset, self.request.GET.get("q"), ["name", "building", "floor", "room", "code"])


class LocationCreateView(AdminItRequiredMixin, BaseCreateView):
    model = Location
    form_class = LocationForm
    template_name = "org/simple_form.html"
    page_title = "افزودن محل استقرار"
    active_menu = "org"
    success_url = reverse_lazy("org:location_list")
    success_message = "محل استقرار ثبت شد."


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

class LocationUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = Location
    form_class = LocationForm
    template_name = "org/simple_form.html"
    page_title = "ویرایش محل استقرار"
    active_menu = "org"
    success_url = reverse_lazy("org:location_list")

    def get_queryset(self):
        scoped = self.request.user.get_scoped_centers()
        return Location.objects.filter(center__in=scoped)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


# ---------------------------------------------------------------------------
# پیمانکاران
# ---------------------------------------------------------------------------
class ContractorListView(AdminItRequiredMixin, BaseListView):
    model = Contractor
    template_name = "org/contractor_list.html"
    page_title = "پیمانکاران"
    active_menu = "org"

    def get_queryset(self):
        user = self.request.user
        contracts = _visible_contracts_for_user(user)
        queryset = Contractor.objects.filter(
            pk__in=contracts.values("contractor_id")
        )
        if user.is_admin_province:
            queryset = queryset.annotate(
                contracts_total=Count("contracts", distinct=True),
                technicians_total=Count("technicians", distinct=True),
            )
        else:
            scoped_centers = user.get_scoped_centers()
            queryset = queryset.annotate(
                contracts_total=Count("contracts", filter=Q(contracts__in=contracts), distinct=True),
                technicians_total=Count(
                    "technicians", filter=Q(technicians__center__in=scoped_centers), distinct=True
                ),
            )
        queryset = queryset.order_by("name")
        return apply_search(queryset, self.request.GET.get("q"), ["name", "code", "contact_person", "phone"])


class ContractorCreateView(ProvinceAdminRequiredMixin, BaseCreateView):
    model = Contractor
    form_class = ContractorForm
    template_name = "org/contractor_form.html"
    page_title = "افزودن پیمانکار"
    active_menu = "org"
    success_url_name = "org:contractor_detail"
    success_message = "پیمانکار ثبت شد."


class ContractorUpdateView(ProvinceAdminRequiredMixin, BaseUpdateView):
    model = Contractor
    form_class = ContractorForm
    template_name = "org/contractor_form.html"
    page_title = "ویرایش پیمانکار"
    active_menu = "org"
    success_url_name = "org:contractor_detail"

    def get_queryset(self):
        contracts = _visible_contracts_for_user(self.request.user)
        return Contractor.objects.filter(pk__in=contracts.values("contractor_id")).distinct()


class ContractorDetailView(AdminItRequiredMixin, BaseDetailView):
    model = Contractor
    template_name = "org/contractor_detail.html"
    page_title = "پرونده پیمانکار"
    active_menu = "org"

    def get_queryset(self):
        contracts = _visible_contracts_for_user(self.request.user)
        return Contractor.objects.filter(pk__in=contracts.values("contractor_id")).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contractor = self.object
        user = self.request.user
        from apps.maintenance.services import visible_visits
        from apps.tickets.services import visible_tickets

        contracts = _visible_contracts_for_user(user).filter(contractor=contractor)
        context["contracts"] = contracts.select_related("contractor").order_by("-start_date")
        technicians = contractor.technicians.all()
        if not user.is_admin_province:
            technicians = technicians.filter(center__in=user.get_scoped_centers())
        context["technicians"] = technicians
        tickets = visible_tickets(user).filter(assigned_contractor=contractor)
        context["tickets_total"] = tickets.count()
        context["tickets_open"] = tickets.filter(status__in=TICKET_OPEN_STATUSES).count()
        context["visits"] = visible_visits(user).filter(
            contract__contractor=contractor
        ).select_related("contract").order_by("-scheduled_date")[:10]
        return context


# ---------------------------------------------------------------------------
# قراردادها
# ---------------------------------------------------------------------------
class ContractListView(AdminItRequiredMixin, BaseListView):
    model = Contract
    template_name = "org/contract_list.html"
    page_title = "قراردادهای نگهداری و تعمیرات"
    active_menu = "contracts"
    filter_form_class = ContractFilterForm

    def get_filter_form(self):
        return self.filter_form_class(
            self.request.GET or None, user=self.request.user
        )

    def get_queryset(self):
        user = self.request.user
        queryset = _visible_contracts_for_user(user).select_related("contractor", "province")
        if user.is_admin_province:
            queryset = queryset.annotate(
                assets_total=Count("assets", distinct=True),
                tickets_total=Count("tickets", distinct=True),
            )
        else:
            centers = user.get_scoped_centers()
            queryset = queryset.annotate(
                assets_total=Count("assets", filter=Q(assets__center__in=centers), distinct=True),
                tickets_total=Count("tickets", filter=Q(tickets__asset__center__in=centers), distinct=True),
            )
        queryset = queryset.order_by("-start_date")
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

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


class ContractCreateView(ProvinceAdminRequiredMixin, ContractFormMixin, BaseCreateView):
    model = Contract
    form_class = ContractForm
    template_name = "org/contract_form.html"
    page_title = "ثبت قرارداد جدید"
    active_menu = "contracts"
    success_url_name = "org:contract_detail"
    creating = True


class ContractUpdateView(ProvinceAdminRequiredMixin, ContractFormMixin, BaseUpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "org/contract_form.html"
    page_title = "ویرایش قرارداد"
    active_menu = "contracts"
    success_url_name = "org:contract_detail"
    creating = False

    def get_queryset(self):
        return _visible_contracts_for_user(self.request.user)


class ContractDetailView(AdminItRequiredMixin, BaseDetailView):
    model = Contract
    template_name = "org/contract_detail.html"
    page_title = "پرونده قرارداد"
    active_menu = "contracts"

    def get_queryset(self):
        return _visible_contracts_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self.object
        from apps.assets.services import visible_assets
        from apps.maintenance.services import visible_visits
        from apps.tickets.services import visible_tickets

        tickets = visible_tickets(self.request.user).filter(contract=contract)
        visits = visible_visits(self.request.user).filter(contract=contract)
        assets = visible_assets(self.request.user).filter(contract=contract)
        context["sla_policies"] = contract.sla_table()
        context["visits"] = visits.select_related("technician").order_by("sequence_number")
        context["assets"] = assets.select_related("category", "location")[:50]
        context["assets_total"] = assets.count()
        context["tickets_total"] = tickets.count()
        context["tickets_open"] = tickets.filter(status__in=TICKET_OPEN_STATUSES).count()
        context["tickets_closed"] = tickets.exclude(status__in=TICKET_OPEN_STATUSES).count()
        context["breached_count"] = tickets.filter(Q(response_met=False) | Q(resolve_met=False)).count()
        context["planned_visits"] = visits.count()
        context["sla_minutes_to_hours"] = True
        return context


def contract_generate_visits(request, pk: int):
    """برنامه‌ریزی بازدیدهای دوره‌ای یک قرارداد."""
    contract = get_object_or_404(
        _visible_contracts_for_user(request.user),
        pk=pk,
    )
    if not request.user.has_role("admin_it"):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("فقط کارشناس فناوری اطلاعات مرکز می‌تواند بازدیدها را برنامه‌ریزی کند.")
    if (
        request.user.has_role("admin_it")
        and not request.user.is_admin_province
        and contract.province_id
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            "برنامه‌ریزی قرارداد استانی باید توسط مدیر استان انجام شود تا بازدیدها بین مراکز تفکیک شوند."
        )
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
