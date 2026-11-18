# وضعیت و Backlog

**Snapshot:** 2026-11-19

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

## به‌روزرسانی UI — 2026-11-18
- PR #19 باز و Draft: اصلاح اولویت cascade بین CSS قدیمی و Metronic.
- head: `dccd73e2e11092850a1b5b94e73a7b3da5e54a49`؛ branch: `fix/metronic-legacy-css-cascade`؛ base: `ui/metronic9-django-rtl`.
- تغییر کد فقط `static/css/itam.css` را در `@layer base` قرار می‌دهد؛ selectorهای سازگاری حفظ شده‌اند.
- CI برای head جدید هنوز نتیجه قابل مشاهده ندارد؛ مرورگر محلی و UAT انجام نشده‌اند.
- **P0 جدید:** پس از همگام‌سازی امن شاخه، بازبینی بصری dashboard، فهرست دارایی، فرم‌ها، login، responsive، dark mode و print؛ ثبت ایرادهای باقی‌مانده به‌صورت مستقل.


## وضعیت جدید UI — 2026-11-19

### زنجیره PR
- PRهای #15، #16، #19، #20، #21، #22، #23، #24 و #25 در آخرین مشاهده باز و Draft هستند؛ هیچ‌کدام Merge نشده‌اند.
- #15 و #16 پایه مرحله UI؛ #19 تا #25 زنجیره تکمیل Metronic.
- #17 (handbook) و #18 (private media/contractor assignment scope) شاخه‌های موازی روی پایه #16 هستند و مستقل باید بازبینی شوند.
- PR #25: branch `ui/metronic-print-hwagent-finalization`، head `94005a451252b501b5667edf3ca87ad8fbbb9f50`, base #24؛ 14 فایل، 355 additions/300 deletions.
- PR #25 CI قبلی شکست خورد چون `formset.html` فیلتر `field_class` را بدون `{% load itam_tags %}` استفاده کرده بود. import اضافه شد؛ run `44403052061` روی head `94005a451252b501b5667edf3ca87ad8fbbb9f50` با 5/5 job موفق شد (393 تست در هر دو Python؛ PostgreSQL 393 تست با 3 skipped).

### P0 — اکنون
1. صبر برای CI کامل PR #25؛ اگر شکست جدیدی رخ داد، فقط علت واقعی اصلاح شود.
2. نگه‌داشتن همه PRها به صورت Draft؛ بدون Merge یا Deploy.
3. تا دسترسی محلی کاربر، فقط بررسی GitHub، اصلاح کد، CI و مستندات انجام شود.

### P1 — پس از دسترسی محلی
1. دریافت `git branch --show-current`, `git log -1 --oneline`, `git status --short`؛ پیش از sync هیچ checkout/reset/stash/clean انجام نشود.
2. sync امن با زنجیره PR تأییدشده، بدون از دست‌دادن فایل‌های untracked/backup/CSV.
3. پذیرش مرورگر: login، dashboard، asset/ticket/maintenance، فرم‌ها، pagination، RTL، dark/light، responsive، keyboard/accessibility و console/network.
4. پذیرش چاپ و PDF: label 62×42، QR، مقیاس 100%، A4 portrait/landscape، page breaks و امضا.
5. پذیرش Windows HWAgent: نصب، token، binding به asset/hostname، snapshot، sync و lifecycle credential.
6. UAT نقش‌محور برای hierarchy/scope، قرارداد و انتساب، ticket/SLA، بازدید، snapshot، تعمیر مستقل، درخواست عمومی/ارجاع، گزارش/export و audit.

### P2 — قبل از پذیرش محصول
- invariant بین county/province/TreatmentManagement و fail-closed بودن واحدهای غیرفعال.
- ماتریس دسترسی و آزمون IDOR/form tampering.
- Admin immutability برای Ticket/Visit/Snapshot/Outbox/Audit.
- private media در وب‌سرور واقعی و export scope/formula injection.
- SLA در تقویم شمسی، تعطیلات و توقف‌ها.
- backup/restore drill در محیط ایزوله.

### P3 — Deferred
- هاست، PostgreSQL production، TLS/reverse proxy، firewall، service hardening، monitoring، secret rotation و Production UAT.
- مجوز خریداری‌شده Metronic برای deployment تجاری باید قبل از عرضه بررسی شود.
- نرمال‌سازی جغرافیای شهر/محله و provenance مراکز.
