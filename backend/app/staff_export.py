"""The staff list as a file (XLSX and CSV). It only reads the central employee table; no second staff database is made.

Phone numbers and employee numbers stay text: in the XLSX every cell is a text cell; in the CSV they are written as ="…"
so Excel keeps the leading zero / plus sign. Any other text that could be read as a formula gets a leading apostrophe."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.models import Employee

HEADERS = ["Mitarbeiter-Nr. / Employee no.", "Name", "Position / Job", "Telefon / Phone", "Eintritt / Start", "Austritt / End",
           "Status", "Gehalt / Salary", "Währung / Currency", "Notizen / Notes"]
TEXT_COLUMNS = {0, 3}  # employee number, phone: never turned into numbers
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def rows_of(employees: list[Employee]) -> list[list[str]]:
    return [
        [
            e.employee_no or "", e.name, e.job_title, e.phone,
            e.hired_on.isoformat() if e.hired_on else "", e.left_on.isoformat() if e.left_on else "",
            "active" if e.is_active else "inactive",
            "" if e.salary is None else format(e.salary, "f"), e.salary_currency if e.salary is not None else "", e.notes,
        ]
        for e in employees
    ]


def _safe_csv(value: str, column: int) -> str:
    if column in TEXT_COLUMNS and value:
        return '="' + value.replace('"', '""') + '"'
    if value.startswith(FORMULA_START):
        return "'" + value
    return value


def csv_response(filename: str, employees: list[Employee]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(HEADERS)
    for row in rows_of(employees):
        writer.writerow([_safe_csv(value, index) for index, value in enumerate(row)])
    return Response(
        content=("﻿" + buffer.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def xlsx_response(filename: str, employees: list[Employee]) -> Response:
    book = Workbook()
    sheet = book.active
    sheet.title = "Staff"
    sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    widths = [len(h) + 2 for h in HEADERS]
    for values in rows_of(employees):
        sheet.append([None] * len(values))
        line = sheet.max_row
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=line, column=index)
            cell.value = value
            cell.data_type = "s"  # always text, never a number or a formula
            cell.number_format = "@"
            cell.alignment = Alignment(horizontal="left")
            widths[index - 1] = max(widths[index - 1], min(len(value) + 2, 60))
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    if employees:
        sheet.auto_filter.ref = sheet.dimensions
    buffer = io.BytesIO()
    book.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
