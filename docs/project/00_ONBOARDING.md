# ورود سریع توسعه‌دهنده جدید

## هدف
این راهنما برای توسعه‌دهنده، پیمانکار یا عامل فنی است که نخستین بار وارد مخزن ITAM می‌شود.

## پیش از شروع بخوانید
1. docs/README.md
2. docs/project/PROJECT_MASTER_CONTEXT_v1.3_2026-11-17.md
3. docs/ENTERPRISE_ARCHITECTURE_AND_SECURITY.md
4. docs/SECURITY_OPERATIONS.md
5. سند دامنه مرتبط با تغییری که قرار است انجام شود.

## محصول و فناوری
ITAM سامانه مدیریت دارایی و نگهداری IT چندمرکزی است. معماری جاری Django Modular Monolith و Django Templates است؛ React مستقل وجود ندارد. رابط فارسی/RTL و Metronic 9 در PR #16 قرار دارد. توسعه محلی SQLite است؛ CI علاوه بر آن PostgreSQL 16 را می‌آزماید.

## نقشه کد
- apps/accounts: حساب، role و permission.
- apps/org: سازمان، مرکز، جغرافیا، قرارداد و پیمانکار.
- apps/assets: دارایی، Snapshot و HWAgent.
- apps/tickets: تیکت.
- apps/maintenance: بازدید، تعمیر، SLA، درخواست عمومی.
- apps/reports: گزارش و export.
- apps/integrations: Outbox و webhook.
- apps/core: زیرساخت مشترک و audit.
- templates و static: UI و assets.
- HWAgent: کلاینت Windows.
- docs: اسناد.

## محیط توسعه
نسخه دقیق Python و dependencyها را از CI و requirements بخوانید؛ حدس نزنید. نمونه ساخت virtual environment در PowerShell:

~~~powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

قبل از نصب dependency مطمئن شوید مسیر مخزن درست است و سیاست محیط اجازه می‌دهد.

## پیش از هر تغییر
~~~powershell
git branch --show-current
git log -1 --oneline
git status --short
~~~

تغییرات محلی و فایل‌های untracked را حفظ کنید. از main به‌عنوان مبنای خودکار استفاده نکنید. reset/clean/stash/rebase ممنوع است.

## مسیر مشارکت
1. مسئله را با شواهد بازتولید کنید.
2. نیازمندی و نقش/حوزه داده متأثر را بخوانید.
3. تغییر کوچک ایجاد کنید.
4. regression test بنویسید.
5. تست مرتبط را در محیط ایزوله اجرا کنید.
6. مستند مرتبط را به‌روزرسانی کنید.
7. PR را Draft نگه دارید.
8. تست‌های اجراشده و نشده را جداگانه گزارش کنید.

## ممنوعیت‌های کلیدی
- ادعای تست محلی بدون شواهد.
- ادعای Production-ready.
- افشای secret یا داده شخصی.
- scope مبتنی بر ورودی client بدون اعتبارسنجی server-side.
- اجرای webhook واقعی، migration یا seed بدون اجازه.
