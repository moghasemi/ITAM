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

## تعارض CSS قدیمی و Metronic — 2026-11-18
- در Metronic/Tailwind 4 فایل vendor، ترتیب layerها `theme, base, components, utilities` تعریف شده است.
- `static/css/itam.css` قبلاً خارج از layer قرار داشت؛ قواعد عادی unlayered نسبت به قواعد عادی داخل layer اولویت بیشتری دارند و ممکن بود utility/componentهای Metronic را تحت‌تأثیر قرار دهند.
- اصلاح پیشنهادی در PR #19: قرار دادن کل stylesheet قدیمی داخل `@layer base`. selectorهای قدیمی حذف نمی‌شوند؛ CSS bridge در `itam-metronic.css` بدون layer باقی می‌ماند تا همچنان سفارشی‌سازی نهایی را اعمال کند.
- **PR اصلاح:** https://github.com/moghasemi/ITAM/pull/19 — Draft، branch `fix/metronic-legacy-css-cascade`، head `dccd73e2e11092850a1b5b94e73a7b3da5e54a49`، base= `ui/metronic9-django-rtl`.
- **وضعیت پذیرش:** تغییر کد ثبت شده؛ آزمون واقعی مرورگر هنوز Open است. این اصلاح به‌تنهایی تضمین نمی‌کند تمام مشکلات layout رفع شوند.
- **مورد بررسی محلی:** dashboard، فهرست دارایی، فرم ایجاد/ویرایش، صفحه ورود، عرض دسکتاپ و موبایل، dropdownها، حالت dark و print.


## وضعیت مهاجرت تکمیلی Metronic — 2026-11-19

### زنجیره تغییرات
- PR #19: `itam.css` در `@layer base` برای اصلاح cascade؛ selectorهای legacy حذف نشدند.
- PR #20: یک منبع حقیقت برای عرض Sidebar و محتوا.
- PR #21: skip link، focus management و mobile sidebar keyboard/inert.
- PR #22: dashboard با KPI، chart، calendar و workbench.
- PR #23: صفحات عملیاتی asset/ticket/maintenance.
- PR #24: مهاجرت templateهای باقیمانده و حذف selectorهای shell قدیمی از CSS legacy.
- PR #25: برگه‌های چاپ، HWAgent standalone و partialهای مشترک.
- تمام PRها Draft و Merge نشده‌اند. CI موفق روی headهای #19 تا #24 در اجرای کامل ثبت شده؛ #25 در زمان ثبت منتظر CI مجدد پس از رفع missing template tag است.

### جزئیات PR #25
- label print: A4 portrait, margin 9mm, label 62×42mm, 3 columns, 3mm gap; heading/footer مخفی.
- visit/ticket print: A4 landscape.
- shell, messages و skip link در چاپ پنهان می‌شوند.
- HWAgent: viewport meta، فونت محلی، dark mode، reduced motion، tablist/tab/tabpanel با ARIA و keyboard، meterهای داخلی RAM/disk؛ Chart.js CDN حذف شده است.
- shared partials: form_fields, filter_bar, pagination, formset, empty, messages, action_button به hookهای Metronic مجهز شده‌اند؛ data hooks/classes قدیمی حفظ شده‌اند.
- شکست CI اولیه: missing `{% load itam_tags %}` در formset partial؛ commit اصلاحی در head جاری ثبت شده؛ CI مجدد باید نتیجه دهد.

### موارد باز
- browser visual acceptance، print/PDF physical acceptance و Windows HWAgent end-to-end.
- حذف کامل legacy compatibility CSS عمداً deferred است تا هر کلاس/رفتار/JS consumer جداگانه مهاجرت و تست شود.
- Metronic commercial license verification.
- هیچ PR Merge/Deploy نشده است.
