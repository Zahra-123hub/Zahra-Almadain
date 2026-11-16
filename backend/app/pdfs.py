"""PDF documents of the accounting: an invoice, and the report of a month. Arabic, right to left, both currencies side by side.

Every document carries the logo of the kindergarten at the top and is signed automatically: the name and role of the person who
issued it, the time (Damascus) and a verification code. The code is an HMAC of the figures of the document with the server secret,
so a changed number on a printed or edited copy no longer matches (it can be checked again with the same data on the server).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.timeutil import to_local

ASSETS = Path(__file__).with_name("assets")
NAVY = (22, 64, 111)
SUN = (232, 163, 61)
INK = (30, 41, 59)
MUTED = (100, 116, 139)
LINE = (214, 222, 233)
SOFT = (242, 246, 251)
ROLE_NAMES = {"accountant": "المحاسب", "manager": "الإدارة", "admin": "المدير"}
KG_NAME = "روضة زهرة المدائن"
MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]


def month_name(key: str) -> str:
    """"2026-11" -> "تشرين الثاني 2026" (words, so the right-to-left line cannot turn the numbers around)."""
    year, month = key.split("-")[:2]
    return f"{MONTHS[int(month) - 1]} {year}"


def day_name(iso: str) -> str:
    """"2026-11-16" -> "16 تشرين الثاني 2026"."""
    year, month, day = iso.split("-")
    return f"{int(day)} {MONTHS[int(month) - 1]} {year}"


def verification(parts: list[str]) -> str:
    secret = os.getenv("SESSION_SECRET", "unset")
    digest = hmac.new(secret.encode(), "|".join(parts).encode(), hashlib.sha256).hexdigest().upper()
    return "-".join(digest[i:i + 4] for i in range(0, 16, 4))


def num(text: str | None) -> str:
    """1234567.5 -> 1,234,567.50 ; whole pounds stay whole."""
    if text is None or text == "":
        return "—"
    negative = text.startswith("-")
    whole, _, fraction = text.lstrip("-").partition(".")
    whole = f"{int(whole):,}"
    return ("-" if negative else "") + whole + ("." + fraction if fraction else "")


class Doc(FPDF):
    def __init__(self, title: str, subtitle: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_title, self.doc_subtitle = title, subtitle
        self.add_font("Tajawal", "", str(ASSETS / "Tajawal-Regular.ttf"))
        self.add_font("Tajawal", "B", str(ASSETS / "Tajawal-Bold.ttf"))
        self.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab", language="ara")
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(15, 15, 15)
        self.set_title(title)
        self.set_creator(KG_NAME)
        self.add_page()

    # ---- frame of every page ----
    def header(self) -> None:
        self.image(str(ASSETS / "logo.png"), x=self.w - self.r_margin - 30, y=10, h=22)
        self.set_xy(self.l_margin, 12)
        self.set_font("Tajawal", "B", 16)
        self.set_text_color(*NAVY)
        self.cell(self.epw - 34, 8, KG_NAME, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Tajawal", "B", 13)
        self.set_text_color(*INK)
        self.cell(self.epw - 34, 7, self.doc_title, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Tajawal", "", 10)
        self.set_text_color(*MUTED)
        self.cell(self.epw - 34, 6, self.doc_subtitle, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*SUN)
        self.set_line_width(0.8)
        self.line(self.l_margin, 36, self.w - self.r_margin, 36)
        self.set_y(41)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Tajawal", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{KG_NAME} · صفحة {self.page_no()}", align="C")

    # ---- pieces ----
    def heading(self, text: str) -> None:
        self.ln(2)
        self.set_font("Tajawal", "B", 12)
        self.set_text_color(*NAVY)
        self.cell(0, 8, text, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def line_text(self, text: str, size: int = 10, color: tuple[int, int, int] = INK, bold: bool = False) -> None:
        self.set_font("Tajawal", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(0, 6, text, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def grid(self, header: list[str], rows: list[list[str]], widths: list[float], bold_last: bool = False, numeric: set[int] | None = None) -> None:
        """A table. The first column is the right-most one (Arabic reading order)."""
        numeric = numeric or set()
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)

        def row(values: list[str], fill: tuple[int, int, int] | None, bold: bool, color: tuple[int, int, int]) -> None:
            if self.get_y() + 8 > self.page_break_trigger:
                self.add_page()
            self.set_font("Tajawal", "B" if bold else "", 9.5)
            self.set_text_color(*color)
            if fill:
                self.set_fill_color(*fill)
            x = self.w - self.r_margin
            y = self.get_y()
            for index, (value, width) in enumerate(zip(values, widths)):
                x -= width
                self.set_xy(x, y)
                self.cell(width, 8, value, border=1, align="L" if index in numeric else "R", fill=bool(fill))
            self.set_xy(self.l_margin, y + 8)

        row(header, NAVY, True, (255, 255, 255))
        for i, values in enumerate(rows):
            last = bold_last and i == len(rows) - 1
            row(values, SOFT if (i % 2 or last) else None, last, INK)

    def signature(self, signer: dict[str, str], code: str) -> None:
        """The automatic signature: who issued the document, as what, when, and the code that proves the figures."""
        if self.get_y() + 34 > self.page_break_trigger:
            self.add_page()
        self.ln(6)
        box_w, box_h = 92, 30
        x = self.l_margin
        y = self.get_y()
        self.set_draw_color(*NAVY)
        self.set_line_width(0.5)
        self.set_fill_color(*SOFT)
        self.rect(x, y, box_w, box_h, style="DF")
        self.set_xy(x + 3, y + 2)
        self.set_font("Tajawal", "B", 10)
        self.set_text_color(*NAVY)
        self.cell(box_w - 6, 6, "موقّع إلكترونياً", align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_font("Tajawal", "B", 12)
        self.set_text_color(*INK)
        self.cell(box_w - 6, 7, f"{ROLE_NAMES.get(signer['role'], signer['role'])}: {signer['name']}", align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_font("Tajawal", "", 9)
        self.set_text_color(*MUTED)
        self.cell(box_w - 6, 5, f"{day_name(signer['day'])} · الساعة {signer['time']} بتوقيت دمشق", align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.cell(box_w - 6, 5, f"رمز التحقق: {code}", align="R", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_y(y + box_h + 2)


def signer_of(name: str, role: str) -> dict[str, str]:
    now = to_local(datetime.now(timezone.utc))
    return {"name": name, "role": role, "day": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M")}


STATUS = {"open": "مفتوحة", "partial": "مدفوعة جزئياً", "paid": "مدفوعة بالكامل", "void": "ملغاة"}


def invoice_pdf(invoice: dict[str, Any], signer: dict[str, str]) -> bytes:
    """`invoice` is the dictionary the API returns for one invoice (with payments)."""
    doc = Doc(f"فاتورة رقم {invoice['number']}", f"تاريخ الإصدار: {day_name(invoice['issued_on'])} · الحالة: {STATUS.get(invoice['status'], invoice['status'])}")
    doc.line_text(f"إلى: {invoice['child'] or invoice['payer_name']}" + (f" · ولي الأمر: {invoice['payer_name']}" if invoice['child'] and invoice['payer_name'] else ""), 11, INK, True)
    if invoice["description"]:
        doc.line_text(invoice["description"], 10, MUTED)
    doc.line_text(f"عملة الفاتورة: {invoice['currency']} · سعر الصرف المعتمد: {num(invoice['rate'])} ليرة للدولار الواحد", 10, MUTED)
    doc.heading("البنود")
    rows = [[i["description"], num(i["usd"]), num(i["syp"])] for i in invoice["items"]]
    rows += [["المجموع", num(invoice["total"]["usd"]), num(invoice["total"]["syp"])],
             ["المدفوع", num(invoice["paid"]["usd"]), num(invoice["paid"]["syp"])],
             ["المتبقي", num(invoice["open"]["usd"]), num(invoice["open"]["syp"])]]
    doc.grid(["البيان", "USD", "SYP"], rows, [100, 40, 40], bold_last=True, numeric={1, 2})
    payments = [p for p in invoice.get("payments", []) if not p["voided"]]
    if payments:
        doc.heading("الدفعات")
        doc.grid(["التاريخ", "المدفوع فعلاً", "سعر الصرف", "القيمة للفاتورة"],
                 [[p["booked_on"], f"{num(p['amount'])} {p['currency']}", num(p["rate"]), f"{num(p['credited'])} {invoice['currency']}"] for p in payments],
                 [35, 50, 40, 55], numeric={1, 2, 3})
    if invoice["voided"]:
        doc.line_text(f"هذه الفاتورة ملغاة: {invoice['void_reason']}", 11, (180, 40, 40), True)
    code = verification(["invoice", invoice["number"], invoice["total"]["usd"] or "", invoice["total"]["syp"] or "", invoice["paid"]["usd"] or "", invoice["status"]])
    doc.signature(signer, code)
    return bytes(doc.output())


def month_report_pdf(summary: dict[str, Any], incomes: list[dict[str, Any]], expenses: list[dict[str, Any]], signer: dict[str, str], rate_text: str) -> bytes:
    """The month: totals per currency, by category, and every income and expense of the month."""
    state = "مغلق" if summary["closed"] else "مفتوح"
    doc = Doc(f"التقرير المالي لشهر {month_name(summary['month'])}", f"حالة الشهر: {state} · سعر الصرف في نهاية الشهر: {rate_text}")
    doc.heading("الملخص (كل عملة على حدة، حسب العملة المدفوعة فعلاً)")
    doc.grid(["البند", "USD", "SYP"], [
        ["إجمالي الإيرادات", num(summary["income"]["usd"]), num(summary["income"]["syp"])],
        ["إجمالي المصروفات", num(summary["expense"]["usd"]), num(summary["expense"]["syp"])],
        ["منها الرواتب", num(summary["salaries"]["usd"]), num(summary["salaries"]["syp"])],
        ["الفائض / العجز", num(summary["surplus"]["usd"]), num(summary["surplus"]["syp"])],
    ], [100, 40, 40], bold_last=True, numeric={1, 2})
    doc.line_text(f"عدد حركات الإيراد: {summary['income_count']} · عدد حركات المصروف: {summary['expense_count']} · "
                  f"فواتير مفتوحة / جزئية: {summary['invoices']['open']} / {summary['invoices']['partial']}", 9, MUTED)
    doc.line_text(f"للمقارنة فقط (كل الحركات محوّلة بسعرها المحفوظ): الفائض بالدولار {num(summary['converted']['surplus']['usd'])} · بالليرة {num(summary['converted']['surplus']['syp'])}", 9, MUTED)
    if summary["income_by_category"]:
        doc.heading("الإيرادات حسب الفئة")
        doc.grid(["الفئة", "USD", "SYP", "العدد"], [[c["name"], num(c["usd"]), num(c["syp"]), str(c["count"])] for c in summary["income_by_category"]], [85, 35, 40, 20], numeric={1, 2, 3})
    if summary["expense_by_category"]:
        doc.heading("المصروفات حسب الفئة")
        doc.grid(["الفئة", "USD", "SYP", "العدد"], [[c["ar"], num(c["usd"]), num(c["syp"]), str(c["count"])] for c in summary["expense_by_category"]], [85, 35, 40, 20], numeric={1, 2, 3})

    def listing(title: str, rows: list[dict[str, Any]], category: str) -> None:
        live = [r for r in rows if not r["voided"]]
        if not live:
            return
        doc.heading(title)
        doc.grid(["التاريخ", "الوصف", "الفئة", "USD", "SYP", "المدفوع فعلاً"],
                 [[r["booked_on"], r["description"][:38], r[category], num(r["usd"]), num(r["syp"]), f"{num(r['amount'])} {r['currency']}"] for r in live],
                 [22, 58, 30, 22, 25, 23], numeric={3, 4, 5})

    listing("الإيرادات", incomes, "category")
    listing("المصروفات", expenses, "category_ar")
    code = verification(["month", summary["month"], summary["income"]["usd"], summary["income"]["syp"], summary["expense"]["usd"], summary["expense"]["syp"]])
    doc.signature(signer, code)
    return bytes(doc.output())


def entries_pdf(kind: str, month: str, rows: list[dict[str, Any]], signer: dict[str, str]) -> bytes:
    """The income or the expenses of one month, every entry with both currencies, the totals per currency really paid."""
    income = kind == "income"
    title = ("الإيرادات" if income else "المصروفات") + f" — {month_name(month)}"
    live = [r for r in rows if not r["voided"]]
    cancelled = len(rows) - len(live)
    doc = Doc(title, f"عدد الحركات: {len(live)}" + (f" · ملغاة (غير محسوبة): {cancelled}" if cancelled else ""))
    if live:
        def who(r: dict[str, Any]) -> str:
            parts = [r.get("payer_name"), r.get("child")] if income else [r.get("recipient"), r.get("employee")]
            return " · ".join(p for p in parts if p)[:26]

        doc.grid(["التاريخ", "الوصف", "الفئة", "USD", "SYP", "المدفوع فعلاً", "الدافع" if income else "المستلم"],
                 [[r["booked_on"], r["description"][:30], (r["category"] if income else r["category_ar"])[:16], num(r["usd"]), num(r["syp"]),
                   f"{num(r['amount'])} {r['currency']}", who(r)] for r in live],
                 [20, 44, 24, 20, 22, 24, 26], numeric={3, 4, 5})
    else:
        doc.line_text("لا توجد حركات في هذا الشهر.", 11, MUTED)
    totals = {"USD": "0", "SYP": "0"}
    for code in totals:
        total = sum((Decimal(r["amount"]) for r in live if r["currency"] == code), Decimal(0))
        totals[code] = str(int(total)) if code == "SYP" and total == total.to_integral_value() else format(total.quantize(Decimal("0.01")), "f")

    def column(paid_in: str | None, key: str) -> str:
        value = sum((Decimal(r[key]) for r in live if paid_in is None or r["currency"] == paid_in), Decimal(0))
        return str(int(value)) if key == "syp" and value == value.to_integral_value() else format(value.quantize(Decimal("0.01")), "f")

    doc.heading("المجموع بالدولار والليرة")
    doc.grid(["", "USD", "SYP"], [
        ["ما دُفع بالدولار (وقيمته بالليرة)", num(column("USD", "usd")), num(column("USD", "syp"))],
        ["ما دُفع بالليرة (وقيمته بالدولار)", num(column("SYP", "usd")), num(column("SYP", "syp"))],
        ["المجموع الكلي", num(column(None, "usd")), num(column(None, "syp"))],
    ], [100, 40, 40], bold_last=True, numeric={1, 2})
    doc.line_text("القيمة بالعملة الأخرى محسوبة بسعر الصرف المحفوظ مع كل حركة.", 9, MUTED)
    code = verification([kind, month, totals["USD"], totals["SYP"], str(len(live))])
    doc.signature(signer, code)
    return bytes(doc.output())


def staff_pdf(people: list[dict[str, Any]], scope: str, signer: dict[str, str]) -> bytes:
    """The staff list of the management (no private notes)."""
    doc = Doc("قائمة الموظفين", ("كل الموظفين" if scope == "all" else "الموظفون الفعّالون فقط") + f" · العدد: {len(people)}")
    if people:
        doc.grid(["الرقم", "الاسم", "الوظيفة", "الهاتف", "تاريخ المباشرة", "الحالة", "الراتب"],
                 [[p["employee_no"], p["name"][:24], (p["job_title"] or "—")[:16], p["phone"] or "—", p["hired_on"] or "—",
                   "فعّال" if p["is_active"] else "غادر" + (f" {p['left_on']}" if p["left_on"] else ""),
                   "—" if p["salary"] is None else f"{num(p['salary'])} {p['salary_currency']}"] for p in people],
                 [18, 40, 26, 26, 22, 24, 24], numeric={0, 3, 4, 6})
    else:
        doc.line_text("لا يوجد موظفون.", 11, MUTED)
    code = verification(["staff", scope, str(len(people))] + [p["employee_no"] for p in people])
    doc.signature(signer, code)
    return bytes(doc.output())
