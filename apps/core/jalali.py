"""ابزارهای تقویم هجری شمسی (بدون وابستگی بیرونی).

تبدیل‌ها بر پایه الگوریتم استاندارد جلالی (Khayyam / jalaali) پیاده‌سازی شده‌اند
تا سامانه در شبکه محلی و بدون اینترنت هم کار کند.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import NamedTuple

from django.utils import timezone

__all__ = [
    "JalaliDate",
    "fa_digits",
    "en_digits",
    "gregorian_to_jalali",
    "jalali_to_gregorian",
    "to_jalali",
    "format_jalali",
    "parse_jalali",
    "parse_jalali_datetime",
    "jalaali_month_name",
    "jalaali_month_names",
    "weekday_name",
    "relative_time",
    "is_jalali_leap",
    "jalaali_month_length",
    "jalaali_today",
]

MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

WEEKDAY_NAMES = ("شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه")

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"


class JalaliDate(NamedTuple):
    year: int
    month: int
    day: int

    @property
    def month_name(self) -> str:
        return MONTH_NAMES[self.month - 1]

    def isoformat(self) -> str:
        return f"{self.year:04d}/{self.month:02d}/{self.day:02d}"


# ---------------------------------------------------------------------------
# ارقام
# ---------------------------------------------------------------------------
def fa_digits(value) -> str:
    """تبدیل ارقام لاتین به ارقام فارسی."""
    if value is None:
        return ""
    text = str(value)
    return text.translate(str.maketrans("0123456789", _PERSIAN_DIGITS))


def en_digits(value) -> str:
    """تبدیل ارقام فارسی/عربی به ارقام لاتین."""
    if value is None:
        return ""
    text = str(value)
    text = text.translate(str.maketrans(_PERSIAN_DIGITS, "0123456789"))
    return text.translate(str.maketrans(_ARABIC_DIGITS, "0123456789"))


# ---------------------------------------------------------------------------
# تبدیل تقویم (الگوریتم مرجع jalaali با چرخه‌های ۳۳ ساله)
# ---------------------------------------------------------------------------
#: سال‌های شکست چرخه‌های کبیسه تقویم هجری شمسی
BREAKS = (
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181,
    1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
)


def _jal_cal(jy: int):
    """روز شروع سال شمسی در تقویم میلادی (اسفند/فروردین) و کبیسه بودن سال."""
    if jy < BREAKS[0] or jy >= BREAKS[-1]:
        raise ValueError(f"سال شمسی خارج از محدوده پشتیبانی است: {jy}")

    gy = jy + 621
    leap_j = -14
    jp = BREAKS[0]
    jump = 0
    for index in range(1, len(BREAKS)):
        jm = BREAKS[index]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += (jump // 33) * 8 + (jump % 33) // 4
        jp = jm

    n = jy - jp
    leap_j += (n // 33) * 8 + ((n % 33) + 3) // 4
    if jump % 33 == 4 and jump - n == 4:
        leap_j += 1

    leap_g = gy // 4 - ((gy // 100 + 1) * 3) // 4 - 150
    march = 20 + leap_j - leap_g

    if jump - n < 6:
        n = n - jump + ((jump + 4) // 33) * 33
    leap = ((n + 1) % 33 - 1) % 4
    if leap == -1:
        leap = 4
    return gy, march, leap


def _gregorian_to_day_number(gy: int, gm: int, gd: int) -> int:
    """شماره روز میلادی نسبت به ۱۹۷۰/۰۱/۰۱ (الگوریتم استاندارد civil)."""
    year = gy - (1 if gm <= 2 else 0)
    era = (year if year >= 0 else year - 399) // 400
    year_of_era = year - era * 400
    day_of_year = (153 * (gm + (-3 if gm > 2 else 9)) + 2) // 5 + gd - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - 719468


def _day_number_to_gregorian(day_number: int):
    """تبدیل شماره روز به تاریخ میلادی."""
    value = day_number + 719468
    era = (value if value >= 0 else value - 146096) // 146097
    day_of_era = value - era * 146097
    year_of_era = (
        day_of_era - day_of_era // 1460 + day_of_era // 36524 - day_of_era // 146096
    ) // 365
    year = year_of_era + era * 400
    day_of_year = day_of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    month_prime = (5 * day_of_year + 2) // 153
    day = day_of_year - (153 * month_prime + 2) // 5 + 1
    month = month_prime + (3 if month_prime < 10 else -9)
    return year + (1 if month <= 2 else 0), month, day


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> JalaliDate:
    """تبدیل تاریخ میلادی به هجری شمسی."""
    day_number = _gregorian_to_day_number(gy, gm, gd)
    jy = gy - 621
    _, march, leap = _jal_cal(jy)
    first_of_year = _gregorian_to_day_number(gy, 3, march)
    k = day_number - first_of_year
    if k >= 0:
        if k <= 185:
            return JalaliDate(jy, 1 + k // 31, (k % 31) + 1)
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return JalaliDate(jy, 7 + k // 30, (k % 30) + 1)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> dt.date:
    """تبدیل تاریخ هجری شمسی به میلادی."""
    gy, march, _ = _jal_cal(jy)
    day_number = (
        _gregorian_to_day_number(gy, 3, march)
        + (jm - 1) * 31
        - (jm // 7) * (jm - 7)
        + jd
        - 1
    )
    gy2, gm2, gd2 = _day_number_to_gregorian(day_number)
    return dt.date(gy2, gm2, gd2)


def is_jalali_leap(jy: int) -> bool:
    return ((jy + 12) % 33) % 4 == 1


def jalaali_month_length(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap(jy) else 29


def jalaali_month_names():
    return list(enumerate(MONTH_NAMES, start=1))


def jalaali_month_name(month: int) -> str:
    if 1 <= month <= 12:
        return MONTH_NAMES[month - 1]
    return ""


def jalaali_today() -> JalaliDate:
    return to_jalali(timezone.localdate())


# ---------------------------------------------------------------------------
# تبدیل و قالب‌بندی
# ---------------------------------------------------------------------------
def _as_local_date(value):
    if isinstance(value, dt.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value
    return value


def to_jalali(value) -> JalaliDate:
    """تبدیل تاریخ/زمان میلادی (یا شمسی) به تاریخ شمسی."""
    if value is None:
        return JalaliDate(0, 0, 0)
    if isinstance(value, JalaliDate):
        return value
    value = _as_local_date(value)
    return gregorian_to_jalali(value.year, value.month, value.day)


def weekday_name(value) -> str:
    """نام روز هفته به فارسی."""
    if value is None:
        return ""
    if isinstance(value, dt.datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    if isinstance(value, (dt.date, dt.datetime)):
        py_weekday = value.weekday()  # دوشنبه = ۰
    else:  # JalaliDate
        value = jalali_to_gregorian(value.year, value.month, value.day)
        py_weekday = value.weekday()
    return WEEKDAY_NAMES[(py_weekday + 2) % 7]


def format_jalali(value, fmt: str = "Y/m/d", persian_digits: bool = True) -> str:
    """قالب‌بندی تاریخ شمسی.

    نشانه‌ها: Y سال، y دو رقم آخر سال، m ماه، d روز، j روز بدون صفر،
    F نام ماه، l نام روز هفته، H ساعت، M دقیقه، S ثانیه، A/B صبح و بعدازظهر.
    """
    if not value:
        return "—"

    # اگر مقدار فقط ساعت باشد (مثل فیلدهای TimeField) تنها نشانه‌های زمانی جایگزین می‌شوند
    if isinstance(value, dt.time):
        hour, minute, second = value.hour, value.minute, value.second
        replacements = {
            "H": f"{hour:02d}",
            "G": f"{hour:d}",
            "M": f"{minute:02d}",
            "S": f"{second:02d}",
            "A": "قبل از ظهر" if hour < 12 else "بعد از ظهر",
            "B": "صبح" if hour < 12 else "عصر",
        }
        result = "".join(replacements.get(char, char) for char in fmt)
        return fa_digits(result) if persian_digits else result

    local = _as_local_date(value)
    jdate = gregorian_to_jalali(local.year, local.month, local.day)

    has_time = isinstance(local, dt.datetime)
    hour = local.hour if has_time else 0
    minute = local.minute if has_time else 0
    second = local.second if has_time else 0

    replacements = {
        "Y": f"{jdate.year:04d}",
        "y": f"{jdate.year % 100:02d}",
        "m": f"{jdate.month:02d}",
        "d": f"{jdate.day:02d}",
        "j": f"{jdate.day:d}",
        "n": f"{jdate.month:d}",
        "F": jdate.month_name,
        "l": weekday_name(local),
        "H": f"{hour:02d}",
        "G": f"{hour:d}",
        "M": f"{minute:02d}",
        "S": f"{second:02d}",
        "A": "قبل از ظهر" if hour < 12 else "بعد از ظهر",
        "B": "صبح" if hour < 12 else "عصر",
    }

    out = []
    for char in fmt:
        out.append(replacements.get(char, char))
    result = "".join(out)
    return fa_digits(result) if persian_digits else result


def parse_jalali(text) -> dt.date:
    """تبدیل رشته «۱۴۰۳/۰۵/۱۲» به تاریخ میلادی."""
    if isinstance(text, dt.date) and not isinstance(text, dt.datetime):
        return text
    if isinstance(text, dt.datetime):
        return text.date()
    if not text:
        raise ValueError("تاریخ خالی است")
    cleaned = en_digits(str(text)).strip().replace("-", "/").replace(".", "/")
    match = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", cleaned)
    if not match:
        raise ValueError("قالب تاریخ باید به شکل ۱۴۰۳/۰۵/۱۲ باشد")
    jy, jm, jd = (int(part) for part in match.groups())
    if not (1 <= jm <= 12):
        raise ValueError("ماه نامعتبر است")
    if not (1 <= jd <= jalaali_month_length(jy, jm)):
        raise ValueError("روز نامعتبر است")
    return jalali_to_gregorian(jy, jm, jd)


def parse_jalali_datetime(text, timezone_obj=None):
    """تبدیل رشته «۱۴۰۳/۰۵/۱۲ ۱۴:۳۰» به زمان آگاه از منطقه زمانی."""
    if not text:
        raise ValueError("تاریخ خالی است")
    cleaned = en_digits(str(text)).strip().replace("-", "/")
    parts = cleaned.split()
    date_part = parts[0]
    time_part = parts[1] if len(parts) > 1 else "00:00"
    date_value = parse_jalali(date_part)
    hour, minute = 0, 0
    if ":" in time_part:
        hour_s, minute_s = time_part.split(":")[:2]
        hour, minute = int(hour_s), int(minute_s)
    naive = dt.datetime.combine(date_value, dt.time(hour, minute))
    tz = timezone_obj or timezone.get_current_timezone()
    return timezone.make_aware(naive, tz)


# ---------------------------------------------------------------------------
# نمایش نسبی
# ---------------------------------------------------------------------------
def relative_time(value) -> str:
    """نمایش فاصله زمانی به فارسی؛ مثال: «۳ ساعت پیش»."""
    if not value:
        return "—"
    now = timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    delta = now - value
    seconds = int(delta.total_seconds())
    future = seconds < 0
    seconds = abs(seconds)

    if seconds < 60:
        text = "لحظه‌ای"
    elif seconds < 3600:
        text = f"{fa_digits(seconds // 60)} دقیقه"
    elif seconds < 86400:
        text = f"{fa_digits(seconds // 3600)} ساعت"
    elif seconds < 2592000:
        text = f"{fa_digits(seconds // 86400)} روز"
    elif seconds < 31536000:
        text = f"{fa_digits(seconds // 2592000)} ماه"
    else:
        text = f"{fa_digits(seconds // 31536000)} سال"
    return f"{text} پیش" if not future else f"{text} آینده"
