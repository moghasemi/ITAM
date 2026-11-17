# رابط کاربری و Metronic 9

## وضعیت
PR #16 در branch ui/metronic9-django-rtl، head 23dbebb19493cb9947c685c069adf205039412a9. PR باز و Draft است؛ merge نشده. CI موفق است اما تست مرورگر کاربر انجام نشده.

## تصمیم معماری
Django Templates حفظ شده؛ React مستقل اضافه نشده. UI در templates، CSS/JS و static assets است. vendor assets self-hosted. منطق permission و workflow در backend می‌ماند.

## فایل‌های اصلی
- templates/base.html: پوسته، header و sidebar.
- templates/accounts/login.html: login.
- templates/core/dashboard.html: داشبورد و chart.
- templates/partials/: فرم و فیلتر مشترک.
- static/css/itam-metronic.css: bridge.
- static/js/itam.js: تعاملات مشترک.
- static/vendor/metronic9/ و static/vendor/vazirmatn/: assets.

## امکانات PR
sidebar نقش‌محور، header ثابت، search، notifications، account dropdown، selector مرکز با get_scoped_centers()، collapse، mobile drawer، light/dark و persistence، ApexCharts، CSS bridge برای فرم/جدول/کارت/filter/pagination، print styles، reduced motion و keyboard focus.

این فهرست به معنی استفاده از همه demo/pluginهای Metronic نیست. انتخاب‌ها برای سازگاری با Django Forms، Jalali inputs، server-side pagination و file validation انجام شده‌اند.

## قواعد UI
- business logic و authorization در backend.
- menu hidden مجوز نیست.
- POSTها CSRF و validation سمت سرور داشته باشند.
- نام فیلد، URL، pagination، formset و workflow حفظ شوند.
- datepicker جدید بدون بررسی Jalali اضافه نشود.
- client-side DataTables جایگزین server-side pagination نشود مگر تصمیم صریح.
- upload widget validation سرور را دور نزند.
- runtime CDN و asset بدون بررسی license اضافه نشود.
- keyboard, focus, contrast, labels, aria و reduced motion بررسی شوند.

## CI و مجوز
run 44161472256 روی head PR #16: 5/5 job موفق؛ 375 تست Python 3.11/3.12، PostgreSQL 16 و deployment checks.

مجوز خریداری‌شده Metronic برای ITAM راستی‌آزمایی نشده است. notice همراه نسخه مرجع برای هر deployment/project مجوز جدا و برای SaaS پولی Extended License را ذکر می‌کند. پیش از عرضه تجاری سند خرید بررسی شود. Vazirmatn با OFL همراه شده است.

## پذیرش
چک‌لیست کامل در 05_TESTING_AND_ACCEPTANCE.md بخش پذیرش دستی است. تا آن زمان UI فقط CI-validated است، نه browser-accepted.
