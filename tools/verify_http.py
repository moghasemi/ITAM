"""آزمایش واقعی HTTP: ورود به سامانه و بررسی صفحات کلیدی."""
import http.cookiejar
import re
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
USERNAME = "admin.it"
PASSWORD = "Admin@1403"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(path, data=None, headers=None):
    url = BASE + path
    body = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(url, data=body, headers=headers or {})
    response = opener.open(request, timeout=20)
    return response.status, response.read().decode("utf-8", errors="replace")


def csrf_token(html):
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return match.group(1) if match else None


status, html = fetch("/accounts/login/")
token = csrf_token(html)
cookie_token = next((c.value for c in jar if c.name == "csrftoken"), "")
print(f"login page: {status}, csrf={'yes' if token else 'NO'}")

status, html = fetch(
    "/accounts/login/",
    data={"username": USERNAME, "password": PASSWORD, "csrfmiddlewaretoken": token},
    headers={"Referer": BASE + "/accounts/login/"},
)
print(f"after login: {status}, dashboard={'داشبورد' in html}, user={'علی محمدی' in html}")

PAGES = [
    ("/", ["داشبورد", "درخواست باز"]),
    ("/tickets/", ["درخواست‌های خرابی", "SLA"]),
    ("/assets/", ["دارایی‌های فناوری اطلاعات", "شماره اموال"]),
    ("/assets/1/", ["شناسنامه دارایی", "اقلام سخت‌افزاری"]),
    ("/assets/1/?focus=hardware", ["اقلام داخل کیس"]),
    ("/assets/hardware/report/", ["گزارش تغییر اقلام سخت‌افزاری"]),
    ("/assets/snapshots/2/", ["اسنپ‌شات", "جدول مقایسه"]),
    ("/maintenance/", ["بازدیدهای دوره‌ای"]),
    ("/maintenance/5/", ["برگه‌های بازدید تجهیزات"]),
    ("/org/contracts/1/", ["تعهدات زمانی", "SLA"]),
    ("/reports/", ["گزارش‌های قابل استخراج"]),
    ("/reports/sla/", ["گزارش SLA"]),
    ("/reports/contractors/", ["کارنامه عملکرد پیمانکاران"]),
    ("/integrations/outbox/", ["صف رخدادهای ارسالی به مدیریت"]),
    ("/accounts/users/", ["کاربران سامانه"]),
    ("/settings/", ["تنظیمات سامانه"]),
    ("/assets/1/qr.svg", ["<svg"]),
    ("/tickets/1/print/", ["زمان‌های کلیدی"]),
]

failures = []
for path, needles in PAGES:
    try:
        status, html = fetch(path)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{path} → خطا: {exc}")
        continue
    missing = [needle for needle in needles if needle not in html]
    mark = "✅" if status == 200 and not missing else "❌"
    if mark == "❌":
        failures.append(f"{path} → کد {status}، ناموجود: {missing}")
    print(f"{mark} {path} [{status}] {'|'.join(needles)}")

# خروجی Excel گزارش (نیازمند openpyxl)
try:
    status, _ = fetch("/reports/sla/?export=1&format=xlsx")
    print(f"export xlsx: {status}")
except Exception as exc:  # noqa: BLE001
    failures.append(f"خروجی Excel → {exc}")

print()
if failures:
    print(f"❌ {len(failures)} خطا:")
    for item in failures:
        print("   -", item)
    raise SystemExit(1)
print("✅ همه صفحات با موفقیت از سرور واقعی دریافت شدند.")
