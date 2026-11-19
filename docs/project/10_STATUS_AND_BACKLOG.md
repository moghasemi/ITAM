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

## نقشه‌راه فازبندی‌شده
مرجع اصلی فازها، زیرمجموعه‌ها، چک‌لیست و معیار پایان در [نقشه‌راه اجرایی و فازبندی پروژه](13_PHASED_ROADMAP_AND_EXECUTION.md) است. وضعیت فاز صفر و مواردی که هنوز باز هستند در انتهای همین سند ثبت شده‌اند.

## وضعیت ممیزی فاز صفر — 2026-11-19

### دامنه بررسی‌شده و تکمیل‌شده
- [x] فهرست PRهای باز و بسته از GitHub دریافت شد: ۱۸ باز، ۷ بسته.
- [x] PRهای بسته Mergeشده از PRهای بسته بدون Merge تفکیک شدند: #1، #2، #4، #5 و #6 Merge شده؛ #3 و #10 بسته بدون Merge.
- [x] base/head/SHA و وضعیت Draft/mergeability برای PRهای باز ثبت شد.
- [x] آخرین CI روی head هر ۱۸ PR باز بررسی شد.
- [x] جزئیات jobهای شکست‌خورده PR #14 بررسی شد.
- [x] وضعیت dirty و عدم mergeability PR #13 شناسایی شد.
- [x] handbook branch مربوط به PR #17 و فایل index و backlog آن بررسی شد.
- [x] نقشه‌راه فاز صفر تا پنج به فهرست مستندات اضافه شد.

### وضعیت فعلی CI روی headهای بررسی‌شده
- موفق: PRهای #7، #8، #9، #11، #12، #13، #15، #16، #17، #18، #19، #20، #21، #22، #23، #24 و #25.
- ناموفق: PR #14؛ jobهای test Python 3.11، test Python 3.12 و PostgreSQL شکست خورده‌اند. production-settings-check و deploy-script-validation موفق بوده‌اند.
- توجه: CI موفق PR #15 روی head فرزند، جایگزین ثبت تاریخی CI ناموفق PR #14 نیست؛ باید اصلاحات و ancestry بررسی شود.
- PR #13: `mergeable=false` و `mergeable_state=dirty`؛ مانع باز است.

### موارد باز فاز صفر
- [ ] بازبینی محتوایی diff تمام PRها و review threads.
- [ ] مقایسه ancestry و محتوای PRهای stacked، به‌خصوص #7–#16.
- [ ] تعیین تکلیف PR #10 بسته‌شده بدون Merge که پایه PR #12 است.
- [ ] تحلیل علت dirty بودن PR #13 و رفع conflict در شاخه مناسب.
- [ ] بررسی required checks و branch protection.
- [ ] نهایی‌کردن ترتیب ادغام و مستندسازی gateهای هر مرحله.
- [ ] بررسی مجدد CI پس از اصلاحات.

### محدودیت‌های این snapshot
- هیچ PR در این مرحله Merge نشده است.
- هیچ Deploy، Migration، Seed، reconciliation apply یا Outbox dispatch اجرا نشده است.
- هیچ DB محلی یا Production بررسی/تغییر داده نشده است.
- تست مرورگر، چاپ فیزیکی و اجرای Windows HWAgent انجام نشده‌اند.
- وضعیت branch/HEAD/working tree روی رایانه کاربر هنوز دریافت نشده است.

## وضعیت زنجیره PRها — بازبینی 2026-11-19

- #7 مستقل از main؛ #8 بر پایه #7؛ #9 بر پایه #8.
- #11 بر پایه #9؛ #14 بر پایه #11؛ #15 بر پایه #14؛ #16 بر پایه #15.
- #17 و #18 شاخه‌های موازی بر پایه #16 هستند.
- #19 نیز بر پایه #16؛ سپس #20 → #21 → #22 → #23 → #24 → #25.
- #10 بسته‌شده بدون Merge است؛ #12 بر پایه شاخه #10 و #13 بر پایه #12 است. پیش از هر ادغام باید diff و ancestry این زنجیره جداگانه بررسی شود.
- #13 در وضعیت dirty و غیرقابل ادغام گزارش شده است.
- #14 CI ناموفق دارد؛ #15 CI موفق دارد اما رابطه اصلاحات و تغییرات پایه باید در diff بررسی شود.

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

---

## Snapshot ممیزی فاز صفر — دور دوم (2026-11-19)

- 18 PR باز و Draft؛ 7 PR بسته. پنج PR #1/#2/#4/#5/#6 Merge شده‌اند؛ #3 و #10 بسته بدون Merge هستند.
- 17/18 head PRهای باز CI موفق؛ تنها #14 ناموفق. #10 نیز CI ناموفق دارد.
- PR #12 از head PR #10 منشعب شده است؛ بنابراین commitهای #10 در ancestry #12 هستند و باید در برنامه ادغام حفظ شوند.
- PR #13 نسبت به base خود 40 ahead و 7 behind و dirty است. PR #14 همان patchهای apps/org/forms.py و apps/org/tests_center_form.py را نیز حمل می‌کند؛ #13 نامزد duplicate/stale است، نه هنوز قطعی.
- لاگ #14: خطای approval gate در تخصیص GeneralITRequest و mismatch بین expected assigned/approved. PR #15 CI موفق دارد؛ head #14 همچنان ناموفق است.
- PR #17 در head c6cf538644815fe178673edbea3497f92a79811c CI موفق run 44485800684 دارد.
- Branch Protection endpoint برای main به علت 403 قابل خواندن نبود؛ required checks هنوز تأیید نشده‌اند.
- بررسی اولیه PRها نشان داده migration TreatmentManagement و Center.save، HWAgent credential binding، trusted proxy/login throttling، Outbox role restrictions، reconciliation CSV-first و private media authorization نیازمند بازبینی/آزمون پذیرش تکمیلی‌اند.
- هیچ Merge، Deploy، Migration، Seed، reconciliation apply یا Outbox dispatch انجام نشده است.

### موارد باز بعد از دور دوم
- [ ] تطبیق کامل #13/#14 و تعیین تکلیف شاخه stale/تکراری.
- [ ] تکمیل بررسی تمام diffها و security review؛ بازبینی انجام‌شده در این دور اولیه و گزینشی است.
- [ ] رفع/ثبت علت دقیق CI ناموفق #14 در زنجیره ادغام؛ PR #15 سبز است اما PR #14 نباید مستقل Merge شود.
- [ ] بررسی Branch Protection/required checks با مجوز مناسب.
- [ ] تهیه برنامه ادغام topological و gate-by-gate.