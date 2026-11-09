"""منطق کاری دارایی‌ها: کنترل دسترسی، مقایسه اقلام سخت‌افزاری و گردش کار اسنپ‌شات."""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.core.constants import (
    DIFF_ADDED,
    DIFF_CHANGED,
    DIFF_REMOVED,
    DIFF_REPLACED,
    DIFF_UNCHANGED,
    EVENT_ASSET_CREATED,
    EVENT_ASSET_UPDATED,
    EVENT_HARDWARE_BASELINE_LOCKED,
    EVENT_HARDWARE_DIFF_DETECTED,
    EVENT_HARDWARE_SNAPSHOT_CREATED,
    ITEM_REPLACED,
    SNAPSHOT_DRAFT,
    SNAPSHOT_LOCKED,
    SNAPSHOT_PENDING,
)
from apps.core.models import Notification, SystemSetting
from apps.core.utils import log_action
from apps.integrations.models import OutboxEvent
from apps.org.models import Contract

from .models import Asset, HardwareSnapshot, SnapshotItem


# ---------------------------------------------------------------------------
# کنترل دسترسی
# ---------------------------------------------------------------------------
def visible_assets(user, center=None):
    """دارایی‌های قابل مشاهده برای هر نقش و مرکز مبتنی بر دامنه سازمانی مجاز (Fail-Closed)."""
    queryset = Asset.objects.select_related(
        "category", "contract", "contract__contractor", "department", "location", "custodian", "center"
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    # مدیر ارشد کشوری یا Superuser
    if user.is_superuser or getattr(user, "is_admin_country", False):
        if center:
            return queryset.filter(center=center)
        return queryset

    # مدیر استانی: دسترسی به تمام مراکز استان خودش
    if getattr(user, "is_admin_province", False):
        scoped = user.get_scoped_centers()
        qs = queryset.filter(center__in=scoped)
        if center:
            qs = qs.filter(center=center)
        return qs

    # مدیر شهرستانی: دسترسی به تمام مراکز شهرستان خودش
    if getattr(user, "is_admin_county", False):
        scoped = user.get_scoped_centers()
        qs = queryset.filter(center__in=scoped)
        if center:
            qs = qs.filter(center=center)
        return qs

    # کارشناس IT مرکز یا مدیر مرکز: منحصراً مرکز خود کاربر
    if user.has_role(User.ROLE_ADMIN_IT, User.ROLE_MANAGER):
        if not user.center_id:
            return queryset.none()
        return queryset.filter(center_id=user.center_id)

    # تکنسین پیمانکار
    if user.has_role(User.ROLE_TECHNICIAN):
        if not user.contractor_id:
            return queryset.none()
        scoped_centers = user.get_scoped_centers()
        qs = queryset.filter(
            Q(contract__contractor_id=user.contractor_id) |
            Q(contract__is_provincial=True, contract__contractor_id=user.contractor_id)
        ).filter(center__in=scoped_centers)
        if center:
            qs = qs.filter(center=center)
        return qs

    # کاربر عادی / متقاضی: فقط دارایی‌هایی که خودش امانت‌دار است در مرکز خودش
    if not user.center_id:
        return queryset.none()
    return queryset.filter(custodian=user, center_id=user.center_id)


def can_edit_asset(user, asset: Asset) -> bool:
    """بررسی صلاحیت ویرایش دارایی (Fail-Closed)."""
    if not getattr(user, "is_authenticated", False) or not asset:
        return False
    if user.is_superuser or getattr(user, "is_admin_country", False):
        return True
    if getattr(user, "is_admin_province", False):
        scoped = user.get_scoped_centers()
        return bool(asset.center and scoped.filter(pk=asset.center_id).exists())
    if getattr(user, "is_admin_county", False):
        scoped = user.get_scoped_centers()
        return bool(asset.center and scoped.filter(pk=asset.center_id).exists())
    if user.has_role(User.ROLE_ADMIN_IT):
        if user.center_id and asset.center_id:
            return user.center_id == asset.center_id
        if not user.center_id and not asset.center_id:
            return True
        return False
    return False


def can_record_snapshot(user, asset: Asset) -> bool:
    """ثبت اسنپ‌شات سخت‌افزاری (Fail-Closed)."""
    if not getattr(user, "is_authenticated", False) or not asset:
        return False
    if user.is_superuser or getattr(user, "is_admin_country", False):
        return True
    if getattr(user, "is_admin_province", False):
        scoped = user.get_scoped_centers()
        return bool(asset.center and scoped.filter(pk=asset.center_id).exists())
    if getattr(user, "is_admin_county", False):
        scoped = user.get_scoped_centers()
        return bool(asset.center and scoped.filter(pk=asset.center_id).exists())
    if user.has_role(User.ROLE_ADMIN_IT):
        if user.center_id and asset.center_id:
            return user.center_id == asset.center_id
        if not user.center_id and not asset.center_id:
            return True
        return False
    if user.has_role(User.ROLE_TECHNICIAN):
        if not user.contractor_id or not asset.center_id or not asset.contract_id:
            return False

        # تکنسین فقط از طریق قرارداد فعالِ متعلق به پیمانکار خود مجاز است؛
        # قرارداد باید همان مرکز دارایی را صراحتاً پوشش دهد.
        scoped_centers = user.get_scoped_centers()
        if not scoped_centers.filter(pk=asset.center_id).exists():
            return False

        return (
            asset.contract.contractor_id == user.contractor_id
            and asset.contract.status == Contract.STATUS_ACTIVE
            and asset.contract.centers.filter(pk=asset.center_id).exists()
        )
    return False

# ---------------------------------------------------------------------------
# مقایسه اقلام (موتور کشف تغییر)
# ---------------------------------------------------------------------------
def _item_snapshot_data(item: SnapshotItem) -> dict:
    return {
        "id": item.pk,
        "component_type": item.component_type.name,
        "component_type_id": item.component_type_id,
        "brand": item.brand,
        "model": item.model_name,
        "serial": item.serial_number,
        "capacity": item.capacity,
        "quantity": item.quantity,
        "slot": item.slot,
        "condition": item.condition,
        "condition_label": item.get_condition_display(),
        "label": item.display_label,
    }


def _comparable_fields(data: dict) -> dict:
    return {
        "brand": (data.get("brand") or "").strip().lower(),
        "model": (data.get("model") or "").strip().lower(),
        "capacity": (data.get("capacity") or "").strip().lower(),
        "slot": (data.get("slot") or "").strip().lower(),
        "quantity": data.get("quantity") or 1,
    }


#: عنوان فارسی مشخصه‌ها برای گزارش تفاوت
_FIELD_LABELS = {
    "brand": "برند",
    "model": "مدل",
    "capacity": "ظرفیت",
    "slot": "اسلات",
    "quantity": "تعداد",
}


def compute_diff(previous_items, current_items) -> dict:
    """مقایسه دو فهرست قلم و تولید گزارش تفاوت.

    خروجی شامل ردیف‌های تفاوت، شمارش هر وضعیت و مشخص‌بودن «حذف/مفقود»
    (که هشدار اصلی کنترل سرقت است).
    """
    previous = [_item_snapshot_data(item) for item in previous_items]
    current = [_item_snapshot_data(item) for item in current_items]

    rows: list[dict] = []
    used_previous: set[int] = set()

    def find_match(entry: dict, strict: bool = True):
        for index, candidate in enumerate(previous):
            if index in used_previous:
                continue
            if candidate["component_type_id"] != entry["component_type_id"]:
                continue
            same_serial = bool(candidate["serial"]) and (
                candidate["serial"].strip().lower() == (entry["serial"] or "").strip().lower()
            )
            if strict:
                if same_serial:
                    return index, candidate
            else:
                # نامزد تعویض: همان گونه قطعه و همان اسلات
                if candidate["slot"].strip().lower() == entry["slot"].strip().lower():
                    return index, candidate
        return None, None

    # قلم‌های فعلی
    for entry in current:
        index, matched = find_match(entry, strict=True)
        if matched is None:
            # تلاش برای تشخیص «تعویض‌شده»
            index, matched = find_match(entry, strict=False)
            if matched is not None:
                used_previous.add(index)
                rows.append(
                    {
                        "state": DIFF_REPLACED,
                        "component_type": entry["component_type"],
                        "previous": matched,
                        "current": entry,
                        "changes": ["سریال/مشخصات قلم تعویض شده است"],
                    }
                )
                continue
            rows.append(
                {
                    "state": DIFF_ADDED,
                    "component_type": entry["component_type"],
                    "previous": None,
                    "current": entry,
                    "changes": ["قلم جدید به تجهیز اضافه شده است"],
                }
            )
            continue

        used_previous.add(index)
        old_values = _comparable_fields(matched)
        new_values = _comparable_fields(entry)
        changes = [
            f"{_FIELD_LABELS[field]} از «{matched.get(field) or '—'}» به «{entry.get(field) or '—'}»"
            for field in ("brand", "model", "capacity", "slot", "quantity")
            if old_values[field] != new_values[field]
        ]
        if matched.get("serial") != entry.get("serial"):
            changes.append(f"سریال از «{matched.get('serial') or '—'}» به «{entry.get('serial') or '—'}»")
        rows.append(
            {
                "state": DIFF_CHANGED if changes else DIFF_UNCHANGED,
                "component_type": entry["component_type"],
                "previous": matched,
                "current": entry,
                "changes": changes,
            }
        )

    # قلم‌های حذف/مفقود
    for index, candidate in enumerate(previous):
        if index in used_previous:
            continue
        rows.append(
            {
                "state": DIFF_REMOVED,
                "component_type": candidate["component_type"],
                "previous": candidate,
                "current": None,
                "changes": ["قلم در تجهیز یافت نشد (احتمال برداشت/مفقودی)"],
            }
        )

    counts = {
        DIFF_UNCHANGED: 0,
        DIFF_ADDED: 0,
        DIFF_REMOVED: 0,
        DIFF_REPLACED: 0,
        DIFF_CHANGED: 0,
    }
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1

    total_changes = counts[DIFF_ADDED] + counts[DIFF_REMOVED] + counts[DIFF_REPLACED] + counts[DIFF_CHANGED]
    return {
        "rows": rows,
        "counts": counts,
        "total_changes": total_changes,
        "removed": counts[DIFF_REMOVED],
        "added": counts[DIFF_ADDED],
        "replaced": counts[DIFF_REPLACED],
        "changed": counts[DIFF_CHANGED],
        "unchanged": counts[DIFF_UNCHANGED],
        "has_alarm": counts[DIFF_REMOVED] > 0 or counts[DIFF_REPLACED] > 0,
        "computed_at": timezone.now().isoformat(),
    }


def reference_snapshot(asset: Asset, exclude=None):
    """اسنپ‌شات مبنای مقایسه: آخرین نسخه قفل‌شده یا پایه."""
    queryset = asset.snapshots.filter(status=SNAPSHOT_LOCKED)
    if exclude is not None and exclude.pk:
        queryset = queryset.exclude(pk=exclude.pk)
    return queryset.order_by("-version").first()


# ---------------------------------------------------------------------------
# گردش کار اسنپ‌شات
# ---------------------------------------------------------------------------
@transaction.atomic
def create_snapshot(asset: Asset, user, *, note="", seal_number="", force_new=False) -> HardwareSnapshot:
    """ساخت اسنپ‌شات جدید برای دارایی."""
    if not can_record_snapshot(user, asset):
        raise PermissionDenied("اجازه ثبت اسنپ‌شات سخت‌افزاری برای این تجهیز را ندارید.")

    existing = asset.snapshots.filter(status=SNAPSHOT_DRAFT).first()
    if existing and not force_new:
        return existing

    reference = reference_snapshot(asset)
    is_baseline = reference is None
    snapshot = HardwareSnapshot.objects.create(
        asset=asset,
        version=HardwareSnapshot.next_version(asset),
        status=SNAPSHOT_DRAFT,
        is_baseline=is_baseline,
        previous=reference,
        recorded_by=user,
        recorded_at=timezone.now(),
        note=note,
        seal_number=seal_number,
    )

    # مقدارگذاری اولیه از آخرین وضعیت ثبت‌شده برای سهولت و دقت
    if reference is not None:
        for item in reference.items.select_related("component_type"):
            SnapshotItem.objects.create(
                snapshot=snapshot,
                component_type=item.component_type,
                brand=item.brand,
                model_name=item.model_name,
                serial_number=item.serial_number,
                capacity=item.capacity,
                quantity=item.quantity,
                slot=item.slot,
            )

    OutboxEvent.emit(
        EVENT_HARDWARE_SNAPSHOT_CREATED,
        {
            "asset_id": asset.pk,
            "asset_tag": asset.asset_tag,
            "snapshot_id": snapshot.pk,
            "version": snapshot.version,
            "is_baseline": is_baseline,
        },
        aggregate_type="HardwareSnapshot",
        aggregate_id=snapshot.pk,
        actor=user,
    )
    log_action(
        "create",
        snapshot,
        object_label=str(snapshot),
        note="شروع ثبت اسنپ‌شات سخت‌افزاری",
        user=user,
    )
    return snapshot


def recompute_diff(snapshot: HardwareSnapshot, save: bool = True) -> dict:
    """محاسبه تفاوت اسنپ‌شات جاری با مبنای مقایسه."""
    reference = snapshot.previous or reference_snapshot(snapshot.asset, exclude=snapshot)
    previous_items = list(reference.items.select_related("component_type")) if reference else []
    current_items = list(snapshot.items.select_related("component_type"))
    result = compute_diff(previous_items, current_items)
    if save:
        snapshot.previous = reference
        snapshot.diff_data = result
        snapshot.diff_count = result["total_changes"]
        snapshot.save(update_fields=["previous", "diff_data", "diff_count", "updated_at"])
    return result


def notify_it_experts(title: str, message: str, url: str = "", level: str = "info"):
    """ارسال اعلان به کارشناسان فناوری اطلاعات مرکز."""
    experts = User.objects.filter(role=User.ROLE_ADMIN_IT, is_active=True)
    Notification.push_many(experts, title, message, url, level)


def _notify_diff_alarm(snapshot: HardwareSnapshot, result: dict):
    """هشدار تغییر اقلام سخت‌افزاری."""
    setting = SystemSetting.load()
    if not setting.hardware_diff_alerts or not result["has_alarm"]:
        return
    parts = []
    if result["removed"]:
        parts.append(f"{result['removed']} قلم مفقود/برداشت‌شده")
    if result["replaced"]:
        parts.append(f"{result['replaced']} قلم تعویض‌شده")
    if result["added"]:
        parts.append(f"{result['added']} قلم اضافه‌شده")
    if result["changed"]:
        parts.append(f"{result['changed']} قلم با مشخصات تغییریافته")
    message = (
        f"در تجهیز {snapshot.asset.asset_tag} — {snapshot.asset.display_name}: "
        + "، ".join(parts)
    )
    notify_it_experts(
        "هشدار تغییر اقلام سخت‌افزاری",
        message,
        url=f"/assets/{snapshot.asset_id}/",
        level="danger",
    )
    OutboxEvent.emit(
        EVENT_HARDWARE_DIFF_DETECTED,
        {
            "asset_id": snapshot.asset_id,
            "asset_tag": snapshot.asset.asset_tag,
            "snapshot_id": snapshot.pk,
            "version": snapshot.version,
            "removed": result["removed"],
            "replaced": result["replaced"],
            "added": result["added"],
            "changed": result["changed"],
            "rows": [
                {
                    "state": row["state"],
                    "component_type": row["component_type"],
                    "previous": (row["previous"] or {}).get("serial", ""),
                    "current": (row["current"] or {}).get("serial", ""),
                }
                for row in result["rows"]
                if row["state"] != DIFF_UNCHANGED
            ],
        },
        aggregate_type="Asset",
        aggregate_id=snapshot.asset_id,
    )


@transaction.atomic
def submit_snapshot(snapshot: HardwareSnapshot, user) -> dict:
    """ارسال اسنپ‌شات برای تایید کارشناس IT."""
    if not snapshot.is_editable and snapshot.status != SNAPSHOT_PENDING:
        raise ValidationError("این اسنپ‌شات قفل شده و قابل تغییر نیست.")
    if not snapshot.items.exists():
        raise ValidationError("حداقل یک قلم سخت‌افزاری باید ثبت شود.")

    result = recompute_diff(snapshot)
    snapshot.confirm_by_technician(user)
    snapshot.submit_for_review(user)
    _notify_diff_alarm(snapshot, result)

    setting = SystemSetting.load()
    if setting.baseline_requires_it_confirm:
        notify_it_experts(
            "اسنپ‌شات در انتظار تایید",
            f"اسنپ‌شات نسخه {snapshot.version} تجهیز {snapshot.asset.asset_tag} در انتظار تایید شماست.",
            url=f"/assets/snapshots/{snapshot.pk}/",
            level="warning",
        )
    else:
        approve_snapshot(snapshot, user)
    return result


@transaction.atomic
def approve_snapshot(snapshot: HardwareSnapshot, user):
    """تایید و قفل اسنپ‌شات و به‌روزرسانی وضعیت جاری دارایی."""
    reference = snapshot.previous or reference_snapshot(snapshot.asset, exclude=snapshot)
    snapshot.previous = reference
    result = compute_diff(
        list(reference.items.select_related("component_type")) if reference else [],
        list(snapshot.items.select_related("component_type")),
    )
    snapshot.diff_data = result
    snapshot.diff_count = result["total_changes"]
    snapshot.lock(user)

    asset = snapshot.asset
    asset.current_snapshot = snapshot
    if snapshot.is_baseline:
        asset.baseline_locked_at = snapshot.locked_at
    update_fields = ["current_snapshot", "updated_at"]
    if snapshot.is_baseline:
        update_fields.append("baseline_locked_at")
    asset.save(update_fields=update_fields)

    if snapshot.is_baseline:
        OutboxEvent.emit(
            EVENT_HARDWARE_BASELINE_LOCKED,
            {
                "asset_id": asset.pk,
                "asset_tag": asset.asset_tag,
                "snapshot_id": snapshot.pk,
                "items_count": snapshot.items.count(),
            },
            aggregate_type="Asset",
            aggregate_id=asset.pk,
            actor=user,
        )
    else:
        _notify_diff_alarm(snapshot, result)

    log_action(
        "approve",
        snapshot,
        object_label=str(snapshot),
        note="تایید و قفل اسنپ‌شات سخت‌افزاری",
        changes={"diff_count": result["total_changes"]},
        user=user,
    )
    return snapshot


@transaction.atomic
def reject_snapshot(snapshot: HardwareSnapshot, user, note: str = ""):
    snapshot.reject(user, note)
    log_action("reject", snapshot, object_label=str(snapshot), note=note, user=user)
    if snapshot.recorded_by_id:
        Notification.push(
            snapshot.recorded_by,
            "اسنپ‌شات برگشت داده شد",
            note or "کارشناس فناوری اطلاعات اسنپ‌شات را نپذیرفت.",
            url=f"/assets/snapshots/{snapshot.pk}/",
            level="warning",
        )
    return snapshot


def asset_spec_rows(asset: Asset) -> list[tuple[str, str]]:
    """مشخصات کامل دارایی برای نمایش در شناسنامه."""
    rows = [
        ("شماره اموال", asset.asset_tag),
        ("مرکز", asset.center.name if asset.center else "—"),
        ("گونه", asset.category.name),
        ("عنوان", asset.title or "—"),
        ("برند / سازنده", asset.brand or "—"),
        ("مدل", asset.model_name or "—"),
        ("شماره سریال", asset.serial_number or "—"),
        ("واحد سازمانی", asset.department.name if asset.department else "—"),
        ("محل استقرار", asset.location.full_label if asset.location else "—"),
        ("امانت‌دار", asset.custodian.display_name if asset.custodian else "—"),
        ("نام رایانه", asset.hostname or "—"),
        ("نشانی IP", asset.ip_address or "—"),
        ("نشانی MAC", asset.mac_address or "—"),
        ("سیستم‌عامل", asset.os_name or "—"),
        ("نرم‌افزارهای اداری", asset.office_software or "—"),
        ("قرارداد پشتیبانی", str(asset.contract) if asset.contract else "—"),
        ("تامین‌کننده", asset.supplier or "—"),
    ]
    return rows


def log_asset_created(asset: Asset, user):
    OutboxEvent.emit(
        EVENT_ASSET_CREATED,
        {
            "asset_id": asset.pk,
            "asset_tag": asset.asset_tag,
            "category": asset.category.name,
            "department": asset.department.name if asset.department else "",
            "brand": asset.brand,
            "model": asset.model_name,
            "serial": asset.serial_number,
        },
        aggregate_type="Asset",
        aggregate_id=asset.pk,
        actor=user,
    )


def log_asset_updated(asset: Asset, changes: dict, user):
    if not changes:
        return
    OutboxEvent.emit(
        EVENT_ASSET_UPDATED,
        {"asset_id": asset.pk, "asset_tag": asset.asset_tag, "changes": changes},
        aggregate_type="Asset",
        aggregate_id=asset.pk,
        actor=user,
    )
