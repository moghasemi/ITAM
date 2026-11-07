"""تولید خروجی Excel و CSV برای گزارش‌ها."""
from __future__ import annotations

import csv

from django.http import HttpResponse

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _safe_spreadsheet_value(value):
    """Neutralize spreadsheet formula injection in untrusted text cells."""
    if value is None:
        return ""
    if isinstance(value, str):
        candidate = value.lstrip(" \t\r\n")
        if candidate.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def xlsx_available() -> bool:
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return False
    return True


def make_csv(filename: str, headers: list, rows: list) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.write("\ufeff")  # نشانه UTF-8 برای Excel
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe_spreadsheet_value(value) for value in row])
    return response


def make_xlsx(filename: str, sheet_title: str, headers: list, rows: list, title_rows: list | None = None) -> HttpResponse:
    """ساخت فایل Excel راست‌به‌چپ؛ در نبود openpyxl خروجی CSV داده می‌شود."""
    if not xlsx_available():
        return make_csv(filename, headers, rows)

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (sheet_title or "report")[:31]
    sheet.sheet_view.rightToLeft = True
    sheet.freeze_panes = "A2"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    row_index = 1
    if title_rows:
        for title_row in title_rows:
            sheet.cell(row=row_index, column=1, value=title_row).font = Font(bold=True, size=12)
            row_index += 1
        row_index += 1
        sheet.freeze_panes = f"A{row_index + 1}"

    header_row = row_index
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=header_row, column=column, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    for offset, row in enumerate(rows, start=1):
        for column, value in enumerate(row, start=1):
            cell = sheet.cell(row=header_row + offset, column=column, value=_safe_spreadsheet_value(value))
            cell.alignment = Alignment(horizontal="center", vertical="center")

    for column, header in enumerate(headers, start=1):
        width = max(12, min(40, len(str(header)) + 6))
        sheet.column_dimensions[get_column_letter(column)].width = width

    response = HttpResponse(content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    workbook.save(response)
    return response


def export_response(request, *, filename, sheet_title, headers, rows, title_rows=None):
    """انتخاب نوع خروجی بر اساس پارامتر format."""
    kind = (request.GET.get("format") or "xlsx").lower()
    if kind == "csv":
        return make_csv(filename, headers, rows)
    return make_xlsx(filename, sheet_title, headers, rows, title_rows=title_rows)
