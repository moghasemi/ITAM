# امنیت و مجوزدهی

## مدل تهدید
تهدیدهای کلیدی: IDOR، scope bypass، role escalation، workflow bypass از Admin/API، تغییر Snapshot تأییدشده، حذف audit/outbox، پیمانکار خارج از قرارداد، افشای HWAgent token، SSRF و نشت private media.

## Fail-closed
هر عملیات باید بررسی کند:
1. کاربر authenticated و active است.
2. role مجاز است.
3. سازمان/مرکز active و در scope است.
4. رکورد متعلق به همان scope است.
5. قرارداد و assignment معتبرند، اگر عملیات پیمانکاری است.
6. workflow اجازه transition می‌دهد.

scope نامعلوم، واحد inactive، قرارداد منقضی یا رابطه ناسازگار نباید به دسترسی منجر شود.

## Queryset و object access
- list/search فقط رکوردهای مجاز.
- detail/update/delete از lookup scoped.
- form choices فقط گزینه‌های مجاز؛ POST دوباره server-side validate.
- export/dashboard/chart/notification/autocomplete همان scope.
- ID معتبر به‌تنهایی مجوز نیست.
- رکورد خارج از حوزه ترجیحاً 404؛ عملیات نامجاز در endpoint مجاز 403.

## RBAC و سازمان
برای تغییر role، permission یا get_scoped_centers():
- ماتریس فعلی را از کد بخوانید.
- empty scope و inactive unit را تست کنید.
- cross-province و cross-county را پوشش دهید.
- roleهای admin_province، admin_county، admin_it، manager، technician و requester را در سناریوهای مناسب بیازمایید.
- menu visibility را با authorization backend اشتباه نگیرید.

## Workflow و تمامیت
- manager decision و assignment state مستقل.
- user confirmation و IT final approval مستقل.
- stale/duplicate transition رد شود.
- approved snapshot immutable.
- Ticket، MaintenanceVisit، Snapshot، Outbox و audit از Admin قابل دور زدن نباشند.
- mutation و audit event atomic باشند.

## HWAgent
credential به asset active و hostname متناظر bind شود؛ legacy بدون binding fail-closed. token خام فقط یک‌بار نمایش داده شود و hash در سرور بماند. nonce/timestamp ضد replay. token در localStorage/log/Git/issue/screenshot قرار نگیرد.

## Private media
فایل private از view مجوزمحور عبور کند. debug media serving امن نیست. Nginx/Apache proxy و internal redirect در مقصد باید جداگانه تست شود.

## Outbox و SSRF
hostname allowlist دقیق، DNS/IP validation، منع redirect، header validation، HMAC، idempotency key، retry مستقل و redaction. receiver باید deduplicate کند؛ exactly-once فرض نشود. dispatch واقعی در DB محلی ممنوع مگر endpoint تست و اجازه صریح.

## Admin
superuser بودن مجوز حذف شواهد یا bypass قواعد محصول نیست. workflow/event باید read-only یا break-glass محدود، دلیل‌دار و ممیزی‌شده باشد.

## گزارش آسیب‌پذیری
دارایی/endpoint، نقش، پیش‌شرط، گام بازتولید غیرمخرب، expected/actual، اثر، ریسک، شواهد، اصلاح، regression test و ریسک باقیمانده را ثبت کنید. token/password و داده شخصی در issue عمومی ننویسید.
