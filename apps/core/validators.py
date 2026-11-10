"""اعتبارسنجی محتوای فایل‌های بارگذاری‌شده بدون اعتماد به پسوند یا MIME کلاینت."""
from __future__ import annotations

import os
import zipfile

from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".tif", ".tiff",
}
ALLOWED_DOCUMENT_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf", ".txt", ".csv",
}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024


def _read_prefix(file_obj, length=64):
    try:
        position = file_obj.tell()
        file_obj.seek(0)
        prefix = file_obj.read(length)
        file_obj.seek(position)
        return prefix
    except (AttributeError, OSError, ValueError) as exc:
        raise ValidationError("خواندن محتوای فایل برای اعتبارسنجی ممکن نیست.") from exc


def _zip_has_required_member(file_obj, required_member):
    position = 0
    try:
        position = file_obj.tell()
        file_obj.seek(0)
        with zipfile.ZipFile(file_obj) as archive:
            valid = required_member in archive.namelist()
        file_obj.seek(position)
        return valid
    except (AttributeError, OSError, ValueError, zipfile.BadZipFile):
        try:
            file_obj.seek(position)
        except (AttributeError, OSError, ValueError):
            pass
        return False


def validate_image_file(file_obj):
    """اعتبارسنجی پسوند و امضای باینری تصویر؛ MIME ارسالی کلاینت قابل اعتماد نیست."""
    if not file_obj:
        return
    name = getattr(file_obj, "name", "") or ""
    extension = os.path.splitext(name)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("پسوند فایل تصویری مجاز نیست.")
    size = getattr(file_obj, "size", 0) or 0
    if size > MAX_UPLOAD_SIZE:
        raise ValidationError("حجم تصویر بیش از ۲۰ مگابایت است.")

    prefix = _read_prefix(file_obj, 32)
    valid = False
    if extension in (".jpg", ".jpeg"):
        valid = prefix.startswith(b"\xff\xd8\xff")
    elif extension == ".png":
        valid = prefix.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension == ".gif":
        valid = prefix.startswith((b"GIF87a", b"GIF89a"))
    elif extension == ".webp":
        valid = len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP"
    elif extension == ".bmp":
        valid = prefix.startswith(b"BM")
    elif extension in (".tif", ".tiff"):
        valid = prefix.startswith((b"II*\x00", b"MM\x00*"))
    elif extension == ".heic":
        valid = (
            len(prefix) >= 12
            and prefix[4:8] == b"ftyp"
            and prefix[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1")
        )
    if not valid:
        raise ValidationError("محتوای فایل با فرمت تصویر اعلام‌شده مطابقت ندارد.")


def validate_document_file(file_obj):
    """اعتبارسنجی حجم، پسوند و امضای محتوای پیوست‌های عمومی."""
    if not file_obj:
        return
    size = getattr(file_obj, "size", 0) or 0
    if size > MAX_UPLOAD_SIZE:
        raise ValidationError("حجم فایل بیش از ۲۰ مگابایت است.")

    name = getattr(file_obj, "name", "") or ""
    extension = os.path.splitext(name)[1].lower()
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        validate_image_file(file_obj)
        return
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError("نوع فایل پیوست مجاز نیست.")

    prefix = _read_prefix(file_obj, 64)
    valid = False
    if extension == ".pdf":
        valid = prefix.startswith(b"%PDF-")
    elif extension in (".doc", ".xls", ".ppt"):
        valid = prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    elif extension == ".docx":
        valid = prefix.startswith(b"PK") and _zip_has_required_member(file_obj, "word/document.xml")
    elif extension == ".xlsx":
        valid = prefix.startswith(b"PK") and _zip_has_required_member(file_obj, "xl/workbook.xml")
    elif extension == ".pptx":
        valid = prefix.startswith(b"PK") and _zip_has_required_member(file_obj, "ppt/presentation.xml")
    elif extension == ".rtf":
        valid = prefix.lstrip().startswith(b"{\\rtf")
    elif extension in (".txt", ".csv"):
        valid = b"\x00" not in prefix
    if not valid:
        raise ValidationError("محتوای فایل با پسوند اعلام‌شده مطابقت ندارد.")
