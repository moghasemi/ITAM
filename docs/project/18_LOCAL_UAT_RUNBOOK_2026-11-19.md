# ITAM — Runbook پذیرش محلی سه‌ساعته
**تاریخ تهیه:** 2026-11-19  
**هدف:** استفاده مؤثر از یک نوبت دسترسی سه‌ساعته به یک سیستم Windows با دیتابیس توسعه SQLite.  
**اصل ایمنی:** این Runbook مجوز Migration، Seed، reset، reconciliation apply، Outbox dispatch یا تغییر داده‌های واقعی نیست.

## 1. برنامه زمانی پیشنهادی

| زمان | فعالیت | خروجی |
|---|---|---|
| 00:00–00:15 | پیش‌پرواز و بررسی وضعیت Git/DB | تعیین مسیر امن تست |
| 00:15–00:45 | تست خودکار regression روی شاخه PR #32 | atomicity مرکز و آزمون امنیت PR #31 |
| 00:45–01:15 | تست خودکار regression روی شاخه PR #33 | فیلتر چاپ برچسب |
| 01:15–02:15 | مرورگر و نقش‌ها | RTL، منو، فهرست، فیلتر، چاپ، فایل خصوصی |
| 02:15–02:45 | workflow کوتاه و HWAgent در صورت آماده بودن محیط | گزارش موفق/ناموفق |
| 02:45–03:00 | جمع‌آوری شواهد و ثبت نتیجه | فهرست باگ‌ها و تصمیم بعدی |

اگر پیش‌پرواز نشان داد working tree تغییرات ثبت‌نشده دارد، هیچ switch/checkout نکنید. وضعیت را گزارش کنید و ابتدا محیط تست جدا بسازید.

## 2. پیش‌پرواز — فقط خواندنی

در PowerShell، از پوشه مخزن اجرا شود:

~~~powershell
git branch --show-current
git log -1 --oneline
git status --short
git remote -v
python --version
python manage.py check
~~~

خروجی چهار دستور Git و نسخه Python و نتیجه check را نگه دارید. اگر `git status --short` خروجی دارد، فایل‌ها را حذف، stash یا reset نکنید. قبل از هر تغییر شاخه، وضعیت بررسی شود.

مسیر دیتابیس را بدون چاپ Secretها می‌توان با دستور زیر بررسی کرد:

~~~powershell
python manage.py shell -c "from django.conf import settings; d=settings.DATABASES['default']; print(d['ENGINE']); print(d['NAME'])"
~~~

اگر قرار است تست مرورگر روی دیتابیس موجود داده ایجاد کند، ابتدا از فایل SQLite فعال یک کپی پشتیبان جداگانه بگیرید. مسیر و نام فایل را از تنظیمات واقعی استخراج کنید؛ نام دیتابیس را حدس نزنید.

## 3. محیط‌های تست مستقل

PR #32 و PR #33 از دو زنجیره متفاوت آمده‌اند؛ آن‌ها را در یک checkout با هم ترکیب نکنید. پس از تأیید clean بودن وضعیت Git و وجود remote مناسب، دو worktree جدا بسازید تا working tree اصلی دست‌نخورده بماند:

~~~powershell
git fetch origin
git worktree add --detach ..\ITAM-uat-center origin/fix/center-save-atomicity
git worktree add --detach ..\ITAM-uat-label origin/fix/asset-label-print-filters
~~~

اگر نام remote، branch یا مسیر با سیستم شما متفاوت است، قبل از اجرا متوقف شوید و خروجی را بفرستید. برای حذف worktree از `git worktree remove` استفاده نکنید مگر بعد از اطمینان از نبود هرگونه فایل محلی ارزشمند؛ حذف worktree در این جلسه ضروری نیست.

## 4. تست‌های خودکار

### محیط PR #32 — شامل PR #31

~~~powershell
cd ..\ITAM-uat-center
python manage.py test apps.org.tests_center_form.CenterFormProvinceCountyTests.test_failed_center_insert_rolls_back_auto_created_treatment_management
python manage.py test apps.core.tests_notifications apps.core.tests_private_media apps.tickets.tests
~~~

معیار قبولی:
- تست atomicity سبز شود و پس از شکست ذخیره مرکز، TreatmentManagement یتیم باقی نماند.
- GET اعلان 405 بدهد و وضعیت خوانده‌شدن تغییر نکند؛ POST مجاز وضعیت را تغییر دهد.
- دانلود امضای کاربر فقط برای مالک مجاز باشد.
- requester نتواند با POST مستقیم قطعه یا پیوست تیکت ثبت کند.
- کاربر هم‌مرکز فاقد مجوز نتواند فایل ارجاع خارج از worklist خود را دانلود کند.

### محیط PR #33 — زنجیره UI

~~~powershell
cd ..\ITAM-uat-label
python manage.py test apps.assets.tests.AssetScopeAndRelationshipTests.test_label_print_uses_the_same_filters_as_asset_list
~~~

معیار قبولی:
- لینک چاپ query string را با `?` منتقل کند.
- چاپ، همان فیلترهای فهرست را اعمال کند و دارایی خارج از scope کاربر وارد خروجی نشود.
- در صورت موفقیت تست هدفمند، در صورت داشتن زمان اجرای کل suite نیز انجام شود:

~~~powershell
python manage.py test
~~~

Django test runner باید از test database ایزوله استفاده کند. اگر خروجی نشان داد به دیتابیس واقعی وصل شده یا ساخت test DB شکست خورده است، ادامه ندهید.

## 5. پذیرش مرورگر — PR #33

با حساب آزمایشی کارشناس IT مرکز:
1. وارد فهرست دارایی‌ها شوید و یک عبارت یکتا در جستجو وارد کنید.
2. تعداد/شماره اموال نتایج را یادداشت کنید.
3. «چاپ برچسب QR» را در تب جدید باز کنید.
4. بررسی کنید URL دارای query string معتبر باشد و فقط نتایج همان فیلتر چاپ شوند.
5. یک بار فیلتر مرکز/گونه/وضعیت را نیز امتحان کنید.
6. چاپ یا PDF را با مقیاس 100% بررسی کنید: اندازه برچسب 62×42mm، حاشیه، QR، برش صفحات و تعداد برچسب‌ها.

## 6. پذیرش امنیتی — PR #31/#32

با حساب‌های آزمایشی و فایل‌های غیرحساس:
- requester در برابر POST مستقیم افزودن قطعه و پیوست تیکت باید 403 بگیرد.
- GET مسیر خواندن اعلان باید 405 باشد و اعلان unread بماند.
- مالک امضا باید فایل خودش را ببیند؛ کاربر هم‌مرکز و مدیر کشوری نباید امضای شخص دیگر را دریافت کنند.
- فایل ارجاعی که در worklist کاربر نمایش داده نمی‌شود نباید از مسیر private media قابل دانلود باشد.
- مسیرهای نامجاز باید 403 یا 404 مورد انتظار بدهند؛ فایل واقعی یا مسیر storage را در screenshot ثبت نکنید.

## 7. مرورگر و پوسته Metronic

حداقل viewportهای 1365، 1024، 768 و 390 پیکسل:
- login/logout و منوی نقش‌محور؛ فقط یک active item برای صفحه جاری.
- sidebar collapse و drawer موبایل؛ عدم قفل ماندن scroll.
- RTL، dark/light، جداول عریض و keyboard focus.
- فهرست دارایی، تیکت، بازدید و شناسنامه دارایی؛ تب‌ها با ArrowLeft/ArrowRight/Home/End.
- فرم‌ها: validation، فیلدهای وابسته، select و فایل.
- DevTools: Console بدون خطای جدید و Network بدون asset 404.

## 8. توقف‌ها و ممنوعیت‌ها

در این نوبت اجرا نکنید:
- `python manage.py migrate` یا هر migration دیگر.
- `seed_demo`، `seed_sistan_demo` یا هر seed.
- `reconcile_organizational_data --apply`.
- Outbox dispatch/requeue واقعی.
- `git reset`، `git clean`، `git stash`، rebase، force-push یا history rewrite.
- حذف فایل، رکورد واقعی، backup یا CSV reconciliation.

PR #32 و #33 هیچ migration جدیدی ندارند؛ بنابراین برای تست این دو تغییر، اجرای migrate لازم نیست.

## 9. قالب گزارش نتیجه

برای هر تست ثبت کنید: branch، SHA، سیستم‌عامل، Python، DB engine، فرمان/URL، نقش کاربر، نتیجه مورد انتظار، نتیجه واقعی، pass/fail، screenshot بدون داده حساس و هر تغییری که در DB یا فایل رخ داده است. تست اجرا‌نشده را صریحاً «انجام نشد» بنویسید.
