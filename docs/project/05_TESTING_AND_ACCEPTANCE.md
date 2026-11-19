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


## به‌روزرسانی UI/Metronic و CI — 2026-11-19

### CI نهایی PR #25
- PR: https://github.com/moghasemi/ITAM/pull/25
- head: `94005a451252b501b5667edf3ca87ad8fbbb9f50`
- run: https://github.com/moghasemi/ITAM/actions/runs/44403052061
- نتیجه: completed/success، 5/5 job.
- Python 3.11: 393 تست؛ Python 3.12: 393 تست.
- PostgreSQL 16: 393 تست، 3 skipped.
- production settings و deploy-script validation موفق.
- این نتایج CI هستند و اجرای محلی یا پذیرش دستی را اثبات نمی‌کنند.

### پذیرش چاپ
- برچسب دارایی: A4 عمودی، حاشیه 9mm، سه ستون، برچسب 62×42mm، فاصله 3mm.
- بررسی مقیاس چاپ 100%، ابعاد فیزیکی، حاشیه غیرقابل چاپ پرینتر، کیفیت QR و وضوح متن.
- بررسی تعداد ردیف در هر صفحه، برش بین صفحات و نبود عنوان/پابرگ نمایشی در خروجی برچسب.
- برگه بازدید و تیکت: A4 افقی؛ جدول‌ها، جزئیات SLA، امضاها و شکست صفحات بررسی شوند.
- PDF خروجی با مرورگر و چاپگر واقعی بازبینی شود.

### پذیرش HWAgent
- بازکردن صفحه standalone در محیط هدف Windows و بررسی font/asset load.
- تست keyboard tabs: ArrowLeft/ArrowRight/Home/End، focus، aria-selected و پنل‌های مخفی.
- اجرای agent.ps1 و تست اسکن جدید، آخرین snapshot، diff و history.
- اتصال به سرور آزمایشی ITAM، token binding به asset/hostname، initial sync و snapshot upload.
- rotate/suspend/revoke و error recovery.
- اطمینان از عدم ذخیره token در localStorage و عدم افشای آن در log/terminal/screenshot.
- تست syntax با node --check در CI، اجرای مرورگر و سرویس محلی را جایگزین نمی‌کند.

### پذیرش responsive و accessibility
- viewportهای 1365، 1024، 768 و 390 پیکسل؛ RTL و dark/light.
- keyboard-only، focus order، sidebar drawer، reduced motion، dropdownها، form validation، filter و pagination.
- console بدون خطای JavaScript و Network بدون 404 برای assetها.


## Runbook پذیرش محلی سه‌ساعته — 2026-11-19
- مرجع اجرایی: `18_LOCAL_UAT_RUNBOOK_2026-11-19.md`.
- PR #32 روی شاخه جداگانه شامل PR #31 است؛ تست rollback مرکز و suiteهای notification/private media/ticket اجرا شوند.
- PR #33 روی زنجیره UI و worktree جدا اجرا شود؛ تست فیلتر چاپ و سپس مرورگر/PDF.
- هر دو PR فاقد migration هستند؛ اجرای migrate لازم نیست.
- ابتدا وضعیت Git و مسیر DB محلی فقط‌خواندنی بررسی شود؛ هیچ switch در صورت working tree کثیف انجام نشود.
- هیچ Seed، reconciliation apply، Outbox dispatch یا تغییر داده واقعی اجرا نشود.
