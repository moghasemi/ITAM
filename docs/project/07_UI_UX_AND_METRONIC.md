# رابط کاربری و Metronic 9

## وضعیت
PR #16 در branch ui/metronic9-django-rtl، head 23dbebb19493cb9947c685c069adf205039412a9. PR باز و Draft است؛ merge نشده. CI موفق است اما تست مرورگر کاربر انجام نشده.

## تصمیم معماری
Django Templates حفظ شده؛ React مستقل اضافه نشده. UI در templates، CSS/JS و static assets است. vendor assets self-hosted. منطق permission و workflow در backend می‌ماند.

## فایل‌های اصلی
- templates/base.html: پوسته، header و sidebar.
- templates/accounts/login.html: login.
- templates/core/dashboard.html: داشبورد و chart.
- templates/partials/: فرم و فیلتر مشترک.
- static/css/itam-metronic.css: bridge.
- static/js/itam.js: تعاملات مشترک.
- static/vendor/metronic9/ و static/vendor/vazirmatn/: assets.

## امکانات PR
sidebar نقش‌محور، header ثابت، search، notifications، account dropdown، selector مرکز با get_scoped_centers()، collapse، mobile drawer، light/dark و persistence، ApexCharts، CSS bridge برای فرم/جدول/کارت/filter/pagination، print styles، reduced motion و keyboard focus.

این فهرست به معنی استفاده از همه demo/pluginهای Metronic نیست. انتخاب‌ها برای سازگاری با Django Forms، Jalali inputs، server-side pagination و file validation انجام شده‌اند.

## قواعد UI
- business logic و authorization در backend.
- menu hidden مجوز نیست.
- POSTها CSRF و validation سمت سرور داشته باشند.
- نام فیلد، URL، pagination، formset و workflow حفظ شوند.
- datepicker جدید بدون بررسی Jalali اضافه نشود.
- client-side DataTables جایگزین server-side pagination نشود مگر تصمیم صریح.
- upload widget validation سرور را دور نزند.
- runtime CDN و asset بدون بررسی license اضافه نشود.
- keyboard, focus, contrast, labels, aria و reduced motion بررسی شوند.

## CI و مجوز
run 44161472256 روی head PR #16: 5/5 job موفق؛ 375 تست Python 3.11/3.12، PostgreSQL 16 و deployment checks.

مجوز خریداری‌شده Metronic برای ITAM راستی‌آزمایی نشده است. notice همراه نسخه مرجع برای هر deployment/project مجوز جدا و برای SaaS پولی Extended License را ذکر می‌کند. پیش از عرضه تجاری سند خرید بررسی شود. Vazirmatn با OFL همراه شده است.

## پذیرش
چک‌لیست کامل در 05_TESTING_AND_ACCEPTANCE.md بخش پذیرش دستی است. تا آن زمان UI فقط CI-validated است، نه browser-accepted.

## تعارض CSS قدیمی و Metronic — 2026-11-18
- در Metronic/Tailwind 4 فایل vendor، ترتیب layerها `theme, base, components, utilities` تعریف شده است.
- `static/css/itam.css` قبلاً خارج از layer قرار داشت؛ قواعد عادی unlayered نسبت به قواعد عادی داخل layer اولویت بیشتری دارند و ممکن بود utility/componentهای Metronic را تحت‌تأثیر قرار دهند.
- اصلاح پیشنهادی در PR #19: قرار دادن کل stylesheet قدیمی داخل `@layer base`. selectorهای قدیمی حذف نمی‌شوند؛ CSS bridge در `itam-metronic.css` بدون layer باقی می‌ماند تا همچنان سفارشی‌سازی نهایی را اعمال کند.
- **PR اصلاح:** https://github.com/moghasemi/ITAM/pull/19 — Draft، branch `fix/metronic-legacy-css-cascade`، head `dccd73e2e11092850a1b5b94e73a7b3da5e54a49`، base= `ui/metronic9-django-rtl`.
- **وضعیت پذیرش:** تغییر کد ثبت شده؛ آزمون واقعی مرورگر هنوز Open است. این اصلاح به‌تنهایی تضمین نمی‌کند تمام مشکلات layout رفع شوند.
- **مورد بررسی محلی:** dashboard، فهرست دارایی، فرم ایجاد/ویرایش، صفحه ورود، عرض دسکتاپ و موبایل، dropdownها، حالت dark و print.


## وضعیت مهاجرت تکمیلی Metronic — 2026-11-19

### زنجیره تغییرات
- PR #19: `itam.css` در `@layer base` برای اصلاح cascade؛ selectorهای legacy حذف نشدند.
- PR #20: یک منبع حقیقت برای عرض Sidebar و محتوا.
- PR #21: skip link، focus management و mobile sidebar keyboard/inert.
- PR #22: dashboard با KPI، chart، calendar و workbench.
- PR #23: صفحات عملیاتی asset/ticket/maintenance.
- PR #24: مهاجرت templateهای باقیمانده و حذف selectorهای shell قدیمی از CSS legacy.
- PR #25: برگه‌های چاپ، HWAgent standalone و partialهای مشترک.
- تمام PRها Draft و Merge نشده‌اند. CI موفق روی headهای #19 تا #24 در اجرای کامل ثبت شده؛ #25 در زمان ثبت منتظر CI مجدد پس از رفع missing template tag است.

### جزئیات PR #25
- label print: A4 portrait, margin 9mm, label 62×42mm, 3 columns, 3mm gap; heading/footer مخفی.
- visit/ticket print: A4 landscape.
- shell, messages و skip link در چاپ پنهان می‌شوند.
- HWAgent: viewport meta، فونت محلی، dark mode، reduced motion، tablist/tab/tabpanel با ARIA و keyboard، meterهای داخلی RAM/disk؛ Chart.js CDN حذف شده است.
- shared partials: form_fields, filter_bar, pagination, formset, empty, messages, action_button به hookهای Metronic مجهز شده‌اند؛ data hooks/classes قدیمی حفظ شده‌اند.
- شکست CI اولیه: missing `{% load itam_tags %}` در formset partial؛ commit اصلاحی در head جاری ثبت شده؛ CI مجدد باید نتیجه دهد.

### موارد باز
- browser visual acceptance، print/PDF physical acceptance و Windows HWAgent end-to-end.
- حذف کامل legacy compatibility CSS عمداً deferred است تا هر کلاس/رفتار/JS consumer جداگانه مهاجرت و تست شود.
- Metronic commercial license verification.
- هیچ PR Merge/Deploy نشده است.


## استاندارد اجباری بازبینی صفحه‌به‌صفحه UX/UI — 2026-11-19

از این تاریخ، هر صفحه‌ای که در PR، کد یا پذیرش بررسی یا پیاده‌سازی می‌شود باید با این چک‌لیست ارزیابی شود. «استفاده از Metronic» به معنی افزودن همه کامپوننت‌ها نیست؛ باید از تمام قابلیت‌های مرتبط و مفید استفاده شود و برای قابلیت نامرتبط دلیل حذف روشن باشد.

### معیارهای ارزیابی هر صفحه
1. **هدف و معماری اطلاعات:** هدف صفحه در نگاه اول روشن باشد؛ عنوان، توضیح، breadcrumb و جایگاه آن در منو با وظیفه کاربر هماهنگ باشد.
2. **اولویت اقدام:** اقدام اصلی برجسته و اقدام‌های ثانویه کم‌تأکیدتر باشند؛ چند CTA رقیب ایجاد نشود.
3. **الگوی Metronic:** متناسب با ماهیت صفحه از الگوهای واقعی Metronic/KTUI مانند card، toolbar، stat/KPI، badge، table، filter/search، pagination، dropdown، tabs، modal/drawer، alert، tooltip، progress، empty state و chart استفاده شود؛ هر مورد فقط وقتی ارزش کاربردی دارد.
4. **فرم و اعتبارسنجی:** گروه‌بندی منطقی، label و help text، required واضح، خطای نزدیک فیلد، حفظ داده واردشده، وضعیت loading/disabled و نمایش خطای سمت سرور.
5. **فهرست و داده:** تراکم خوانا، ستون‌های اولویت‌دار، فیلترهای قابل فهم، sort و pagination سمت سرور، حالت بدون نتیجه، loading و خطا؛ در موبایل راه‌حل جدول عریض مشخص باشد.
6. **وضعیت و بازخورد:** status badge با واژگان یکسان، پیام موفقیت/خطا، تأیید عملیات پرریسک و نمایش نتیجه اقدام.
7. **RTL و فارسی:** جهت آیکون‌ها، فاصله‌ها، اعداد، تاریخ شمسی، متن‌های طولانی و ترتیب فوکوس بررسی شود.
8. **واکنش‌گرایی:** حداقل عرض‌های موبایل، تبلت و دسکتاپ؛ overflow افقی ناخواسته، sidebar/drawer و actionها بررسی شوند.
9. **دسترس‌پذیری:** semantic HTML، heading order، label، aria، keyboard، focus visible، contrast، target size و reduced motion.
10. **یکپارچگی بصری:** typography، spacing، radius، elevation، رنگ وضعیت و آیکون‌ها با design system هم‌خوان باشد؛ CSS سفارشی فقط در صورت نبود راه‌حل استاندارد و با دامنه محدود.
11. **امنیت و منطق:** منو و UI صرفاً نمایش‌اند؛ permission، scope، validation و workflow باید server-side باقی بمانند. هیچ بازطراحی نباید URL، نام فیلد، formset، pagination یا منطق دامنه را ناخواسته بشکند.
12. **کارایی و نگهداری:** از JS/plugin تکراری، CDN runtime، asset بلااستفاده، وابستگی غیرضروری و mock data در محصول پرهیز شود.

### فرم ثبت بازبینی صفحه
برای هر صفحه در گزارش روزانه یا PR ثبت شود:
- مسیر template و URL name؛ نقش‌های هدف؛ هدف کاربر.
- وضعیت قبل و مشکل مشاهده‌شده.
- الگوها/کامپوننت‌های Metronic موجود و قابل استفاده.
- موارد استفاده‌شده و موارد عمداً استفاده‌نشده به همراه دلیل.
- نتیجه در desktop/tablet/mobile، RTL، keyboard و dark mode.
- تست‌های اجراشده و نتیجه دقیق؛ تفکیک static review، CI و browser acceptance.
- یافته‌ها با severity، شناسه و regression test.
- وضعیت: Not reviewed / Static reviewed / Implemented / CI verified / Browser accepted.

### قاعده «بهترین استفاده از Metronic»
هیچ امتیاز یا ادعای «استفاده کامل» صرفاً از روی ظاهر یا تعداد کامپوننت‌ها داده نمی‌شود. معیار، تناسب با کار، سادگی، دسترس‌پذیری، انسجام و عدم تحمیل پیچیدگی است. برای هر صفحه یک فهرست کوتاه از قابلیت‌های مرتبط Metronic تهیه و پوشش آن ثبت می‌شود.

## بازبینی اولیه منوی اصلی — 2026-11-19

منبع بررسی: `templates/base.html` در branch `ui/metronic9-django-rtl`، فایل SHA `d5c0bdab5cf7c3d7a8c8d3439909a8fb5249735f`. این بررسی static است و هنوز تغییر کد یا browser test انجام نشده است.

### مشکلات مشاهده‌شده
- «درخواست‌های خرابی»، «اعلام خرابی جدید»، «درخواست‌های من»، «درخواست‌های عمومی IT»، «تعمیرات مستقل»، «تعمیرکاران مستقل»، «ارزیابی تعمیرکاران» و «ارجاع‌های عمومی» همگی در گروه بزرگ «درخواست‌ها و خدمات» قرار گرفته‌اند؛ چند زیرحوزه با نقش و هدف متفاوت مخلوط شده‌اند.
- «قرارداد و بازدید» یک گروه ناهمگون است: بازدید دوره‌ای کنار مراکز استان، انتساب پیمانکار، قرارداد، پیمانکار و واحدها/محل‌ها آمده است.
- «پایش و مدیریت» گزارش‌ها، صف Outbox و گزارش ممیزی را کنار هم قرار داده؛ این‌ها سه مفهوم متفاوت (تحلیل، یکپارچه‌سازی، ممیزی) هستند.
- «مدیریت کاربران» و «تنظیمات سراسری» گروه‌های جدا هستند، اما دسته‌بندی تنظیمات پایه و واژگان آن‌ها یکپارچه نیست.
- چند لینک از یک `active_menu` مشترک استفاده می‌کنند؛ برای نمونه سه لینک تعمیرات مستقل/تعمیرکاران/ارزیابی همگی `repairs` هستند. در نتیجه احتمال active شدن هم‌زمان چند آیتم وجود دارد و باید با کلیدهای یکتای معنایی اصلاح شود.
- گروه «مدیریت دارایی» بخشی از عملیات سخت‌افزار (تأیید Snapshot و ورود گروهی HWAgent) را در کنار فهرست دارایی گذاشته؛ این‌ها می‌توانند زیرگروه «عملیات و کشف دارایی» یا کارتابل قرار گیرند.
- نمایش لینک‌های جداگانه برای هر عملیات می‌تواند منو را طولانی کند؛ ایجاد گروه/زیرمنوی قابل فهم و محدود به نقش باید ارزیابی شود.

### ساختار هدف پیشنهادی برای طراحی و اعتبارسنجی
1. **نمای کلی:** داشبورد.
2. **میز خدمت:** درخواست‌های خرابی، ثبت خرابی، درخواست‌های من، درخواست عمومی IT؛ با تفکیک کارتابل شخصی از مدیریت درخواست‌ها.
3. **دارایی‌ها:** فهرست/ثبت دارایی، دسته‌بندی دارایی و قطعه، عملیات سخت‌افزاری و تأیید Snapshot.
4. **نگهداری و تعمیرات:** بازدیدهای دوره‌ای، کارتابل بازدید تکنسین، تعمیرات مستقل، تعمیرکاران و ارزیابی.
5. **سازمان و قراردادها:** مراکز، واحدها و محل‌ها، پیمانکاران، قراردادها و انتساب پیمانکار به مراکز.
6. **ارجاع و یکپارچه‌سازی:** ارجاع‌ها و صف ارسال/یکپارچه‌سازی؛ فقط اگر نقش‌ها و حجم عملیات آن را توجیه کنند.
7. **گزارش و ممیزی:** گزارش‌ها و تحلیل، گزارش ممیزی؛ تفکیک بصری روشن بین تحلیل مدیریتی و سوابق ممیزی.
8. **مدیریت سامانه:** کاربران، تنظیمات سراسری و تنظیمات پایه؛ فقط برای نقش‌های مجاز.

این ساختار **پیشنهاد طراحی** است، نه تغییر قطعی. پیش از پیاده‌سازی باید تمام URLها، role predicates، active_menuها، صفحه‌های مقصد و وظایف واقعی هر نقش استخراج شوند. مجوز backend نباید تغییر کند و مخفی‌سازی منو جایگزین مجوزدهی نیست.

### اولویت اجرایی
- P0: استخراج کامل ماتریس منو/نقش/URL و تعیین گروه‌بندی نهایی.
- P0: اصلاح کلیدهای active_menu تکراری و آزمون active state.
- P1: بازطراحی sidebar با headingهای معنادار، گروه‌بندی کم‌عمق، آیکون‌های هم‌معنا و حالت موبایل/جمع‌شده.
- P1: بررسی breadcrumb، page title و CTA هر صفحه در امتداد منو.
- P2: پذیرش نقش‌محور و مرورگر در اندازه‌های مختلف.

