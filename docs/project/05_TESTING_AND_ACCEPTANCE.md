# تست، CI و پذیرش

## سطوح تست
Unit، service/model، view/permission، regression، integration، CI matrix، local manual QA، Windows/HWAgent، UAT و operational acceptance. سبز بودن یک سطح جایگزین سطوح دیگر نیست.

## CI ثبت‌شده
- PR #15: run 44156594235 روی head 4ce9e0d...؛ 5/5 job موفق؛ 372 تست در Python 3.11 و 3.12؛ PostgreSQL 16 و production/deploy checks موفق.
- PR #16: run 44161472256 روی head 23dbebb...؛ 5/5 job موفق؛ 375 تست در Python 3.11 و 3.12؛ PostgreSQL 16، production settings و deploy validation موفق.

این‌ها GitHub Actions هستند؛ اجرای محلی کاربر را ثابت نمی‌کنند.

## فرمان‌های متداول
~~~powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
~~~

manage.py test ممکن است test DB بسازد؛ مطمئن شوید تست‌ها endpoint واقعی را فراخوانی نمی‌کنند. این فرمان‌ها مجوز Migration روی DB اصلی نیستند.

## Regression coverage
هر تغییر در role/scope، inactive org، IDOR، form tampering، stale/duplicate workflow، audit atomicity، snapshot lock/Admin، Outbox/idempotency/SSRF، HWAgent binding، export formula injection و private media باید تست متناظر داشته باشد.

## پذیرش دستی Metronic
1. login/logout.
2. منوی نقش‌محور برای roleهای مختلف.
3. sidebar collapse.
4. mobile drawer/backdrop و scroll lock.
5. dark/light و persistence پس از reload.
6. global search و shortcut.
7. notification/account dropdown.
8. فرم، validation، checkbox، file/date/select و formset.
9. table/filter/pagination و horizontal scroll.
10. dashboard chart و حالت no-JS.
11. print/report/labels.
12. responsive viewport.
13. Network panel: asset 404 نداشته باشد.
14. console: JavaScript error نداشته باشد.
15. contrast، keyboard focus و reduced motion.

برای هر اشکال role، URL، viewport، مراحل، expected/actual و screenshot بدون داده حساس ثبت شود.

## پذیرش workflow
دارایی، تیکت، SLA، قرارداد، انتساب، بازدید، Snapshot baseline/lock/diff، تعمیر مستقل، درخواست عمومی، ارجاع، گزارش، export و audit را با نقش‌های مجاز و غیرمجاز تست کنید.

## خارج از CI
Windows HWAgent، private media پشت reverse proxy، TLS/network، backup/restore و UAT واقعی.

## گزارش تست
branch/SHA، محیط، نسخه Python/DB، فرمان، pass/fail/skip، CI یا local بودن، تست‌های اجرا نشده و اثر DB/file را ثبت کنید.
