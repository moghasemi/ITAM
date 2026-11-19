# ماتریس ممیزی صفحه‌به‌صفحه UX/UI — ITAM

**آخرین به‌روزرسانی:** 2026-11-19  
**مرجع معیارها:** `07_UI_UX_AND_METRONIC.md`  
**قاعده:** وجود کلاس Metronic یا سبز بودن CI به‌تنهایی به معنی تأیید تجربه کاربری نیست.

## وضعیت‌ها
- **Not reviewed:** هنوز بازبینی صفحه‌محور انجام نشده.
- **Static reviewed:** template/view/CSS به‌صورت ایستا بررسی شده؛ مرورگر واقعی آزموده نشده.
- **PR in progress:** اصلاح در PR باز است.
- **CI verified:** CI همان head موفق شده؛ پذیرش مرورگر همچنان مستقل است.
- **Browser accepted:** مرورگر/نقش/اندازه نمایشگر با شواهد واقعی پذیرفته شده است.

## ماتریس صفحات

| حوزه | صفحه/template | مبنای Metronic | ممیزی UX/UI | نکته/اقدام بعدی |
|---|---|---|---|---|
| پوسته | sidebar | Metronic KT Menu و partial مستقل | CI verified در PR #26؛ browser open | آزمون نقش‌ها، active state، collapse و mobile drawer |
| پوسته | header/footer/base | پوسته Metronic | Not reviewed در این دور | بررسی header search، notification dropdown، user menu، center selector |
| داشبورد | `core/dashboard.html` | kt-card، kt-btn، ApexCharts و CSS ترکیبی | CI verified در PR #27؛ browser open | role gating، native badge، table regions، chart text alternative؛ visual acceptance باقی است |
| دارایی | `assets/asset_list.html` | Metronic migration contract | PR #28 in progress | 12 سرستون/11 سلول؛ مرکز غایب، colspan اشتباه، badge legacy، scope و N+1 احتمالی؛ PR28 اصلاح اولیه را انجام می‌دهد |
| دارایی | `assets/asset_detail.html` | Metronic migration contract | Not reviewed | تب‌ها، timeline، پیوست، snapshot، action permissions |
| دارایی | `assets/asset_form.html` | Metronic migration contract | Not reviewed | گروه‌بندی فرم، validation، dependent fields |
| دارایی | `assets/category_list.html` و `assets/component_type_list.html` | Metronic migration contract | Not reviewed | taxonomy، search، empty state |
| دارایی | `assets/attachment_form.html` | Metronic migration contract | Not reviewed | upload feedback، file constraints |
| دارایی | snapshot detail/form/pending/start | Metronic migration contract | Not reviewed | تفاوت نقش مشاهده/تأیید، diff و state |
| دارایی | hardware report و HWAgent upload/batch import | Metronic migration contract | Not reviewed | پیام خطا، batch progress، نتیجه import |
| تیکت | `tickets/ticket_list.html` | Metronic migration contract | Static reviewed (first pass) | 12 ستون هم‌تراز؛ badge legacy، th scope و table region هنوز لازم است |
| تیکت | `tickets/ticket_detail.html` | Metronic migration contract | Not reviewed | گردش‌کار، timeline، تأییدها، قطعه و پیوست |
| تیکت | `tickets/ticket_form.html` و `tickets/my_tickets.html` | Metronic migration contract | Not reviewed | فرم و کارتابل کاربر |
| نگهداری | visit list/detail/form و my visits | Metronic migration contract | Static reviewed (visit list first pass) | 12 ستون هم‌تراز؛ stat-card و badge legacy، th scope و table region لازم است |
| نگهداری | IT request، repair، workflow list/form، check form | Metronic migration contract | Not reviewed | تفکیک کارتابل‌ها، action permissions و فرم‌های گردش‌کار |
| سازمان | center list، department list، location list، simple form | Metronic migration contract | Not reviewed | سلسله‌مراتب، فیلتر و فرم‌های وابسته |
| قرارداد | contract list/detail/form، contractor list/detail/form، assignment list/form | Metronic migration contract | Not reviewed | تاریخ اعتبار، وضعیت قرارداد، انتساب و دسترسی |
| حساب‌ها | login، profile، user list/detail/form/password | Metronic migration contract | Not reviewed | فرم ورود، پروفایل، جدول کاربران و عملیات حساس |
| هسته | audit list، notification list، search، holiday/settings | Metronic migration contract | Not reviewed | خوانایی audit، جستجو، اعلان و تقویم شمسی |
| گزارش | home، SLA، inventory، contractors، failures، repairs، visits | Metronic migration contract | Not reviewed | فیلترهای گزارش، chart/table، export و empty state |
| یکپارچه‌سازی | endpoint list و outbox | Metronic migration contract | Not reviewed | status، retry/requeue، نقش و بازخورد عملیات |

## نتایج بازبینی انجام‌شده در 2026-11-19

### Sidebar
- ساختار گروه‌ها بازطراحی شده و active_menuهای ناسازگار اصلاح شده‌اند.
- PR #26: `ui/primary-navigation-ux-audit`، commit `4abb2a2d86ea2c90a14663f8c204e22fb0059e16`.
- CI push و pull_request هر دو موفق؛ pull_request برابر 5/5 job.
- Browser acceptance و UAT نقش‌محور هنوز انجام نشده است.

### Dashboard
- فایل: `templates/core/dashboard.html`، SHA پایه بررسی‌شده `a17a1558b0ef79cc6bbef1ef9f0fbf47e94d3469`.
- استفاده موجود: Metronic cards، card header/content، buttons، ApexCharts، responsive custom grid، dark-mode styles، empty states و timeline.
- gap اولیه: badgeهای legacy، table scroll بدون نام/focus keyboard و نمایش کارتابل اسنپ‌شات به نقش‌های فاقد مجوز endpoint.
- PR #27: `ui/dashboard-role-aware-ux`، head فعلی `6d32645b6ec6a1ad1144d7a69a43db53e9c6e17e`.
- تغییرات PR: snapshot KPI/panel فقط برای admin_it، query role-gated، Metronic kt-badge و variant mapping، پنج table region قابل فوکوس و `scope="col"`، regression tests.
- CI head فعلی در زمان این ثبت در حال اجرا است؛ browser/visual acceptance باز است.
- کامپوننت‌های نامرتبط مثل modal، tabs، stepper و dropdown عمداً برای داشبورد اضافه نشده‌اند؛ معیار، تناسب با وظیفه صفحه است نه استفاده اجباری از همه اجزا.

## قاعده تکمیل هر ردیف
هر ردیف فقط پس از ثبت مسیر template، view، role، قابلیت‌های Metronic مرتبط، موارد استفاده/عدم استفاده، یافته‌ها، اصلاح PR، CI و شواهد مرورگر به وضعیت بعدی ارتقا می‌یابد.


### فهرست دارایی‌ها — بازبینی ایستا 2026-11-19
- Header count: 12؛ cell count در row template: 11؛ مقدار مرکز جا افتاده و داده واحد/محل در ستون اشتباه قرار گرفته است.
- empty colspan=11 است؛ پس از اصلاح باید 12 باشد.
- وضعیت‌ها با badgeهای legacy نمایش داده می‌شوند؛ استفاده از filter `metronic_badge_variant` و `kt-badge` در PR بعدی.
- جدول wrapper افقی دارد اما keyboard region، نام دسترس‌پذیر و scope ستون‌ها ندارد.
- احتمال N+1 در `components_count` به علت عدم prefetch `current_snapshot__items` ثبت شد؛ نیازمند تست query count.


### وضعیت CI و یافته‌های تکمیلی — 2026-11-19
- PR #26: 5/5 job success.
- PR #27 head `f5003339bff2f692d8177926ea9ddbedbfc75ced`: 5/5 job success؛ browser acceptance open.
- PR #28 head `e974dc79ee17fa368d31ff3ce2453d676e415a7a`: CI run `44510515229` در حال اجرا.
- Ticket list و visit list static first-pass شدند؛ هر دو 12 ستون هم‌تراز دارند، اما badgeهای legacy و accessibility جدول‌ها نیازمند اصلاح‌اند.
