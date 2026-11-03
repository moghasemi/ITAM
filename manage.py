#!/usr/bin/env python
"""ابزار خط فرمان جنگو برای سامانه مدیریت دارایی فناوری اطلاعات."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# وابستگی‌های همراه پروژه (vendor) در صورت وجود
VENDOR_DIR = BASE_DIR / "vendor"
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


def main():
    # کنسول ویندوز به‌صورت پیش‌فرض از کدپیج غیر UTF-8 استفاده می‌کند؛
    # این تنظیم باعث نمایش صحیح پیام‌های فارسی می‌شود.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "جنگو نصب نشده است. اجرا کنید:  pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
