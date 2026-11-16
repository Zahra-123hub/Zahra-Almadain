"""Tables as Excel files (the system log). Text always stays text (a cell like "=SUM(A1)" can never run as a formula); amounts given
as Decimal are written as numbers."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

from fastapi import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def xlsx_response(filename: str, sheets: list[tuple[str, list[str], list[list[Any]]]], right_to_left: bool = True) -> Response:
    book = Workbook()
    book.remove(book.active)
    for title, header, rows in sheets:
        sheet = book.create_sheet(title[:31])
        sheet.sheet_view.rightToLeft = right_to_left
        sheet.append(header)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        widths = [len(str(h)) + 2 for h in header]
        for values in rows:
            sheet.append([None] * len(values))
            line = sheet.max_row
            for index, value in enumerate(values, start=1):
                cell = sheet.cell(row=line, column=index)
                if isinstance(value, Decimal):
                    whole = value == value.to_integral_value()
                    cell.value = int(value) if whole else float(value)
                    cell.number_format = "#,##0" if whole else "#,##0.00"
                    cell.alignment = Alignment(horizontal="right")
                    text = str(value)
                else:
                    text = "" if value is None else str(value)
                    cell.value = text
                    cell.data_type = "s"
                if index <= len(widths):
                    widths[index - 1] = max(widths[index - 1], min(len(text) + 2, 60))
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    book.save(buffer)
    return Response(
        content=buffer.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', **HEADERS},
    )
