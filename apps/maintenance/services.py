"""منطق کاری بازدیدهای دوره‌ای."""
from __future__ import annotations

import datetime as dt

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.core.constants import (
    CHECK_HEALTHY,
    CHECK_NOT_SEEN,
    EVENT_VISIT_COMPLETED,
    EVENT_VISIT_MISSED,
    EVENT_VISIT_PLANNED,
    VISIT_CANCELED,
    VISIT_DONE,
    VISIT_IN_PROGRESS,
    VISIT_MISSED,
    VISIT_PLANNED,
)
from apps.core.models import Notification
from apps.core.utils import log_action
from apps.integrations.models import OutboxEvent

from .models import MaintenanceVisit, VisitAssetCheck


# ---------------------------------------------------------------------------
# دسترسی
# ---------------------------------------------------------------------------
def visible_visits(user):
    """بازدیدهای قابل مشاهده؛ دامنه مرکز/پیمانکار به‌صورت fail-closed اعمال می‌شود."""
    queryset = MaintenanceVisit.objects.select_related(
        "contract", "contract__contractor", "technician", "center"
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_superuser or user.role == User.ROLE_ADMIN_COUNTRY:
        return queryset
    if user.role == User.ROLE_ADMIN_PROVINCE:
        centers = user.get_scoped_centers()
        province_ids = centers.values("parent_unit__parent_id")
        return queryset.filter(
            Q(center__in=centers) | Q(contract__province_id__in=province_ids)
        ).distinct()
    if user.role == User.ROLE_ADMIN_COUNTY:
        return queryset.filter(center__in=user.get_scoped_centers())
    if user.has_role(User.ROLE_ADMIN_IT, User.ROLE_MANAGER):
        centers = user.get_scoped_centers()
        if not centers.exists():
            return queryset.none()
        return queryset.filter(center__in=centers)
    if user.has_role(User.ROLE_TECHNICIAN):
        if not user.contractor_id:
            return queryset.none()
        centers = user.get_scoped_centers()
        active_contracts = user.get_active_contractor_contracts()
        return queryset.filter(
            contractor_id=user.contractor_id,
            contract__in=active_contracts,
        ).filter(
            Q(center__in=centers) | Q(center__isnull=True, contract__province_id__in=active_contracts.values("province_id"))
        )
    return queryset.none()


def visible_checks(user, visit: MaintenanceVisit):
    if not visible_visits(user).filter(pk=visit.pk).exists():
        return visit.checks.none()
    checks = visit.checks.select_related("asset", "asset__category", "asset__location")
    if user.is_superuser or user.role == User.ROLE_ADMIN_COUNTRY:
        return checks
    return checks.filter(asset__center__in=user.get_scoped_centers())


def can_manage_visit(user, visit: MaintenanceVisit) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_admin_country:
        return True
    if not visible_visits(user).filter(pk=visit.pk).exists():
        return False
    if user.is_admin_province:
        centers = user.get_scoped_centers()
        if visit.center_id:
            return centers.filter(pk=visit.center_id).exists()
        return bool(
            visit.contract_id
            and visit.contract.province_id
            and centers.filter(parent_unit__parent_id=visit.contract.province_id).exists()
        )
    if user.has_role(User.ROLE_ADMIN_IT):
        return user.get_scoped_centers().filter(pk=visit.center_id).exists()
    if user.has_role(User.ROLE_TECHNICIAN):
        centers = user.get_scoped_centers()
        if not user.contractor_id or visit.contract.contractor_id != user.contractor_id:
            return False
        if visit.center_id:
            return centers.filter(pk=visit.center_id).exists()
        return bool(
            visit.contract.is_current
            and visit.contract.province_id
            and centers.filter(parent_unit__parent_id=visit.contract.province_id).exists()
        )
    return False


# ---------------------------------------------------------------------------
# برنامه‌ریزی بازدید
# ---------------------------------------------------------------------------
def _period_bounds(contract, index: int):
    """بازه شروع و پایان هر نوبت بازدید."""
    interval = contract.visit_interval_days or 90
    start = contract.start_date + dt.timedelta(days=index * interval)
    end = start + dt.timedelta(days=interval - 1)
    if end > contract.end_date:
        end = contract.end_date
    return start, end


@transaction.atomic
def generate_visits(contract, *, user=None, populate=True) -> dict:
    """ساخت نوبت‌های بازدید دوره‌ای یک قرارداد بر اساس دوره تعریف‌شده."""
    if not contract.visit_interval_days:
        raise ValidationError("دوره بازدید برای این قرارداد تعریف نشده است.")

    if not contract.province_id:
        raise ValidationError("استان قرارداد تعیین نشده است؛ ابتدا پرونده قرارداد را تکمیل کنید.")
    if not contract.province_id or contract.province.unit_type != "province":
        raise ValidationError("استان قرارداد معتبر نیست.")
    visit_center = None  # قرارداد به یک استان تعلق دارد و بازدید در سطح استان ثبت می‌شود.

    total = contract.planned_visit_count()
    created = 0
    existing = 0
    for index in range(total):
        scheduled_start, scheduled_end = _period_bounds(contract, index)
        if scheduled_start > contract.end_date:
            break
        visit, is_new = MaintenanceVisit.objects.get_or_create(
            contract=contract,
            sequence_number=index + 1,
            defaults={
                "scheduled_date": scheduled_start,
                "scheduled_end_date": scheduled_end,
                "center": visit_center,
                "period_label": f"بازدید دوره‌ای شماره {index + 1}",
                "created_by": user if getattr(user, "is_authenticated", False) else None,
            },
        )
        if is_new:
            created += 1
            OutboxEvent.emit(
                EVENT_VISIT_PLANNED,
                {
                    "visit_id": visit.pk,
                    "number": visit.number,
                    "contract": contract.number,
                    "sequence": visit.sequence_number,
                    "scheduled_date": scheduled_start.isoformat(),
                    "scheduled_end_date": scheduled_end.isoformat(),
                },
                aggregate_type="MaintenanceVisit",
                aggregate_id=visit.pk,
                actor=user,
            )
        else:
            existing += 1
        if populate:
            populate_checks(visit)
    if created:
        log_action(
            "create",
            contract,
            object_label=str(contract),
            note=f"برنامه‌ریزی {created} نوبت بازدید دوره‌ای",
            user=user,
        )
    return {"created": created, "existing": existing, "planned": total}


def populate_checks(visit: MaintenanceVisit, only_missing: bool = True) -> int:
    """ساخت برگه بازدید برای دارایی‌های قرارداد."""
    assets = Asset.objects.filter(
        contract=visit.contract,
        center__parent_unit__parent_id=visit.contract.province_id,
    ).exclude(status="retired")
    existing_ids = set()
    if only_missing:
        existing_ids = set(visit.checks.values_list("asset_id", flat=True))
    count = 0
    for asset in assets:
        if asset.pk in existing_ids:
            continue
        VisitAssetCheck.objects.get_or_create(visit=visit, asset=asset)
        count += 1
    return count


def mark_missed_visits(user=None) -> int:
    """نشان‌دارکردن بازدیدهای گذشته از مهلت."""
    today = timezone.localdate()
    queryset = MaintenanceVisit.objects.filter(
        status__in=[VISIT_PLANNED, VISIT_IN_PROGRESS],
        scheduled_end_date__lt=today,
    )
    count = 0
    for visit in queryset:
        previous = visit.status
        visit.status = VISIT_MISSED
        visit.save(update_fields=["status", "updated_at"])
        count += 1
        OutboxEvent.emit(
            EVENT_VISIT_MISSED,
            {
                "visit_id": visit.pk,
                "number": visit.number,
                "contract": visit.contract.number,
                "scheduled_date": visit.scheduled_date.isoformat(),
                "deadline": (visit.scheduled_end_date or visit.scheduled_date).isoformat(),
                "days_late": (today - (visit.scheduled_end_date or visit.scheduled_date)).days,
            },
            aggregate_type="MaintenanceVisit",
            aggregate_id=visit.pk,
            actor=user,
        )
        Notification.push_many(
            list(User.objects.filter(role=User.ROLE_ADMIN_IT, is_active=True)),
            f"بازدید {visit.number} انجام نشد",
            f"مهلت بازدید دوره‌ای قرارداد {visit.contract.number} به پایان رسید.",
            visit.get_absolute_url(),
            level="danger",
        )
    if count:
        log_action("status_change", None, model_name="MaintenanceVisit",
                   object_label="بازدیدهای انجام‌نشده", note=f"{count} بازدید خارج از مهلت", user=user)
    return count


# ---------------------------------------------------------------------------
# گردش کار بازدید
# ---------------------------------------------------------------------------
@transaction.atomic
def start_visit(visit: MaintenanceVisit, user):
    if not can_manage_visit(user, visit):
        raise PermissionDenied("اجازه شروع این بازدید را ندارید.")
    if visit.status == VISIT_DONE:
        raise ValidationError("این بازدید پایان یافته است.")
    populate_checks(visit)
    visit.status = VISIT_IN_PROGRESS
    visit.started_at = visit.started_at or timezone.now()
    if not visit.technician_id:
        visit.technician = user
    visit.save(update_fields=["status", "started_at", "technician", "updated_at"])
    log_action("status_change", visit, note="شروع بازدید دوره‌ای", user=user)
    return visit


@transaction.atomic
def complete_visit(visit: MaintenanceVisit, user, *, report_text="", recommendation="", force=False):
    if not can_manage_visit(user, visit):
        raise PermissionDenied("اجازه پایان این بازدید را ندارید.")
    if visit.status == VISIT_DONE:
        raise ValidationError("این بازدید پیش‌تر پایان یافته است.")

    pending = visit.checks.filter(checked=False).count()
    if pending and not force:
        raise ValidationError(
            f"{pending} برگه بازدید تکمیل نشده است. برای پایان اجباری گزینه «پایان با ناقص» را انتخاب کنید."
        )

    if report_text:
        visit.report_text = report_text
    if recommendation:
        visit.recommendation = recommendation
    visit.complete(user)

    OutboxEvent.emit(
        EVENT_VISIT_COMPLETED,
        {
            "visit_id": visit.pk,
            "number": visit.number,
            "contract": visit.contract.number,
            "contractor": visit.contract.contractor.name,
            "scheduled_date": visit.scheduled_date.isoformat(),
            "finished_at": visit.finished_at.isoformat(),
            "checks_total": visit.checks_total,
            "checks_done": visit.checks_done,
            "faulty_count": visit.faulty_count,
            "duration_minutes": visit.duration_minutes,
            "report_text": visit.report_text,
        },
        aggregate_type="MaintenanceVisit",
        aggregate_id=visit.pk,
        actor=user,
    )
    Notification.push_many(
        list(User.objects.filter(role=User.ROLE_ADMIN_IT, is_active=True)),
        f"پایان بازدید {visit.number}",
        f"بازدید دوره‌ای قرارداد {visit.contract.number} تکمیل شد و در انتظار تایید است.",
        visit.get_absolute_url(),
        level="info",
    )
    log_action("status_change", visit, note="پایان بازدید دوره‌ای", user=user)
    return visit


@transaction.atomic
def confirm_visit(visit: MaintenanceVisit, user, note: str = ""):
    """تایید بازدید توسط کارشناس فناوری اطلاعات مرکز."""
    if not user.has_role(User.ROLE_ADMIN_IT) or not can_manage_visit(user, visit):
        raise PermissionDenied("تایید بازدید فقط توسط کارشناس فناوری اطلاعات مجاز همان دامنه انجام می‌شود.")
    visit.it_confirmed_by = user
    visit.it_confirmed_at = timezone.now()
    visit.it_note = note[:300]
    visit.save(update_fields=["it_confirmed_by", "it_confirmed_at", "it_note", "updated_at"])
    log_action("approve", visit, note="تایید بازدید دوره‌ای", user=user)
    return visit


@transaction.atomic
def save_check(check: VisitAssetCheck, user, *, condition=None, actions_taken=None,
               parts_replaced=None, notes=None, next_due_date=None, photo=None,
               hardware_snapshot=None, checked=True):
    """ثبت نتیجه بازدید یک تجهیز."""
    if not can_manage_visit(user, check.visit):
        raise PermissionDenied("اجازه ثبت نتیجه این برگه بازدید را ندارید.")
    if not user.get_scoped_centers().filter(pk=check.asset.center_id).exists():
        raise PermissionDenied("این تجهیز خارج از دامنه مراکز مجاز شماست.")
    if condition:
        check.condition = condition
    if actions_taken is not None:
        check.actions_taken = actions_taken
    if parts_replaced is not None:
        check.parts_replaced = parts_replaced
    if notes is not None:
        check.notes = notes
    if next_due_date is not None:
        check.next_due_date = next_due_date
    if photo is not None:
        check.photo = photo
    if hardware_snapshot is not None:
        check.hardware_snapshot = hardware_snapshot
    if checked:
        check.checked = True
        check.checked_at = timezone.now()
        check.checked_by = user
    check.save()
    return check


def visit_statistics(visit: MaintenanceVisit, checks=None) -> dict:
    """آمار بازدید؛ در صورت ارسال queryset فقط همان اقلام مجاز محاسبه می‌شوند."""
    checks = checks if checks is not None else visit.checks.all()
    total = checks.count()
    done = checks.filter(checked=True).count()
    summary = {}
    for check in checks:
        label = check.get_condition_display()
        summary[label] = summary.get(label, 0) + 1
    return {
        "total": total,
        "done": done,
        "pending": total - done,
        "percent": (done * 100 / total) if total else 0,
        "conditions": summary,
        "faulty": checks.exclude(condition=CHECK_HEALTHY).filter(checked=True).count(),
        "not_seen": checks.filter(condition=CHECK_NOT_SEEN).count(),
    }


def open_visits_for_user(user):
    """کارتابل بازدیدهای باز برای کارشناس پیمانکار."""
    queryset = visible_visits(user).exclude(status__in=[VISIT_DONE, VISIT_CANCELED])
    return queryset.order_by("scheduled_date")
