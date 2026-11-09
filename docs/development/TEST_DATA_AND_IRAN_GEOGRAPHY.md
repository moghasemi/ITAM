# راهنمای داده‌های جغرافیایی و نمونه ITAM

## داده‌های جغرافیایی

فایل‌های `data/iran_admin/` شامل ۳۱ استان و ۴۸۴ شهرستان ایران بر پایه مجموعه‌داده تقسیمات کشوری تا پایان سال ۱۴۰۴ هستند. منبع، نسخه پین‌شده مخزن `sajaddp/list-of-cities-in-Iran` است؛ جزئیات و مجوز در همان پوشه ثبت شده است.

بارگذاری فقط واحدهای سلسله‌مراتبی جغرافیایی را ایجاد یا به‌روزرسانی می‌کند:
- یک ریشه کشوری با کد `IR-NAT`
- استان‌ها با کدهای پایدار `IR-PROV-<source-id>`
- شهرستان‌ها با کدهای پایدار `IR-COUNTY-<source-id>`

این فرمان **حذف انجام نمی‌دهد** و برای هر شهرستان مرکز عملیاتی IT ایجاد نمی‌کند. مراکز واقعی سازمان باید جداگانه ثبت شوند.

## اجرای اعتبارسنجی و بارگذاری

ابتدا در محیط توسعه از پایگاه داده نسخه پشتیبان بگیرید. برای SQLite در PowerShell:

```powershell
Copy-Item .\db.sqlite3 (".\db.sqlite3.before-geography-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".bak")
```

سپس:

```powershell
python manage.py load_iran_geography --dry-run
python manage.py load_iran_geography
```

فرمان بارگذاری تکرارپذیر است؛ اجرای مجدد رکورد تکراری ایجاد نمی‌کند.

## ایجاد داده‌های نمونه عملیاتی

فرمان `seed_demo` ابتدا جغرافیای ایران را بارگذاری می‌کند و سپس داده‌های نمونه سامانه را می‌سازد:

```powershell
python manage.py seed_demo --admin-password "USE-A-UNIQUE-LOCAL-PASSWORD" --assets 30
```

این داده‌ها شامل کاربران نمونه با نقش‌های مختلف، مراکز نمونه استان مرکزی، واحدها، مکان‌ها، پیمانکار و قرارداد، دارایی‌ها، بازدیدها، اسنپ‌شات‌ها و درخواست‌های نمونه است.

برای بازسازی کامل پایگاه داده محلی (با حذف همه رکوردهای فعلی)، از فرمان زیر استفاده می‌شود. این فرمان فقط با `DEBUG=True`، پایگاه SQLite فایل‌محور در ریشه پروژه و آرگومان صریح `--confirm-reset` اجرا می‌شود. قبل از پاک‌سازی، نسخه پشتیبان SQLite در پوشه‌ای خارج از مخزن می‌سازد و اگر seed شکست بخورد، تلاش می‌کند پایگاه قبلی را از همان نسخه بازیابی کند:

```powershell
python manage.py rebuild_demo_database --confirm-reset --admin-password "USE-A-UNIQUE-LOCAL-PASSWORD" --assets 30
```

گزینه `--reset` عمداً در `seed_demo` وجود ندارد تا اجرای اشتباه باعث حذف داده نشود.

## آزمون

```powershell
python manage.py check
python manage.py test apps.org.tests_iran_geography
python manage.py test apps.org apps.assets apps.accounts apps.tickets apps.maintenance
```

نتیجه اجرای این فرمان‌ها باید از محیطی که واقعاً در آن اجرا شده‌اند گزارش شود؛ ثبت کد در GitHub به‌تنهایی به معنی پرشدن پایگاه داده محلی نیست.
