"""ابزارهای کمکی عمومی، لاگ ممیزی و فرمت‌دهی."""
from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal, InvalidOperation

from django.db import models
from django.utils import timezone

from . import jalali
from .middleware import client_ip, client_user_agent, get_current_user

logger = logging.getLogger("itam")


# ---------------------------------------------------------------------------
# لاگ ممیزی
# ---------------------------------------------------------------------------
def log_action(
    action: str,
    obj=None,
    *,
    model_name: str = "",
    object_id=None,
    object_label: str = "",
    changes: dict | None = None,
    note: str = "",
    user=None,
) -> "object":
    """ثبت یک رخداد در لاگ ممیزی."""
    from .models import AuditLog

    actor = user if user is not None else get_current_user()
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    if obj is not None:
        model_name = model_name or obj.__class__.__name__
        object_id = object_id if object_id is not None else getattr(obj, "pk", "")
        object_label = object_label or str(obj)[:250]

    return AuditLog.objects.create(
        user=actor,
        user_label=str(actor) if actor else "سامانه",
        action=action,
        model_name=model_name,
        object_id=str(object_id or ""),
        object_label=object_label,
        changes=changes or {},
        note=note[:300],
        ip_address=client_ip(),
        user_agent=client_user_agent(),
    )


def model_changes(before: dict, after: dict) -> dict:
    """تفاوت دو دیکشنری را برای درج در لاگ ممیزی برمی‌گرداند."""
    changes = {}
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value != new_value:
            changes[key] = {
                "از": _jsonable(old_value),
                "به": _jsonable(new_value),
            }
    return changes


def _jsonable(value):
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, models.Model):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def snapshot_instance(instance, fields=None) -> dict:
    """مقادیر فعلی فیلدهای یک نمونه را برای مقایسه برمی‌گرداند."""
    data = {}
    for field in instance._meta.fields:
        if fields and field.name not in fields:
            continue
        data[field.name] = getattr(instance, field.attname, None)
    return data


# ---------------------------------------------------------------------------
# فرمت‌دهی اعداد و زمان
# ---------------------------------------------------------------------------
def to_decimal(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(jalali.en_digits(value)).replace(",", ""))
    except (InvalidOperation, ValueError):
        return default


def fa_number(value, decimals: int = 0) -> str:
    """عدد را با جداکننده هزارگان و ارقام فارسی برمی‌گرداند."""
    if value in (None, ""):
        return "—"
    try:
        number = float(jalali.en_digits(value))
    except (TypeError, ValueError):
        return str(value)
    if decimals:
        text = f"{number:,.{decimals}f}"
    else:
        text = f"{number:,.0f}"
    return jalali.fa_digits(text)


def duration_fa(minutes) -> str:
    """مدت زمان را به فارسی خوانا برمی‌گرداند."""
    if minutes is None:
        return "—"
    try:
        total = int(round(float(minutes)))
    except (TypeError, ValueError):
        return "—"
    if total < 0:
        return "منفی " + duration_fa(-total)
    if total < 60:
        return f"{jalali.fa_digits(total)} دقیقه"
    hours, mins = divmod(total, 60)
    if hours < 24:
        if mins:
            return f"{jalali.fa_digits(hours)} ساعت و {jalali.fa_digits(mins)} دقیقه"
        return f"{jalali.fa_digits(hours)} ساعت"
    days, hours = divmod(hours, 24)
    if hours:
        return f"{jalali.fa_digits(days)} روز و {jalali.fa_digits(hours)} ساعت"
    return f"{jalali.fa_digits(days)} روز"


def percent(part, whole, decimals: int = 0) -> str:
    try:
        part = float(part or 0)
        whole = float(whole or 0)
    except (TypeError, ValueError):
        return "—"
    if not whole:
        return "—"
    return jalali.fa_digits(f"{part * 100 / whole:.{decimals}f}") + "٪"


def local_now():
    return timezone.localtime(timezone.now())


def today():
    return timezone.localdate()
