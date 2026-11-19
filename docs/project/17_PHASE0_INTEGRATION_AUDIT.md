# ITAM — گزارش ممیزی فاز صفر و آمادگی یکپارچه‌سازی

**تاریخ snapshot:** 2026-11-19  
**Repository:** https://github.com/moghasemi/ITAM  
**مبنای کد ممیزی:** شاخه‌های PR و headهای ثبت‌شده در GitHub؛ نه checkout محلی یا Production  
**وضعیت:** ممیزی ریموت تا حد زیادی تکمیل؛ ادغام و پذیرش محلی انجام نشده است.

## 1. خلاصه اجرایی

در snapshot این گزارش 24 PR باز (#7 تا #31 به‌جز #10) وجود دارد. CI آخرین head برای 23 PR موفق و برای PR #14 ناموفق است. PR #31 نیز پس از اصلاحات امنیتی، هر پنج job را با موفقیت گذرانده است.

شاخه main محافظت نشده است: Branch Protection غیرفعال، Required Checks خالی و Repository Ruleset وجود ندارد. این وضعیت پیش از هر Merge باید با تصمیم مالک اصلاح شود.

**هیچ PR ادغام، هیچ Deploy، هیچ Migration، Seed، reconciliation، تغییر داده یا Outbox dispatch انجام نشده است.**

## 2. گراف وابستگی PRها

```
main
└── #7 feature/separate-org-geography
    └── #8 feature/itam-mvp-buildout
        └── #9 feature/itam-mvp-workflow-integrity
            └── #11 fix/itam-hardware-contractor-boundary
                └── #14 integration/itam-v1.1-qa
                    └── #15 fix/integration-qa-security-workflow
                        └── #16 ui/metronic9-django-rtl
                            ├── #17 docs/itam-project-handbook-v1.3
                            ├── #18 fix/private-media-and-assignment-scope
                            └── #19 → #20 → #21 → #22 → #23 → #24
                                → #25 → #26 → #27 → #28 → #29 → #30

#31 security/p2-authorization-hardening
└── base: head فعلی PR #15 (شاخه fix/integration-qa-security-workflow)
```

### نکات ancestry
- PR #10 در 2026-11-14 بسته شد و Merge نشد؛ head آن ancestor شاخه #11 و شاخه #12 است. بنابراین تغییرات commitهایش در ancestry حفظ شده‌اند.
- PR #12 بر شاخه PR #10 بنا شده و mergeable=true است، اما با مسیر #14/#15 هم‌پوشانی دارد؛ Merge مستقل آن توصیه نمی‌شود.
- PR #13 نسبت به base خود 40 commit جلو و 7 commit عقب است؛ status=diverged و mergeable=false. Merge مستقل ممنوع/متوقف بماند.
- PR #14 پایه PR #15 است، اما CI مستقل آن قرمز است. head PR #15 که شامل ancestry #14 به‌علاوه اصلاحات بعدی است، CI سبز دارد.
- PR #17 و #18 شاخه‌های موازی بر #16 هستند؛ UI از #19 تا #30 به‌صورت زنجیره‌ای stacked است.
- PR #31 بر پایه #15 و sibling شاخه #16 است؛ قبل از ادغام باید ترتیب ورود آن به زنجیره و به‌روزرسانی امن شاخه‌های فرزند مشخص شود.

## 3. وضعیت CI آخرین headها

| PR | نتیجه آخرین CI | نکته |
|---:|---|---|
| #7–#9 | موفق | مسیر پایه جغرافیا و MVP |
| #11–#13 | موفق | #13 با وجود CI سبز، diverged است |
| #14 | ناموفق | سه error و یک failure در تست‌های گردش درخواست عمومی IT |
| #15–#30 | موفق | همه jobهای آخرین head مشاهده‌شده موفق |
| #31 | موفق | run 44540345588، پنج از پنج job |

### شکست PR #14
در logهای Python 3.11، Python 3.12 و PostgreSQL موارد زیر دیده شد:
- `test_general_request_bypass_requires_reason_and_is_audited`: خطای ValidationError درباره لزوم تعیین تکلیف تایید مدیر.
- `test_manager_approval_is_optional_when_bypass_reason_is_recorded`: همان خطای ValidationError.
- `test_stale_manager_review_cannot_replace_first_decision`: assertion اختلاف وضعیت `assigned` و `approved`.
- تست seed داده نمونه نیز به علت همان قاعده تخصیص با خطا مواجه شد.

PR #15 روی head `4ce9e0d96a8446622a4bf2c5fc7c1da405cd76ad` هر پنج job را موفق گذرانده است. بنابراین PR #14 را به‌تنهایی Merge نکنید؛ ابتدا باید یک واحد ادغام‌شده با اصلاحات PR #15 و CI سبز ساخته شود.

### CI PR #31
- head: `6ed9e53c8aa13c7984057613c5de1966be9785f9`
- run: `44540345588`
- نتیجه: `test (3.11)`, `test (3.12)`, `postgres-test`, `production-settings-check`, `deploy-script-validation` همگی success.
- PR باز، Draft و mergeable=true است.

## 4. Branch Protection و سیاست Merge

مشاهده مستقیم metadata شاخه main:
- `protected=false`
- Required Status Checks: هیچ موردی
- Repository Rulesets: خالی

**توصیه:** پیش از Merge، protection برای main فعال و Required Checks حداقل روی این پنج job تنظیم شود:
1. test (3.11)
2. test (3.12)
3. postgres-test
4. production-settings-check
5. deploy-script-validation

هیچ تنظیمی تغییر نکرده است. این اقدام به تصمیم و مجوز صریح مالک نیاز دارد.

### ترتیب پیشنهادی
1. تعیین تکلیف PR #12/#13؛ از Merge مستقل PR #13 خودداری شود.
2. PR #14 و #15 به‌عنوان یک واحد integration با CI سبز بررسی شوند؛ PR #14 به‌تنهایی وارد main نشود.
3. PR #31 به‌عنوان اصلاح امنیتی مبتنی بر #15 در برنامه integration لحاظ شود؛ چون sibling شاخه #16 است، به‌روزرسانی فرزندان باید فقط با merge commitهای غیرتخریبی و CI مجدد انجام شود؛ rebase/force push ممنوع.
4. پس از تثبیت #15، PR #16 و سپس مسیرهای #17/#18 و #19 تا #30 به ترتیب ancestry بررسی شوند.
5. Merge نهایی فقط با اجازه صریح مالک.

## 5. ماتریس خلاصه نقش و دامنه

| نقش | دامنه پایه | مرزهای مهم |
|---|---|---|
| مدیر کشوری / Superuser | کل سامانه | برخی عملیات حساس مانند Outbox همچنان endpoint-specific هستند |
| مدیر استان | مراکز فعال استان | تطبیق استان قرارداد با مدیریت درمان مرکز؛ دامنه نامعتبر fail-closed |
| مدیر شهرستان | مراکز فعال شهرستان | محدود به county معتبر |
| کارشناس IT مرکز | مرکز فعال منتسب | مدیریت دارایی و عملیات IT در مرکز |
| مدیر/ناظر مرکز | مشاهده و گزارش مرکز | mutation با کارشناس IT یکسان نیست؛ `can_manage_ticket` برای manager false است |
| تکنسین پیمانکار | قرارداد فعال + انتساب صریح مرکز | تطبیق پیمانکار، استان، مرکز، تاریخ و نوع خرابی؛ بدون دسترسی به repair request مستقل |
| درخواست‌کننده | داده‌های خود در مرکز | تیکت‌های مرتبط، دارایی‌های امانت‌داری‌شده و درخواست‌های شخصی؛ ارجاع فقط در صورت recipient بودن |

نقش‌های بالادست در `role_codes()` برخی قابلیت‌های نقش پایین‌تر را به ارث می‌برند. این جدول فقط خلاصه است؛ برای هر mutation باید endpoint و service همان عملیات بررسی شود.

## 6. Export، Admin و endpointها

### Reports و Export
- گزارش‌های SLA، کارنامه پیمانکار، عملکرد تعمیرکار مستقل، موجودی دارایی، انطباق بازدید و تحلیل خرابی از querysetهای scope-aware استفاده می‌کنند.
- `apps/reports/exports.py` مقادیر متنی آغازشونده با `=`, `+`, `-`, `@` را برای CSV/XLSX خنثی می‌کند.
- رخداد export با `log_action` ثبت می‌شود.

### Admin
در دامنه نمونه‌برداری‌شده:
- AuditLog read-only است.
- MaintenanceVisit و VisitAssetCheck از طریق Admin قابل تغییر/حذف نیستند.
- بخش‌های حساس Ticket به‌صورت readonly ارائه شده‌اند.
- SystemSetting تک‌نمونه است و delete ندارد.

### HWAgent
- توکن به‌صورت hash ذخیره/بررسی می‌شود.
- scope مرکز و active بودن زنجیره جغرافیایی کنترل می‌شود.
- timestamp با پنجره 300 ثانیه، nonce یکتا و ثبت اتمیک بررسی می‌شود.
- اندازه Content-Length و اندازه واقعی `request.body` کنترل می‌شود.
- credential بدون asset و hostname binding fail-closed است.
- تست Windows، قطع شبکه و نصب واقعی هنوز محلی است.

### Outbox
- مشاهده رخدادها scope-aware است.
- dispatch/requeue به POST و مدیر کشوری محدود شده است.
- Outbox dispatch واقعی اجرا نشده است.
- lease/lock و unique delivery در کد و Migration بررسی شده؛ رقابت واقعی در محیط مقصد همچنان UAT می‌خواهد.

## 7. Migration و داده

Migrationهای مهم مرورشده:
- `org.0005_contract_province_scope`: backfill قراردادهای استانی فقط وقتی مراکز قدیمی دقیقاً یک استان را مشخص کنند؛ RunPython reverse noop.
- `org.0006_treatment_management`: ایجاد مدیریت درمان و backfill مراکز از county→province؛ RunPython reverse noop.
- `org.0007` و `org.0009`: هم‌ترازی فیلد جغرافیایی و منسوخ‌شدن فیلد متنی استان.
- `org.0010_contract_center_assignment`: قید partial unique برای یک انتساب active به‌ازای هر مرکز.
- `accounts.0005_login_throttle_lock`: جدول قفل محدودسازی ورود.
- `assets.0006_agentcredential_asset_binding`: FK nullable به دارایی؛ endpoint credential فاقد binding را رد می‌کند.
- `integrations.0003_outboxdelivery_lease_lock`: token و زمان انقضای lease.

### ریسک و اقدام پیش از Migration
- reverse noop در دو data migration به معنی بازسازی رابطه‌های backfill‌شده در rollback نیست؛ rollback باید با backup و طرح بازسازی داده سنجیده شود.
- پیش از `org.0010`، duplicateهای assignment با status=active باید فقط‌خواندنی بررسی شوند؛ unique constraint در صورت وجود duplicate می‌تواند Migration را fail کند.
- credentialهای قدیمی HWAgent باید به asset و hostname معتبر bind شوند؛ nullable بودن فیلد به معنی مجازبودن credential بدون binding نیست.
- CI PostgreSQL با دیتابیس آزمایشی موفق است و جایگزین rehearsal روی کپی دیتابیس واقعی نیست.
- هیچ Migration یا DB mutation اجرا نشده است.

## 8. اصلاحات امنیتی در PR #31

PR #31 با 8 فایل تغییرکرده، بدون Migration یا تغییر URL:
1. تابع مشترک `visible_referrals` برای همسانی scope فهرست ارجاع و private media.
2. فایل امضای کاربر فقط برای مالک احرازشده.
3. افزودن قطعه و پیوست تیکت فقط با login، POST و `can_manage_ticket`.
4. `notification_read` فقط POST+CSRF؛ GET پاسخ 405 می‌دهد و state را تغییر نمی‌دهد.

هفت regression test افزوده شد. CI run `44540345588` هر پنج job را موفق گذراند. PR هنوز Draft و Merge نشده است.

## 9. یافته‌های باقیمانده

- تطبیق province در `Center.clean/save` در سطح مدل کنترل می‌شود؛ رفتار race هم‌زمان county/center و نیاز به تست/تصمیم تکمیلی باز است.
- در `assign_contractor_to_center` دو decorator متوالی `transaction.atomic` دیده شد؛ nested atomic عموماً بی‌خطر است، اما cleanup لازم است.
- اصلاح query string چاپ برچسب دارایی در backlog UX باقی است.
- در PRهای نمونه‌برداری‌شده review submission یا inline review thread دیده نشد؛ این به معنی approval نیست.
- در دامنه static بررسی‌شده P1 تازه‌ای مشاهده نشد؛ این ادعا به کل مخزن تعمیم داده نمی‌شود.

## 10. موارد نیازمند سیستم محلی

- مرورگر: RTL، responsive، dark mode، keyboard، screen reader و نقش‌های واقعی.
- چاپ: صفحات و برچسب دارایی.
- HWAgent: Windows، نصب، شبکه، replay و قطع/وصل.
- Reverse Proxy/TLS و trusted proxy.
- Backup/Restore و rehearsal Migration روی کپی دیتابیس واقعی.
- UAT نقش‌محور برای گردش تیکت، بازدید، قرارداد و Outbox.

## 11. وضعیت پایان فاز صفر

**از راه دور:** گراف PR، CI، Branch Protection، scope نقش‌ها، export/admin، endpointهای منتخب، Migrationهای مرتبط و اصلاحات P2/P3 اصلی بررسی شده‌اند.

**باز:** تصمیم ادغام #14/#15، تعیین تکلیف #12/#13، مجوز Branch Protection و مرور P3های باقیمانده.

**محلی:** تمام موارد بخش 10.

مرجع نقشه‌راه: `13_PHASED_ROADMAP_AND_EXECUTION.md`؛ دفتر روزانه: `14_DAILY_WORK_LOG.md`؛ وضعیت: `10_STATUS_AND_BACKLOG.md`.


## 12. بررسی نهایی CI مستندات و متادیتای Review

- commit مستندات: `720a8456b3694504a40866dd87ed3c08b7745afb`.
- PR #17 head جدید CI run `44541718233` هر پنج job را با موفقیت گذراند.
- متادیتای تمام 24 PR باز بررسی شد: هیچ Review Submission و هیچ Inline Review Thread ثبت نشده است؛ بنابراین هیچ PRی از این مسیر approval رسمی ندارد.
- conversation comments در PRهای #26 تا #31 نیز صفر بود.
- نتیجه: 23 از 24 PR باز CI سبز دارند؛ تنها PR #14 قرمز است. PR #31 و head فعلی PR #17 سبز هستند.

## 13. تنظیمات امنیتی Production و Reverse Proxy

بازبینی static `config/settings.py` و `apps/core/middleware.py`:
- در Production، `DEBUG=False`، `ITAM_SECRET_KEY` تصادفی با حداقل 50 نویسه و `ITAM_ALLOWED_HOSTS` صریح و بدون wildcard اجباری‌اند.
- Production فقط PostgreSQL را می‌پذیرد؛ SQLite برای توسعه/دمو است.
- کوکی‌های Session و CSRF به‌صورت پیش‌فرض Secure هستند؛ Session کوکی HttpOnly است. CSRF cookie عمداً HttpOnly نیست تا JS بتواند توکن را برای Fetch/AJAX بخواند.
- `TrustedProxyHeadersMiddleware` قبل از `SecurityMiddleware` قرار دارد و هدرهای Forwarded را از peerهای غیرمجاز حذف می‌کند.
- اعتماد به proxy بر اساس `ITAM_TRUSTED_PROXY_IPS` است؛ زنجیره X-Forwarded-For از راست به چپ پیمایش می‌شود و proxyهای trusted رد می‌شوند.
- در Production با فعال بودن proxy SSL header، HSTS پیش‌فرض یک‌ساله می‌شود؛ `SECURE_SSL_REDIRECT` به‌صورت پیش‌فرض خاموش است و TLS termination باید در proxy درست تنظیم شود.
- `ITAM_HSTS_INCLUDE_SUBDOMAINS` و `ITAM_HSTS_PRELOAD` پیش‌فرض True هستند؛ قبل از استقرار باید اطمینان حاصل شود تمام subdomainها HTTPS معتبر دارند.
- CI مربوط به production settings موفق است؛ صحت IP پراکسی، TLS واقعی، host/origin و رفتار redirect/HSTS فقط در UAT محلی/محیط استقرار قابل تأیید است.


---

## 14. به‌روزرسانی snapshot پس از ادامه ممیزی — 2026-11-19، ساعت 14:30 UTC

این بخش بر اطلاعات snapshotهای قبلی اولویت زمانی دارد؛ بخش‌های قبلی برای حفظ سابقه دست‌نخورده مانده‌اند.

### وضعیت PRهای باز
- تعداد PRهای باز در API فهرست‌شده: 26 (از #7 تا #33 به‌جز #10).
- PR #32: https://github.com/moghasemi/ITAM/pull/32 — Draft، stacked بر #31، head `60c7337e12d235c56c3925e56422f0fa5618bd7b`.
- PR #33: https://github.com/moghasemi/ITAM/pull/33 — Draft، stacked بر #30، head `f04726b4273466dae9f1df0c932639da0c177b67`.
- PR #32 در run `44543874381` هر پنج job را موفق گذراند: test 3.11، test 3.12، postgres-test، production-settings-check و deploy-script-validation.
- PR #33 در run `44544201157` هنگام ثبت این snapshot در حال اجرا بود؛ نتیجه نهایی هنوز تأیید نشده است.
- از 24 PR قبلی، #14 آخرین وضعیت شناخته‌شده CI قرمز و #15 تا #31 سبز بودند؛ #32 سبز و #33 در حال اجراست. این گزارش وضعیت #33 را success فرض نمی‌کند.

### اصلاحات تکمیلی
- در PR #32، `Center.save()` با `transaction.atomic` پوشانده شد تا ایجاد خودکار TreatmentManagement و ذخیره Center یک تراکنش باشند؛ regression test شکست درج مرکز و rollback مدیریت درمانی یتیم را می‌سنجد.
- decorator تکراری `transaction.atomic` در `assign_contractor_to_center` حذف شد؛ یک مرز تراکنش حفظ شده است.
- در PR #33، منطق فیلتر فهرست دارایی به queryset مشترک منتقل شد؛ فهرست و چاپ از یک فیلتر scope-aware استفاده می‌کنند. query string چاپ اصلاح و تست فیلتر چاپ اضافه شد.
- هیچ Migration، Seed، reconciliation، DB mutation، Outbox dispatch، Merge یا Deploy انجام نشده است.

### Branch Protection
- endpoint مربوط به Branch Protection در بررسی مجدد با 403 `Resource not accessible by integration` پاسخ داد؛ بنابراین وضعیت مستقیم protection در این نوبت قابل تأیید مجدد نبود.
- endpoint فهرست Repository Rulesets آرایه خالی برگرداند.
- آخرین مشاهده مستقیم قبلی در همین تاریخ `protected=false` و Required Checks خالی بود؛ این نتیجه را به‌عنوان آخرین snapshot شناخته‌شده نگه دارید، نه تأیید تازه.
- هیچ تنظیم Branch Protection یا Ruleset تغییر نکرد.

### موارد باقیمانده
- بررسی race هم‌زمان بین تغییر county و ایجاد/ویرایش center هنوز به تست concurrency روی PostgreSQL و تصمیم نهایی نیاز دارد؛ atomicity PR #32 فقط rollback ایجاد TreatmentManagement را پوشش می‌دهد.
- ماتریس endpoint×role هنوز نمونه‌ای است و باید برای تمام mutationها تکمیل شود.
- UAT محلی و تست چاپ واقعی طبق Runbook بخش 10 و سند `18_LOCAL_UAT_RUNBOOK_2026-11-19.md` باقی است.
