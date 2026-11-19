# دفتر ثبت روزانه فعالیت‌های ITAM

این دفتر مرجع تاریخی و append-only فعالیت‌هاست. ورودی‌های قبلی حذف یا بازنویسی نمی‌شوند؛ اصلاح خطا با یادداشت تکمیلی و ارجاع انجام می‌شود.

## قالب هر روز
- تاریخ و فاز(ها)
- هدف و درخواست مالک پروژه
- فعالیت‌های انجام‌شده و دامنه دقیق
- فایل‌ها/مسیرها و SHAهای بررسی یا تغییرکرده
- PR/commit/CI و نتیجه دقیق
- یافته‌ها، ریسک‌ها و تصمیم‌ها
- مواردی که شروع شدند اما تکمیل نشدند (با علت و گام بعدی)
- اقدامات ممنوع/اجرا‌نشده برای شفافیت
- اولویت جلسه بعد

---

## 2026-11-19 — آغاز ثبت روزانه و بازبینی UX/UI و منوی اصلی

**فاز:** 0 و 1  
**درخواست مالک پروژه:** ثبت کامل فعالیت‌ها در GitHub؛ ایجاد دفتر روزانه؛ الزام بازبینی UX/UI هر صفحه؛ ارزیابی استفاده متناسب از قابلیت‌های Metronic؛ اولویت دادن به مرتب‌سازی منوی سایت.

### فعالیت‌های انجام‌شده
1. وضعیت PR #17 و شاخه مستندات دوباره بررسی شد:
   - PR #17 باز، Draft، Merge نشده و mergeable گزارش شد.
   - branch: `docs/itam-project-handbook-v1.3`
   - head پیش از این ثبت: `91c59a2d3fa952521d8a9eb87fe57a4a7d6fa9ab`
2. CI آخرین commit مستندات بررسی شد: run `44499445182`؛ هر 5 job موفق (Python 3.11، Python 3.12، PostgreSQL، production settings و deploy-script validation).
3. سند UI/Metronic موجود بررسی شد:
   - `docs/project/07_UI_UX_AND_METRONIC.md`
   - `docs/UI_UX_METRONIC9.md`
4. قالب اصلی `templates/base.html` در branch `ui/metronic9-django-rtl` به‌صورت static بررسی شد؛ SHA فایل: `d5c0bdab5cf7c3d7a8c8d3439909a8fb5249735f`.
5. یافته‌های اولیه منو ثبت شد:
   - گروه «درخواست‌ها و خدمات» بیش از حد گسترده و ترکیبی از میز خدمت، تعمیرات مستقل، تعمیرکاران، ارزیابی و ارجاع است.
   - «قرارداد و بازدید» موضوعات متفاوت بازدید، مرکز، قرارداد، پیمانکار و واحد سازمانی را مخلوط می‌کند.
   - «پایش و مدیریت» گزارش، Outbox و Audit را کنار هم می‌گذارد.
   - سه آیتم تعمیرات/تعمیرکاران/ارزیابی از `active_menu='repairs'` مشترک استفاده می‌کنند؛ نیازمند اصلاح و تست active state.
6. ساختار هدف پیشنهادی منو ثبت شد: نمای کلی؛ میز خدمت؛ دارایی‌ها؛ نگهداری و تعمیرات؛ سازمان و قراردادها؛ ارجاع و یکپارچه‌سازی؛ گزارش و ممیزی؛ مدیریت سامانه.
7. استاندارد بازبینی UX/UI صفحه‌به‌صفحه شامل هدف صفحه، CTA، الگوهای Metronic، فرم‌ها، جدول‌ها، وضعیت‌ها، RTL، responsive، accessibility، امنیت و کارایی تدوین شد.

### شواهد و وضعیت
- CI: **5/5 success** روی run `44499445182` برای commit مستندات `91c59a2...`.
- بررسی منو: **Static reviewed**؛ هنوز هیچ کد منو تغییر نکرده است.
- UX/UI همه صفحات: **Not reviewed**؛ استاندارد و روش ثبت تعریف شده، اما صفحات هنوز تک‌به‌تک ارزیابی نشده‌اند.
- Browser/visual/mobile/keyboard acceptance: انجام نشده.
- PR #17: باز و Draft؛ هیچ Merge انجام نشده.

### کارهای باز و گام بعدی
- [ ] ثبت تغییرات مستندات این جلسه در branch docs و کنترل CI commit جدید.
- [ ] استخراج کامل منو به ماتریس role × URL × permission × active_menu.
- [ ] بررسی base/head جاری PR #25 و انتخاب پایه درست برای PR مستقل بازطراحی منو.
- [ ] پیاده‌سازی گروه‌بندی منو و active state بدون تغییر authorization یا URL.
- [ ] آغاز ممیزی UX صفحه‌به‌صفحه از dashboard و سپس فهرست دارایی، تیکت و نگهداری.
- [ ] ثبت یافته‌های هر صفحه با وضعیت شواهد و تست.

### اقدامات اجرا‌نشده
- هیچ کد برنامه‌ای تغییر نکرد.
- هیچ PR ادغام یا بسته نشد.
- هیچ Deploy، Migration، Seed، reconciliation apply، Outbox dispatch یا تغییر DB انجام نشد.
- هیچ آزمون مرورگر یا چاپ فیزیکی انجام نشد.



### تکمله همان روز — پیاده‌سازی اولیه منوی اصلی و PR #26

**تاریخ:** 2026-11-19؛ ادامه جلسه کاری همان روز.

#### ممیزی تکمیلی و نگاشت منو
- فایل منبع در شاخه پایه PR #25: `templates/partials/metronic/sidebar.html`، SHA اولیه `00acc6cab1b483ff79e3afb46193a7a2f8712b49`.
- viewها و URLهای مرتبط در `apps/tickets/views.py`، `apps/assets/views.py`، `apps/maintenance/repair_views.py`، `apps/org/views.py`، `apps/core/views.py` و `apps/integrations/views.py` بررسی شدند.
- اختلاف‌های active state: ایجاد تیکت با کلید `tickets` به‌جای `ticket_new`؛ ایجاد دارایی با `assets` به‌جای `assets_new`؛ تعمیرکار مستقل و ارزیابی با کلید مشترک `repairs`؛ مراکز/واحدها/پیمانکاران با کلید عمومی `org`؛ انتساب پیمانکار با `contracts`؛ گونه‌های دارایی/قطعه با `settings`؛ HWAgent دسته‌ای با `assets`؛ تعطیلات با `settings`.
- فهرست اعلان‌ها و تقویم تعطیلات لینک مستقل sidebar نداشتند؛ لینک آن‌ها اضافه شد. گونه قطعات نیز به‌صورت مستقل در گروه دارایی‌ها قرار گرفت.

#### پیاده‌سازی
- شاخه: `ui/primary-navigation-ux-audit`، پایه دقیق: head PR #25 برابر `94005a451252b501b5667edf3ca87ad8fbbb9f50`.
- commit کد: `4abb2a2d86ea2c90a14663f8c204e22fb0059e16`.
- PR #26: https://github.com/moghasemi/ITAM/pull/26 — باز، Draft، base شاخه PR #25، mergeable در آخرین مشاهده true.
- فایل‌های تغییرکرده: `templates/partials/metronic/sidebar.html` و viewهای tickets/assets/maintenance/org/core برای کلیدهای active menu.
- گروه‌ها: نمای کلی، میز خدمت، دارایی‌ها، نگهداری و تعمیرات، ارجاع و هماهنگی، سازمان و قراردادها، گزارش و پایش، یکپارچه‌سازی و مدیریت سامانه.
- role predicates فعلی منو حفظ شده‌اند؛ URL، مدل، permission backend و workflow تغییر نکرده‌اند.

#### وضعیت CI و پذیرش
- CI مستندات commit `0c98a133e682726b1f2ad936421788e24c178595` در run `44506985845`: 5/5 job success؛ push و pull_request هر دو success.
- CI کد PR #26 در run `44507835886` هنگام ثبت این تکمله: production-settings-check: success; deploy-script-validation: success; test (3.11): in_progress; test (3.12): in_progress; postgres-test: in_progress.
- browser/visual/mobile/keyboard/role-based acceptance هنوز انجام نشده است.
- پیاده‌سازی منو تا پایان CI و بازبینی نهایی، پذیرفته‌شده محسوب نمی‌شود.


### نتیجه نهایی CI منوی اصلی — 2026-11-19
- PR #26 head `4abb2a2d86ea2c90a14663f8c204e22fb0059e16`؛ run push `44507835886` و run pull_request `44507866034` هر دو completed/success شدند.
- run pull_request هر 5/5 job را با موفقیت گذراند: test Python 3.11، test Python 3.12، PostgreSQL test، production-settings-check و deploy-script-validation.
- PR #26 در آخرین بررسی باز، Draft و mergeable=true است؛ Merge نشده.
- CI موفق به معنی browser acceptance یا UAT نقش‌محور نیست؛ این موارد همچنان بازند.


### بازبینی صفحه‌به‌صفحه — داشبورد (2026-11-19)
- صفحه بررسی‌شده: `templates/core/dashboard.html`، SHA پایه `a17a1558b0ef79cc6bbef1ef9f0fbf47e94d3469`؛ view: `DashboardView` در `apps/core/views.py`.
- Metronic موجود: kt-card، kt-card-header/content، kt-btn، ApexCharts، responsive grid اختصاصی، dark-mode CSS، empty state و timeline.
- gapها: پنل و KPI تأیید اسنپ‌شات برای همه نقش‌ها نشان داده می‌شد درحالی‌که endpoint فقط admin_it را مجاز می‌کند؛ badgeها از کلاس legacy بودند؛ table wrapperها keyboard-focus و accessible name نداشتند؛ thها scope نداشتند.
- PR #27 این موارد را اصلاح می‌کند: role-gating UI و query، kt-badge native با mapping، پنج region قابل فوکوس و scope ستون‌ها.
- head فعلی PR #27: `6d32645b6ec6a1ad1144d7a69a43db53e9c6e17e`؛ CI در زمان ثبت pending/in progress؛ browser acceptance باز.
- ماتریس کامل صفحات و وضعیت‌ها در `15_UI_PAGE_AUDIT_MATRIX.md` ایجاد شد. سایر صفحات در این دور هنوز UX-reviewed نیستند، حتی اگر مهاجرت پایه Metronic داشته باشند.


### بازبینی صفحه فهرست دارایی‌ها — 2026-11-19
- Template: `templates/assets/asset_list.html`، SHA `adf7a4be8d221cd91c80839592509599eb1c47be`.
- View: `AssetListView` در `apps/assets/views.py`؛ از `visible_assets` استفاده می‌کند و فرم فیلتر به مراکز scope‌شده محدود است.
- Metronic موجود: kt-card، kt-table، kt-btn، filter_bar و pagination؛ table wrapper برای overflow افقی وجود دارد.
- **یافته UX/data alignment:** 12 سرستون تعریف شده اما هر ردیف 11 سلول دارد؛ مقدار مرکز نمایش داده نمی‌شود و مقدار واحد/محل زیر عنوان مرکز می‌افتد؛ empty-state نیز colspan=11 دارد. باید مرکز و واحد/محل در دو سلول مجزا نمایش داده شوند و colspan به 12 تغییر کند.
- **یافته consistency/accessibility:** badgeهای وضعیت هنوز legacy هستند؛ thها scope ندارند و ستون عملیات نام ندارد.
- **ریسک کارایی احتمالی:** `visible_assets`، category/contract/department/location/custodian/center را select_related می‌کند اما current_snapshot/items را prefetch نمی‌کند؛ `components_count` برای هر ردیف از related manager count می‌گیرد. این یک N+1 محتمل است و باید با query-count test تأیید شود.
- **اقدام بعدی:** PR مستقل برای اصلاح ساختار ستون‌ها، native Metronic badges، accessibility و prefetch بهینه؛ هیچ کدی در این بازبینی تغییر نکرد.


### نتیجه CI و ادامه ممیزی صفحات — 2026-11-19

#### CI و PRها
- PR #26 head `4abb2a2d86ea2c90a14663f8c204e22fb0059e16`: push و pull_request هر دو 5/5 success.
- PR #27 head فعلی `f5003339bff2f692d8177926ea9ddbedbfc75ced`: push run `44509732686`، 5/5 success؛ PR باز، Draft و mergeable=true.
- PR #28: https://github.com/moghasemi/ITAM/pull/28، branch `ui/asset-list-alignment-ux`، head `e974dc79ee17fa368d31ff3ce2453d676e415a7a`، base PR #27؛ CI run `44510515229` هنگام ثبت در حال اجرا.
- آخرین commit مستندات تا این لحظه `e5edbad6c9331ca546257517e56b7e55a1c85253`: CI run `44510194516`، 5/5 success.

#### صفحات تیکت و بازدید — مرور ایستا اولیه
- `templates/tickets/ticket_list.html`: 12 header، 12 cell در ردیف، colspan=12؛ mismatch ساختاری مشابه asset list مشاهده نشد. badgeهای legacy، th بدون scope، header عملیات بدون نام و table wrapper بدون keyboard region باقی‌اند.
- `templates/maintenance/visit_list.html`: 12 header و 12 cell و colspan=12؛ stat-grid/stat-card قدیمی، badgeهای legacy، th بدون scope، header عملیات بدون نام و table wrapper بدون keyboard region.
- filter bar و pagination مشترک استفاده می‌شوند؛ بررسی کامل widget styling، فیلترها و browser behavior هنوز باز است.

#### یافته تکمیلی فهرست دارایی
- لینک چاپ برچسب در template، `request.GET.urlencode` را بدون علامت `?` به مسیر می‌چسباند؛ ضمن اینکه `label_print` فعلاً فقط `ids` و `new` را مصرف می‌کند و سایر فیلترهای فهرست را اعمال نمی‌کند. برای جلوگیری از ادعای چاپ فهرست فیلترشده، این رفتار باید جداگانه اصلاح و مستند شود.

هیچ مرورگر واقعی، چاپ فیزیکی یا UAT نقش‌محور در این جلسه انجام نشد.
