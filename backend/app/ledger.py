"""The cash book: one calculation for how much money the kindergarten has, per currency.

Money moves in three places and nowhere else:
  * fee payments (a payment is an income, a refund is a negative income),
  * salaries that were really paid out (a salary without a payment date moves no money),
  * bookings of the cash book (typed in by hand, or taken over from the old sheets).

Cash balance = opening + every income - every expense, per currency. USD and SYP are never added or converted.
Two figures are kept apart:
  * the CASH balance counts real movements only,
  * the HISTORICAL balance also counts the historical adjustments that keep old monthly figures explainable.
Nothing here writes data; the helpers at the end (bookings, cancellations) are used by app.finance.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.fees import CURRENCIES, ZERO, FeesActor, ensure_open, money
from app.models import (
    CashOpening,
    CashTransaction,
    Child,
    Employee,
    EntryReceipt,
    FeeAuditLog,
    FeeCharge,
    FeePayment,
    LedgerCutover,
    PeriodLock,
    SalaryLine,
)

# ---- categories ------------------------------------------------------------------------------------------------------------
INCOME_CATEGORIES = ("fees", "donations", "other_income")
EXPENSE_CATEGORIES = (
    "salaries", "rent", "food", "operating", "activities", "material", "transport", "advertising", "other_expense",
)
SYSTEM_CATEGORIES = ("fees", "salaries")  # only the fee payments and the salary payments may carry these
CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "fees": {"ar": "رسوم الأطفال", "de": "Gebühren"},
    "donations": {"ar": "تبرعات", "de": "Spenden"},
    "other_income": {"ar": "إيرادات أخرى", "de": "Sonstige Einnahmen"},
    "salaries": {"ar": "الرواتب", "de": "Gehälter"},
    "rent": {"ar": "الإيجار", "de": "Miete"},
    "food": {"ar": "الطعام", "de": "Lebensmittel"},
    "operating": {"ar": "المصروفات التشغيلية", "de": "Laufender Betrieb"},
    "activities": {"ar": "الأنشطة", "de": "Aktivitäten"},
    "material": {"ar": "المواد والمستلزمات", "de": "Material"},
    "transport": {"ar": "المواصلات", "de": "Transport"},
    "advertising": {"ar": "الإعلانات", "de": "Werbung"},
    "other_expense": {"ar": "مصروفات أخرى", "de": "Sonstiges"},
}

# how a date of a movement came about (every movement has exactly one of these)
DATE_BASES = ("actual", "estimated_fee_month", "legacy_month_end", "legacy_week_mid", "derived_payment_date")
SOURCES = ("fee_payment", "salary_payment", "booking", "legacy", "legacy_adjustment")
ADJUSTMENT_KINDS = ("salary_unpaid", "manual_override", "salary_counter")
NOT_IN_CASH = ("salary_unpaid", "salary_counter")  # historical adjustments that never moved real money


def categories_for(kind: str) -> tuple[str, ...]:
    return INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES


def category_list() -> dict[str, Any]:
    def rows(keys: tuple[str, ...]) -> list[dict[str, Any]]:
        return [{"key": key, "ar": CATEGORY_LABELS[key]["ar"], "de": CATEGORY_LABELS[key]["de"], "system": key in SYSTEM_CATEGORIES} for key in keys]

    return {"income": rows(INCOME_CATEGORIES), "expense": rows(EXPENSE_CATEGORIES)}


# ---- the switch between the old sheets and the cash book ---------------------------------------------------------------------
def cutover_row(session: Session) -> LedgerCutover | None:
    return session.get(LedgerCutover, 1)


def ledger_mode(session: Session) -> str:
    """"legacy" (no cutover yet), "shadow" (the new calculation runs alongside) or "live" (the cash book is the truth)."""
    row = cutover_row(session)
    return "legacy" if row is None else row.state


def is_live(session: Session) -> bool:
    return ledger_mode(session) == "live"


def count_live_write(session: Session) -> None:
    """Every new booking or cancellation counts: after the first one there is no way back to the old sheets."""
    row = cutover_row(session)
    if row is not None and row.state == "live":
        row.live_writes = (row.live_writes or 0) + 1


def require_live(session: Session) -> None:
    if not is_live(session):
        raise HTTPException(409, "دفتر الصندوق الجديد لم يُفعَّل بعد.")


def refuse_when_live(session: Session, what: str = "الحذف") -> None:
    """After the switch nothing financial is deleted for good: it is cancelled with a reason."""
    if is_live(session):
        raise HTTPException(409, f"لا يُسمح بـ{what} بعد الآن؛ استخدم الإلغاء مع ذكر السبب (يبقى السجل ظاهراً).")


# ---- small helpers -------------------------------------------------------------------------------------------------------------
def net_pay(base: Decimal | None, bonus: Decimal | None, advance: Decimal | None, deduction: Decimal | None) -> Decimal | None:
    """Same rule as app.accounting.net_pay (a test keeps the two equal): without a base there is no net."""
    if base is None:
        return None
    return money(money(base) + money(bonus) - money(advance) - money(deduction))


def last_day(year: int, month: int) -> date:
    return date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)


def month_key(day: date) -> tuple[int, int]:
    return (day.year, day.month)


def month_is_closed(session: Session, year: int, month: int) -> bool:
    return session.scalar(select(PeriodLock.id).where(PeriodLock.year == year, PeriodLock.month == month)) is not None


def audit(
    session: Session, actor: FeesActor, action: str, entity_type: str, entity_id: Any,
    before: dict[str, Any] | None = None, after: dict[str, Any] | None = None, reason: str = "", details: str = "",
) -> None:
    """One line of the activity log: who, when (the time stamp), what, from which value to which, and why."""
    from app import activity

    activity.record(
        session, actor_id=actor.account_id, actor_name=actor.name, domain="finance", action=action, entity_type=entity_type, entity_id=entity_id,
        before=before, after=after, reason=reason, details=details,
    )


# ---- movements ---------------------------------------------------------------------------------------------------------------------
@dataclass
class Movement:
    day: date
    currency: str
    kind: str  # income | expense (a refund is a negative income)
    amount: Decimal
    category: str
    description: str
    source: str
    source_id: str
    date_basis: str = "actual"
    counts_in_cash: bool = True
    adjustment_kind: str = ""
    actor: str = ""
    created_at: datetime | None = None
    voided: bool = False
    void_reason: str = ""
    voided_by: str = ""
    voided_at: datetime | None = None
    counterparty: str = ""
    receipt_no: str = ""
    receipts: int = 0
    legacy_note: str = ""
    editable: bool = False
    version: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        label = CATEGORY_LABELS.get(self.category, {"ar": self.category, "de": self.category})
        return {
            "day": self.day.isoformat(), "currency": self.currency, "kind": self.kind, "amount": str(money(self.amount)),
            "category": self.category, "category_ar": label["ar"], "category_de": label["de"],
            "description": self.description, "source": self.source, "source_id": self.source_id,
            "date_basis": self.date_basis, "counts_in_cash": self.counts_in_cash, "adjustment_kind": self.adjustment_kind,
            "actor": self.actor, "created_at": self.created_at.isoformat() if self.created_at else None,
            "voided": self.voided, "void_reason": self.void_reason, "voided_by": self.voided_by,
            "voided_at": self.voided_at.isoformat() if self.voided_at else None,
            "counterparty": self.counterparty, "receipt_no": self.receipt_no, "receipts": self.receipts,
            "needs_receipt": self.needs_receipt, "legacy_note": self.legacy_note, "editable": self.editable,
            "version": self.version, **self.extra,
        }

    @property
    def needs_receipt(self) -> bool:
        """A manual or taken-over expense that has neither a receipt file nor a receipt number."""
        return (
            self.source in ("booking", "legacy") and self.kind == "expense" and not self.voided
            and not self.receipts and not self.receipt_no.strip()
        )


def receipt_counts(session: Session, transactions: list[CashTransaction]) -> dict[uuid.UUID, int]:
    """Receipt files per booking (its own files plus the files of the old sheet row it was taken over from)."""
    ids = [t.id for t in transactions]
    legacy = {t.legacy_entry_id: t.id for t in transactions if t.legacy_entry_id}
    counts: dict[uuid.UUID, int] = {}
    if ids:
        for tid, number in session.execute(
            select(EntryReceipt.transaction_id, func.count()).where(EntryReceipt.transaction_id.in_(ids), EntryReceipt.removed_at.is_(None)).group_by(EntryReceipt.transaction_id)
        ).all():
            counts[tid] = counts.get(tid, 0) + number
    if legacy:
        for entry_id, number in session.execute(
            select(EntryReceipt.entry_id, func.count()).where(EntryReceipt.entry_id.in_(list(legacy)), EntryReceipt.removed_at.is_(None)).group_by(EntryReceipt.entry_id)
        ).all():
            tid = legacy[entry_id]
            counts[tid] = counts.get(tid, 0) + number
    return counts


def movements(
    session: Session, currency: str, start: date | None = None, end: date | None = None, include_voided: bool = False,
) -> list[Movement]:
    """Every movement of one currency, from the three places, oldest first. Cancelled ones only when asked for."""
    rows: list[Movement] = []

    payments = session.execute(
        select(FeePayment, FeeCharge, Child)
        .join(FeeCharge, FeeCharge.id == FeePayment.charge_id)
        .join(Child, Child.id == FeeCharge.child_id)
        .where(FeeCharge.currency == currency)
    ).all()
    for payment, charge, child in payments:
        voided = payment.deleted_at is not None
        if voided and not include_voided:
            continue
        refund = money(payment.amount) < 0
        if payment.paid_on is not None:
            day, basis = payment.paid_on, "actual"
        else:  # an imported payment without a date: counted on the last day of the month of its fee, and marked as such
            day, basis = last_day(charge.year, charge.month), "estimated_fee_month"
        rows.append(Movement(
            day=day, currency=currency, kind="income", amount=money(payment.amount), category="fees",
            description=("استرداد: " if refund else "") + (payment.note or "").strip(), source="fee_payment", source_id=str(payment.id),
            date_basis=basis, actor=payment.created_by_name or "", created_at=payment.created_at, voided=voided,
            void_reason=payment.void_reason or "", voided_by=payment.voided_by or "", voided_at=payment.deleted_at,
            counterparty=payment.payer_name or "", receipt_no=payment.receipt_no or "",
            extra={"child": child.display_name, "fee_month": f"{charge.year}-{charge.month:02d}", "refund": refund, "charge_id": str(charge.id)},
        ))

    salaries = session.execute(
        select(SalaryLine, Employee).join(Employee, Employee.id == SalaryLine.employee_id).where(SalaryLine.currency == currency, SalaryLine.paid_on.is_not(None))
    ).all()
    for line, employee in salaries:
        voided = line.voided_at is not None
        if voided and not include_voided:
            continue
        net = net_pay(line.base, line.bonus, line.advance, line.deduction)
        if net is None or net == 0:
            continue
        rows.append(Movement(
            day=line.paid_on, currency=currency, kind="expense", amount=net, category="salaries", description="",
            source="salary_payment", source_id=str(line.id), actor=line.paid_by or line.recorded_by or "", created_at=line.created_at,
            voided=voided, void_reason=line.void_reason or "", voided_by=line.voided_by or "", voided_at=line.voided_at,
            counterparty=employee.name, extra={"employee": employee.name, "salary_month": f"{line.year}-{line.month:02d}"},
        ))

    transactions = list(session.scalars(select(CashTransaction).where(CashTransaction.currency == currency)))
    paid_lines = {
        line_id for (line_id,) in session.execute(
            select(SalaryLine.id).where(SalaryLine.currency == currency, SalaryLine.paid_on.is_not(None), SalaryLine.voided_at.is_(None))
        ).all()
    }
    countered = {t.reverses_adjustment_id for t in transactions if t.adjustment_kind == "salary_counter" and t.voided_at is None}
    counts = receipt_counts(session, transactions)
    for t in transactions:
        voided = t.voided_at is not None
        if voided and not include_voided:
            continue
        if (t.adjustment_kind == "salary_unpaid" and not voided and t.adjusts_salary_line_id in paid_lines and t.id not in countered):
            # the salary was paid out meanwhile but this adjustment was not cancelled: it must never count twice
            continue
        source = t.origin if t.origin in ("legacy", "legacy_adjustment") else "booking"
        rows.append(Movement(
            day=t.booked_on, currency=currency, kind=t.kind, amount=money(t.amount), category=t.category, description=t.description or "",
            source=source, source_id=str(t.id), date_basis=t.date_basis or "actual", counts_in_cash=bool(t.counts_in_cash),
            adjustment_kind=t.adjustment_kind or "", actor=t.created_by or "", created_at=t.created_at, voided=voided,
            void_reason=t.void_reason or "", voided_by=t.voided_by or "", voided_at=t.voided_at, counterparty=t.counterparty or "",
            receipt_no=t.receipt_no or "", receipts=counts.get(t.id, 0), legacy_note=t.legacy_note or "",
            editable=(t.origin == "manual" and not voided), version=t.version or 1,
        ))

    rows = [m for m in rows if (start is None or m.day >= start) and (end is None or m.day <= end)]
    rows.sort(key=lambda m: (m.day, m.created_at or datetime.min, m.source_id))
    return rows


# ---- the balance ---------------------------------------------------------------------------------------------------------------------
def opening_of(session: Session, currency: str) -> tuple[Decimal, tuple[int, int]] | None:
    row = session.scalar(select(CashOpening).where(CashOpening.currency == currency))
    return None if row is None else (money(row.amount), (row.start_year, row.start_month))


def month_series(
    session: Session, currency: str, today: date, until: tuple[int, int] | None = None, rows: list[Movement] | None = None,
) -> dict[str, Any]:
    """Month by month from the opening month: the cash balance and, next to it, the historical one."""
    rows = rows if rows is not None else movements(session, currency)
    opening = opening_of(session, currency)
    if opening is not None:
        amount, start = opening
    else:
        amount = ZERO
        start = min((month_key(m.day) for m in rows), default=month_key(today))
    end = max(month_key(today), until or (0, 0), start)
    rows = [m for m in rows if month_key(m.day) >= start]
    by_month: dict[tuple[int, int], list[Movement]] = {}
    for m in rows:
        by_month.setdefault(month_key(m.day), []).append(m)
    months: list[dict[str, Any]] = []
    cash = hist = money(amount)
    year, month = start
    while (year, month) <= end and len(months) < 240:
        incomes = expenses = h_incomes = h_expenses = ZERO
        for m in by_month.get((year, month), []):
            if m.kind == "income":
                h_incomes += m.amount
                if m.counts_in_cash:
                    incomes += m.amount
            else:
                h_expenses += m.amount
                if m.counts_in_cash:
                    expenses += m.amount
        months.append({
            "year": year, "month": month, "opening": str(cash), "income": str(money(incomes)), "expense": str(money(expenses)),
            "closing": str(money(cash + incomes - expenses)),
            "hist_opening": str(hist), "hist_income": str(money(h_incomes)), "hist_expense": str(money(h_expenses)),
            "hist_closing": str(money(hist + h_incomes - h_expenses)),
        })
        cash, hist = money(cash + incomes - expenses), money(hist + h_incomes - h_expenses)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {"opening": str(money(amount)), "configured": opening is not None, "start": start, "months": months}


def cash_report(session: Session, currency: str, today: date, until: tuple[int, int] | None = None) -> dict[str, Any]:
    """The same shape the old /cash answer has, now counted from the cash book (cash balance, real movements only)."""
    series = month_series(session, currency, today, until)
    months = series["months"]
    now = month_key(today)
    to_now = [m for m in months if (m["year"], m["month"]) <= now] or months[:1]
    income = sum((Decimal(m["income"]) for m in to_now), ZERO)
    expense = sum((Decimal(m["expense"]) for m in to_now), ZERO)
    return {
        "currency": currency, "configured": series["configured"], "opening": series["opening"],
        "start_year": series["start"][0], "start_month": series["start"][1],
        "income": str(money(income)), "expense": str(money(expense)),
        "balance": to_now[-1]["closing"] if to_now else series["opening"],
        "historical_balance": to_now[-1]["hist_closing"] if to_now else series["opening"],
        "months": months,
    }


def balance_on(session: Session, currency: str, day: date) -> Decimal | None:
    """The cash balance at the end of a day, or None while no opening capital was entered."""
    opening = opening_of(session, currency)
    if opening is None:
        return None
    amount, start = opening
    total = amount
    for m in movements(session, currency, end=day):
        if month_key(m.day) < start or not m.counts_in_cash:
            continue
        total += m.amount if m.kind == "income" else -m.amount
    return money(total)


def month_totals(session: Session, currency: str, year: int, month: int) -> dict[str, str]:
    """Income and expense of one month, historical (cash plus adjustments): what a month closing keeps."""
    first, last = date(year, month, 1), last_day(year, month)
    income = expense = ZERO
    for m in movements(session, currency, first, last):
        if m.kind == "income":
            income += m.amount
        else:
            expense += m.amount
    return {"income": str(money(income)), "expense": str(money(expense))}


# ---- overview and book --------------------------------------------------------------------------------------------------------------
def overview(session: Session, today: date) -> dict[str, Any]:
    """Per currency, never added together: cash balance, totals, this month, the monthly development, the latest movements."""
    result: dict[str, Any] = {"mode": ledger_mode(session), "currencies": {}}
    for currency in CURRENCIES:
        rows = movements(session, currency)
        series = month_series(session, currency, today, rows=rows)
        report = cash_report(session, currency, today)
        now = next((m for m in series["months"] if (m["year"], m["month"]) == month_key(today)), None)
        adjustments = [m for m in rows if m.source == "legacy_adjustment"]
        non_cash = sum((m.amount if m.kind == "income" else -m.amount for m in adjustments if not m.counts_in_cash and month_key(m.day) >= series["start"]), ZERO)
        result["currencies"][currency] = {
            "currency": currency,
            "configured": series["configured"],
            "balance": report["balance"],  # the cash balance: only real money
            "total_income": report["income"],
            "total_expense": report["expense"],
            "this_month": None if now is None else {
                "year": now["year"], "month": now["month"], "income": now["income"], "expense": now["expense"],
                "net": str(money(Decimal(now["income"]) - Decimal(now["expense"]))), "closing": now["closing"],
            },
            "months": series["months"],
            "historical": {
                "balance": report["historical_balance"],
                "difference": str(money(Decimal(report["historical_balance"]) - Decimal(report["balance"]))),
                "adjustments": len(adjustments),
                "adjustments_not_in_cash": str(money(non_cash)),
            },
            "recent": [m.as_dict() for m in rows[-10:][::-1]],
            "flags": {
                "estimated_dates": sum(1 for m in rows if m.date_basis != "actual"),
                "legacy": sum(1 for m in rows if m.source == "legacy"),
                "adjustments": len(adjustments),
                "missing_receipts": sum(1 for m in rows if m.needs_receipt and m.source == "booking"),
            },
        }
    return result


def book(
    session: Session, currency: str, date_from: date | None = None, date_to: date | None = None, category: str | None = None,
    source: str | None = None, kind: str | None = None, only_missing_receipt: bool = False, only_estimated: bool = False,
    include_voided: bool = True, newest_first: bool = True, limit: int = 500,
) -> dict[str, Any]:
    rows = movements(session, currency, date_from, date_to, include_voided=include_voided)
    if category:
        rows = [m for m in rows if m.category == category]
    if source:
        rows = [m for m in rows if m.source == source]
    if kind:
        rows = [m for m in rows if m.kind == kind]
    if only_missing_receipt:
        rows = [m for m in rows if m.needs_receipt]
    if only_estimated:
        rows = [m for m in rows if m.date_basis != "actual"]
    counted = [m for m in rows if not m.voided]
    income = sum((m.amount for m in counted if m.kind == "income" and m.counts_in_cash), ZERO)
    expense = sum((m.amount for m in counted if m.kind == "expense" and m.counts_in_cash), ZERO)
    ordered = rows[::-1] if newest_first else rows
    return {
        "currency": currency, "count": len(rows), "income": str(money(income)), "expense": str(money(expense)),
        "net": str(money(income - expense)), "rows": [m.as_dict() for m in ordered[: max(1, min(limit, 2000))]],
    }


# ---- bookings (written by app.finance) ----------------------------------------------------------------------------------------------
def check_booking_fields(kind: str, category: str, amount: Decimal, currency: str, booked_on: date, today: date) -> None:
    if currency not in CURRENCIES:
        raise HTTPException(422, "عملة غير صالحة.")
    if kind not in ("income", "expense"):
        raise HTTPException(422, "اختر إيراداً أو مصروفاً.")
    if category in SYSTEM_CATEGORIES:
        raise HTTPException(422, "هذا التصنيف يأتي تلقائياً من الرسوم أو الرواتب ولا يُسجَّل يدوياً.")
    if category not in categories_for(kind):
        raise HTTPException(422, "التصنيف لا يناسب نوع الحركة.")
    if money(amount) <= 0:
        raise HTTPException(422, "المبلغ يجب أن يكون أكبر من صفر.")
    if booked_on > today:
        raise HTTPException(422, "لا يمكن تسجيل حركة بتاريخ مستقبلي.")


def transaction_snapshot(t: CashTransaction) -> dict[str, Any]:
    return {
        "currency": t.currency, "kind": t.kind, "amount": str(money(t.amount)), "booked_on": t.booked_on.isoformat(),
        "category": t.category, "description": t.description, "counterparty": t.counterparty, "receipt_no": t.receipt_no,
        "voided": t.voided_at is not None, "void_reason": t.void_reason,
    }


def void_transaction(session: Session, actor: FeesActor, t: CashTransaction, reason: str, automatic: bool = False) -> None:
    """Cancels a booking: it stays in the book (crossed out), counts no more, and the reason is kept."""
    before = transaction_snapshot(t)
    t.voided_at = datetime.now(timezone.utc)
    t.voided_by, t.voided_by_id, t.void_reason = actor.name[:80], actor.account_id, reason.strip()[:300]
    audit(session, actor, "booking.void.auto" if automatic else "booking.void", "booking", t.id, before, transaction_snapshot(t), reason.strip())


def settle_unpaid_salary_adjustment(session: Session, actor: FeesActor, line: SalaryLine, paid_on: date) -> None:
    """A salary that was taken over as unpaid has now really been paid out on `paid_on`.

    Adjustment in an open month: it is cancelled in the same save. Adjustment in a closed month: it stays (the closed month does
    not change) and a counter-booking in the month of the payment cancels it in the historical figures. The month of the payment
    must be open (the caller checks that), so a closed month is never touched."""
    adjustment = session.scalar(
        select(CashTransaction).where(
            CashTransaction.adjusts_salary_line_id == line.id, CashTransaction.adjustment_kind == "salary_unpaid", CashTransaction.voided_at.is_(None),
        )
    )
    if adjustment is None:
        return
    reason = f"Gehalt am {paid_on.isoformat()} ausgezahlt"
    if not month_is_closed(session, adjustment.booked_on.year, adjustment.booked_on.month):
        void_transaction(session, actor, adjustment, reason, automatic=True)
        return
    counter = CashTransaction(
        currency=adjustment.currency, kind="income", amount=adjustment.amount, booked_on=paid_on, date_basis="derived_payment_date",
        category="other_income", description=f"Gegenbuchung zur historischen Ausgleichsbuchung (Gehalt {line.month}/{line.year})",
        origin="legacy_adjustment", adjustment_kind="salary_counter", counts_in_cash=False, adjusts_salary_line_id=line.id,
        reverses_adjustment_id=adjustment.id, legacy_note=reason, created_by_id=actor.account_id, created_by=actor.name[:80],
    )
    session.add(counter)
    session.flush()
    audit(session, actor, "booking.counter.auto", "booking", counter.id, None, transaction_snapshot(counter), reason,
          details=f"Ausgleich {adjustment.id} in geschlossenem Monat bleibt; Gegenbuchung im Zahlungsmonat")


def active_unpaid_adjustment(session: Session, line_id: uuid.UUID) -> CashTransaction | None:
    return session.scalar(
        select(CashTransaction).where(
            CashTransaction.adjusts_salary_line_id == line_id, CashTransaction.adjustment_kind == "salary_unpaid", CashTransaction.voided_at.is_(None),
        )
    )


def ensure_months_open(session: Session, *days: date | None) -> None:
    ensure_open(session, *[(d.year, d.month) for d in days if d is not None])


def guard_reset(session: Session) -> None:
    """Resets (wiping fees, payments, salaries, sheets) are blocked once the cash book is live. They are allowed only in an
    isolated test setup: the server variable ALLOW_FINANCE_RESET=1 AND a SQLite database. Never on PostgreSQL (the real database)."""
    import os

    if not is_live(session):
        return
    isolated = os.getenv("ALLOW_FINANCE_RESET", "") == "1" and session.get_bind().dialect.name == "sqlite"
    if not isolated:
        raise HTTPException(423, "التصفير غير متاح بعد تفعيل دفتر الصندوق؛ يُسمح به فقط في بيئة اختبار معزولة.")
