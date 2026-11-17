# Outbox، یکپارچه‌سازی و HWAgent

## Outbox
رخداد در transaction عملیات اصلی ثبت می‌شود و worker آن را ارسال می‌کند.
- delivery برای هر endpoint مستقل.
- HMAC و idempotency key.
- retry و lease/fencing برای worker همزمان.
- receiver باید Idempotency-Key را deduplicate کند.
- exactly-once بدون همکاری receiver تضمین نمی‌شود.
- logها secret و payload حساس را redact کنند.
- hostname allowlist، DNS/IP validation و منع redirect.

## ممنوعیت dispatch محلی
در DB کاربر به مقصد واقعی ارسال نکنید. تست با mock یا endpoint آزمایشی کنترل‌شده. هر dispatch واقعی نیازمند تعیین مقصد، ارزیابی payload و اجازه صریح است.

## HWAgent
کلاینت Windows برای inventory/snapshot و ارسال به ITAM.
فایل‌ها: HWAgent/Start.bat، HWAgent/agent.ps1، HWAgent/index.html، HWAgent/README.md؛ backend در apps/assets/hwagent_service.py.

## Credential binding
- credential به asset فعال و hostname متناظر bind شود.
- center از credential سمت سرور استخراج شود.
- legacy بدون asset binding fail-closed.
- token خام فقط یک‌بار نمایش؛ hash در سرور.
- timestamp/nonce ضد replay.
- token در localStorage/log/terminal screenshot/Git/docs نباشد.

## Windows acceptance
1. صدور credential برای asset مشخص.
2. انتقال امن token.
3. اجرای Start.bat و listener محلی.
4. scan و ذخیره JSON.
5. بررسی CPU، motherboard، RAM، disks، GPU، network و OS.
6. sync با HTTPS برای سرور راه‌دور.
7. تطبیق asset، center و hostname.
8. مشاهده snapshot و audit در ITAM.
9. rotate/revoke/suspend.
10. بررسی خطاهای 401/404/500 بدون افشای secret.

CI فقط بخشی از syntax و backend را پوشش می‌دهد؛ Windows acceptance واقعی جداست.

## Private media
فایل private باید از authorization عبور کند. مسیر Nginx/Apache و internal redirect در محیط مقصد هنوز تست عملیاتی لازم دارد. debug media serving برای LAN/Production قابل اتکا نیست.

## منابع
HWAgent/README.md، docs/SECURITY_OPERATIONS.md، docs/ENTERPRISE_ARCHITECTURE_AND_SECURITY.md، docs/CONTRACT_CENTER_ASSIGNMENTS.md.
