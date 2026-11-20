# دستورالعمل عامل هوش مصنوعی ITAM

این فایل قرارداد کاری coding agent یا دستیار فنی است.

## اولویت
1. حفظ داده و تغییرات کاربر.
2. امنیت و جداسازی سازمانی.
3. صحت workflow و audit.
4. تغییر کم‌دامنه و regression test.
5. مستندسازی و گزارش دقیق.

## پیش از کار
- این فایل و سند جامع نسخه 1.3 را بخوان.
- branch، HEAD و working tree را از وضعیت واقعی بگیر.
- PR و CI زنده را بررسی کن.
- برای تغییر permission/data، کد و تست مرتبط را بخوان؛ خلاصه قدیمی حقیقت کد نیست.

## ممنوعیت
- reset، clean، stash، rebase، force-push یا history rewrite.
- merge یا deploy.
- migration روی DB کاربر بدون اجازه صریح.
- reconcile_organizational_data --apply.
- seed_sistan_demo یا seed_demo.
- حذف/جابجایی/overwrite/commit فایل db.pre-geography-20261114-142558.sqlite3 یا CSVهای reconciliation.
- Outbox واقعی بدون مقصد تست و اجازه.
- ادعای تست محلی بدون شواهد.
- ادعای Production-ready.
- ثبت secret یا داده شخصی در کد/docs/issues/log.

## تغییر کد
- هر ادعای امنیتی با تست اثبات شود.
- permission فقط در UI پیاده نشود.
- scope در queryset/detail/form/service/export/dashboard هماهنگ باشد.
- mutation و audit atomic.
- stale/duplicate/concurrent submission بررسی شود.
- Admin و API مستقیم در threat model باشند.
- dependency یا تغییر معماری با ضرورت و پیامد مستند شود.

## GitHub
- پیش از commit head شاخه را دوباره بخوان.
- ref update با expected_sha و force=false.
- PR Draft.
- stacked PR بدون بررسی ancestry/base تغییر نکند.
- پس از commit CI بررسی شود.

## مستندسازی خودکار — الزام دائمی
- پس از هر تصمیم یا کار معنادار، اسناد مرتبط را در همان مرحله به‌روز کن؛ برای مستندسازی مرتبط اجازه جداگانه نخواه.
- تصمیم‌ها را در docs/project/DECISION_LOG.md ثبت کن.
- سند جامع، وضعیت/Backlog، راهنمای توسعه و این دستورالعمل را در صورت اثر به‌روز نگه دار.
- نتایج CI و تست محلی را با SHA و شواهد دقیق ثبت کن؛ موارد اجرا نشده را صریح بنویس.
- اگر تصمیم موقت است، Proposed/Open ثبت کن، نه Accepted.
- نسخه قبلی را بی‌دلیل حذف نکن و تاریخچه را حفظ کن.
- این اختیار هیچ مجوزی برای Merge، Deploy، Migration، Seed یا عملیات مخرب ایجاد نمی‌کند.

## گزارش تحویل
چه تغییر کرد، کدام فایل‌ها، branch/commit/PR، تست واقعی، تست اجرا نشده، DB/data impact، ریسک و اقدام بعدی را بنویس. اگر شواهد کافی نیست، «نامشخص/نیازمند بررسی» بگو.
