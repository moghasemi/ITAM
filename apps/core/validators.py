"""اعتبارسنجی‌های سبک بدون وابستگی به کتابخانه‌های تصویری."""
from __future__ import annotations

import os

from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".tif", ".tiff",
}

IMAGE_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
    "image/heic", "image/tiff",
}


def validate_image_file(file_obj):
    """بررسی می‌کند فایل بارگذاری‌شده یک تصویر باشد (بر پایه پسوند و نوع)."""
    if not file_obj:
        return
    name = getattr(file_obj, "name", "") or ""
    extension = os.path.splitext(name)[1].lower()
    if extension and extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            "فقط فایل تصویری مجاز است (jpg، png، webp، …)."
        )
    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type and content_type not in IMAGE_CONTENT_TYPES and extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("نوع فایل ارسالی تصویر نیست.")


def validate_document_file(file_obj):
    """محدودکردن حجم و نوع فایل‌های پیوست عمومی."""
    if not file_obj:
        return
    max_size = 20 * 1024 * 1024  # ۲۰ مگابایت
    size = getattr(file_obj, "size", 0) or 0
    if size > max_size:
        raise ValidationError("حجم فایل بیش از ۲۰ مگابایت است.")
