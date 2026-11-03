"""محاسبه زمان کاری و SLA.

ساعت SLA می‌تواند بر مبنای ساعت کاری اداره یا شبانه‌روزی محاسبه شود و
تعطیلات رسمی از آن کسر گردد.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from django.utils import timezone

from . import jalali


@dataclass
class WorkCalendar:
    """تقویم کاری سامانه."""

    is_24_7: bool = False
    work_start: dt.time = dt.time(7, 30)
    work_end: dt.time = dt.time(15, 30)
    work_days: set[int] = field(default_factory=lambda: {5, 6, 0, 1, 2})
    holiday_dates: set[dt.date] = field(default_factory=set)
    recurring_holidays: set[tuple[int, int]] = field(default_factory=set)
    exclude_holidays: bool = True

    # -- بررسی روز ---------------------------------------------------------
    def is_holiday(self, day: dt.date) -> bool:
        if not self.exclude_holidays:
            return False
        if day in self.holiday_dates:
            return True
        jdate = jalali.to_jalali(day)
        return (jdate.month, jdate.day) in self.recurring_holidays

    def is_working_day(self, day: dt.date) -> bool:
        if self.is_24_7:
            return not self.is_holiday(day)
        if day.weekday() not in self.work_days:
            return False
        return not self.is_holiday(day)

    # -- پنجره کاری یک روز -------------------------------------------------
    def window(self, day: dt.date):
        """بازه کاری یک روز به‌صورت زمان آگاه از منطقه زمانی."""
        if not self.is_working_day(day):
            return None
        tz = timezone.get_current_timezone()
        if self.is_24_7:
            start = timezone.make_aware(dt.datetime.combine(day, dt.time.min), tz)
            end = start + dt.timedelta(days=1)
            return start, end
        start = timezone.make_aware(dt.datetime.combine(day, self.work_start), tz)
        end = timezone.make_aware(dt.datetime.combine(day, self.work_end), tz)
        if end <= start:
            return None
        return start, end

    # -- محاسبه ------------------------------------------------------------
    def working_minutes_between(self, start, end) -> float:
        """دقیقه‌های کاری میان دو زمان."""
        if start is None or end is None:
            return 0.0
        start = _ensure_aware(start)
        end = _ensure_aware(end)
        if end <= start:
            return 0.0
        if self.is_24_7 and not self.exclude_holidays:
            return (end - start).total_seconds() / 60.0

        total = 0.0
        day = timezone.localtime(start).date()
        last_day = timezone.localtime(end).date()
        guard = 0
        while day <= last_day and guard < 4000:
            guard += 1
            window = self.window(day)
            if window:
                window_start, window_end = window
                overlap_start = max(window_start, start)
                overlap_end = min(window_end, end)
                if overlap_end > overlap_start:
                    total += (overlap_end - overlap_start).total_seconds() / 60.0
            day += dt.timedelta(days=1)
        return total

    def add_working_minutes(self, start, minutes: float):
        """افزودن دقیقه کاری به یک زمان و رسیدن به زمان سرسید."""
        if start is None:
            return None
        start = _ensure_aware(start)
        if minutes is None:
            return start
        if minutes <= 0:
            return start
        if self.is_24_7 and not self.exclude_holidays:
            return start + dt.timedelta(minutes=minutes)

        remaining = float(minutes)
        cursor = start
        day = timezone.localtime(start).date()
        guard = 0
        while guard < 4000:
            guard += 1
            window = self.window(day)
            if window:
                window_start, window_end = window
                work_from = max(cursor, window_start)
                if work_from < window_end:
                    available = (window_end - work_from).total_seconds() / 60.0
                    if remaining <= available:
                        return work_from + dt.timedelta(minutes=remaining)
                    remaining -= available
            day += dt.timedelta(days=1)
            cursor = timezone.make_aware(
                dt.datetime.combine(day, dt.time.min), timezone.get_current_timezone()
            )
        return cursor

    def subtract_pauses(self, start, end, pauses) -> float:
        """دقیقه‌های کاری پس از کسر بازه‌های توقف ساعت."""
        total = self.working_minutes_between(start, end)
        for pause in pauses or []:
            pause_start = pause.get("start") if isinstance(pause, dict) else pause[0]
            pause_end = pause.get("end") if isinstance(pause, dict) else pause[1]
            if pause_start is None:
                continue
            effective_end = min(pause_end or end, end)
            if effective_end > pause_start:
                total -= self.working_minutes_between(pause_start, effective_end)
        return max(total, 0.0)


def _ensure_aware(value):
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def build_calendar(setting=None) -> WorkCalendar:
    """ساخت تقویم کاری بر اساس تنظیمات سامانه و تعطیلات ثبت‌شده."""
    from .models import Holiday, SystemSetting

    if setting is None:
        setting = SystemSetting.load()

    holiday_dates: set[dt.date] = set()
    recurring: set[tuple[int, int]] = set()
    try:
        for holiday in Holiday.objects.filter(is_active=True):
            if holiday.is_recurring_annual:
                recurring.add(holiday.jalali_key())
            else:
                holiday_dates.add(holiday.date)
    except Exception:  # پایگاه داده هنوز آماده نیست
        pass

    return WorkCalendar(
        is_24_7=setting.is_24_7,
        work_start=setting.work_start,
        work_end=setting.work_end,
        work_days=setting.work_day_set,
        holiday_dates=holiday_dates,
        recurring_holidays=recurring,
        exclude_holidays=setting.exclude_holidays,
    )


def get_calendar() -> WorkCalendar:
    """تقویم کاری با کش کوتاه‌مدت در طول یک درخواست."""
    from django.core.cache import cache

    cache_key = "itam:work-calendar"
    calendar = cache.get(cache_key)
    if calendar is None:
        calendar = build_calendar()
        cache.set(cache_key, calendar, 120)
    return calendar


def invalidate_calendar_cache():
    from django.core.cache import cache

    cache.delete("itam:work-calendar")
    cache.delete("itam:system-setting")


def sla_verdict(met: bool | None, due=None, actual=None, now=None):
    """وضعیت SLA را برای نمایش در قالب تعیین می‌کند."""
    if met is True:
        return "met", "رعایت شده"
    if met is False:
        return "breached", "نقض شده"
    if due is None:
        return "unknown", "بدون تعریف"
    now = now or timezone.now()
    if now > due:
        return "breached", "نقض شده"
    return "pending", "در جریان"
