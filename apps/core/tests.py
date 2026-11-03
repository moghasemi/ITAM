"""آزمون‌های تقویم شمسی، تقویم کاری و محاسبه SLA."""
from __future__ import annotations

import datetime as dt

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from . import jalali
from .models import Holiday, SystemSetting
from .sla import WorkCalendar, build_calendar


class JalaliCalendarTests(TestCase):
    def test_known_new_year_dates(self):
        self.assertEqual(jalali.gregorian_to_jalali(2024, 3, 20), jalali.JalaliDate(1403, 1, 1))
        self.assertEqual(jalali.gregorian_to_jalali(2025, 3, 21), jalali.JalaliDate(1404, 1, 1))
        self.assertEqual(jalali.gregorian_to_jalali(2023, 3, 21), jalali.JalaliDate(1402, 1, 1))

    def test_round_trip(self):
        day = dt.date(2020, 1, 1)
        while day < dt.date(2030, 1, 1):
            jdate = jalali.to_jalali(day)
            back = jalali.jalali_to_gregorian(jdate.year, jdate.month, jdate.day)
            self.assertEqual(back, day, f"تبدیل رفت و برگشت برای {day} ناموفق بود")
            day += dt.timedelta(days=1)

    def test_month_length_and_leap(self):
        self.assertEqual(jalali.jalaali_month_length(1403, 1), 31)
        self.assertEqual(jalali.jalaali_month_length(1403, 7), 30)
        self.assertIn(jalali.jalaali_month_length(1403, 12), (29, 30))

    def test_parse_persian_digits(self):
        self.assertEqual(jalali.parse_jalali("۱۴۰۳/۰۱/۰۱"), dt.date(2024, 3, 20))
        self.assertEqual(jalali.parse_jalali("1403-1-1"), dt.date(2024, 3, 20))

    def test_parse_invalid(self):
        with self.assertRaises(ValueError):
            jalali.parse_jalali("1403/13/01")
        with self.assertRaises(ValueError):
            jalali.parse_jalali("نامعتبر")

    def test_format_tokens(self):
        value = timezone.make_aware(dt.datetime(2024, 3, 20, 14, 5), timezone.get_current_timezone())
        self.assertEqual(jalali.format_jalali(value, "Y/m/d", persian_digits=False), "1403/01/01")
        self.assertEqual(jalali.format_jalali(value, "H:M", persian_digits=False), "14:05")
        self.assertEqual(jalali.format_jalali(value, "F", persian_digits=False), "فروردین")
        self.assertEqual(jalali.format_jalali(value, "l", persian_digits=False), "چهارشنبه")

    def test_format_time_only(self):
        """فیلدهای ساعت (TimeField) نباید باعث خطا شوند."""
        self.assertEqual(jalali.format_jalali(dt.time(7, 30), "H:M", persian_digits=False), "07:30")

    def test_weekday_names(self):
        self.assertEqual(jalali.weekday_name(dt.date(2024, 3, 23)), "شنبه")   # شنبه
        self.assertEqual(jalali.weekday_name(dt.date(2024, 3, 29)), "جمعه")   # جمعه


class WorkCalendarTests(TestCase):
    def setUp(self):
        cache.clear()
        self.setting = SystemSetting.load()
        self.setting.counting_mode = SystemSetting.COUNTING_WORK_HOURS
        self.setting.work_start = dt.time(8, 0)
        self.setting.work_end = dt.time(16, 0)
        self.setting.work_days = [5, 6, 0, 1, 2]  # شنبه تا چهارشنبه
        self.setting.exclude_holidays = True
        self.setting.save()
        self.calendar = build_calendar(self.setting)

    def _at(self, year, month, day, hour, minute=0):
        return timezone.make_aware(
            dt.datetime(year, month, day, hour, minute), timezone.get_current_timezone()
        )

    def test_working_day_detection(self):
        self.assertTrue(self.calendar.is_working_day(dt.date(2024, 3, 23)))   # شنبه
        self.assertFalse(self.calendar.is_working_day(dt.date(2024, 3, 28)))  # پنج‌شنبه
        self.assertFalse(self.calendar.is_working_day(dt.date(2024, 3, 29)))  # جمعه

    def test_minutes_within_one_day(self):
        start = self._at(2024, 3, 23, 9, 0)
        end = self._at(2024, 3, 23, 11, 30)
        self.assertAlmostEqual(self.calendar.working_minutes_between(start, end), 150, places=1)

    def test_minutes_skip_non_working_hours(self):
        # شنبه ۱۵:۰۰ تا یک‌شنبه ۱۰:۰۰ = ۶۰ دقیقه شنبه + ۱۲۰ دقیقه یک‌شنبه
        start = self._at(2024, 3, 23, 15, 0)
        end = self._at(2024, 3, 24, 10, 0)
        self.assertAlmostEqual(self.calendar.working_minutes_between(start, end), 180, places=1)

    def test_minutes_skip_weekend(self):
        # چهارشنبه ۱۵:۰۰ تا شنبه ۹:۰۰ = ۶۰ دقیقه چهارشنبه + ۶۰ دقیقه شنبه
        start = self._at(2024, 3, 27, 15, 0)
        end = self._at(2024, 3, 30, 9, 0)
        self.assertAlmostEqual(self.calendar.working_minutes_between(start, end), 120, places=1)

    def test_add_working_minutes(self):
        start = self._at(2024, 3, 23, 15, 0)
        result = self.calendar.add_working_minutes(start, 120)
        # ۶۰ دقیقه تا پایان روز کاری + ۶۰ دقیقه از روز بعد
        expected = self._at(2024, 3, 24, 9, 0)
        self.assertEqual(result, expected)

    def test_add_working_minutes_across_weekend(self):
        start = self._at(2024, 3, 27, 15, 0)  # چهارشنبه
        result = self.calendar.add_working_minutes(start, 120)
        expected = self._at(2024, 3, 30, 9, 0)  # شنبه
        self.assertEqual(result, expected)

    def test_holiday_is_excluded(self):
        holiday_date = dt.date(2024, 3, 24)  # یک‌شنبه
        Holiday.objects.create(title="تعطیل آزمایشی", date=holiday_date, is_active=True)
        cache.clear()
        calendar = build_calendar(SystemSetting.load())
        self.assertFalse(calendar.is_working_day(holiday_date))
        start = self._at(2024, 3, 23, 15, 0)
        end = self._at(2024, 3, 25, 9, 0)  # دوشنبه
        self.assertAlmostEqual(calendar.working_minutes_between(start, end), 120, places=1)

    def test_24_7_mode(self):
        calendar = WorkCalendar(is_24_7=True)
        start = self._at(2024, 3, 28, 22, 0)
        end = self._at(2024, 3, 29, 2, 0)
        self.assertAlmostEqual(calendar.working_minutes_between(start, end), 240, places=1)
        self.assertEqual(
            calendar.add_working_minutes(start, 120), self._at(2024, 3, 29, 0, 0)
        )

    def test_pause_subtraction(self):
        start = self._at(2024, 3, 23, 8, 0)
        end = self._at(2024, 3, 23, 12, 0)
        pauses = [{"start": self._at(2024, 3, 23, 9, 0), "end": self._at(2024, 3, 23, 10, 0)}]
        self.assertAlmostEqual(self.calendar.subtract_pauses(start, end, pauses), 180, places=1)
