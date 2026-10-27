"""Accounting area: payroll, monthly and weekly sheets, overview.

Fees themselves live in app.fees. Everything here is only reachable through the same guard
(accountant or admin). USD and SYP are never added or converted. Names and amounts are not logged.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    AccountingEntry,
    Child,
    Employee,
    FeeCharge,
    FeePayment,
    SalaryLine,
)

# key, Arabic label, kind of money the row normally carries
STANDARD_ITEMS = [
    ("registration", "رسوم التسجيل والاشتراكات", "income"),
    ("operating", "المصروفات التشغيلية", "expense"),
    ("salaries", "رواتب المدرسات والموظفين", "expense"),
    ("activities", "الأنشطة والفعاليات", "expense"),
    ("purchases", "المشتريات والوسائل التعليمية", "expense"),
    ("misc", "مصروفات نثرية / أخرى", "expense"),
]
AUTO_ITEMS = {"registration", "salaries"}


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


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


# --- request models ----------------------------------------------------------


class EmployeeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    job_title: str = Field(default="", max_length=80)


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


class SalaryUpdate(BaseModel):
    """Correction of a row; amounts left out (null) stay empty."""

    employee_name: str | None = Field(default=None, max_length=120)
    job_title: str | None = Field(default=None, max_length=80)
    base: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    bonus: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    advance: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    deduction: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    paid_on: date | None = None


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


def auto_values(
    session: Session, period_type: str, year: int, month: int, week_start: date | None, currency: str
) -> dict[str, Decimal]:
    """Registration income (paid fees) and salary expense (net pay) for the period."""
    start, end = sheet_range(period_type, year, month, week_start)
    if period_type == "month":
        paid = session.scalar(
            select(func.coalesce(func.sum(FeePayment.amount), 0))
            .join(FeeCharge, FeeCharge.id == FeePayment.charge_id)
            .where(
                FeePayment.deleted_at.is_(None),
                FeeCharge.currency == currency,
                FeeCharge.year == year,
                FeeCharge.month == month,
            )
        )
        lines = session.scalars(
            select(SalaryLine).where(
                SalaryLine.currency == currency, SalaryLine.year == year, SalaryLine.month == month
            )
        ).all()
    else:
        paid = session.scalar(
            select(func.coalesce(func.sum(FeePayment.amount), 0))
            .join(FeeCharge, FeeCharge.id == FeePayment.charge_id)
            .where(
                FeePayment.deleted_at.is_(None),
                FeeCharge.currency == currency,
                FeePayment.paid_on >= start,
                FeePayment.paid_on <= end,
            )
        )
        lines = session.scalars(
            select(SalaryLine).where(
                SalaryLine.currency == currency, SalaryLine.paid_on >= start, SalaryLine.paid_on <= end
            )
        ).all()
    salaries = sum(
        (net_pay(l.base, l.bonus, l.advance, l.deduction) or ZERO for l in lines), ZERO
    )
    return {"registration": money(paid), "salaries": money(salaries)}


def build_sheet(
    session: Session, period_type: str, year: int, month: int, week_start: date | None, currency: str
) -> dict[str, Any]:
    start, _ = sheet_range(period_type, year, month, week_start)
    stored = session.scalars(
        select(AccountingEntry).where(
            AccountingEntry.period_type == period_type,
            AccountingEntry.year == year,
            AccountingEntry.currency == currency,
            (AccountingEntry.month == month) if period_type == "month" else (AccountingEntry.week_start == start),
        ).order_by(AccountingEntry.created_at)
    ).all()
    by_key = {entry.item_key: entry for entry in stored if entry.item_key != "custom"}
    auto = auto_values(session, period_type, year, month, week_start, currency)
    rows: list[dict[str, Any]] = []
    for key, label, kind in STANDARD_ITEMS:
        entry = by_key.get(key)
        auto_income = auto["registration"] if key == "registration" else ZERO
        auto_expense = auto["salaries"] if key == "salaries" else ZERO
        manual = bool(entry and entry.manual)
        if key in AUTO_ITEMS and not manual:
            income, expense = auto_income, auto_expense
        elif entry:
            income, expense = money(entry.income), money(entry.expense)
        else:
            income = expense = ZERO
        rows.append(
            {
                "id": str(entry.id) if entry else None,
                "key": key,
                "label": label,
                "kind": kind,
                "custom": False,
                "details": entry.details if entry else "",
                "note": entry.note if entry else "",
                "income": str(income),
                "expense": str(expense),
                "auto": key in AUTO_ITEMS,
                "auto_income": str(auto_income),
                "auto_expense": str(auto_expense),
                "manual": manual,
            }
        )
    for entry in stored:
        if entry.item_key == "custom":
            rows.append(
                {
                    "id": str(entry.id), "key": "custom", "label": entry.item_label,
                    "kind": "expense" if money(entry.expense) > 0 or money(entry.income) == 0 else "income",
                    "custom": True, "details": entry.details, "note": entry.note,
                    "income": str(money(entry.income)), "expense": str(money(entry.expense)),
                    "auto": False, "auto_income": "0.00", "auto_expense": "0.00", "manual": True,
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


def build_router(guard: Callable[..., FeesActor]) -> APIRouter:
    router = APIRouter(prefix="/api/admin/accounting")

    # ---- employees ----------------------------------------------------------

    def employee_by_name(session: Session, name: str) -> Employee | None:
        return session.scalar(
            select(Employee).where(func.lower(Employee.name) == name.strip().lower(), Employee.is_active.is_(True))
        )

    @router.get("/employees")
    def list_employees(
        response: Response,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, str]]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.scalars(select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.name)).all()
        return [{"id": str(e.id), "name": e.name, "job_title": e.job_title} for e in rows]

    @router.post("/employees", status_code=201)
    def create_employee(
        payload: EmployeeIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        if employee_by_name(session, payload.name) is not None:
            raise HTTPException(409, "يوجد موظف بهذا الاسم.")
        employee = Employee(name=payload.name.strip(), job_title=payload.job_title.strip())
        session.add(employee)
        session.flush()
        log(session, actor, "employee.create", employee.id, "")
        session.commit()
        return {"id": str(employee.id), "name": employee.name, "job_title": employee.job_title}

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
        check_net(payload.base, payload.bonus, payload.advance, payload.deduction)
        line = get_line(session, line_id)
        for field in ("base", "bonus", "advance", "deduction"):
            value = getattr(payload, field)
            setattr(line, field, None if value is None else money(value))
        line.paid_on = payload.paid_on
        if payload.job_title is not None:
            line.employee.job_title = payload.job_title.strip()
        if payload.employee_name is not None:
            line.employee.name = payload.employee_name.strip()
        log(session, actor, "salary.update", line.id, f"{line.month}/{line.year} {line.currency}")
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
                    start=start.isoformat(), end=end.isoformat())
        return data

    @router.put("/entries")
    def save_entry(
        payload: EntryIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        start, _ = sheet_range(payload.period_type, payload.year, payload.month, payload.week_start)
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
                    AccountingEntry.year == payload.year,
                    AccountingEntry.currency == payload.currency,
                    AccountingEntry.item_key == payload.item_key,
                    (AccountingEntry.month == payload.month) if payload.period_type == "month"
                    else (AccountingEntry.week_start == start),
                )
            )
        created = entry is None
        if entry is None:
            entry = AccountingEntry(
                period_type=payload.period_type, year=payload.year,
                month=payload.month if payload.period_type == "month" else 0,
                week_start=start if payload.period_type != "month" else None,
                currency=payload.currency, item_key=payload.item_key,
            )
            session.add(entry)
        entry.item_label = payload.item_label.strip()
        entry.details = payload.details.strip()
        entry.note = payload.note.strip()
        entry.income, entry.expense = money(payload.income), money(payload.expense)
        entry.manual = payload.manual
        session.flush()
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
            select(FeeCharge, Child).join(Child, Child.id == FeeCharge.child_id).where(FeeCharge.year == year)
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
            for month in range(1, 13):
                totals = build_sheet(session, "month", year, month, None, currency)["totals"]
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
