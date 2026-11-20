# ایمنی دیتابیس و داده

## وضعیت
SQLite محلی کاربر گزارش شده، اما فایل DB و migrationهای فعلی تا دریافت شواهد تازه نامعلوم‌اند. DB محلی داده ارزشمند است.

## فایل‌های محافظت‌شده
- db.pre-geography-20261114-142558.sqlite3 — حذف، جابه‌جایی، overwrite، commit یا cleanup نشود.
- تمام CSVهای reconciliation و نسخه‌های آن‌ها حفظ شوند.
- فایل‌های untracked/ناشناخته پیش از هر اقدام بررسی شوند.
- db.sqlite3 بدون مجوز تغییر نکند.

## فرمان‌های ممنوع
- reconcile_organizational_data --apply
- seed_sistan_demo
- seed_demo
- هر migration روی DB اصلی.
- flush، rebuild/reset، حذف داده یا fake migration.
- Outbox dispatch واقعی یا webhook واقعی.

وجود command در docs/CI مجوز اجرا نیست.

## پیش از migration مجاز
1. branch و commit را تأیید کنید.
2. showmigrations را بخوانید.
3. schema/data effect را توضیح دهید.
4. backup تازه از DB اصلی بسازید.
5. checksum و SQLite integrity/FK check را بررسی کنید.
6. recovery plan را توضیح دهید.
7. اجازه صریح کاربر برای همان migration بگیرید.
8. پس از اجرا integrity، FK، migration state و workflowها را بررسی کنید.

Backup قدیمی جای backup تازه را نمی‌گیرد.

## Reconciliation
CSV-first؛ هر سطر evidence/source قابل ردیابی؛ ambiguity یعنی توقف و گزارش؛ گزارش پیش از apply بررسی شود؛ evidence در لحظه apply دوباره اعتبارسنجی شود؛ تغییر atomic و audit شود. apply فعلاً ممنوع است.

## جغرافیا
مستندات loader را برای 31 استان و 484 شهرستان گزارش می‌کنند. این loader به‌تنهایی فهرست مراکز عملیاتی واقعی یا شهرهای نرمال‌شده نیست. اسناد مرتبط: docs/architecture/ORGANIZATION_AND_GEOGRAPHY.md و docs/development/TEST_DATA_AND_IRAN_GEOGRAPHY.md.

## تست دیتابیس
تست‌ها باید از test DB ایزوله استفاده کنند. migration test در CI disposable است و مجوز migration محلی نیست. fixtureها synthetic و بدون credential واقعی باشند.
