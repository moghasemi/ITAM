# ITAM — سند جامع زمینه و انتقال پروژه

**نسخه:** 1.6  
**تاریخ بازبینی:** 2026-11-19  
**Repository:** https://github.com/moghasemi/ITAM  
**زبان:** فارسی و RTL  
**معماری جاری:** Django Modular Monolith + Django Templates؛ frontend مستقل React وجود ندارد.

> این سند ادامه نسخه 1.3 مورخ 2026-11-17 است؛ نسخه 1.3 و 1.2 به‌عنوان سابقه حفظ شده‌اند. نسخه 1.2 و تاریخچه نیازمندی‌هایش باید حفظ شوند. این نسخه وضعیت جاری GitHub و تصمیم‌های مرحله Metronic را ثبت می‌کند. وضعیت checkout و دیتابیس روی رایانه کاربر هنوز با خروجی تازه محلی تأیید نشده است.

## 1. خلاصه اجرایی

ITAM سامانه مدیریت دارایی و نگهداری فناوری اطلاعات در ساختار چندسطحی کشور، استان، شهرستان و مرکز است. مسیر فعلی **توسعه و پذیرش محلی با SQLite** است. خرید هاست، استقرار و Production در این مرحله متوقف‌اند.

تغییرهای اصلی نسبت به نسخه 1.2:
- PR #15 اصلاحات امنیتی و Integration QA را ارائه می‌کند.
- PR #16 پوسته Metronic 9.4.13 فارسی/RTL را اضافه می‌کند و معماری Django Templates را حفظ می‌کند.
- هر دو PR هنوز باز و Draft هستند و Merge نشده‌اند.
- CI روی head فعلی PR #16 موفق است.
- تست مرورگر و پذیرش محلی کاربر هنوز انجام نشده.
- مرحله بعد از مستندسازی: دریافت وضعیت Git محلی، همگام‌سازی امن checkout و تست؛ نه Migration یا Seed.

## 2. وضعیت زنده GitHub در 2026-11-17

Repository: moghasemi/ITAM؛ default branch برابر main است. از main به‌عنوان مبنای خودکار توسعه استفاده نکنید.

| مورد | وضعیت مشاهده‌شده |
|---|---|
| integration/itam-v1.1-qa | head: 51aed2e88e3583eeac03b0851391018616db5313 |
| PR #15 | باز، Draft، Merge نشده؛ base=integration/itam-v1.1-qa |
| head PR #15 | fix/integration-qa-security-workflow |
| SHA PR #15 | 4ce9e0d96a8446622a4bf2c5fc7c1da405cd76ad |
| PR #16 | باز، Draft، Merge نشده؛ stacked روی PR #15 |
| head PR #16 | ui/metronic9-django-rtl |
| SHA PR #16 | 23dbebb19493cb9947c685c069adf205039412a9 |
| base PR #16 | fix/integration-qa-security-workflow با SHA پایه 4ce9e0d... |
| PR #16 | 5 commit، 22 فایل، حدود 31,455 افزودن و 354 حذف |
| branch مستندسازی | docs/itam-project-handbook-v1.3؛ از head PR #16 ساخته شده است |

هر دو PR در آخرین مشاهده GitHub open، draft=true، merged=false و mergeable گزارش شده‌اند. پیش از هر اقدام آینده وضعیت زنده را دوباره بررسی کنید.

### 2.1 PR #15 — امنیت و تثبیت Integration QA
PR: https://github.com/moghasemi/ITAM/pull/15

کارهای مهم:
- اصلاح تخصیص اولیه درخواست IT در حالت pending بودن تصمیم مدیر مرکز؛ تصمیم مدیر و وضعیت تخصیص مستقل‌اند.
- حفظ وضعیت تخصیص هنگام تأیید مدیر.
- اصلاح ممیزی استان فاقد مرکز عملیاتی/TreatmentManagement.
- حذف credential ثابت از tools/verify_http.py و استفاده از environment variables.
- fail-closed کردن scope فعال در مرز استان، شهرستان و مرکز.
- bind کردن اعتبارنامه HWAgent به asset فعال و hostname؛ credential legacy بدون asset binding رد می‌شود.
- محافظت قفل HardwareSnapshot در Django Admin.
- reconciliation محافظه‌کار، CSV-first، اتمیک و با بازبینی مجدد شواهد.
- احراز هویت endpointهای فعال‌سازی/تغییر رمز، read-only کردن لاگ‌ها و workflow records، atomic کردن mutation و AuditLog، اصلاح form filters و SLA calendar.
- Migration apps/accounts/migrations/0005_login_throttle_lock.py افزوده شده و در CI روی DBهای disposable اجرا شده؛ روی دیتابیس محلی یا Production کاربر اجرا نشده است.

CI ثبت‌شده در متن PR:
- run 44156594235 روی head 4ce9e0d...، هر 5 job موفق.
- Python 3.11: 372 تست؛ Python 3.12: 372 تست.
- PostgreSQL 16، production settings و deployment validation موفق.
- هیچ Migration روی دیتابیس محلی یا Production اجرا نشده است.

### 2.2 PR #16 — Metronic 9 فارسی/RTL
PR: https://github.com/moghasemi/ITAM/pull/16

- Metronic 9.4.13 از نسخه HTML فارسی/RTL مرجع.
- Django Templates و server-rendered architecture حفظ شده؛ React مستقل اضافه نشده.
- پوسته پایه، sidebar نقش‌محور، header، جستجو، اعلان، منوی حساب، selector مرکز، theme روشن/تاریک، collapse، drawer موبایل، responsive و print styles.
- CSS/JS/فونت‌های لازم به شکل self-hosted اضافه شده‌اند.
- KTUI، Keenicons، Vazirmatn و ApexCharts برای نیازهای مشخص.
- CSS bridge برای قالب‌های موجود فرم، جدول، فیلتر، کارت، pagination و پیام‌ها.
- منطق URL، مدل، permission و workflow عملیاتی عمداً بازنویسی نشده.
- selector مرکز از get_scoped_centers() تغذیه می‌شود و در خطا fail-closed است.

CI روی head دقیق PR #16:
- run 44161472256، completed/success، هر 5 job موفق.
- Python 3.11: 375 تست؛ Python 3.12: 375 تست.
- PostgreSQL 16 migration/test suite موفق.
- production settings check موفق.
- deployment script / PowerShell / HWAgent browser JavaScript validation موفق.
- این نتایج GitHub Actions هستند، نه تست روی رایانه کاربر.
- CI موفق، آزمون واقعی مرورگر، accessibility کامل، پذیرش workflow یا Production readiness را اثبات نمی‌کند.

### 2.3 زنجیره PR
PR #16 روی PR #15 stacked است. تا تعیین تکلیف #15، base #16 را خودسرانه تغییر ندهید. پس از Merge مجاز #15، diff و base #16 دوباره بررسی شود تا فقط تغییرات UI باقی بماند. هیچ PRی بدون اجازه صریح کاربر Merge نشود.

## 3. معماری و نقشه مخزن

معماری جاری:
- Django Modular Monolith.
- Django Templates؛ frontend مستقل React وجود ندارد.
- CSS/JavaScript داخلی و static assets.
- SQLite برای توسعه محلی؛ PostgreSQL 16 در CI نیز آزموده می‌شود.

| مسیر | مسئولیت غالب |
|---|---|
| apps/accounts | کاربران، نقش‌ها، مجوزها، ورود و rate limiting |
| apps/org | سازمان، جغرافیا، مراکز، قراردادها و پیمانکاران |
| apps/assets | دارایی، قطعات، Snapshot و HWAgent |
| apps/tickets | تیکت و رخدادهای گردش |
| apps/maintenance | بازدید، تعمیر، SLA، درخواست عمومی و تعمیرکار مستقل |
| apps/reports | گزارش و خروجی |
| apps/integrations | Outbox، webhook و API logs |
| apps/core | زیرساخت مشترک، audit، middleware و notifications |
| config | settings و root URLs |
| templates / static | UI و assets |
| HWAgent | کلاینت Windows |
| docs | مستندات |

## 4. دامنه محصول و قواعد سازمانی

- سلسله‌مراتب هدف: کشور ← استان ← شهرستان ← مرکز.
- مرکز باید به شهرستان معتبر متصل باشد؛ Center.parent_unit مرجع ساختاری مهم است.
- Center.province در مستندات deprecated/historical compatibility است.
- TreatmentManagement مالکیت سازمانی مرکز را از موقعیت جغرافیایی جدا می‌کند؛ مدل جغرافیایی نرمال‌شده شهر/محله و provenance کامل داده‌ها هنوز کامل نیست.
- scope مبهم، رابطه ناسازگار یا واحد غیرفعال باید fail-closed شود.
- شمار مراکز واقعی در منابع عمومی 408 و 413 متعارض است؛ هیچ مرکز ساختگی برای پرکردن اختلاف ایجاد نشود.
- نقش‌ها: superuser/admin country، admin_province، admin_county، admin_it، manager، technician، requester. ماتریس دقیق باید از کد و تست جاری استخراج شود.

## 5. گردش‌های اصلی

### دارایی
شناسنامه تجهیز، شماره اموال، مشخصات فنی، مرکز/واحد، امانت‌دار، پیوست و QR؛ پیوند با تیکت، بازدید و Snapshot.

### تیکت و SLA
گردش مورد انتظار: reported → acknowledged → arrived → work_started → resolved_declared → user confirmation → IT final confirmation. reported_at مبدأ SLA است. ساعت کاری، تعطیلات شمسی، اولویت و توقف‌های مجاز باید لحاظ شوند. تأیید کاربر و IT مستقل‌اند.

### Snapshot سخت‌افزاری
baseline با workflow تأیید و قفل؛ snapshot بعدی missing/changed/added و تغییر مشخصات را ثبت کند. قفل باید در view، service، model و Admin enforce شود.

### پیمانکار و بازدید
پوشش پیمانکار از انتساب فعال و تاریخ‌دار مرکز و قرارداد معتبر مشتق می‌شود؛ صرف استانی بودن قرارداد مجوز مرکز نیست. جدول legacy Contract.centers مرجع مجوز نیست.

### تعمیرکار مستقل و درخواست عمومی
نیازمندی شامل برآورد، تصمیم استان، نتیجه تعمیر، ارزیابی، اختلاف هزینه و ارجاع است. تصمیم مدیر، تخصیص کارشناس و وضعیت اجرایی باید مستقل باشند.

### Outbox
رخداد در transaction عملیات اصلی ثبت و سپس ارسال می‌شود. retry و idempotency در هر endpoint مستقل‌اند. exactly-once بدون deduplication مقصد فرض نشود.

## 6. اصول امنیتی

1. Fail-closed: scope نامعلوم، واحد غیرفعال، قرارداد منقضی یا binding ناسازگار نباید دسترسی بدهد.
2. Server-side authorization: مخفی‌کردن لینک مجوز نیست.
3. Scoped querysets: list/detail/form/export/dashboard همه scope سازگار داشته باشند.
4. IDOR: رکورد خارج از حوزه ترجیحاً 404؛ عملیات نامجاز در endpoint مجاز 403.
5. Audit atomicity: تغییر حساس و AuditLog در یک transaction.
6. Append-only: رخدادها و لاگ‌های حساس از Admin قابل تغییر/حذف عادی نباشند.
7. Secrets: token/password/secret در کد، log، issue، screenshot و docs قرار نگیرد.
8. Private media: دسترسی از authorization رکورد عبور کند؛ debug serving جایگزین proxy امن نیست.
9. Webhook/SSRF: allowlist دقیق hostname، کنترل DNS/IP، منع redirect و validation header.
10. Reconciliation: CSV-first، شواهد قابل ردیابی، بازبینی پیش از apply؛ تطبیق مبهم حدس زده نشود.
11. HWAgent: credential به asset فعال و hostname bind شود.
12. Admin نباید workflow، snapshot lock، SLA یا audit را دور بزند.

## 7. ایمنی دیتابیس

- فایل db.pre-geography-20261114-142558.sqlite3 محافظت‌شده است.
- تمام CSVهای reconciliation و فایل‌های untracked مرتبط حفظ شوند.
- وضعیت فعلی db.sqlite3، migrationها و working tree تا دریافت خروجی تازه نامعلوم است.
- هیچ flush، reset، rebuild، حذف داده، fake migration یا seed اجرا نشود.
- reconcile_organizational_data --apply مطلقاً اجرا نشود.
- seed_sistan_demo و seed_demo اجرا نشوند.
- migration روی DB اصلی فقط پس از بررسی showmigrations، backup تازه با checksum، شرح اثر schema/data و اجازه صریح کاربر.
- تست‌ها باید روی test database ایزوله باشند.
- Outbox واقعی در DB محلی dispatch نشود.

## 8. قواعد Git و همکاری

- مبنای مرحله UI، head PR #16 است؛ نه main.
- پیش از هر تغییر محلی: git branch --show-current، git log -1 --oneline، git status --short.
- پیش از commit، head شاخه دوباره بررسی شود؛ از expected_sha و force=false استفاده شود.
- PRها Draft بمانند تا اجازه صریح کاربر.
- Merge، Deploy، Migration، Seed، cleanup و عملیات مخرب بدون اجازه ممنوع.
- هر مسئله مستقل: reproduce ← root cause ← کم‌دامنه change ← regression test ← report.
- ممنوع: reset، clean، stash، rebase، force-push، history rewrite و حذف فایل ناشناخته.

## 9. UI و Metronic

پیاده‌سازی در PR #16 است؛ CI موفق اما مرورگر واقعی هنوز توسط کاربر پذیرفته نشده. تست دستی: login/logout، منوهای نقش‌محور، collapse/drawer، theme persistence، search، dropdownها، فرم، جدول، pagination، chart، print، responsive و نبود asset 404.

مجوز خریداری‌شده Metronic برای ITAM راستی‌آزمایی نشده است. اطلاعیه همراه نسخه مرجع برای هر deployment/project مجوز جداگانه و برای SaaS پولی Extended License را ذکر می‌کند؛ پیش از عرضه تجاری سند خرید/شرایط مجوز بررسی شود.

## 10. Backlog

### P0 — قبل از تست محلی
- دریافت وضعیت branch/HEAD/status از سیستم کاربر.
- حفاظت DB backup و CSVهای reconciliation.
- همگام‌سازی امن به head UI پس از بررسی working tree.
- پذیرش بصری/عملکردی Metronic در مرورگر.
- تست نقش‌ها و scope واقعی.

### P1 — امنیت و صحت داده
- cross-province/county/center و inactive organization.
- invariant بین county province و TreatmentManagement province.
- قرارداد استانی چندمرکزی و انتساب فعال.
- Admin immutability و direct endpoint.
- HWAgent credential binding.
- export scope و formula injection.
- private media authorization.

### P2 — پذیرش محصول و عملیات
- چرخه تیکت، SLA، بازدید، قرارداد، تعمیر مستقل، ارجاع و گزارش.
- Persian/Jalali dates و تعطیلات.
- backup/restore در محیط ایزوله.
- private media و reverse proxy.
- logging، monitoring و secret rotation.

### P3 — آینده
- هاست/Production و PostgreSQL deployment.
- نرمال‌سازی جغرافیای شهر/محله و provenance مراکز.
- معماری frontend مستقل.
- قابلیت‌های خارج از MVP.

## 11. سطح اطمینان تست

- PR #15 CI: 5/5 job موفق؛ 372 تست در Python 3.11 و 3.12 و PostgreSQL 16.
- PR #16 CI: run 44161472256 روی head 23dbebb...، 5/5 job موفق؛ 375 تست در Python 3.11 و 3.12، PostgreSQL 16، production settings و deploy validation.
- تست محلی کاربر، مرورگر، Windows/HWAgent، شبکه واقعی، private media و UAT هنوز بازند.
- هیچ ادعای Production-ready بودن مجاز نیست.

## 12. شروع نشست بعد

ابتدا PRها و headهای زنده را بررسی کنید. سپس فقط این خروجی‌های امن را از کاربر بگیرید؛ پیش از بررسی status هیچ switch/checkout انجام نشود:

~~~powershell
git branch --show-current
git log -1 --oneline
git status --short
~~~

پس از بررسی خروجی، برنامه امن fetch/switch به ui/metronic9-django-rtl ارائه شود. در مرحله UI هیچ Migration یا Seed لازم نیست.

## 13. اسناد مرتبط
فهرست کامل در docs/README.md است. نسخه 1.2 و اسناد معماری/امنیت قبلی را به‌عنوان سابقه حفظ کنید.


## 14. تصمیم جدید — مستندسازی هم‌زمان (2026-11-18)

**وضعیت:** Accepted  
**مرجع:** Decision Log، شناسه D-2026-11-18-001

به‌روزرسانی مستندات مرتبط از این تاریخ بخشی از Definition of Done است. پس از هر تصمیم، تغییر فنی، تست یا تحویل مرحله‌ای، دستیار باید بدون درخواست اجازه جداگانه:
- تصمیم و دلیل آن را در Decision Log ثبت کند.
- اسناد حوزه‌ای و در صورت لزوم سند جامع/Backlog را به‌روز کند.
- branch، commit، PR، CI، تست‌های محلی و تست‌های انجام‌نشده را دقیق ثبت کند.
- نسخه‌های قبلی و سابقه تصمیم‌ها را حفظ کند.

این اختیار صرفاً برای مستندسازی و commit امن اسناد در شاخه مناسب است؛ مجوز Merge، Deploy، Migration، Seed یا عملیات مخرب نیست.


## 15. وضعیت اصلاح cascade رابط کاربری — 2026-11-18

- PR #19 با عنوان «Fix Metronic and legacy CSS cascade priority» ایجاد شده است؛ Draft، باز و Merge نشده.
- شاخه: `fix/metronic-legacy-css-cascade`.
- head: `dccd73e2e11092850a1b5b94e73a7b3da5e54a49`.
- base: `ui/metronic9-django-rtl` (head ثبت‌شده PR #16: `23dbebb19493cb9947c685c069adf205039412a9`).
- فایل تغییرکرده: `static/css/itam.css`؛ کل CSS سازگاری قدیمی داخل `@layer base` قرار گرفته است. selectorها و قواعد قدیمی حذف نشده‌اند.
- علت: Metronic/Tailwind 4 layerهای `theme, base, components, utilities` را تعریف می‌کند؛ قواعد عادی unlayered در stylesheet قدیمی می‌توانستند بر قواعد داخل layer غلبه کنند.
- `static/css/itam-metronic.css` همچنان بدون layer است تا bridge اختصاصی ITAM اولویت نهایی خود را حفظ کند.
- نتیجه مورد انتظار: utility/componentهای Metronic اولویت cascade مناسب‌تری نسبت به قواعد legacy پیدا کنند، درحالی‌که کلاس‌های قدیمی مورد استفاده Django templates باقی بمانند.
- **سطح اطمینان:** اصلاح ساختاری پیاده‌سازی شده؛ CI برای head PR #19 در زمان ثبت نتیجه‌ای نداشت؛ تست محلی، مرورگر و پذیرش بصری هنوز انجام نشده‌اند.
- **محدودیت:** رفع این تعارض لزوماً تمام ایرادهای layout را برطرف نمی‌کند. dashboard، asset list، فرم‌ها، login، responsive، dark mode و print باید در مرورگر بررسی شوند.
- جزئیات تصمیم در `docs/project/DECISION_LOG.md` با شناسه D-2026-11-18-002 و سند UI در `docs/project/07_UI_UX_AND_METRONIC.md` ثبت شده است.


---

## 16. الحاقیه نسخه 1.5 — تکمیل مرحله UI/Metronic و وضعیت جاری (2026-11-19)

این الحاقیه وضعیت PRهای UI را پس از PR #16 ثبت می‌کند؛ نسخه 1.4 و تاریخچه قبلی حفظ شده‌اند.

### 16.1 زنجیره UI در GitHub

تمام PRهای زیر در آخرین بازبینی باز، Draft و Merge نشده‌اند. هیچ‌کدام به معنی پذیرش مرورگر یا Merge نیستند.

| PR | موضوع | شاخه head | وضعیت CI ثبت‌شده |
|---|---|---|---|
| #15 | تثبیت Integration QA و امنیت | `fix/integration-qa-security-workflow` | موفق، 5 job |
| #16 | ادغام Metronic 9 RTL | `ui/metronic9-django-rtl` | موفق، 5 job |
| #19 | اولویت cascade CSS قدیمی و Metronic | `fix/metronic-legacy-css-cascade` | اجرای کامل موفق روی همان head ثبت شده |
| #20 | هم‌ترازی عرض Sidebar و محتوا | `fix/metronic-single-sidebar-width` | اجرای کامل موفق روی همان head ثبت شده |
| #21 | دسترس‌پذیری پوسته و ناوبری موبایل | `ui/metronic-shell-accessibility` | اجرای کامل موفق روی همان head ثبت شده |
| #22 | بازطراحی داشبورد | `ui/dashboard-metronic-redesign` | موفق، 5 job |
| #23 | صفحات عملیاتی دارایی/تیکت/نگهداری | `ui/operational-pages-metronic-redesign` | اجرای کامل موفق روی همان head ثبت شده |
| #24 | مهاجرت سراسری templateها و حذف selectorهای shell قدیمی | `ui/metronic-full-migration-legacy-cleanup` | موفق، 5 job |
| #25 | چاپ، HWAgent و partialهای مشترک | `ui/metronic-print-hwagent-finalization` | CI مجدد در انتظار نتیجه |

PRهای #17 (مستندات) و #18 (private media و scope انتساب پیمانکار) شاخه‌های موازی مبتنی بر PR #16 هستند؛ در زنجیره UI شماره 19 تا 25 قرار ندارند و باید مستقل بازبینی شوند.

### 16.2 PR #25 — تکمیل لایه نمایش

- PR: https://github.com/moghasemi/ITAM/pull/25
- head فعلی در زمان ثبت: `94005a451252b501b5667edf3ca87ad8fbbb9f50`
- base: `ui/metronic-full-migration-legacy-cleanup` (PR #24)
- وضعیت: Draft، باز، Merge نشده.
- 14 فایل تغییرکرده؛ 355 افزودن و 300 حذف در آخرین snapshot.
- تغییرات:
  - برچسب دارایی با اندازه 62×42mm؛ صفحه A4 عمودی با حاشیه 9mm و سه ستون با فاصله 3mm. عرض مفید 192mm است: سه برچسب 62mm و دو فاصله 3mm.
  - برگه بازدید و تیکت با صفحه A4 افقی، جزئیات، جدول‌ها، تاریخچه و محل امضا.
  - حذف پوسته، پیام‌های موقت و عنوان/پابرگ نمایشی از خروجی چاپ برچسب.
  - هم‌راستاسازی HWAgent مستقل با زبان بصری Metronic؛ تب‌های ARIA/keyboard و حذف Chart.js CDN با meterهای سبک RAM/دیسک.
  - partialهای مشترک فرم، فیلتر، صفحه‌بندی، formset، پیام‌ها، empty state و action button به hookهای Metronic مجهز شده‌اند.
  - کلاس‌های سازگاری و data-hookهای قدیمی لازم برای رفتار Django/JavaScript حفظ شده‌اند.
- CI نهایی run `44403052061` روی head `94005a451252b501b5667edf3ca87ad8fbbb9f50` completed/success و 5/5 job موفق است: Python 3.11 و 3.12 هرکدام 393 تست؛ PostgreSQL 16 تعداد 393 تست با 3 skipped؛ production settings و deploy-script validation نیز موفق. شکست قبلی ناشی از نبود `itam_tags` در formset بود و اصلاح شد.
- workflow موجود، JavaScript درون HWAgent را با `node --check` بررسی می‌کند؛ این syntax check جایگزین اجرای واقعی Windows agent نیست.
- هیچ view، model، URL، permission، workflow دامنه‌ای، migration، داده یا vendor asset در PR #25 تغییر نکرده است.

### 16.3 مواردی که همچنان باز هستند

- پذیرش واقعی مرورگر: RTL، viewportهای 1365/1024/768/390، روشن/تاریک، keyboard/focus، dropdown، فرم‌ها، فیلتر، pagination، جدول‌ها و نبود خطای console/asset 404.
- چاپ واقعی و PDF: مقیاس 100%، ابعاد برچسب، کیفیت QR، حاشیه چاپگر، شکستن صفحات و امضاها.
- اجرای HWAgent روی Windows: نصب، token issuance/transfer، initial sync، snapshot، rotate/suspend/revoke و recovery.
- حذف کامل CSS سازگاری legacy هنوز انجام نشده؛ این کلاس‌ها مصرف‌کننده دارند و حذف آن‌ها نیازمند مهاجرت معنایی و آزمون است.
- مجوز خریداری‌شده Metronic برای deployment تجاری ITAM هنوز بررسی نشده است.
- PRهای #15 تا #25 هنوز Merge نشده‌اند؛ ترتیب و وابستگی baseها باید پیش از Merge مجدداً بررسی شود.

### 16.4 قواعد ادامه

1. تا دسترسی محلی کاربر، فقط کارهای repository-side، تست CI و مستندسازی انجام شوند.
2. PR #25 تا موفق‌شدن CI روی head فعلی Draft بماند.
3. هیچ PRی بدون اجازه صریح Merge نشود؛ هیچ Deploy انجام نشود.
4. هیچ migration، seed، reconcile --apply یا Outbox dispatch اجرا نشود.
5. هنگام بازگشت دسترسی محلی، ابتدا branch/HEAD/status بررسی شود؛ سپس sync امن و پذیرش مرورگر/کارکردی آغاز شود.
6. هاست و Production همچنان Deferred هستند.



---

## 17. الحاقیه ممیزی فاز صفر — دور دوم (2026-11-19)

نقشه‌راه رسمی فازهای صفر تا پنج در docs/project/13_PHASED_ROADMAP_AND_EXECUTION.md ثبت شده است. این الحاقیه وضعیت تازه GitHub را ثبت می‌کند و جایگزین تاریخچه قبلی نیست.

- Snapshot: 18 PR باز و Draft؛ 7 PR بسته؛ 5 مورد از بسته‌ها Merge و 2 مورد بسته بدون Merge.
- CI روی headهای 18 PR باز: 17 موفق و #14 ناموفق. PR #10 بسته و CI آن ناموفق است.
- PR #12 از head PR #10 منشعب شده؛ commitهای #10 در ancestry #12 حضور دارند.
- PR #13 نسبت به base خودش diverged (40 ahead / 7 behind) و mergeable=false/dirty است. PR #14 patchهای فرم مرکز و تست‌های #13 را نیز دارد؛ #13 باید تا تعیین تکلیف به‌عنوان duplicate/stale candidate باقی بماند.
- علت شکست PR #14 در لاگ CI، اختلاف تست‌ها با approval gate گردش GeneralITRequest بود؛ PR #15 روی head خودش CI موفق دارد.
- PR #17 head c6cf538644815fe178673edbea3497f92a79811c، run 44485800684 موفق.
- Branch Protection برای main با 403 قابل خواندن نبود؛ required checks تأیید نشده‌اند.
- بازبینی کد فعلی گزینشی است: migration و TreatmentManagement/Center.save، HWAgent credential checks، trusted proxy/login throttle، Outbox permissions، reconciliation command و private media بررسی اولیه شده‌اند؛ این به معنی تأیید کامل امنیت یا پذیرش نیست.
- هیچ Merge، Deploy، Migration، Seed، reconciliation apply یا Outbox dispatch انجام نشده است.


### اصلاحیه ممیزی PR #13/#14 (2026-11-19)
- تطبیق hash 25 فایل PR #13 با head PR #14: 12 فایل یکسان، 13 فایل متفاوت.
- PR #13 duplicate کامل نیست؛ partially overlapping و diverged است. 13 فایل متفاوت نیازمند بررسی معنایی‌اند. از بستن/حذف آن پیش از این بررسی خودداری شود.


### 18. تکمیل ancestry PRهای #10 تا #14 (2026-11-19)
- head PR #10 ancestor شاخه #11 است (ahead 142 / behind 0) و #14 فرزند #11 است؛ commitهای #10 از مسیر #11/#14 حفظ شده‌اند.
- PR #12 با PR #14 از 19 فایل، 12 محتوای یکسان و 7 متفاوت دارد. PR #13 با PR #14 از 25 فایل، 12 محتوای یکسان و 13 متفاوت دارد.
- #12/#13 نباید جداگانه و کور Merge شوند؛ deltaهای مفقود باید با مسیر #14 تطبیق داده شوند.
- مسیر محتمل اصلی: #7 → #8 → #9 → #11 → #14 → #15 → #16؛ برنامه نهایی Merge هنوز باز است.


### 19. ممیزی گزینشی scope و HWAgent — 2026-11-19
- head PR #15، scope مراکز غیرکشوری را به مرکز/شهرستان/استان فعال و consistency TreatmentManagement محدود می‌کند؛ تکنسین به قرارداد و انتساب فعال مرکز محدود است.
- API HWAgent توکن hash، timestamp، nonce، asset/center/hostname binding و active geography را enforce می‌کند؛ legacy credential بدون asset binding fail-closed است.
- Outbox dispatch/requeue به POST و country-admin محدود است؛ Adminهای Ticket و Repair workflow read-only هستند.
- موارد باز: Center.clean/save mismatch، atomicity/concurrency ایجاد TreatmentManagement، trusted proxy واقعی، replay/race UAT و ممیزی کامل IDOR/export/admin/private media. این بررسی security sign-off نیست.

### 20. نتیجه مقایسه معنایی PRهای #12 و #13 با #14 — 2026-11-19

- هفت فایل متفاوت PR #12 با head PR #14 از نظر رفتار بررسی شدند؛ کنترل taxonomy سراسری، settings/holidays، audit log scope، بازخورد تعمیر و قراردادهای قابل مشاهده در #14 حضور دارند.
- سیزده فایل متفاوت PR #13 بررسی شدند؛ private media cache-control/404، seed و TreatmentManagement، فرم مرکز، SQLite-only test guards، visibility repair/general IT، notification/state guard و delegation viewها در #14 وجود دارند یا با منطق کامل‌تری جایگزین شده‌اند.
- مسیر visible_contracts در service متمرکز شده و دسترسی مرکز/شهرستان به قرارداد را به assignment فعال و تاریخ‌دار محدود می‌کند؛ Province Admin مسیر استانی جداگانه دارد.
- workflow درخواست عمومی IT در #14 manager approval gate را نیز اعمال می‌کند؛ تغییر ساده‌تر PR #13 نباید روی این منطق جایگزین شود.
- اختلاف cleanup stream در تست private media یک موضوع test hygiene باقی می‌ماند و delta عملکردی محسوب نمی‌شود.
- نتیجه: در فایل‌های بررسی‌شده delta عملکردیِ مفقودی برای port مستقل از #12/#13 شناسایی نشد. PR #13 همچنان branch diverged/dirty است و این نتیجه مجوز بستن یا Merge آن نیست.
- CI آخرین commit مستندات PR #17، run 44488869040، completed/success است.
- هیچ تغییر کد برنامه یا عملیات DB/Seed/Migration/Reconciliation/Outbox انجام نشده است.


### 21. وضعیت حفاظت شاخه main — 2026-11-19
- GitHub API برای main مقدار protected=false و protection.enabled=false گزارش کرد.
- required status checks خاموش و بدون context/check بودند؛ repository rulesets نیز خالی بود.
- این یک ریسک governance پیش از Merge است؛ فعال‌سازی branch protection و required CI checks توصیه می‌شود. هیچ تنظیم مخزن تغییر داده نشد.


### 22. بررسی تکمیلی مجوز پیوست ارجاع و CI مستندات — 2026-11-19

- CI آخرین head مستندات PR #17 (`0f38834f467776c69b8baf6109b369fa6be20d9f`) تکمیل شد: push run `44494487453` و pull_request run `44494500448`، هر کدام 5/5 job موفق.
- CI head PR #18 (`130bb091caf7c751f0ca6d406d93afa83528259a`) در run `44174205183` با 5/5 job موفق است.
- بررسی کد PR #18 نشان داد `private_media` در مسیر `referrals/` برای هر کاربر دارای مرکز در scope، امکان دانلود فایل ارجاع را می‌دهد؛ اما فهرست ارجاع برای manager/requester غیرگیرنده فقط `recipient_user=request.user` را نمایش می‌دهد.
- این اختلاف می‌تواند دسترسی مستقیم به پیوست را برای manager/requester هم‌مرکز یا هم‌استان، در صورت دانستن مسیر فایل، ممکن کند. شدت اولیه P2؛ اصلاح باید با یک visibility service مشترک و تست‌های منفی/مثبت نقش‌محور انجام شود.
- تست‌های موجود private media، admin IT هم‌مرکز و کاربر مرکز دیگر را پوشش می‌دهند؛ manager/requester غیرگیرنده را پوشش نمی‌دهند.
- این دور فقط audit و documentation بود؛ کد برنامه تغییر نکرد. سایر مسیرهای IDOR/export/Admin/media و UAT وب‌سرور واقعی همچنان باز هستند.


### 23. یافته‌های تکمیلی authorization و overlap — 2026-11-19

- CI commit قبلی مستندات `1f370bb3798367bacb8feceff2a3feca8ddefc78` با push run `44495868255` و PR run `44495875141`، هر دو 5/5 job موفق، تأیید شد.
- در `private_media`، مسیر `signatures/` برای کاربران هم‌مرکز گسترده‌تر از endpoint owner-only `signature_file` است؛ نیازمند تعیین سیاست و یکسان‌سازی.
- endpointهای `ticket_add_part` و `ticket_add_attachment` در backend فقط visible ticket را کنترل می‌کنند و permission متناظر با شرط `is_manager_side` در template را enforce نمی‌کنند؛ direct POST از requester/نقش فاقد مجوز باید با تست رد شود.
- اسکن filenameها نشان داد PRهای #17 و #18 با زنجیره UI #19–#25 مسیر مشترک ندارند؛ هم‌پوشانی درون زنجیره UI از ancestry شاخه‌های فرزند است.
- این‌ها یافته‌های code review با شدت اولیه P2 هستند؛ exploit یا UAT محیط عملیاتی اجرا نشده است. اصلاح کد و regression tests در فاز یک باز می‌ماند.
