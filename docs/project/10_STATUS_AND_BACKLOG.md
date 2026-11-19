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
### اصلاحیه مهم PR #13/#14 — تطبیق hash فایل‌ها
- 25 فایل PR #13 با محتوای head PR #14 مقایسه شد: 12 فایل دقیقاً یکسان، 13 فایل متفاوت.
- فایل‌های یکسان: org/forms.py، org/load_iran_geography.py، org/services.py، org/tests_center_form.py، org/tests_iran_geography.py، reports/forms.py، reports/tests_scope.py، reports/views.py، tickets/views.py، config/urls.py و دو template مرکز/درخواست.
- فایل‌های متفاوت شامل assets views/tests، core seed/private-media/security tests، maintenance services/views/tests، org/views و tickets/tests هستند.
- نتیجه: PR #13 یک duplicate کامل نیست؛ یک شاخه partially overlapping و diverged است. هیچ تصمیم بستن یا حذف آن گرفته نشده؛ 13 فایل متفاوت باید از نظر رفتار/امنیت مقایسه شوند.
### تکمیل ancestry — PRهای #10 تا #14
- head بسته‌شده #10 ancestor شاخه #11 است (ahead 142 / behind 0)؛ بنابراین commitهای #10 در شاخه #11 و فرزند آن #14 حفظ شده‌اند و برای حفظ آن‌ها نیازی به re-open #10 نیست.
- PR #12 در مقایسه با #14، 12/19 فایل با محتوای دقیقاً یکسان دارد و 7 فایل متفاوت؛ بخش‌هایی از تغییرات #12 جذب شده اما branch کامل redundant نیست.
- PR #13 در مقایسه با #14، 12/25 فایل دقیقاً یکسان و 13 فایل متفاوت دارد؛ duplicate کامل نیست و mergeable=false/dirty باقی می‌ماند.
- مسیر محتمل mainline از نظر ancestry: #7 → #8 → #9 → #11 → #14 → #15 → #16؛ #10 ancestor #11 است. #12/#13 فقط پس از reconcile کردن deltaهای مفقود قابل تعیین تکلیف‌اند.
### ممیزی گزینشی امنیتی و داده — 2026-11-19
- در head PR #15، scope غیرکشوری با active center/county/province و consistency بین جغرافیا و TreatmentManagement محدود شده است؛ technician فقط از قرارداد و assignment فعال مرکز scope می‌گیرد.
- HWAgent در API به credential، asset، center، hostname، timestamp و nonce bind شده؛ legacy credential بدون asset binding fail-closed است.
- Outbox dispatch/requeue به POST و country-admin محدود است؛ Adminهای RepairRequest و Ticket/Event read-only هستند.
- موارد باز: یکسان‌سازی Center.clean/save، atomicity و هم‌زمانی get_or_create مدیریت درمان، تنظیم واقعی trusted proxy، تست replay/race و ممیزی کامل IDOR/export/admin/private media.
- این دور بازبینی گزینشی است؛ security sign-off صادر نشده.

## نتیجه ممیزی معنایی PR #12 و #13 در برابر #14 — 2026-11-19

- PR #12: هفت فایل متفاوت بررسی شد. کنترل‌های taxonomy، تنظیمات سراسری، audit scope، visibility بازخورد تعمیر و contract visibility در head #14 وجود دارند؛ مورد مفقود عملکردی مشاهده نشد.
- PR #13: سیزده فایل متفاوت بررسی شد. کنترل‌های private/no-store و 404، seed/TreatmentManagement، CenterForm، SQLite test guard، visibility نقش‌ها و گردش GeneralITRequest در #14 وجود دارند یا با پیاده‌سازی کامل‌تری جایگزین شده‌اند.
- visible_contracts در apps/org/services.py مسیر scope قرارداد را متمرکز می‌کند؛ برای Center/County فقط assignment فعال و تاریخ‌دار مرکز مجاز است و برای Province Admin scope استانی صریح کنترل می‌شود.
- در GeneralITRequest، #14 علاوه بر کنترل وضعیت و قفل ردیف، manager approval را پیش‌نیاز تخصیص قرار داده است؛ بنابراین تغییر ساده‌تر #13 نباید روی آن overwrite شود.
- مورد کم‌اهمیت: تفاوت در بستن stream فایل در تست private media؛ فعلاً به‌عنوان cleanup تست ثبت می‌شود، نه delta محصول.
- تصمیم: cherry-pick مستقل از #12/#13 در این مرحله لازم تشخیص داده نشد. PR #13 به علت divergence و mergeable=false همچنان باز و حل‌نشده می‌ماند؛ این بررسی مجوز بستن یا Merge نیست.
- آخرین CI مستندات PR #17 روی commit 954c3f6a2a8f3037aad4ce5c9c48f56e852657df در run 44488869040 با نتیجه success تمام شد.
- هیچ کد برنامه، migration، seed، DB، reconciliation یا Outbox تغییر/اجرا نشد.


## Branch protection و required checks — 2026-11-19
- شاخه main از GitHub API با protected=false و protection.enabled=false گزارش شده است.
- required_status_checks در وضعیت enforcement_level=off و بدون check/context ثبت شده؛ repository rulesets نیز خالی برگشته است.
- این وضعیت یک ریسک governance است: CI سبز به‌صورت اجباری gate ادغام main نشده است. پیش از شروع Mergeهای زنجیره‌ای، فعال‌سازی branch protection و required checks توصیه می‌شود.


## ممیزی امنیتی تکمیلی — 2026-11-19

- [x] CI آخرین commit مستندات PR #17، `0f38834f467776c69b8baf6109b369fa6be20d9f`: دو run `44494487453` (push) و `44494500448` (pull_request)، هر کدام 5/5 job موفق.
- [x] CI head PR #18، `130bb091caf7c751f0ca6d406d93afa83528259a`: run `44174205183`، هر 5 job موفق.
- [x] بررسی نمونه‌ای اختلاف مجوز فایل ارجاع با فهرست ارجاع انجام شد.
- **یافته P2 باز:** در `apps/core/views.py::private_media` مسیر `referrals/`، scope مرکز/استان برای دانلود کافی شمرده می‌شود؛ در `apps/maintenance/repair_views.py::referral_list` نقش‌های غیرمجازِ ایجاد/مدیریت ارجاع فقط ارجاع‌های گیرنده خود را می‌بینند. بنابراین manager/requester غیرگیرنده در همان scope می‌تواند با داشتن مسیر فایل به پیوست دسترسی پیدا کند.
- **شواهد پوشش ناقص:** تست‌های `apps/core/tests_private_media.py` دسترسی user_a با نقش admin_it و منع user_b در مرکز دیگر را می‌سنجند؛ تست منفی برای manager/requester هم‌مرکزِ غیرگیرنده مشاهده نشد.
- [ ] اصلاح: ایجاد یک سیاست/queryset واحد برای visibility ارجاع و استفاده مشترک در فهرست، resolve و private media.
- [ ] افزودن regression tests برای manager/requester غیرگیرنده (مرکزدار و referral استانی بدون مرکز)، و حفظ دسترسی گیرنده/نقش‌های مجاز.
- [ ] اجرای CI کامل پس از اصلاح.
- این مورد در این دور فقط audit و مستندسازی شد؛ هیچ کد برنامه‌ای تغییر نکرد.

### محدودیت‌ها
این یافته به معنی تکمیل ممیزی امنیتی نیست. سایر IDORها، همه exportها، Admin endpoints، signature/visit/hardware media و UAT وب‌سرور واقعی همچنان باید جداگانه بررسی شوند.


## تکمیل ممیزی امنیتی و هم‌پوشانی PR — 2026-11-19

- [x] CI commit مستندات `1f370bb3798367bacb8feceff2a3feca8ddefc78`: push `44495868255` و pull_request `44495875141`، هر کدام 5/5 job موفق.
- **P2 — امضاها:** مسیر عمومی private media برای `signatures/` به owner، مدیر کشوری و اعضای همان center scope دسترسی می‌دهد؛ در مقابل endpoint `signature_file` و تست accounts آن owner-only هستند. نیازمند تصمیم سیاستی؛ در صورت owner-only بودن، محدودکردن private_media و تست منفی هم‌مرکز.
- **P2 — افزودن قطعه/پیوست Ticket:** `ticket_add_part` و `ticket_add_attachment` در backend فقط visibility تیکت را می‌سنجند، نه `can_manage_ticket`؛ درحالی‌که template فرم‌ها را فقط برای manager-side نمایش می‌دهد. نیازمند permission server-side و تست direct POST برای requester/نقش غیرمجاز.
- **P2 — پیوست ارجاع:** همان mismatch قبلی بین referral list و private media؛ سیاست مشترک visibility لازم است.
- [x] اسکن file-path overlap: PR #17 و #18 با زنجیره #19–#25 مسیر مشترک نداشتند؛ overlapهای درون زنجیره UI از ancestry شاخه‌های فرزند می‌آیند و باید با compare واقعی تفسیر شوند.
- [ ] اصلاح هر سه مورد امنیتی و افزودن regression tests.
- [ ] تکمیل ممیزی سایر endpointهای مستقیم، exportها و Admin.

هیچ کد برنامه‌ای در این دور تغییر نکرد؛ موارد فوق code-review finding هستند، نه exploit اجراشده یا UAT عملیاتی.


## وضعیت reviewهای GitHub و CI نهایی handbook — 2026-11-19

- [x] GitHub Reviews برای PRهای #7 تا #25 بررسی شد: صفر review رسمی.
- [x] Inline review comments برای PRهای #7 تا #25: صفر مورد.
- [x] Conversation comments در issue thread PRهای #7 تا #25: صفر مورد.
- [x] CI آخرین commit handbook `d54eba7b8cbd505723bd1ff14ea63e15e6c7b8a9`: push run `44496497082` و pull_request run `44496504493`، هر دو 5/5 job success.
- **تفسیر:** نبود reviewها نشانه تأیید کد نیست؛ تمام PRها هنوز به review مستقل محتوایی و تعیین ترتیب merge نیاز دارند.


## ممیزی endpointهای عملیاتی — 2026-11-19

- [x] بررسی static مسیرهای maintenance، assets/HWAgent، org/contract assignments، accounts، reports و notifications.
- [x] تایید وجود service-level checks برای عملیات اصلی تعمیر مستقل، بازخورد، ارجاع، درخواست عمومی IT، بازدید و snapshot در مسیرهای مرورشده.
- [x] بررسی exportها: گزارش‌های مرورشده از StaffRequiredMixin و querysets scope-aware مانند visible_assets، visible_tickets، visible_visits، visible_repair_requests استفاده می‌کنند.
- **P3 باز:** `notification_read` از طریق لینک GET اجرا می‌شود و `mark_read()` را صدا می‌زند؛ GET باعث تغییر وضعیت می‌شود. اصلاح با POST+CSRF و تست عدم تغییر در GET پیشنهاد می‌شود.
- [ ] اصلاح P3 notification state change.
- [ ] اصلاح سه یافته P2 ثبت‌شده در D-009 و D-010 و D-011.
- [ ] ادامه بررسی همه exportها و ماتریس نقش‌ها؛ بررسی فعلی نمونه‌ای/ایستا است.

**نتیجه:** در مسیرهای مرورشده شکاف P1 جدیدی مشاهده نشد؛ این گزاره جایگزین ممیزی کامل یا تست اجرایی نیست.


## اولویت جدید مالک محصول — ثبت روزانه، UX/UI و منو (2026-11-19)

### تصمیم و تعهد
- [x] ایجاد دفتر ثبت روزانه به‌عنوان مرجع append-only در `14_DAILY_WORK_LOG.md`.
- [x] تعریف استاندارد اجباری بازبینی صفحه‌به‌صفحه UX/UI و استفاده متناسب از Metronic در `07_UI_UX_AND_METRONIC.md`.
- [x] بازبینی static اولیه `templates/base.html` و ثبت مشکلات و ساختار پیشنهادی منو.
- [ ] استخراج ماتریس کامل نقش/لینک/URL/active_menu.
- [ ] اصلاح گروه‌بندی منو و کلیدهای active_menu تکراری در PR مستقل.
- [ ] اجرای بازبینی UX برای تمام صفحات؛ هنوز هیچ ادعای پذیرش مرورگر نداریم.

### یافته اولیه منو
- «درخواست‌ها و خدمات» چند حوزه کاربری و عملیاتی را مخلوط کرده است.
- «قرارداد و بازدید» گروه‌بندی معنایی مناسبی ندارد.
- «پایش و مدیریت» گزارش، Outbox و Audit را کنار هم گذاشته است.
- active_menu تکراری در لینک‌های تعمیرکاران/ارزیابی/تعمیرات مشاهده شد.
- جزئیات و ساختار هدف پیشنهادی در سند UI/Metronic و دفتر روزانه ثبت شده است.

### وضعیت فعلی کار
- مستندات/تصمیم‌ها: ثبت در همین تغییر.
- کد منو: هنوز تغییر نکرده.
- مرورگر/موبایل/دسترس‌پذیری: هنوز آزمون نشده.
- اولویت بعدی: استخراج ماتریس منو و ایجاد PR مستقل برای بازطراحی آن پس از تعیین head پایه صحیح زنجیره UI.


## وضعیت بازطراحی منو — 2026-11-19

- [x] بررسی static partial منو و تطبیق با viewها و URLهای مرتبط.
- [x] تعریف گروه‌بندی وظیفه‌محور و ثبت در handbook.
- [x] پیاده‌سازی اولیه sidebar و active_menu در PR #26: https://github.com/moghasemi/ITAM/pull/26
- [x] افزودن لینک اعلان‌ها، تقویم تعطیلات و گونه قطعات به گروه مناسب.
- [ ] CI کامل PR #26 و بررسی mergeability پس از تکمیل workflow.
- [ ] تست فعال‌شدن فقط یک آیتم منو برای هر صفحه و تست نقش‌محور.
- [ ] browser acceptance در desktop/tablet/mobile، RTL، dark mode، collapse و drawer.
- [ ] بررسی لینک‌های جدید در نقش‌های مجاز و فقط همان نقش‌ها.
- **Commit کد:** `4abb2a2d86ea2c90a14663f8c204e22fb0059e16`؛ branch `ui/primary-navigation-ux-audit`.
- **CI در آخرین snapshot:** `production-settings-check: success; deploy-script-validation: success; test (3.11): in_progress; test (3.12): in_progress; postgres-test: in_progress`.


### نتیجه CI PR #26 — 2026-11-19
- [x] CI push run `44507835886`: success.
- [x] CI pull_request run `44507866034`: 5/5 job success.
- [x] PR #26 در آخرین مشاهده mergeable=true و همچنان Draft است.
- [ ] browser acceptance و UAT نقش‌محور هنوز انجام نشده‌اند.


## شروع ممیزی صفحه‌به‌صفحه UX/UI — 2026-11-19
- [x] ایجاد ماتریس صفحات و وضعیت ممیزی: `15_UI_PAGE_AUDIT_MATRIX.md`.
- [x] بازبینی static داشبورد و تطبیق role visibility با endpoint اسنپ‌شات.
- [x] ایجاد PR #27 برای اصلاح dashboard role gating، Metronic badges و table accessibility.
- [ ] CI نهایی PR #27 روی head `6d32645b6ec6a1ad1144d7a69a43db53e9c6e17e`.
- [ ] مرورگر و آزمون visual/responsive/dark-mode/keyboard.
- [ ] بازبینی UX صفحه‌های دارایی، تیکت و نگهداری؛ وضعیت هر صفحه در ماتریس ثبت می‌شود.


## ممیزی UX صفحه فهرست دارایی‌ها — 2026-11-19
- [x] بررسی template و view و filter form.
- [x] ثبت ایراد قطعی 12 header در برابر 11 cell و colspan اشتباه.
- [x] ثبت gapهای badge، scope و table accessibility.
- [ ] اصلاح در PR مستقل stacked بر PR #27.
- [ ] تست هم‌ترازی ستون‌ها و query count برای جلوگیری از N+1.
