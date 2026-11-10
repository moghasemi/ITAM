"""نماهای درخواست خرابی و اقدام‌های گردش کار."""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from apps.accounts.permissions import AnyRoleRequiredMixin
from apps.assets.models import Asset
from apps.assets.services import visible_assets
from apps.core.constants import (
    STATUS_RESOLVED,
    STATUS_USER_CONFIRMED,
    TICKET_OPEN_STATUSES,
)
from apps.core.mixins import BaseListView, PageContextMixin, apply_search
from apps.core.utils import log_action

from .forms import (
    AcknowledgeForm,
    ArriveForm,
    CancelForm,
    ItConfirmForm,
    PauseForm,
    ResolveForm,
    ResumeForm,
    TicketAttachmentForm,
    TicketCreateForm,
    TicketFilterForm,
    TicketNoteForm,
    TicketPartForm,
    UserConfirmForm,
    UserRejectForm,
)
from .models import Ticket, TicketEvent, TicketPart
from .services import (
    acknowledge,
    can_confirm_as_it,
    can_confirm_as_user,
    can_manage_ticket,
    confirm_by_it,
    confirm_by_user,
    create_ticket,
    declare_resolved,
    mark_arrived,
    pause_clock,
    recalculate_sla,
    reject_by_user,
    reject_ticket,
    resume_clock,
    sla_state,
    start_work,
    visible_tickets,
)


# ---------------------------------------------------------------------------
# فهرست‌ها
# ---------------------------------------------------------------------------
class TicketListView(AnyRoleRequiredMixin, BaseListView):
    model = Ticket
    template_name = "tickets/ticket_list.html"
    page_title = "درخواست‌های خرابی"
    active_menu = "tickets"
    paginate_by = 25
    filter_form_class = TicketFilterForm

    def get_filter_form(self):
        return self.filter_form_class(
            self.request.GET or None, user=self.request.user
        )

    def get_queryset(self):
        queryset = visible_tickets(self.request.user)
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            data = form.cleaned_data
            queryset = apply_search(
                queryset, data.get("q"), ["number", "title", "description", "asset__asset_tag"]
            )
            if data.get("status"):
                queryset = queryset.filter(status=data["status"])
            if data.get("priority"):
                queryset = queryset.filter(priority=data["priority"])
            if data.get("failure_type"):
                queryset = queryset.filter(failure_type=data["failure_type"])
            if data.get("contract"):
                queryset = queryset.filter(contract=data["contract"])
            if data.get("contractor"):
                queryset = queryset.filter(assigned_contractor=data["contractor"])
            if data.get("date_from"):
                queryset = queryset.filter(reported_at__date__gte=data["date_from"])
            if data.get("date_to"):
                queryset = queryset.filter(reported_at__date__lte=data["date_to"])
            if data.get("open_only"):
                queryset = queryset.filter(status__in=TICKET_OPEN_STATUSES)
            sla_filter = data.get("sla")
            if sla_filter == "breached":
                queryset = queryset.filter(Q(response_met=False) | Q(resolve_met=False))
            elif sla_filter == "met":
                queryset = queryset.filter(response_met=True, resolve_met=True)
        return queryset.order_by("-reported_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["open_count"] = visible_tickets(self.request.user).filter(
            status__in=TICKET_OPEN_STATUSES
        ).count()
        context["can_create"] = True
        context["sla_filter"] = self.request.GET.get("sla", "")
        return context


class MyTicketsView(TicketListView):
    template_name = "tickets/my_tickets.html"
    page_title = "درخواست‌های من"
    active_menu = "my_tickets"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        return queryset.filter(
            Q(reported_by=user) | Q(asset__custodian=user)
        ).distinct()


# ---------------------------------------------------------------------------
# ثبت و مشاهده
# ---------------------------------------------------------------------------
class TicketCreateView(PageContextMixin, CreateView):
    model = Ticket
    form_class = TicketCreateForm
    template_name = "tickets/ticket_form.html"
    page_title = "اعلام خرابی تجهیز"
    active_menu = "tickets"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        asset_id = self.request.GET.get("asset")
        if asset_id:
            initial["asset"] = asset_id
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["assets"] = visible_assets(self.request.user).order_by("asset_tag")
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            ticket = create_ticket(
                asset=data["asset"],
                title=data["title"],
                description=data["description"],
                priority=data["priority"],
                failure_type=data.get("failure_type") or "",
                user=self.request.user,
                reporter_name=data.get("reporter_name") or "",
                reporter_phone=data.get("reporter_phone") or "",
                reported_at=data.get("reported_at"),
            )
        except ValidationError as exc:
            form.add_error(None, "؛ ".join(exc.messages))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"درخواست {ticket.number} ثبت شد و برای پیمانکار ارسال گردید. زمان اعلام: "
            f"{ticket.reported_at:%Y-%m-%d %H:%M}",
        )
        return redirect("tickets:detail", pk=ticket.pk)


class TicketDetailView(AnyRoleRequiredMixin, PageContextMixin, DetailView):
    model = Ticket
    template_name = "tickets/ticket_detail.html"
    page_title = "جزئیات درخواست خرابی"
    active_menu = "tickets"

    def get_queryset(self):
        return visible_tickets(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = self.object
        user = self.request.user
        recalculate_sla(ticket)
        context["events"] = ticket.events.select_related("actor")
        context["pauses"] = ticket.pauses.all()
        context["parts"] = ticket.parts.select_related("component_type")
        context["attachments"] = ticket.attachments.all()
        context["timeline"] = ticket.timeline()
        context["steps"] = ticket.workflow_steps()
        context["sla"] = sla_state(ticket)
        context["is_manager_side"] = can_manage_ticket(user, ticket)
        context["is_it"] = can_confirm_as_it(user, ticket)
        context["can_user_confirm"] = can_confirm_as_user(user, ticket)
        context["note_form"] = TicketNoteForm()
        context["part_form"] = TicketPartForm()
        context["attachment_form"] = TicketAttachmentForm()
        return context


def ticket_print(request, pk: int):
    """نسخه چاپی درخواست."""
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    recalculate_sla(ticket)
    return render(
        request,
        "tickets/ticket_print.html",
        {
            "ticket": ticket,
            "events": ticket.events.select_related("actor"),
            "pauses": ticket.pauses.all(),
            "parts": ticket.parts.all(),
            "timeline": ticket.timeline(),
        },
    )


# ---------------------------------------------------------------------------
# اقدام‌های گردش کار
# ---------------------------------------------------------------------------
def _run_action(request, pk, handler, success_message: str, redirect_to="tickets:detail"):
    """اجرای یک اقدام گردش کار با مدیریت خطا."""
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    if request.method != "POST":
        return redirect(redirect_to, pk=ticket.pk)
    try:
        handler(ticket)
        messages.success(request, success_message)
    except (ValidationError, PermissionDenied) as exc:
        detail = "؛ ".join(getattr(exc, "messages", [str(exc)]))
        messages.error(request, detail)
    return redirect(redirect_to, pk=ticket.pk)


def ticket_acknowledge(request, pk: int):
    form = AcknowledgeForm(request.POST or None)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    return _run_action(
        request, pk,
        lambda ticket: acknowledge(ticket, request.user, note),
        "درخواست پذیرفته شد و زمان پذیرش ثبت گردید.",
    )


def ticket_arrive(request, pk: int):
    form = ArriveForm(request.POST or None)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    wait_parts = bool(form.cleaned_data.get("parts_wait")) if form.is_valid() else False

    def handler(ticket):
        mark_arrived(ticket, request.user, note)
        if wait_parts:
            pause_clock(ticket, request.user, "awaiting_parts", "در انتظار تامین قطعه پس از حضور")

    return _run_action(
        request, pk, handler,
        "حضور در محل ثبت شد؛ زمان پاسخ SLA محاسبه گردید.",
    )


def ticket_start(request, pk: int):
    return _run_action(
        request, pk,
        lambda ticket: start_work(ticket, request.user, request.POST.get("note", "")),
        "شروع تعمیر ثبت شد.",
    )


def ticket_pause(request, pk: int):
    form = PauseForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "دلیل توقف ساعت را انتخاب کنید.")
        return redirect("tickets:detail", pk=pk)
    return _run_action(
        request, pk,
        lambda ticket: pause_clock(
            ticket, request.user, form.cleaned_data["reason"], form.cleaned_data.get("note", "")
        ),
        "ساعت SLA متوقف شد.",
    )


def ticket_resume(request, pk: int):
    form = ResumeForm(request.POST or None)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    return _run_action(
        request, pk,
        lambda ticket: resume_clock(ticket, request.user, note),
        "شمارش ساعت SLA ادامه یافت.",
    )


def ticket_resolve(request, pk: int):
    form = ResolveForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "علت خرابی و اقدام انجام‌شده الزامی است.")
        return redirect("tickets:detail", pk=pk)
    return _run_action(
        request, pk,
        lambda ticket: declare_resolved(
            ticket, request.user,
            root_cause=form.cleaned_data["root_cause"],
            action_taken=form.cleaned_data["action_taken"],
            parts_text=form.cleaned_data.get("parts_text", ""),
            note=form.cleaned_data.get("note", ""),
        ),
        "اعلام رفع خرابی ثبت شد؛ در انتظار تایید کاربر و کارشناس IT.",
    )


def ticket_user_confirm(request, pk: int):
    form = UserConfirmForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "اطلاعات فرم تایید ناقص است.")
        return redirect("tickets:detail", pk=pk)
    return _run_action(
        request, pk,
        lambda ticket: confirm_by_user(
            ticket, request.user,
            form.cleaned_data.get("note", ""),
            form.cleaned_data.get("satisfaction"),
        ),
        "تایید کاربر ثبت شد.",
    )


def ticket_user_reject(request, pk: int):
    form = UserRejectForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "دلیل عدم تایید را وارد کنید.")
        return redirect("tickets:detail", pk=pk)
    return _run_action(
        request, pk,
        lambda ticket: reject_by_user(ticket, request.user, form.cleaned_data["reason"]),
        "عدم تایید ثبت شد و درخواست به جریان رسیدگی بازگشت.",
    )


def ticket_it_confirm(request, pk: int):
    form = ItConfirmForm(request.POST or None)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    return _run_action(
        request, pk,
        lambda ticket: confirm_by_it(ticket, request.user, note),
        "تایید نهایی کارشناس IT ثبت و درخواست بسته شد.",
    )


def ticket_cancel(request, pk: int):
    form = CancelForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "دلیل لغو را وارد کنید.")
        return redirect("tickets:detail", pk=pk)
    return _run_action(
        request, pk,
        lambda ticket: reject_ticket(ticket, request.user, form.cleaned_data["reason"]),
        "درخواست لغو/رد شد.",
    )


def ticket_add_note(request, pk: int):
    form = TicketNoteForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "متن یادداشت را وارد کنید.")
        return redirect("tickets:detail", pk=pk)
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    if request.method == "POST":
        TicketEvent.objects.create(
            ticket=ticket,
            event_type=TicketEvent.EVENT_NOTE,
            actor=request.user,
            actor_label=str(request.user),
            note=form.cleaned_data["note"],
        )
        messages.success(request, "یادداشت ثبت شد.")
    return redirect("tickets:detail", pk=pk)


def ticket_add_part(request, pk: int):
    form = TicketPartForm(request.POST or None)
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    if request.method == "POST" and form.is_valid():
        part = form.save(commit=False)
        part.ticket = ticket
        part.save()
        TicketEvent.objects.create(
            ticket=ticket,
            event_type=TicketEvent.EVENT_NOTE,
            actor=request.user,
            actor_label=str(request.user),
            note=f"ثبت قطعه: {part}",
        )
        messages.success(request, "قطعه ثبت شد.")
    else:
        messages.error(request, "اطلاعات قطعه کامل نیست.")
    return redirect("tickets:detail", pk=pk)


def ticket_add_attachment(request, pk: int):
    form = TicketAttachmentForm(request.POST or None, request.FILES or None)
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    if request.method == "POST" and form.is_valid():
        attachment = form.save(commit=False)
        attachment.ticket = ticket
        attachment.uploaded_by = request.user
        attachment.save()
        TicketEvent.objects.create(
            ticket=ticket,
            event_type=TicketEvent.EVENT_ATTACHMENT,
            actor=request.user,
            actor_label=str(request.user),
            note=f"افزودن پیوست: {attachment.title or attachment.file.name}",
        )
        messages.success(request, "پیوست ثبت شد.")
    else:
        messages.error(request, "بارگذاری پیوست انجام نشد.")
    return redirect("tickets:detail", pk=pk)
