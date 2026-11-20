# استاندارد مشارکت و کدنویسی

## اصول
خوانایی بر cleverness؛ تغییر کم‌دامنه؛ naming موجود؛ regression test؛ مستندات بخشی از تحویل.

## Django/Python
- قواعد دامنه حساس در service/model enforce شوند.
- mutation چندمرحله‌ای و audit در transaction.
- row locking در backendهای پشتیبان؛ محدودیت SQLite لحاظ شود.
- QuerySet با organization scope.
- form choices و server-side validation هماهنگ.
- stale workflow به پاسخ کنترل‌شده تبدیل شود.
- catch-all خاموش برای خطاهای مهم ممنوع.
- immutable/append-only در Admin هم محافظت شود.

## Templates/JavaScript
- template برای presentation.
- business rule و authorization در backend.
- CSRF و escaping حفظ شود.
- aria-label، label، keyboard focus و responsive.
- progressive enhancement؛ شکست JS نباید امنیت را کاهش دهد.
- asset داخلی self-hosted؛ تعاملات با الگوهای موجود هماهنگ.

## Forms و تاریخ
- Jalali input و server-side parsing حفظ شود.
- datepicker Gregorian بدون بررسی وارد نشود.
- validation سمت سرور مرجع نهایی.
- file upload با size/type/content validation سمت سرور.
- formset management و error/help text حفظ شوند.

## Reports
- scope همان صفحه.
- pagination سمت سرور.
- neutralize formula injection در CSV/XLSX.
- secret و داده حساس export نشود.
- locale فارسی رعایت شود.

## Tests
- behavior و invariant تست شود.
- authorization با چند role و scope.
- negative tests برای workflow مهم.
- DB test روی test database.
- fixtureهای synthetic آشکارا غیرواقعی باشند.

## Branch و commit
branch موضوعی مانند fix/، feature/، ui/، docs/. commit کوتاه و روشن. PR واحد موضوعی و Draft. docs در همان تغییر به‌روز شود.

## پیش از تحویل
diff کامل، secret/debug/mock data، tests، CI، تغییرات DB/schema/static و scope ناخواسته بررسی شود.
