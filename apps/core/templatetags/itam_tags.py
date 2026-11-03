"""برچسب‌ها و پالایه‌های قالبی سامانه."""
from __future__ import annotations

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .. import jalali
from ..utils import duration_fa, fa_number, percent

register = template.Library()


# ---------------------------------------------------------------------------
# پالایه‌ها
# ---------------------------------------------------------------------------
@register.filter(name="fa")
def filter_fa(value):
    """تبدیل ارقام به فارسی."""
    return jalali.fa_digits(value)


@register.filter(name="fa_num")
def filter_fa_num(value):
    """عدد با جداکننده هزارگان و ارقام فارسی."""
    return fa_number(value)


@register.filter(name="jdate")
def filter_jdate(value):
    """تاریخ شمسی کوتاه: ۱۴۰۳/۰۵/۱۲"""
    return jalali.format_jalali(value, "Y/m/d")


@register.filter(name="jdate_full")
def filter_jdate_full(value):
    """تاریخ شمسی کامل با نام روز هفته."""
    return jalali.format_jalali(value, "l j F Y")


@register.filter(name="jdatetime")
def filter_jdatetime(value):
    """تاریخ و ساعت شمسی."""
    return jalali.format_jalali(value, "Y/m/d H:M")


@register.filter(name="jdatetime_full")
def filter_jdatetime_full(value):
    """تاریخ و ساعت شمسی با نام روز و ماه."""
    return jalali.format_jalali(value, "l j F Y — H:M")


@register.filter(name="jtime")
def filter_jtime(value):
    return jalali.format_jalali(value, "H:M")


@register.filter(name="rel")
def filter_rel(value):
    """فاصله زمانی نسبی."""
    return jalali.relative_time(value)


@register.filter(name="dur")
def filter_dur(value):
    """مدت زمان خوانا از دقیقه."""
    return duration_fa(value)


@register.filter(name="pct")
def filter_pct(value, arg):
    return percent(value, arg)


@register.filter(name="diff_css")
def filter_diff_css(value):
    """کلاس CSS برای وضعیت تفاوت اقلام."""
    from ..constants import DIFF_CSS

    return DIFF_CSS.get(value, "neutral")


@register.filter(name="item_css")
def filter_item_css(value):
    """کلاس CSS برای وضعیت قلم سخت‌افزاری."""
    from ..constants import ITEM_CONDITION_CSS

    return ITEM_CONDITION_CSS.get(value, "neutral")


@register.filter(name="priority_css")
def filter_priority_css(value):
    from ..constants import PRIORITY_CSS

    return PRIORITY_CSS.get(value, "neutral")


@register.filter(name="status_css")
def filter_status_css(value):
    from ..constants import TICKET_STATUS_CSS

    return TICKET_STATUS_CSS.get(value, "neutral")


@register.filter(name="visits_status_css")
def filter_visit_status_css(value):
    from ..constants import VISIT_STATUS_CSS

    return VISIT_STATUS_CSS.get(value, "neutral")


@register.filter(name="check_css")
def filter_check_css(value):
    from ..constants import CHECK_CONDITION_CSS

    return CHECK_CONDITION_CSS.get(value, "neutral")


@register.filter(name="asset_status_css")
def filter_asset_status_css(value):
    from ..constants import ASSET_STATUS_CSS

    return ASSET_STATUS_CSS.get(value, "neutral")


@register.filter(name="event_label")
def filter_event_label(value):
    from ..constants import EVENT_TYPE_CHOICES

    return dict(EVENT_TYPE_CHOICES).get(value, value)


@register.filter(name="percent_value")
def filter_percent_value(value, arg=1):
    """درصد عددی برای نوار پیشرفت."""
    try:
        return float(value or 0) * 100 / float(arg or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


@register.filter(name="yesno_fa")
def filter_yesno_fa(value):
    return "بله" if value else "خیر"


@register.filter(name="field_class")
def filter_field_class(field, css):
    """افزودن کلاس CSS به ویجت یک فیلد فرم."""
    existing = field.field.widget.attrs.get("class", "")
    field.field.widget.attrs["class"] = f"{existing} {css}".strip()
    return field


@register.filter(name="has_role")
def filter_has_role(user, roles):
    """آیا کاربر یکی از نقش‌های داده‌شده را دارد؟"""
    if not getattr(user, "is_authenticated", False):
        return False
    wanted = {role.strip() for role in str(roles).split(",") if role.strip()}
    return bool(wanted & set(user.role_codes()))


@register.filter(name="mask_serial")
def filter_mask_serial(value):
    """نمایش کوتاه سریال."""
    text = str(value or "")
    if len(text) <= 6:
        return text
    return f"{text[:3]}…{text[-3:]}"


# ---------------------------------------------------------------------------
# برچسب‌ها
# ---------------------------------------------------------------------------
@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    """ساخت نشانی با تغییر پارامترهای GET (برای صفحه‌بندی و پالایه‌ها)."""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode() if hasattr(params, "urlencode") else ""
    return f"?{encoded}" if encoded else "?"


@register.simple_tag
def status_badge(label, css_class="neutral", icon=""):
    """نشان وضعیت رنگی."""
    icon_html = f'<span class="badge-icon">{icon}</span>' if icon else ""
    return format_html(
        '<span class="badge badge-{}">{}{}</span>', css_class, icon_html, label
    )


@register.simple_tag
def sla_badge(state: str, label: str = ""):
    mapping = {
        "met": ("success", "رعایت شده"),
        "breached": ("danger", "نقض شده"),
        "pending": ("warning", "در جریان"),
        "unknown": ("neutral", "بدون تعریف"),
    }
    css, default_label = mapping.get(state, ("neutral", "نامشخص"))
    return format_html(
        '<span class="badge badge-{}">{}</span>', css, label or default_label
    )


@register.simple_tag
def progress_bar(value, total, label=""):
    """نوار پیشرفت ساده."""
    try:
        value = float(value or 0)
        total = float(total or 0)
        pct_value = min(100.0, max(0.0, value * 100 / total)) if total else 0.0
    except (TypeError, ValueError):
        pct_value = 0.0
    width = f"{pct_value:.1f}"
    return format_html(
        '<div class="progress" title="{}"><div class="progress-bar" style="width:{}%"></div></div>',
        label or f"{pct_value:.0f}%",
        width,
    )


@register.simple_tag
def qr_svg(content, size=6):
    """تصویر QR به‌صورت SVG درون‌خطی."""
    from apps.assets.qrgen import svg

    return mark_safe(svg(content, module_size=size))
