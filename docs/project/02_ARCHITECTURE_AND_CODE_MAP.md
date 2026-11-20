# معماری و نقشه کد

## سبک معماری
Django Modular Monolith:
- یک برنامه Django با اپ‌های دامنه‌ای.
- صفحات server-rendered با Django Templates.
- CSS/JavaScript و static assets داخلی.
- React مستقل در معماری جاری وجود ندارد.
- SQLite در توسعه محلی و PostgreSQL 16 در CI.

تغییر به microservices، SPA مستقل یا framework جدید تصمیم معماری است، نه refactor کوچک.

## اپلیکیشن‌ها
| مسیر | مسئولیت غالب |
|---|---|
| apps/accounts | User، role، permission، account admin و login throttle |
| apps/org | OrganizationalUnit، TreatmentManagement، Center، قرارداد، پیمانکار و loader جغرافیا |
| apps/assets | Asset، component، HardwareSnapshot، attachment، QR و HWAgent |
| apps/tickets | Ticket، TicketEvent و workflow خرابی |
| apps/maintenance | MaintenanceVisit، SLA، repair، independent repairer و general IT requests |
| apps/reports | گزارش، filter و CSV/XLSX |
| apps/integrations | OutboxEvent، OutboxDelivery، API log و webhook |
| apps/core | middleware، base views، audit، notifications و private media |
| config | settings و root URLs |
| templates | صفحات Django |
| static | CSS/JS/vendor |
| HWAgent | کلاینت Windows |
| docs | اسناد |

این جدول نقشه مسئولیت است؛ برای تغییر واقعی، importها، مدل‌ها و تست‌ها را بررسی کنید.

## مسیر بررسی feature
1. URL و view.
2. authentication و permission.
3. queryset/object lookup و organization scope.
4. form و server-side validation.
5. service/domain operation.
6. model invariant و transaction.
7. AuditLog/domain event.
8. template و JavaScript.
9. regression tests.

اصلاح یک template یا queryset بدون بررسی سایر مسیرها ممکن است امنیت یا workflow را ناقص کند.

## قواعد وابستگی
- منطق دامنه در template/JavaScript قرار نگیرد.
- viewها orchestration باشند؛ قواعد حساس در service/model enforce شوند.
- از import cycle اجتناب شود.
- list/detail/form/export/dashboard scope هماهنگ داشته باشند.
- helperهای permission موجود را بررسی کنید و منطق را کپی نکنید.
- callerهای API داخلی را در refactor جستجو کنید.

## سازمان و جغرافیا
Center.parent_unit در ساختار فعلی به شهرستان اشاره می‌کند. TreatmentManagement مالکیت سازمانی استان را نگه می‌دارد. Center.province legacy/deprecated است و نباید بدون بررسی منبع حقیقت تلقی شود.

مدل جغرافیایی نرمال‌شده Province/County/City هنوز کامل نیست. docs/architecture/ORGANIZATION_AND_GEOGRAPHY.md بخشی target architecture و بخشی پیاده‌سازی فعلی را شرح می‌دهد. 31 استان و 484 شهرستان loader به معنی فهرست کامل مراکز واقعی نیست.

## تراکنش و audit
- mutation حساس و AuditLog را در یک transaction قرار دهید.
- stale object و double-submit را مدیریت کنید.
- از row locking در backendهای پشتیبان استفاده کنید؛ SQLite محدودیت دارد.
- append-only بودن رخدادها را در Admin/model/service enforce کنید.

## UI
- پوسته اصلی templates/base.html.
- CSS bridge در static/css/itam-metronic.css.
- JS مشترک در static/js/itam.js.
- vendor در static/vendor.
- UI جایگزین permission سمت سرور نیست.
