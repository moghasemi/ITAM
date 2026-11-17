# گردش توسعه، Git و بازبینی

## اصول
تغییر کوچک و قابل ردیابی؛ حفظ داده محلی مقدم بر سرعت؛ هیچ Merge، Deploy، Migration، Seed یا عملیات مخرب بدون اجازه صریح. PRها Draft بمانند.

## پیش از شروع
~~~powershell
git branch --show-current
git log -1 --oneline
git status --short
~~~

فایل modified/untracked متعلق به کاربر فرض شود مگر خلاف آن روشن باشد. DB backup و CSV reconciliation را دست نزنید.

## branch
وضعیت ثبت‌شده 2026-11-17: PR #15 head امنیتی، PR #16 head UI و stacked روی #15. branch مستندسازی از head UI ساخته شده. پیش از checkout، refs را دوباره از GitHub بخوانید. main مبنای خودکار نیست.

## ممنوعیت‌های Git
بدون اجازه جداگانه هرگز:
- git reset، مخصوصاً --hard
- git clean
- git stash
- git rebase
- force push یا history rewrite
- حذف/overwrite فایل untracked ناشناخته

fetch و fast-forward عادی فقط پس از بررسی status و ancestry.

## Commit
- پیش از commit head شاخه را دوباره بخوانید.
- در ref update از expected_sha و force=false استفاده کنید.
- پیام روشن: docs:, fix:, test:, ui:.
- commit واحد موضوعی.
- بعد از push SHA و CI را بررسی کنید.
- تست اجرا نشده را موفق گزارش نکنید.

## PR
هدف، دامنه، فایل‌ها، security/data impact، تست‌های اجراشده/نشده، DB impact، rollback/limitations و CI link را بنویسید. Draft بماند. stacked PR را بدون بررسی diff و ancestry تغییر base ندهید.

## حل مسئله
reproduce → root cause → کم‌دامنه change → regression test → اجرای تست → بررسی diff → به‌روزرسانی docs → گزارش.

## Dependency و معماری
dependency جدید باید ضرورت، مجوز، نگهداری و اثر امنیتی داشته باشد. frontend framework یا runtime CDN بدون تصمیم معماری اضافه نشود.
