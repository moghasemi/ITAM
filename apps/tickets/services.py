"""منطق کاری درخواست خرابی: گردش کار، محاسبه SLA، اعلان و ارسال رخداد."""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.core.constants import (
    ASSET_ACTIVE,
    ASSET_IN_REPAIR,
    EVENT_TICKET_ACKNOWLEDGED,
    EVENT_TICKET_ARRIVED,
    EVENT_TICKET_CLOSED,
    EVENT_TICKET_REPORTED,
    EVENT_TICKET_RESOLVED,
    EVENT_TICKET_SLA_BREACHED,
    EVENT_TICKET_STATUS_CHANGED,
    PAUSE_PARTS,
    STATUS_ACKNOWLEDGED,
    STATUS_CANCELED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_REJECTED,
    STATUS_REPORTED,
    STATUS_RESOLVED,
    STATUS_USER_CONFIRMED,
    STATUS_WAITING_PARTS,
    TICKET_CLOSED_STATUSES,
    TICKET_OPEN_STATUSES,
    TICKET_STATUS_LABELS,
)
from apps.core.models import Notification, SystemSetting
from apps.core.sla import get_calendar
from apps.core.utils import log_action
from apps.integrations.models import OutboxEvent

from .models import Ticket, TicketEvent, TicketPause


# ---------------------------------------------------------------------------
# دسترسی
# ---------------------------------------------------------------------------
def visible_tickets(user, center=None):
    """درخواست‌های قابل مشاهده برای هر نقش و مرکز."""
    queryset = Ticket.objects.select_related(
        "asset", "asset__category", "asset__location", "contract", "assigned_contractor",
        "assigned_technician", "reported_by", "center", "asset__center",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if getattr(user, "is_admin_province", False) or user.is_superuser:
        if center:
            queryset = queryset.filter(Q(center=center) | Q(asset__center=center))
        return queryset

    if user.has_role(User.ROLE_ADMIN_IT, User.ROLE_MANAGER):
        if user.center_id:
            return queryset.filter(Q(center_id=user.center_id) | Q(asset__center_id=user.center_id))
        elif center:
            return queryset.filter(Q(center=center) | Q(asset__center=center))
        return queryset

    if user.has_role(User.ROLE_TECHNICIAN):
        if not user.contractor_id:
            return queryset.none()
        qs = queryset.filter(
            Q(assigned_contractor_id=user.contractor_id) | Q(assigned_technician=user) |
            Q(contract__contractor_id=user.contractor_id)
        )
        if center:
            qs = qs.filter(Q(center=center) | Q(asset__center=center))
        return qs.distinct()

    condition = Q(reported_by=user)
    if user.department_id:
        condition |= Q(asset__department_id=user.department_id)
    if user.center_id:
        condition &= (Q(center_id=user.center_id) | Q(asset__center_id=user.center_id) | Q(center__isnull=True))
    return queryset.filter(condition).distinct()


def can_manage_ticket(user, ticket: Ticket) -> bool:
    """کارشناس IT یا کارشناس پیمانکار مسئول این درخواست."""
    if user.has_role(User.ROLE_ADMIN_IT):
        return True
    if user.has_role(User.ROLE_TECHNICIAN):
        if ticket.assigned_technician_id == user.pk:
            return True
        return bool(
            user.contractor_id
            and ticket.assigned_contractor_id
            and user.contractor_id == ticket.assigned_contractor_id
        )
    return False


def can_confirm_as_user(user, ticket: Ticket) -> bool:
    if user.has_role(User.ROLE_ADMIN_IT):
        return True
    if ticket.reported_by_id and ticket.reported_by_id == user.pk:
        return True
    if ticket.asset.custodian_id and ticket.asset.custodian_id == user.pk:
        return True
    if user.department_id and ticket.asset.department_id == user.department_id:
        return True
    return False


def can_confirm_as_it(user, ticket: Ticket) -> bool:
    """تایید نهایی فقط در دامنه سازمانی کاربر مجاز است."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_admin_province:
        return True
    ticket_center_id = ticket.center_id or ticket.asset.center_id
    return bool(
        user.has_role(User.ROLE_ADMIN_IT)
        and user.center_id
        and ticket_center_id == user.center_id
    )


# ---------------------------------------------------------------------------
# سیاست SLA
# ---------------------------------------------------------------------------
def sla_policy_for(ticket: Ticket):
    """سیاست SLA متناظر با قرارداد و اولویت درخواست."""
    if ticket.contract_id:
        policy = ticket.contract.sla_for(ticket.priority)
        if policy:
            return policy
    return None


def apply_sla_deadlines(ticket: Ticket):
    """محاسبه مهلت حضور و مهلت رفع خرابی بر پایه ساعت کاری."""
    setting = SystemSetting.load()
    calendar = get_calendar()
    policy = sla_policy_for(ticket)

    response_minutes = policy.response_minutes if policy else setting.default_response_minutes
    resolve_minutes = policy.resolve_minutes if policy else setting.default_resolve_minutes

    start = ticket.reported_at or timezone.now()
    ticket.response_due_at = calendar.add_working_minutes(start, response_minutes)
    ticket.resolve_due_at = calendar.add_working_minutes(
        ticket.arrived_at or start, resolve_minutes
    )
    return ticket


def recalculate_sla(ticket: Ticket, save: bool = True) -> dict:
    """محاسبه شاخص‌های SLA و ذخیره آن‌ها روی درخواست."""
    setting = SystemSetting.load()
    calendar = get_calendar()
    policy = sla_policy_for(ticket)

    pauses = ticket.pause_intervals()
    paused_minutes = 0.0
    for pause in pauses:
        end = pause["end"] or timezone.now()
        if end > pause["start"]:
            paused_minutes += calendar.working_minutes_between(pause["start"], end)

    response_minutes = None
    if ticket.arrived_at and ticket.reported_at:
        response_minutes = calendar.subtract_pauses(
            ticket.reported_at, ticket.arrived_at, pauses
        )

    resolve_minutes = None
    if ticket.resolved_declared_at:
        base = ticket.arrived_at or ticket.reported_at
        if base:
            resolve_minutes = calendar.subtract_pauses(base, ticket.resolved_declared_at, pauses)

    total_minutes = None
    end_point = (
        ticket.it_confirmed_at
        or ticket.closed_at
        or ticket.resolved_declared_at
        or ticket.user_confirmed_at
    )
    if end_point and ticket.reported_at:
        total_minutes = calendar.subtract_pauses(ticket.reported_at, end_point, pauses)

    response_target = policy.response_minutes if policy else setting.default_response_minutes
    resolve_target = policy.resolve_minutes if policy else setting.default_resolve_minutes

    ticket.paused_minutes = int(round(paused_minutes))
    ticket.response_minutes_used = int(round(response_minutes)) if response_minutes is not None else None
    ticket.resolve_minutes_used = int(round(resolve_minutes)) if resolve_minutes is not None else None
    ticket.total_minutes_used = int(round(total_minutes)) if total_minutes is not None else None
    ticket.response_met = (response_minutes <= response_target) if response_minutes is not None else None
    ticket.resolve_met = (resolve_minutes <= resolve_target) if resolve_minutes is not None else None

    if save and ticket.pk:
        ticket.save(
            update_fields=[
                "paused_minutes",
                "response_minutes_used",
                "resolve_minutes_used",
                "total_minutes_used",
                "response_met",
                "resolve_met",
            ]
        )
    return {
        "response_minutes": response_minutes,
        "resolve_minutes": resolve_minutes,
        "total_minutes": total_minutes,
        "paused_minutes": paused_minutes,
        "response_target": response_target,
        "resolve_target": resolve_target,
        "response_met": ticket.response_met,
        "resolve_met": ticket.resolve_met,
    }


def sla_state(ticket: Ticket) -> dict:
    """وضعیت جاری SLA برای نمایش."""
    calendar = get_calendar()
    now = timezone.now()
    setting = SystemSetting.load()

    response_state = "unknown"
    if ticket.response_met is True:
        response_state = "met"
    elif ticket.response_met is False:
        response_state = "breached"
    elif ticket.arrived_at is None:
        due = ticket.response_due_at
        if due is None and ticket.reported_at:
            due = calendar.add_working_minutes(ticket.reported_at, setting.default_response_minutes)
        if due is not None:
            response_state = "breached" if now > due else "pending"

    resolve_state = "unknown"
    if ticket.resolve_met is True:
        resolve_state = "met"
    elif ticket.resolve_met is False:
        resolve_state = "breached"
    elif ticket.resolved_declared_at is None and ticket.is_open:
        due = ticket.resolve_due_at
        if due is not None:
            resolve_state = "breached" if now > due else "pending"

    return {
        "response_state": response_state,
        "resolve_state": resolve_state,
        "response_due_at": ticket.response_due_at,
        "resolve_due_at": ticket.resolve_due_at,
        "is_paused": ticket.is_sla_paused,
    }


def detect_sla_breach(ticket: Ticket, user=None):
    """ثبت رخداد نقض SLA (یک‌بار برای هر درخواست)."""
    state = sla_state(ticket)
    breached = [key for key in ("response_state", "resolve_state") if state[key] == "breached"]
    if not breached:
        return
    flag = f"sla_breach_logged:{','.join(sorted(breached))}"
    if ticket.events.filter(meta__flag=flag).exists():
        return

    labels = {"response_state": "زمان پاسخ (حضور در محل)", "resolve_state": "زمان رفع خرابی"}
    log_event(
        ticket,
        TicketEvent.EVENT_STATUS,
        actor=user,
        note="نقض تعهد SLA در " + "، ".join(labels[key] for key in breached),
        meta={
            "flag": flag,
            "breached": breached,
            "response_state": state["response_state"],
            "resolve_state": state["resolve_state"],
        },
    )
    OutboxEvent.emit(
        EVENT_TICKET_SLA_BREACHED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "asset_tag": ticket.asset.asset_tag,
            "breached": breached,
            "priority": ticket.priority,
            "response_met": ticket.response_met,
            "resolve_met": ticket.resolve_met,
            "response_due_at": ticket.response_due_at.isoformat() if ticket.response_due_at else None,
            "resolve_due_at": ticket.resolve_due_at.isoformat() if ticket.resolve_due_at else None,
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )


# ---------------------------------------------------------------------------
# رخدادنگاری
# ---------------------------------------------------------------------------
def log_event(
    ticket: Ticket,
    event_type: str,
    *,
    actor=None,
    note: str = "",
    from_status: str = "",
    to_status: str = "",
    meta: dict | None = None,
) -> TicketEvent:
    return TicketEvent.objects.create(
        ticket=ticket,
        event_type=event_type,
        from_status=from_status or "",
        to_status=to_status or "",
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_label=str(actor) if actor else "سامانه",
        note=note,
        meta=meta or {},
    )


def _technicians_of(contractor):
    if contractor is None:
        return User.objects.none()
    return User.objects.filter(
        role=User.ROLE_TECHNICIAN, contractor=contractor, is_active=True
    )


def _it_experts():
    return User.objects.filter(role=User.ROLE_ADMIN_IT, is_active=True)


def notify(users, title, message, url, level="info"):
    return Notification.push_many(list(users), title, message, url, level)


# ---------------------------------------------------------------------------
# گردش کار
# ---------------------------------------------------------------------------
def create_ticket(*, asset: Asset, title: str, description: str, priority: str, user,
                  reporter_name: str = "", reporter_phone: str = "", failure_type: str = "",
                  reported_at=None) -> Ticket:
    """ثبت درخواست خرابی توسط اداره (شروع ساعت SLA)."""
    ticket = Ticket(
        asset=asset,
        title=title,
        description=description,
        priority=priority,
        failure_type=failure_type,
        reported_by=user if getattr(user, "is_authenticated", False) else None,
        reporter_name=reporter_name or (user.display_name if user and user.is_authenticated else ""),
        reporter_phone=reporter_phone or (getattr(user, "phone", "") if user else ""),
        reported_at=reported_at or timezone.now(),
        status=STATUS_REPORTED,
    )
    ticket.save()

    log_event(
        ticket,
        TicketEvent.EVENT_CREATED,
        actor=user,
        note=f"اعلام خرابی: {title}",
        to_status=STATUS_REPORTED,
    )
    OutboxEvent.emit(
        EVENT_TICKET_REPORTED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "asset_id": asset.pk,
            "asset_tag": asset.asset_tag,
            "priority": priority,
            "title": title,
            "description": description,
            "reported_at": ticket.reported_at.isoformat(),
            "response_due_at": ticket.response_due_at.isoformat() if ticket.response_due_at else None,
            "resolve_due_at": ticket.resolve_due_at.isoformat() if ticket.resolve_due_at else None,
            "contract": str(ticket.contract) if ticket.contract else "",
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    notify(
        _technicians_of(ticket.assigned_contractor) | _it_experts(),
        f"اعلام خرابی {ticket.number}",
        f"{asset.asset_tag} — {title}",
        ticket.get_absolute_url(),
        level="warning" if priority in ("critical", "high") else "info",
    )
    log_action("create", ticket, note="ثبت درخواست خرابی", user=user)
    return ticket


def _require_open(ticket: Ticket, action: str):
    if ticket.status in TICKET_CLOSED_STATUSES:
        raise ValidationError(f"این درخواست بسته شده است و «{action}» امکان‌پذیر نیست.")


@transaction.atomic
def acknowledge(ticket: Ticket, user, note: str = "") -> Ticket:
    """پذیرش درخواست توسط پیمانکار."""
    _require_open(ticket, "پذیرش")
    if ticket.status not in (STATUS_REPORTED,):
        raise ValidationError("پذیرش فقط برای درخواست تازه‌ثبت‌شده امکان‌پذیر است.")
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("اجازه پذیرش این درخواست را ندارید.")

    previous = ticket.status
    ticket.status = STATUS_ACKNOWLEDGED
    ticket.acknowledged_at = timezone.now()
    if not ticket.assigned_technician_id and user.has_role(User.ROLE_TECHNICIAN):
        ticket.assigned_technician = user
    ticket.save(update_fields=["status", "acknowledged_at", "assigned_technician", "updated_at"])

    log_event(
        ticket, TicketEvent.EVENT_ACKNOWLEDGED, actor=user, note=note,
        from_status=previous, to_status=ticket.status,
    )
    recalculate_sla(ticket)
    OutboxEvent.emit(
        EVENT_TICKET_ACKNOWLEDGED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "acknowledged_at": ticket.acknowledged_at.isoformat(),
            "technician": str(user),
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    notify(
        [ticket.reported_by] if ticket.reported_by_id else [],
        f"درخواست {ticket.number} پذیرفته شد",
        f"پیمانکار درخواست خرابی {ticket.asset.asset_tag} را پذیرفت.",
        ticket.get_absolute_url(),
        level="info",
    )
    log_action("status_change", ticket, note="پذیرش پیمانکار", user=user)
    return ticket


@transaction.atomic
def mark_arrived(ticket: Ticket, user, note: str = "", scheduled_at=None) -> Ticket:
    """ثبت حضور کارشناس در محل (پایان شمارش زمان پاسخ)."""
    _require_open(ticket, "ثبت حضور")
    if ticket.arrived_at:
        raise ValidationError("زمان حضور پیش‌تر ثبت شده است.")
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("اجازه ثبت حضور برای این درخواست را ندارید.")

    previous = ticket.status
    ticket.arrived_at = timezone.now()
    if scheduled_at:
        ticket.scheduled_at = scheduled_at
    if ticket.status == STATUS_REPORTED:
        ticket.acknowledged_at = ticket.acknowledged_at or ticket.arrived_at
        ticket.status = STATUS_ACKNOWLEDGED
    ticket.save(
        update_fields=["arrived_at", "scheduled_at", "acknowledged_at", "status", "updated_at"]
    )

    log_event(
        ticket, TicketEvent.EVENT_ARRIVED, actor=user,
        note=note or "حضور کارشناس در محل ثبت شد.",
        from_status=previous, to_status=ticket.status,
    )
    metrics = recalculate_sla(ticket)
    OutboxEvent.emit(
        EVENT_TICKET_ARRIVED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "arrived_at": ticket.arrived_at.isoformat(),
            "response_minutes_used": metrics["response_minutes"],
            "response_target": metrics["response_target"],
            "response_met": metrics["response_met"],
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    detect_sla_breach(ticket, user)
    log_action("status_change", ticket, note="ثبت حضور در محل", user=user)
    return ticket


@transaction.atomic
def start_work(ticket: Ticket, user, note: str = "") -> Ticket:
    _require_open(ticket, "شروع تعمیر")
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("اجازه ثبت شروع تعمیر را ندارید.")
    if ticket.status in (STATUS_RESOLVED, STATUS_USER_CONFIRMED):
        raise ValidationError("پس از اعلام رفع، امکان شروع مجدد وجود ندارد مگر با برگشت وضعیت.")

    previous = ticket.status
    ticket.status = STATUS_IN_PROGRESS
    ticket.work_started_at = ticket.work_started_at or timezone.now()
    if not ticket.assigned_technician_id and user.has_role(User.ROLE_TECHNICIAN):
        ticket.assigned_technician = user
    ticket.save(update_fields=["status", "work_started_at", "assigned_technician", "updated_at"])

    log_event(
        ticket, TicketEvent.EVENT_WORK_STARTED, actor=user, note=note,
        from_status=previous, to_status=ticket.status,
    )
    assign_asset_state(ticket, ASSET_IN_REPAIR)
    log_action("status_change", ticket, note="شروع تعمیر", user=user)
    return ticket


@transaction.atomic
def pause_clock(ticket: Ticket, user, reason: str = PAUSE_PARTS, note: str = "") -> Ticket:
    """توقف ساعت SLA (مثلاً انتظار قطعه)."""
    _require_open(ticket, "توقف ساعت")
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("اجازه توقف ساعت SLA را ندارید.")
    if ticket.is_sla_paused:
        raise ValidationError("ساعت SLA از قبل متوقف است.")

    previous = ticket.status
    TicketPause.objects.create(
        ticket=ticket, reason=reason, started_at=timezone.now(), note=note, created_by=user
    )
    if reason == PAUSE_PARTS:
        ticket.status = STATUS_WAITING_PARTS
    ticket.save(update_fields=["status", "updated_at"])

    log_event(
        ticket, TicketEvent.EVENT_PAUSED, actor=user,
        note=note or f"توقف ساعت: {dict(TicketPause._meta.get_field('reason').choices).get(reason, reason)}",
        from_status=previous, to_status=ticket.status,
        meta={"reason": reason},
    )
    recalculate_sla(ticket)
    log_action("status_change", ticket, note="توقف ساعت SLA", user=user)
    return ticket


@transaction.atomic
def resume_clock(ticket: Ticket, user, note: str = "") -> Ticket:
    _require_open(ticket, "ادامه شمارش")
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("اجازه ادامه شمارش ساعت SLA را ندارید.")

    pause = ticket.open_pause()
    if pause is None:
        raise ValidationError("ساعت SLA متوقف نیست.")
    pause.ended_at = timezone.now()
    pause.save(update_fields=["ended_at", "updated_at"])

    previous = ticket.status
    if ticket.status == STATUS_WAITING_PARTS:
        ticket.status = STATUS_IN_PROGRESS
    ticket.save(update_fields=["status", "updated_at"])

    log_event(
        ticket, TicketEvent.EVENT_RESUMED, actor=user, note=note,
        from_status=previous, to_status=ticket.status,
    )
    recalculate_sla(ticket)
    log_action("status_change", ticket, note="ادامه شمارش ساعت SLA", user=user)
    return ticket


@transaction.atomic
def declare_resolved(ticket: Ticket, user, *, root_cause="", action_taken="", parts_text="",
                     note: str = "") -> Ticket:
    """اعلام رفع خرابی توسط پیمانکار (نیازمند تایید کاربر و کارشناس IT)."""
    _require_open(ticket, "اعلام رفع خرابی")
    if ticket.status in (STATUS_RESOLVED, STATUS_USER_CONFIRMED):
        raise ValidationError("رفع خرابی پیش‌تر اعلام شده است.")
    if not can_manage_ticket(user, ticket):
        raise PermissionDenied("اجازه اعلام رفع خرابی را ندارید.")

    previous = ticket.status
    ticket.status = STATUS_RESOLVED
    ticket.resolved_declared_at = timezone.now()
    if root_cause:
        ticket.root_cause = root_cause
    if action_taken:
        ticket.action_taken = action_taken
    if parts_text:
        ticket.parts_text = parts_text
    ticket.save(
        update_fields=[
            "status", "resolved_declared_at", "root_cause", "action_taken", "parts_text", "updated_at",
        ]
    )

    log_event(
        ticket, TicketEvent.EVENT_RESOLVED, actor=user, note=note or "اعلام رفع خرابی توسط پیمانکار",
        from_status=previous, to_status=ticket.status,
    )
    metrics = recalculate_sla(ticket)
    OutboxEvent.emit(
        EVENT_TICKET_RESOLVED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "resolved_declared_at": ticket.resolved_declared_at.isoformat(),
            "root_cause": ticket.root_cause,
            "action_taken": ticket.action_taken,
            "parts_text": ticket.parts_text,
            "resolve_minutes_used": metrics["resolve_minutes"],
            "resolve_target": metrics["resolve_target"],
            "resolve_met": metrics["resolve_met"],
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    detect_sla_breach(ticket, user)

    setting = SystemSetting.load()
    if setting.require_user_confirmation:
        notify(
            [ticket.reported_by] if ticket.reported_by_id else [],
            f"تایید رفع خرابی {ticket.number}",
            f"پیمانکار رفع خرابی {ticket.asset.asset_tag} را اعلام کرد؛ لطفاً تایید کنید.",
            ticket.get_absolute_url(),
            level="warning",
        )
    notify(
        _it_experts(),
        f"اعلام رفع خرابی {ticket.number}",
        f"{ticket.asset.asset_tag} — در انتظار تایید نهایی",
        ticket.get_absolute_url(),
        level="info",
    )
    log_action("status_change", ticket, note="اعلام رفع خرابی", user=user)
    return ticket


@transaction.atomic
def confirm_by_user(ticket: Ticket, user, note: str = "", satisfaction=None) -> Ticket:
    """تایید رفع خرابی توسط کاربر."""
    if ticket.status != STATUS_RESOLVED:
        raise ValidationError("درخواست در وضعیت «اعلام رفع خرابی» نیست.")
    if not can_confirm_as_user(user, ticket):
        raise PermissionDenied("اجازه تایید این درخواست را ندارید.")

    previous = ticket.status
    ticket.user_confirmed_at = timezone.now()
    ticket.user_confirm_note = note[:300]
    if satisfaction:
        try:
            ticket.satisfaction = max(1, min(5, int(satisfaction)))
        except (TypeError, ValueError):
            pass

    setting = SystemSetting.load()
    if setting.require_it_confirmation:
        ticket.status = STATUS_USER_CONFIRMED
    else:
        ticket.status = STATUS_CLOSED
        ticket.closed_at = ticket.user_confirmed_at
    ticket.save(
        update_fields=[
            "status", "user_confirmed_at", "user_confirm_note", "satisfaction", "closed_at", "updated_at",
        ]
    )

    log_event(
        ticket, TicketEvent.EVENT_USER_CONFIRMED, actor=user, note=note,
        from_status=previous, to_status=ticket.status,
    )
    recalculate_sla(ticket)
    OutboxEvent.emit(
        EVENT_TICKET_STATUS_CHANGED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "to_status": ticket.status,
            "user_confirmed_at": ticket.user_confirmed_at.isoformat(),
            "satisfaction": ticket.satisfaction,
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    notify(
        _it_experts(),
        f"تایید کاربر برای {ticket.number}",
        "در انتظار تایید نهایی کارشناس فناوری اطلاعات مرکز",
        ticket.get_absolute_url(),
        level="info",
    )
    if ticket.status == STATUS_CLOSED:
        _finalize_close(ticket, user, note)
    log_action("approve", ticket, note="تایید کاربر", user=user)
    return ticket


@transaction.atomic
def reject_by_user(ticket: Ticket, user, reason: str = "") -> Ticket:
    """کاربر رفع خرابی را نپذیرفت؛ درخواست به جریان بازمی‌گردد."""
    if ticket.status != STATUS_RESOLVED:
        raise ValidationError("درخواست در وضعیت «اعلام رفع خرابی» نیست.")
    if not can_confirm_as_user(user, ticket):
        raise PermissionDenied("اجازه این اقدام را ندارید.")

    previous = ticket.status
    ticket.status = STATUS_IN_PROGRESS
    ticket.resolved_declared_at = None
    ticket.save(update_fields=["status", "resolved_declared_at", "updated_at"])

    log_event(
        ticket, TicketEvent.EVENT_REJECTED, actor=user,
        note=reason or "کاربر رفع خرابی را نپذیرفت.",
        from_status=previous, to_status=ticket.status,
    )
    notify(
        _technicians_of(ticket.assigned_contractor) | _it_experts(),
        f"عدم تایید رفع خرابی {ticket.number}",
        reason or "کاربر اعلام کرد مشکل برطرف نشده است.",
        ticket.get_absolute_url(),
        level="danger",
    )
    log_action("reject", ticket, note="عدم تایید کاربر", user=user)
    return ticket


@transaction.atomic
def confirm_by_it(ticket: Ticket, user, note: str = "") -> Ticket:
    """تایید نهایی کارشناس فناوری اطلاعات مرکز و بستن درخواست."""
    if ticket.status not in (STATUS_RESOLVED, STATUS_USER_CONFIRMED):
        raise ValidationError("درخواست آماده تایید نهایی نیست.")
    if not can_confirm_as_it(user, ticket):
        raise PermissionDenied("تایید نهایی فقط توسط کارشناس فناوری اطلاعات مرکز انجام می‌شود.")

    previous = ticket.status
    ticket.it_confirmed_at = timezone.now()
    ticket.it_confirm_note = note[:300]
    if not ticket.user_confirmed_at:
        ticket.user_confirmed_at = ticket.it_confirmed_at
        ticket.user_confirm_note = "تایید ضمنی در جریان تایید کارشناس IT"
    ticket.status = STATUS_CLOSED
    ticket.closed_at = ticket.it_confirmed_at
    ticket.save(
        update_fields=[
            "it_confirmed_at", "it_confirm_note", "status", "closed_at",
            "user_confirmed_at", "user_confirm_note", "updated_at",
        ]
    )

    log_event(
        ticket, TicketEvent.EVENT_IT_CONFIRMED, actor=user, note=note,
        from_status=previous, to_status=ticket.status,
    )
    metrics = recalculate_sla(ticket)
    OutboxEvent.emit(
        EVENT_TICKET_CLOSED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "asset_tag": ticket.asset.asset_tag,
            "closed_at": ticket.closed_at.isoformat(),
            "response_minutes_used": ticket.response_minutes_used,
            "resolve_minutes_used": ticket.resolve_minutes_used,
            "total_minutes_used": ticket.total_minutes_used,
            "paused_minutes": ticket.paused_minutes,
            "response_met": ticket.response_met,
            "resolve_met": ticket.resolve_met,
            "sla_targets": {
                "response": metrics["response_target"],
                "resolve": metrics["resolve_target"],
            },
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    _finalize_close(ticket, user, note)
    log_action("approve", ticket, note="تایید نهایی کارشناس IT", user=user)
    return ticket


def _finalize_close(ticket: Ticket, user, note: str = ""):
    """اقدام‌های پس از بسته شدن درخواست."""
    if ticket.asset.status == ASSET_IN_REPAIR:
        ticket.asset.status = ASSET_ACTIVE
        ticket.asset.save(update_fields=["status", "updated_at"])
    notify(
        [ticket.reported_by] if ticket.reported_by_id else [],
        f"درخواست {ticket.number} بسته شد",
        note or "خرابی به تایید رسید و درخواست بسته شد.",
        ticket.get_absolute_url(),
        level="success",
    )
    notify(
        _technicians_of(ticket.assigned_contractor),
        f"بسته شدن درخواست {ticket.number}",
        "درخواست با تایید نهایی بسته شد.",
        ticket.get_absolute_url(),
        level="success",
    )


@transaction.atomic
def reject_ticket(ticket: Ticket, user, reason: str = "") -> Ticket:
    """رد یا لغو درخواست."""
    if ticket.status in TICKET_CLOSED_STATUSES:
        raise ValidationError("این درخواست قبلاً بسته شده است.")
    if not (can_confirm_as_it(user, ticket) or can_manage_ticket(user, ticket)):
        raise PermissionDenied("اجازه لغو این درخواست را ندارید.")

    previous = ticket.status
    ticket.status = STATUS_CANCELED if user.has_role(User.ROLE_ADMIN_IT) else STATUS_REJECTED
    ticket.rejection_reason = reason[:300]
    ticket.closed_at = timezone.now()
    ticket.save(update_fields=["status", "rejection_reason", "closed_at", "updated_at"])

    log_event(
        ticket, TicketEvent.EVENT_CANCELED, actor=user, note=reason,
        from_status=previous, to_status=ticket.status,
    )
    OutboxEvent.emit(
        EVENT_TICKET_STATUS_CHANGED,
        {
            "ticket_id": ticket.pk,
            "number": ticket.number,
            "to_status": ticket.status,
            "reason": reason,
        },
        aggregate_type="Ticket",
        aggregate_id=ticket.pk,
        actor=user,
    )
    log_action("status_change", ticket, note=f"لغو/رد: {reason}", user=user)
    return ticket


def assign_asset_state(ticket: Ticket, state: str):
    asset = ticket.asset
    if asset.status != state:
        asset.status = state
        asset.save(update_fields=["status", "updated_at"])


def available_actions(ticket: Ticket, user) -> list[dict]:
    """اقدام‌های مجاز برای نمایش دکمه‌ها."""
    actions: list[dict] = []
    if not getattr(user, "is_authenticated", False):
        return actions
    is_manager_side = can_manage_ticket(user, ticket)
    is_it = can_confirm_as_it(user, ticket)

    if ticket.status == STATUS_REPORTED and is_manager_side:
        actions.append({"key": "acknowledge", "label": "پذیرش درخواست", "css": "primary"})
    if ticket.status in (STATUS_REPORTED, STATUS_ACKNOWLEDGED) and is_manager_side and not ticket.arrived_at:
        actions.append({"key": "arrive", "label": "ثبت حضور در محل", "css": "primary"})
    if ticket.status in (STATUS_ACKNOWLEDGED, STATUS_WAITING_PARTS) and is_manager_side:
        actions.append({"key": "start", "label": "شروع تعمیر", "css": "secondary"})
        actions.append({"key": "pause", "label": "توقف ساعت (انتظار قطعه)", "css": "secondary"})
    if ticket.status == STATUS_IN_PROGRESS and is_manager_side:
        actions.append({"key": "pause", "label": "توقف ساعت SLA", "css": "secondary"})
    if ticket.is_sla_paused and is_manager_side:
        actions.append({"key": "resume", "label": "ادامه شمارش ساعت", "css": "secondary"})
    if ticket.status in (STATUS_ACKNOWLEDGED, STATUS_IN_PROGRESS, STATUS_WAITING_PARTS) and is_manager_side:
        actions.append({"key": "resolve", "label": "اعلام رفع خرابی", "css": "success"})
    if ticket.status == STATUS_RESOLVED:
        if can_confirm_as_user(user, ticket):
            actions.append({"key": "user_confirm", "label": "تایید رفع خرابی (کاربر)", "css": "success"})
            actions.append({"key": "user_reject", "label": "مشکل برطرف نشده", "css": "danger"})
        if is_it:
            actions.append({"key": "it_confirm", "label": "تایید نهایی کارشناس IT", "css": "success"})
    if ticket.status == STATUS_USER_CONFIRMED and is_it:
        actions.append({"key": "it_confirm", "label": "تایید نهایی و بستن", "css": "success"})
    if ticket.is_open and (is_it or is_manager_side):
        actions.append({"key": "cancel", "label": "لغو درخواست", "css": "danger"})
    return actions


def status_label(status: str) -> str:
    return TICKET_STATUS_LABELS.get(status, status)
