# وضعیت و Backlog

**Snapshot:** 2026-11-18

## اکنون
- PR #15 باز، Draft و merge نشده؛ امنیت و Integration QA.
- PR #16 باز، Draft و merge نشده؛ Metronic 9 RTL؛ stacked روی #15.
- CI روی headهای ثبت‌شده هر دو موفق.
- handbook branch از head PR #16 ساخته شده.
- browser test و local acceptance هنوز انجام نشده.
- branch، HEAD، working tree و DB کاربر تأیید نشده‌اند.
- هاست/Production در مرحله جاری متوقف‌اند.

## P0
1. دریافت وضعیت branch/HEAD/status از سیستم کاربر.
2. بررسی working tree و فایل‌های untracked.
3. همگام‌سازی امن به branch UI بدون reset/stash/clean.
4. تست دستی Metronic.
5. ثبت اشکال‌ها به‌صورت مستقل.

## P1 — امنیت و داده
- role scope در کشور/استان/شهرستان/مرکز.
- inactive organization و empty scope.
- county/TreatmentManagement province mismatch.
- قرارداد چندمرکزی و assignment فعال.
- form tampering و IDOR.
- Admin immutability برای Ticket/Visit/Snapshot/Outbox/Audit.
- HWAgent credential binding.
- export scope/formula injection.
- private media authorization.

## P2 — پذیرش محصول
- تیکت و SLA.
- بازدید و تأیید.
- قرارداد و انتساب.
- Snapshot baseline/lock/diff.
- تعمیرکار مستقل، اختلاف هزینه و ارجاع.
- گزارش و export.
- Jalali calendar/holiday behavior.

## P3 — عملیات آینده
Windows HWAgent، backup/restore، TLS/reverse proxy، private media، monitoring، PostgreSQL deployment، مجوز تجاری Metronic، provenance جغرافیا و فهرست رسمی مراکز. هاست فقط با تصمیم جدید کاربر فعال شود.

## معیار بستن
رفتار روشن، commit قابل ردیابی، regression test، CI موفق، پذیرش محلی در صورت نیاز، مستند به‌روز و ریسک باقیمانده ثبت‌شده.


## قانون جدید مستندسازی
از 2026-11-18 مستندسازی هم‌زمان و بدون درخواست اجازه جداگانه بخشی از Done است. Decision Log، سند جامع و backlog پس از تصمیم‌ها/کارها/تست‌های معنادار به‌روز می‌شوند. این قاعده مجوز Merge، Deploy، Migration، Seed یا عملیات مخرب نیست. جزئیات: DECISION_LOG.md.
