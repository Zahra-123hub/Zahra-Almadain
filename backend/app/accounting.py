"""Accounting area: payroll, monthly and weekly sheets, overview.

Fees themselves live in app.fees. Everything here is only reachable through the same guard
(accountant or admin). USD and SYP are never added or converted. Names and amounts are not logged.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_session
from app.fees import (
    CURRENCIES,
    ZERO,
    FeesActor,
    Money,
    active_payments,
    log,
    money,
    paid_amount,
    remaining_amount,
)
from app.models import (
    Account,
    AccountingEntry,
    CashOpening,
    Child,
    Employee,
    FeeCharge,
    FeePayment,
    Role,
    SalaryLine,
)

# key, Arabic label, kind of money the row normally carries
STANDARD_ITEMS = [
    ("registration", "رسوم التسجيل والاشتراكات", "income"),
    ("operating", "المصروفات التشغيلية", "expense"),
    ("salaries", "رواتب المدرسات والموظفين", "expense"),
    ("activities", "الأنشطة والفعاليات", "expense"),
    ("purchases", "المشتريات والوسائل التعليمية", "expense"),
    ("buffet", "البوفيه", "expense"),
    ("transport", "وسائل النقل (المواصلات)", "expense"),
    ("advertising", "الإعلانات والدعاية", "expense"),
    ("misc", "مصروفات نثرية / أخرى", "expense"),
]
AUTO_ITEMS = {"registration", "salaries"}
# Rows that can be income (e.g. buffet sales, bus fees) or expense: the user picks the type.
CHOICE_ITEMS = {"buffet", "transport", "advertising"}


# --- calculations (pure, unit tested) ---------------------------------------


def net_pay(
    base: Decimal | None, bonus: Decimal | None, advance: Decimal | None, deduction: Decimal | None
) -> Decimal | None:
    """Net = base + bonus - advance - deduction. Empty bonus/advance/deduction count as 0 in the
    calculation only (nothing is stored); without a base salary there is no net (None)."""
    if base is None:
        return None
    return money(money(base) + money(bonus) - money(advance) - money(deduction))


def salary_totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    keys = ("base", "bonus", "advance", "deduction", "net")
    result = {code: {key: ZERO for key in keys} for code in CURRENCIES}
    for row in rows:
        for key in keys:
            if row[key] is not None:
                result[row["currency"]][key] += Decimal(row[key])
    return {code: {key: str(money(value)) for key, value in bucket.items()} for code, bucket in result.items()}


def week_start_day() -> int:
    """First day of the week for the weekly sheet: 0 = Monday (default) ... 5 = Saturday, 6 = Sunday.
    Set ACCOUNTING_WEEK_START on the server; stored weeks are keyed by their first day."""
    try:
        value = int(os.getenv("ACCOUNTING_WEEK_START", "0"))
    except ValueError:
        return 0
    return value if 0 <= value <= 6 else 0


def week_monday(day: date) -> date:
    return day - timedelta(days=(day.weekday() - week_start_day()) % 7)


# --- request models ----------------------------------------------------------


class EmployeeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    job_title: str = Field(default="", max_length=80)
    account_id: uuid.UUID | None = None  # the person's platform account (teacher / accountant)
    salary: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)  # usual monthly salary
    salary_currency: str = Field(default="SYP", pattern="^(USD|SYP)$")


class SalaryIn(BaseModel):
    employee_id: uuid.UUID | None = None
    employee_name: str = Field(default="", max_length=120)
    job_title: str = Field(default="", max_length=80)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    currency: str = Field(pattern="^(USD|SYP)$")
    base: Decimal = Money
    bonus: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    advance: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    deduction: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    paid_on: date | None = None
    paid_by: str = Field(default="", max_length=120)  # who handed the salary out


class SalaryGenerate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    currency: str = Field(default="SYP", pattern="^(USD|SYP)$")


class SalaryUpdate(BaseModel):
    """Correction of a row; amounts left out (null) stay empty."""

    employee_name: str | None = Field(default=None, max_length=120)
    job_title: str | None = Field(default=None, max_length=80)
    base: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    bonus: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    advance: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    deduction: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    paid_on: date | None = None
    paid_by: str | None = Field(default=None, max_length=120)


class CashIn(BaseModel):
    currency: str = Field(pattern="^(USD|SYP)$")
    opening: Decimal = Money  # money in the cash box when the books start
    start_year: int = Field(ge=2000, le=2100)
    start_month: int = Field(ge=1, le=12)


class EntryIn(BaseModel):
    id: uuid.UUID | None = None
    period_type: str = Field(pattern="^(month|week|day)$")
    year: int = Field(ge=2000, le=2100)
    month: int = Field(default=0, ge=0, le=12)
    week_start: date | None = None
    currency: str = Field(pattern="^(USD|SYP)$")
    item_key: str = Field(max_length=20)
    item_label: str = Field(default="", max_length=120)
    details: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=500)
    income: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    expense: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=2)
    manual: bool = True
    person: str = Field(default="", max_length=120)  # who spent / received the money


# --- serialisation ------------------------------------------------------------


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(money(value))


def salary_row(line: SalaryLine) -> dict[str, Any]:
    return {
        "id": str(line.id),
        "employee_id": str(line.employee_id),
        "employee_name": line.employee.name,
        "job_title": line.employee.job_title,
        "year": line.year,
        "month": line.month,
        "currency": line.currency,
        "base": _text(line.base),
        "bonus": _text(line.bonus),
        "advance": _text(line.advance),
        "deduction": _text(line.deduction),
        "net": _text(net_pay(line.base, line.bonus, line.advance, line.deduction)),
        "paid_on": line.paid_on.isoformat() if line.paid_on else None,
        "paid_by": line.paid_by,
        "recorded_by": line.recorded_by,
        "needs_review": line.needs_review,
        "raw_text": line.raw_text,
        "source": line.source,
    }


def sheet_range(period_type: str, year: int, month: int, week_start: date | None) -> tuple[date, date]:
    if period_type == "day":
        if week_start is None:
            raise HTTPException(422, "حدّد اليوم.")
        return week_start, week_start  # a daily sheet stores its date in week_start
    if period_type == "week":
        if week_start is None:
            raise HTTPException(422, "حدّد بداية الأسبوع.")
        start = week_monday(week_start)
        return start, start + timedelta(days=6)
    if not 1 <= month <= 12:
        raise HTTPException(422, "حدّد الشهر.")
    first = date(year, month, 1)
    last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return first, last


def sheet_year(period_type: str, year: int, start: date) -> int:
    """Monthly sheets use the year given; weekly and daily sheets always use the year of their own date,
    so the year field can never disagree with the date."""
    return year if period_type == "month" else start.year


def _add_days(day: date, days: int) -> date:
    return day + timedelta(days=days)


class Ledger:
    """Everything one currency has in the books, loaded once. Sheets, the monthly series and the cash balance
    are all worked out from this one picture, so they can never disagree.

    Money is counted by the day it moved: fee payments by their payment date, salaries by the day they were
    handed out. Exceptions (monthly sheet only): a payment without a date counts in the month of its fee, a salary
    not yet handed out in its own salary month.
    Rows written by hand: the most summarised sheet wins (month > week > day). Whatever is not written on a
    higher sheet adds up automatically from the weeks and days below it."""

    def __init__(self, currency: str, entries: list[AccountingEntry], payments: list[tuple], salaries: list[tuple]):
        self.currency = currency
        self.payments = payments  # (paid_on or None, amount, fee year, fee month)
        self.salaries = salaries  # (paid_on or None, net pay, year, month)
        self.month_items: dict[tuple[int, int], dict[str, AccountingEntry]] = {}
        self.month_customs: dict[tuple[int, int], list[AccountingEntry]] = {}
        self.week_items: dict[date, dict[str, AccountingEntry]] = {}
        self.week_customs: dict[date, list[AccountingEntry]] = {}
        self.day_items: dict[date, dict[str, AccountingEntry]] = {}
        self.day_customs: dict[date, list[AccountingEntry]] = {}
        for entry in sorted(entries, key=lambda e: (e.created_at is not None, e.created_at)):
            if entry.period_type == "month":
                where_items, where_customs, where = self.month_items, self.month_customs, (entry.year, entry.month)
            elif entry.period_type == "week" and entry.week_start:
                where_items, where_customs, where = self.week_items, self.week_customs, entry.week_start
            elif entry.period_type == "day" and entry.week_start:
                where_items, where_customs, where = self.day_items, self.day_customs, entry.week_start
            else:
                continue
            if entry.item_key == "custom":
                where_customs.setdefault(where, []).append(entry)
            else:
                where_items.setdefault(where, {})[entry.item_key] = entry  # the newest one wins

    @classmethod
    def load(cls, session: Session, currency: str) -> "Ledger":
        entries = list(session.scalars(select(AccountingEntry).where(AccountingEntry.currency == currency)))
        payments = [
            (paid_on, money(amount), year, month)
            for paid_on, amount, year, month in session.execute(
                select(FeePayment.paid_on, FeePayment.amount, FeeCharge.year, FeeCharge.month)
                .join(FeeCharge, FeeCharge.id == FeePayment.charge_id)
                .where(FeePayment.deleted_at.is_(None), FeeCharge.currency == currency)
            )
        ]
        salaries = [
            (line.paid_on, net_pay(line.base, line.bonus, line.advance, line.deduction) or ZERO, line.year, line.month)
            for line in session.scalars(select(SalaryLine).where(SalaryLine.currency == currency))
        ]
        return cls(currency, entries, payments, salaries)

    # ---- automatic items -------------------------------------------------------
    def auto(self, period_type: str, year: int, month: int, start: date, end: date) -> dict[str, Decimal]:
        def total(records: list[tuple]) -> Decimal:
            result = ZERO
            for paid_on, amount, record_year, record_month in records:
                if paid_on is None:
                    hit = period_type == "month" and (record_year, record_month) == (year, month)
                else:
                    hit = start <= paid_on <= end
                if hit:
                    result += amount
            return money(result)

        return {"registration": total(self.payments), "salaries": total(self.salaries)}

    # ---- roll-up of the weeks and days below a sheet ---------------------------
    def _week_in_month(self, week_start: date, year: int, month: int) -> bool:
        middle = _add_days(week_start, 3)  # a week counts for the month most of its days belong to
        return (middle.year, middle.month) == (year, month)

    def _rolled_item(self, period_type: str, key: str, year: int, month: int, start: date, end: date) -> tuple[Decimal, Decimal] | None:
        income = expense = ZERO
        found = False
        if period_type == "week":
            for offset in range((end - start).days + 1):
                entry = self.day_items.get(_add_days(start, offset), {}).get(key)
                if entry is not None:
                    income, expense, found = income + money(entry.income), expense + money(entry.expense), True
        elif period_type == "month":
            weeks = [ws for ws, items in self.week_items.items() if key in items]
            for ws in weeks:
                if self._week_in_month(ws, year, month):
                    entry = self.week_items[ws][key]
                    income, expense, found = income + money(entry.income), expense + money(entry.expense), True
            for day, items in self.day_items.items():
                entry = items.get(key)
                if entry is None or not start <= day <= end:
                    continue
                if any(ws <= day <= _add_days(ws, 6) for ws in weeks):
                    continue  # the weekly row already covers this day
                income, expense, found = income + money(entry.income), expense + money(entry.expense), True
        return (income, expense) if found else None

    def _rolled_customs(self, period_type: str, year: int, month: int, start: date, end: date) -> list[tuple[str, Decimal, Decimal]]:
        sources: list[AccountingEntry] = []
        if period_type == "week":
            for offset in range((end - start).days + 1):
                sources += self.day_customs.get(_add_days(start, offset), [])
        elif period_type == "month":
            for ws, items in self.week_customs.items():
                if self._week_in_month(ws, year, month):
                    sources += items
            for day, items in self.day_customs.items():
                if start <= day <= end:
                    sources += items
        groups: dict[str, list] = {}
        for entry in sources:
            group = groups.setdefault(entry.item_label.strip().lower(), [entry.item_label.strip(), ZERO, ZERO])
            group[1] += money(entry.income)
            group[2] += money(entry.expense)
        return [(label, income, expense) for label, income, expense in groups.values()]

    # ---- a sheet -----------------------------------------------------------------
    def sheet(self, period_type: str, year: int, month: int, week_start: date | None) -> dict[str, Any]:
        start, end = sheet_range(period_type, year, month, week_start)
        if period_type == "month":
            stored, customs = self.month_items.get((year, month), {}), self.month_customs.get((year, month), [])
        elif period_type == "week":
            stored, customs = self.week_items.get(start, {}), self.week_customs.get(start, [])
        else:
            stored, customs = self.day_items.get(start, {}), self.day_customs.get(start, [])
        auto = self.auto(period_type, year, month, start, end)
        rows: list[dict[str, Any]] = []
        for key, label, kind in STANDARD_ITEMS:
            entry = stored.get(key)
            auto_income = auto["registration"] if key == "registration" else ZERO
            auto_expense = auto["salaries"] if key == "salaries" else ZERO
            manual = bool(entry and entry.manual)
            rolled = False
            if key in AUTO_ITEMS and not manual:
                income, expense = auto_income, auto_expense
            elif entry:
                income, expense = money(entry.income), money(entry.expense)
            else:
                income = expense = ZERO
                below = self._rolled_item(period_type, key, year, month, start, end)
                if below is not None:
                    income, expense = below
                    rolled = True
            if key in CHOICE_ITEMS and income > 0 and expense == 0:
                kind = "income"
            rows.append(
                {
                    "id": str(entry.id) if entry else None,
                    "key": key,
                    "label": label,
                    "kind": kind,
                    "choice": key in CHOICE_ITEMS,
                    "custom": False,
                    "rolled": rolled,
                    "details": entry.details if entry else "",
                    "note": entry.note if entry else "",
                    "person": entry.person if entry else "",
                    "entered_by": entry.entered_by if entry else "",
                    "income": str(income),
                    "expense": str(expense),
                    "auto": key in AUTO_ITEMS,
                    "auto_income": str(auto_income),
                    "auto_expense": str(auto_expense),
                    "manual": manual,
                }
            )
        for entry in customs:
            rows.append(
                {
                    "id": str(entry.id), "key": "custom", "label": entry.item_label,
                    "kind": "expense" if money(entry.expense) > 0 or money(entry.income) == 0 else "income",
                    "custom": True, "rolled": False, "details": entry.details, "note": entry.note,
                    "person": entry.person, "entered_by": entry.entered_by,
                    "income": str(money(entry.income)), "expense": str(money(entry.expense)),
                    "auto": False, "auto_income": "0.00", "auto_expense": "0.00", "manual": True,
                }
            )
        for label, income, expense in self._rolled_customs(period_type, year, month, start, end):
            rows.append(
                {
                    "id": None, "key": "rolled", "label": label,
                    "kind": "expense" if expense > 0 or income == 0 else "income",
                    "custom": False, "rolled": True, "details": "", "note": "", "person": "", "entered_by": "",
                    "income": str(income), "expense": str(expense),
                    "auto": False, "auto_income": "0.00", "auto_expense": "0.00", "manual": False,
                }
            )
        income_total = sum((Decimal(r["income"]) for r in rows), ZERO)
        expense_total = sum((Decimal(r["expense"]) for r in rows), ZERO)
        return {
            "rows": rows,
            "totals": {
                "income": str(money(income_total)),
                "expense": str(money(expense_total)),
                "net": str(money(income_total - expense_total)),
            },
        }

    # ---- cash balance --------------------------------------------------------------
    def first_month(self) -> tuple[int, int] | None:
        found: list[tuple[int, int]] = []
        for paid_on, _amount, year, month in self.payments + self.salaries:
            found.append((paid_on.year, paid_on.month) if paid_on else (year, month))
        found += list(self.month_items) + list(self.month_customs)
        for week_start in list(self.week_items) + list(self.week_customs):
            found.append((_add_days(week_start, 3).year, _add_days(week_start, 3).month))
        for day in list(self.day_items) + list(self.day_customs):
            found.append((day.year, day.month))
        return min(found) if found else None

    def cash_months(self, opening: Decimal, start: tuple[int, int], end: tuple[int, int]) -> list[dict[str, str]]:
        """Month by month: balance at the start, income, expense, balance at the end (start..end inclusive)."""
        months: list[dict[str, str]] = []
        balance = money(opening)
        year, month = start
        while (year, month) <= end and len(months) < 240:
            totals = self.sheet("month", year, month, None)["totals"]
            income, expense = Decimal(totals["income"]), Decimal(totals["expense"])
            closing = money(balance + income - expense)
            months.append({"year": year, "month": month, "opening": str(balance), "income": str(income),
                           "expense": str(expense), "closing": str(closing)})
            balance = closing
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return months


def auto_values(
    session: Session, period_type: str, year: int, month: int, week_start: date | None, currency: str
) -> dict[str, Decimal]:
    """Registration income (paid fees) and salary expense (net pay) for the period."""
    start, end = sheet_range(period_type, year, month, week_start)
    return Ledger.load(session, currency).auto(period_type, year, month, start, end)


def build_sheet(
    session: Session, period_type: str, year: int, month: int, week_start: date | None, currency: str
) -> dict[str, Any]:
    return Ledger.load(session, currency).sheet(period_type, year, month, week_start)


def cash_report(session: Session, currency: str, today: date, until: tuple[int, int] | None = None) -> dict[str, Any]:
    """How much money the kindergarten has: opening balance + all income - all expense, month by month,
    up to this month (or up to `until` when a later month is asked for)."""
    ledger = Ledger.load(session, currency)
    opening = session.scalar(select(CashOpening).where(CashOpening.currency == currency))
    if opening is not None:
        start, amount = (opening.start_year, opening.start_month), money(opening.amount)
    else:
        start, amount = ledger.first_month() or (today.year, today.month), ZERO
    end = max((today.year, today.month), until or (0, 0), start)
    months = ledger.cash_months(amount, start, end)
    now = (today.year, today.month)
    to_now = [m for m in months if (m["year"], m["month"]) <= now] or months[:1]
    income = sum((Decimal(m["income"]) for m in to_now), ZERO)
    expense = sum((Decimal(m["expense"]) for m in to_now), ZERO)
    return {
        "currency": currency,
        "configured": opening is not None,
        "opening": str(amount),
        "start_year": start[0],
        "start_month": start[1],
        "income": str(money(income)),
        "expense": str(money(expense)),
        "balance": to_now[-1]["closing"] if to_now else str(amount),
        "months": months,
    }


def build_router(guard: Callable[..., FeesActor]) -> APIRouter:
    router = APIRouter(prefix="/api/admin/accounting")

    # ---- employees ----------------------------------------------------------

    def employee_data(e: Employee, usernames: dict[uuid.UUID, str]) -> dict[str, Any]:
        return {
            "id": str(e.id), "name": e.name, "job_title": e.job_title,
            "salary": None if e.salary is None else str(money(e.salary)),
            "salary_currency": e.salary_currency,
            "account_id": str(e.account_id) if e.account_id else "",
            "account_username": usernames.get(e.account_id, "") if e.account_id else "",
        }

    def link_account(session: Session, employee: Employee, account_id: uuid.UUID | None) -> None:
        """Ties the person to a teacher/accountant account, or unties them (None)."""
        if account_id is None:
            employee.account_id = None
            return
        account = session.scalar(
            select(Account).join(Account.roles).where(Account.id == account_id, Role.name.in_(("teacher", "accountant")))
        )
        if account is None:
            raise HTTPException(404, "الحساب غير موجود أو ليس حساب معلمة/محاسب.")
        taken = session.scalar(
            select(Employee.id).where(Employee.account_id == account_id, Employee.id != employee.id)
        )
        if taken is not None:
            raise HTTPException(409, "هذا الحساب مرتبط بموظف آخر.")
        employee.account_id = account_id

    def employee_by_name(session: Session, name: str) -> Employee | None:
        return session.scalar(
            select(Employee).where(func.lower(Employee.name) == name.strip().lower(), Employee.is_active.is_(True))
        )

    @router.get("/employees")
    def list_employees(
        response: Response,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.scalars(select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.name)).all()
        usernames = {
            a.id: a.username
            for a in session.scalars(select(Account).where(Account.id.in_([e.account_id for e in rows if e.account_id])))
        }
        return [employee_data(e, usernames) for e in rows]

    @router.get("/staff-accounts")
    def staff_accounts(
        response: Response,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        """Teacher and accountant accounts a saved person can be tied to (names only, no personal data)."""
        response.headers["Cache-Control"] = "no-store"
        accounts = session.scalars(
            select(Account)
            .join(Account.roles)
            .where(Role.name.in_(("teacher", "accountant")), Account.is_active.is_(True))
            .order_by(Account.username)
        ).unique().all()
        taken = {
            e.account_id: e.name
            for e in session.scalars(select(Employee).where(Employee.account_id.is_not(None), Employee.is_active.is_(True)))
        }
        return [
            {"id": str(a.id), "username": a.username, "roles": sorted(r.name for r in a.roles if r.name in ("teacher", "accountant")),
             "linked_to": taken.get(a.id, "")}
            for a in accounts
        ]

    @router.post("/employees", status_code=201)
    def create_employee(
        payload: EmployeeIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        if employee_by_name(session, payload.name) is not None:
            raise HTTPException(409, "يوجد موظف بهذا الاسم.")
        employee = Employee(
            name=payload.name.strip(), job_title=payload.job_title.strip(),
            salary=None if payload.salary is None else money(payload.salary),
            salary_currency=payload.salary_currency,
        )
        session.add(employee)
        session.flush()
        link_account(session, employee, payload.account_id)
        log(session, actor, "employee.create", employee.id, "")
        session.commit()
        account = session.get(Account, employee.account_id) if employee.account_id else None
        return employee_data(employee, {account.id: account.username} if account else {})

    @router.patch("/employees/{employee_id}")
    def update_employee(
        employee_id: uuid.UUID,
        payload: EmployeeIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        employee = session.get(Employee, employee_id)
        if employee is None or not employee.is_active:
            raise HTTPException(404, "الموظف غير موجود.")
        clash = session.scalar(
            select(Employee.id).where(
                func.lower(Employee.name) == payload.name.strip().lower(),
                Employee.is_active.is_(True),
                Employee.id != employee.id,
            )
        )
        if clash is not None:
            raise HTTPException(409, "يوجد موظف بهذا الاسم.")
        employee.name = payload.name.strip()
        employee.job_title = payload.job_title.strip()
        if "salary" in payload.model_fields_set:  # only touched when the form sends it
            employee.salary = None if payload.salary is None else money(payload.salary)
            employee.salary_currency = payload.salary_currency
        if "account_id" in payload.model_fields_set:  # only touched when the form sends it
            link_account(session, employee, payload.account_id)
        log(session, actor, "employee.update", employee.id, "")
        session.commit()
        account = session.get(Account, employee.account_id) if employee.account_id else None
        return employee_data(employee, {account.id: account.username} if account else {})

    @router.delete("/employees/{employee_id}", status_code=204)
    def remove_employee(
        employee_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> Response:
        """Takes the person off the list of saved names; old salary rows keep the name."""
        employee = session.get(Employee, employee_id)
        if employee is None:
            raise HTTPException(404, "الموظف غير موجود.")
        employee.is_active = False
        log(session, actor, "employee.remove", employee.id, "")
        session.commit()
        return Response(status_code=204)

    @router.get("/names")
    def saved_names(
        response: Response,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, list[str]]:
        """Names typed before, offered as suggestions so nobody has to retype them."""
        response.headers["Cache-Control"] = "no-store"

        def distinct(column, *conditions) -> list[str]:
            query = select(column).where(column != "", *conditions).distinct().order_by(column)
            return [value for (value,) in session.execute(query) if value]

        staff = distinct(Employee.name, Employee.is_active.is_(True))
        persons = sorted(
            set(staff)
            | set(distinct(AccountingEntry.person))
            | set(distinct(SalaryLine.paid_by))
        )
        payers = distinct(FeePayment.payer_name, FeePayment.deleted_at.is_(None))
        return {"staff": staff, "persons": persons, "payers": payers}

    # ---- salaries -----------------------------------------------------------

    @router.get("/salaries")
    def list_salaries(
        response: Response,
        year: int | None = None,
        month: int | None = None,
        currency: str = "",
        needs_review: bool | None = None,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        query = select(SalaryLine)
        if year:
            query = query.where(SalaryLine.year == year)
        if month:
            query = query.where(SalaryLine.month == month)
        if currency in CURRENCIES:
            query = query.where(SalaryLine.currency == currency)
        if needs_review is not None:
            query = query.where(SalaryLine.needs_review.is_(needs_review))
        rows = [salary_row(line) for line in session.scalars(query).unique().all()]
        rows.sort(key=lambda r: r["employee_name"])
        for number, row in enumerate(rows, start=1):
            row["n"] = number
        return {"rows": rows, "totals": salary_totals(rows)}

    def resolve_employee(session: Session, actor: FeesActor, payload: SalaryIn) -> Employee:
        if payload.employee_id is not None:
            employee = session.get(Employee, payload.employee_id)
            if employee is None or not employee.is_active:
                raise HTTPException(404, "الموظف غير موجود.")
            return employee
        name = payload.employee_name.strip()
        if len(name) < 2:
            raise HTTPException(422, "اكتب اسم الموظف أو اختره من القائمة.")
        employee = employee_by_name(session, name)
        if employee is None:
            employee = Employee(name=name, job_title=payload.job_title.strip())
            session.add(employee)
            session.flush()
            log(session, actor, "employee.create", employee.id, "")
        elif payload.job_title.strip():
            employee.job_title = payload.job_title.strip()
        return employee

    def check_net(base: Decimal | None, bonus: Decimal | None, advance: Decimal | None, deduction: Decimal | None) -> None:
        net = net_pay(base, bonus, advance, deduction)
        if net is not None and net < 0:
            raise HTTPException(422, "الصافي المستحق سالب: السلف والخصومات أكبر من الراتب والمكافآت.")

    @router.post("/salaries/generate")
    def generate_salaries(
        payload: SalaryGenerate,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, int]:
        """One payroll row per employee with a saved salary (in that currency) that has none for the month."""
        created = skipped = 0
        employees = session.scalars(
            select(Employee).where(
                Employee.is_active.is_(True),
                Employee.salary.is_not(None),
                Employee.salary_currency == payload.currency,
            )
        ).all()
        for employee in employees:
            exists = session.scalar(
                select(SalaryLine.id).where(
                    SalaryLine.employee_id == employee.id, SalaryLine.year == payload.year,
                    SalaryLine.month == payload.month, SalaryLine.currency == payload.currency,
                )
            )
            if exists is not None:
                skipped += 1
                continue
            session.add(SalaryLine(
                employee_id=employee.id, year=payload.year, month=payload.month, currency=payload.currency,
                base=money(employee.salary), bonus=ZERO, advance=ZERO, deduction=ZERO,
                recorded_by=actor.name[:80],
            ))
            created += 1
        log(session, actor, "salary.generate", f"{payload.month}/{payload.year}", f"{created} {payload.currency}")
        session.commit()
        return {"created": created, "skipped": skipped}

    @router.post("/salaries", status_code=201)
    def create_salary(
        payload: SalaryIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        check_net(payload.base, payload.bonus, payload.advance, payload.deduction)
        employee = resolve_employee(session, actor, payload)
        line = SalaryLine(
            employee_id=employee.id, year=payload.year, month=payload.month, currency=payload.currency,
            base=money(payload.base), bonus=money(payload.bonus), advance=money(payload.advance),
            deduction=money(payload.deduction), paid_on=payload.paid_on,
            paid_by=payload.paid_by.strip(), recorded_by=actor.name[:80],
        )
        session.add(line)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "يوجد سطر راتب لهذا الموظف في الشهر والعملة نفسيهما.") from exc
        log(session, actor, "salary.create", line.id, f"{payload.month}/{payload.year} {payload.currency}")
        session.commit()
        session.refresh(line)
        return salary_row(line)

    def get_line(session: Session, line_id: uuid.UUID) -> SalaryLine:
        line = session.scalar(select(SalaryLine).where(SalaryLine.id == line_id).with_for_update())
        if line is None:
            raise HTTPException(404, "سطر الراتب غير موجود.")
        return line

    @router.patch("/salaries/{line_id}")
    def update_salary(
        line_id: uuid.UUID,
        payload: SalaryUpdate,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        line = get_line(session, line_id)
        sent = payload.model_fields_set  # a field that was not sent stays as it is (null clears it)
        amounts = ("base", "bonus", "advance", "deduction")
        merged = {name: (getattr(payload, name) if name in sent else getattr(line, name)) for name in amounts}
        check_net(merged["base"], merged["bonus"], merged["advance"], merged["deduction"])
        before = f"{line.base} → "
        for name in amounts:
            if name in sent:
                value = getattr(payload, name)
                setattr(line, name, None if value is None else money(value))
        if "paid_on" in sent:
            line.paid_on = payload.paid_on
        if payload.paid_by is not None:
            line.paid_by = payload.paid_by.strip()
        if payload.employee_name is not None:
            new_name = payload.employee_name.strip()
            if len(new_name) < 2:
                raise HTTPException(422, "اسم الموظف مطلوب (حرفان على الأقل).")
            if new_name != line.employee.name:
                clash = session.scalar(
                    select(Employee.id).where(
                        func.lower(Employee.name) == new_name.lower(),
                        Employee.is_active.is_(True),
                        Employee.id != line.employee.id,
                    )
                )
                if clash is not None:
                    raise HTTPException(409, "يوجد موظف بهذا الاسم.")
                line.employee.name = new_name
        if payload.job_title is not None:
            line.employee.job_title = payload.job_title.strip()
        line.recorded_by = actor.name[:80]
        log(session, actor, "salary.update", line.id, f"{line.month}/{line.year} {line.currency} {before}{line.base}")
        session.commit()
        session.refresh(line)
        return salary_row(line)

    @router.post("/salaries/{line_id}/reviewed")
    def salary_reviewed(
        line_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        line = get_line(session, line_id)
        line.needs_review = False
        log(session, actor, "salary.reviewed", line.id, "")
        session.commit()
        session.refresh(line)
        return salary_row(line)

    @router.delete("/salaries/{line_id}", status_code=204)
    def delete_salary(
        line_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> Response:
        line = get_line(session, line_id)
        log(session, actor, "salary.delete", line.id, f"{line.month}/{line.year} {line.currency}")
        session.delete(line)
        session.commit()
        return Response(status_code=204)

    # ---- monthly / weekly sheets -------------------------------------------

    @router.get("/sheet")
    def sheet(
        response: Response,
        period_type: str,
        year: int,
        currency: str,
        month: int = 0,
        week_start: date | None = None,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        if period_type not in ("month", "week", "day") or currency not in CURRENCIES:
            raise HTTPException(422, "نوع الجدول أو العملة غير صالح.")
        start, end = sheet_range(period_type, year, month, week_start)
        data = build_sheet(session, period_type, year, month, week_start, currency)
        data.update(period_type=period_type, year=year, month=month, currency=currency,
                    start=start.isoformat(), end=end.isoformat(), balance=None)
        if period_type == "month":
            cash = cash_report(session, currency, date.today(), until=(year, month))
            current = next((m for m in cash["months"] if (m["year"], m["month"]) == (year, month)), None)
            if current is not None and cash["configured"]:
                data["balance"] = {"opening": current["opening"], "closing": current["closing"]}
        return data

    @router.get("/cash")
    def cash(
        response: Response,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """The cash balance per currency, with the month-by-month trail. USD and SYP are never mixed."""
        response.headers["Cache-Control"] = "no-store"
        return {code: cash_report(session, code, date.today()) for code in CURRENCIES}

    @router.put("/cash")
    def set_cash_opening(
        payload: CashIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """Sets the money the kindergarten had at the start of a month; the balance is counted from there."""
        row = session.scalar(select(CashOpening).where(CashOpening.currency == payload.currency))
        if row is None:
            row = CashOpening(currency=payload.currency)
            session.add(row)
        row.amount = money(payload.opening)
        row.start_year, row.start_month = payload.start_year, payload.start_month
        row.updated_by = actor.name[:80]
        log(session, actor, "cash.opening", payload.currency, f"{payload.start_month}/{payload.start_year}")
        session.commit()
        return cash_report(session, payload.currency, date.today())

    @router.put("/entries")
    def save_entry(
        payload: EntryIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        start, _ = sheet_range(payload.period_type, payload.year, payload.month, payload.week_start)
        year = sheet_year(payload.period_type, payload.year, start)
        standard = {key for key, _label, _kind in STANDARD_ITEMS}
        if payload.item_key != "custom" and payload.item_key not in standard:
            raise HTTPException(422, "بند غير معروف.")
        if payload.item_key == "custom" and not payload.item_label.strip():
            raise HTTPException(422, "اكتب اسم البند.")
        entry: AccountingEntry | None
        if payload.item_key == "custom":
            entry = session.get(AccountingEntry, payload.id) if payload.id else None
        else:
            entry = session.scalar(
                select(AccountingEntry).where(
                    AccountingEntry.period_type == payload.period_type,
                    AccountingEntry.year == year,
                    AccountingEntry.currency == payload.currency,
                    AccountingEntry.item_key == payload.item_key,
                    (AccountingEntry.month == payload.month) if payload.period_type == "month"
                    else (AccountingEntry.week_start == start),
                ).order_by(AccountingEntry.created_at.desc())
            )
        created = entry is None
        if entry is None:
            entry = AccountingEntry(
                period_type=payload.period_type, year=year,
                month=payload.month if payload.period_type == "month" else 0,
                week_start=start if payload.period_type != "month" else None,
                currency=payload.currency, item_key=payload.item_key,
            )
            session.add(entry)
        entry.item_label = payload.item_label.strip()
        entry.details = payload.details.strip()
        entry.note = payload.note.strip()
        entry.person = payload.person.strip()
        entry.entered_by = actor.name[:80]
        entry.income, entry.expense = money(payload.income), money(payload.expense)
        entry.manual = payload.manual
        if payload.manual and payload.item_key in AUTO_ITEMS:
            # Saving only a note / name next to an unchanged amount must not freeze the automatic value.
            auto = auto_values(session, payload.period_type, payload.year, payload.month, payload.week_start, payload.currency)
            if payload.item_key == "registration":
                same = money(payload.income) == auto["registration"] and money(payload.expense) == ZERO
            else:
                same = money(payload.expense) == auto["salaries"] and money(payload.income) == ZERO
            if same:
                entry.manual = False
        session.flush()
        if payload.item_key != "custom":  # two people saving the same row at once must not leave two rows
            for extra in session.scalars(
                select(AccountingEntry).where(
                    AccountingEntry.period_type == payload.period_type,
                    AccountingEntry.year == year,
                    AccountingEntry.currency == payload.currency,
                    AccountingEntry.item_key == payload.item_key,
                    (AccountingEntry.month == payload.month) if payload.period_type == "month"
                    else (AccountingEntry.week_start == start),
                    AccountingEntry.id != entry.id,
                )
            ).all():
                session.delete(extra)
        log(session, actor, "entry.create" if created else "entry.update", entry.id,
            f"{payload.period_type} {payload.item_key} {payload.currency}")
        session.commit()
        data = build_sheet(session, payload.period_type, payload.year, payload.month, payload.week_start, payload.currency)
        return data

    @router.delete("/entries/{entry_id}")
    def delete_entry(
        entry_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """Removes a custom row, or resets a standard row to its automatic value."""
        entry = session.get(AccountingEntry, entry_id)
        if entry is None:
            raise HTTPException(404, "السطر غير موجود.")
        period = (entry.period_type, entry.year, entry.month, entry.week_start, entry.currency)
        log(session, actor, "entry.delete", entry.id, f"{entry.period_type} {entry.item_key} {entry.currency}")
        session.delete(entry)
        session.commit()
        return build_sheet(session, period[0], period[1], period[2], period[3], period[4])

    # ---- overview -----------------------------------------------------------

    @router.get("/overview")
    def overview(
        response: Response,
        year: int,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        charges = session.execute(
            select(FeeCharge, Child)
            .join(Child, Child.id == FeeCharge.child_id)
            .where(FeeCharge.year == year)
            .options(selectinload(FeeCharge.payments))
        ).all()
        result: dict[str, Any] = {}
        for currency in CURRENCIES:
            cells: dict[tuple[str, int], dict[str, Any]] = {}
            for charge, child in charges:
                if charge.currency != currency:
                    continue
                cell = cells.setdefault(
                    (child.class_name or "—", charge.month),
                    {"required": ZERO, "paid": ZERO, "remaining": ZERO, "children_open": set()},
                )
                open_amount = remaining_amount(charge)
                if charge.amount is not None:
                    cell["required"] += money(charge.amount)
                    cell["remaining"] += open_amount
                cell["paid"] += paid_amount(charge)
                if open_amount is not None and open_amount > 0:
                    cell["children_open"].add(child.id)
            by_class: dict[str, list[dict[str, Any]]] = {}
            for (class_name, month), cell in sorted(cells.items()):
                by_class.setdefault(class_name, []).append(
                    {
                        "month": month,
                        "required": str(money(cell["required"])),
                        "paid": str(money(cell["paid"])),
                        "remaining": str(money(cell["remaining"])),
                        "children_open": len(cell["children_open"]),
                    }
                )
            series = []
            ledger = Ledger.load(session, currency)
            for month in range(1, 13):
                totals = ledger.sheet("month", year, month, None)["totals"]
                series.append({"month": month, "income": totals["income"], "expense": totals["expense"]})
            open_children = len({
                child.id for charge, child in charges
                if charge.currency == currency and (remaining_amount(charge) or 0) > 0
            })
            result[currency] = {"classes": by_class, "series": series, "children_open": open_children}
        result["review"] = {
            "fees": session.scalar(select(func.count()).select_from(FeeCharge).where(FeeCharge.needs_review.is_(True))) or 0,
            "salaries": session.scalar(select(func.count()).select_from(SalaryLine).where(SalaryLine.needs_review.is_(True))) or 0,
        }
        return result

    return router
