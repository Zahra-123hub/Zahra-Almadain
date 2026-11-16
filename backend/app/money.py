"""The accounting of the kindergarten. Three pages: income, expenses, month overview. Nothing else handles money.

Rules that hold everywhere:
* An entry keeps what was really paid (amount, currency), the rate it was entered with and the value in the other currency.
  A later rate never changes an entry that exists.
* US dollars and Syrian pounds are never added to each other. Every total is made per currency, from the money that was
  really paid in that currency. The value in the other currency is shown beside an entry, it is never counted a second time.
* An invoice is a claim, not an income. Only a payment (an income entry tied to the invoice) is income; what is paid and
  what is open is always calculated, never typed.
* Nothing is deleted. An entry of an open month is cancelled with a reason; an entry of a closed month is corrected by a
  reversal entry in the open month. Every change is written to the activity log (who, when, before, after, why).
* Rounding, one rule (half up): dollars -> whole pounds, pounds -> cents.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import activity
from app.actors import Actor, has_grant
from app.database import get_session
from app.models import Child, CurrencyRate, Employee, ExpenseEntry, FeeAuditLog, IncomeCategory, IncomeEntry, Invoice, InvoiceItem, MonthClosing
from app.tables import csv_response, xlsx_response
from app.timeutil import local_today, to_local

CURRENCIES = ("USD", "SYP")
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
INCOME_KEYS = {  # the built-in income categories (seeded by the migration; the management may add others)
    "tuition": {"ar": "رسوم الروضة", "en": "Kindergarten fees"},
    "registration": {"ar": "رسوم التسجيل", "en": "Registration fees"},
    "extra_fees": {"ar": "رسوم إضافية", "en": "Additional fees"},
    "other_income": {"ar": "إيرادات أخرى", "en": "Other income"},
}
EXPENSE_CATEGORIES = {  # fixed on purpose
    "salaries": {"ar": "الرواتب", "en": "Salaries"},
    "rent": {"ar": "الإيجار", "en": "Rent"},
    "food": {"ar": "الطعام", "en": "Food"},
    "teaching_material": {"ar": "المواد التعليمية", "en": "Teaching material"},
    "toys_equipment": {"ar": "الألعاب والتجهيزات", "en": "Toys and equipment"},
    "utilities": {"ar": "الكهرباء والماء", "en": "Electricity and water"},
    "maintenance": {"ar": "الصيانة والإصلاحات", "en": "Maintenance and repairs"},
    "transport": {"ar": "المواصلات", "en": "Transport"},
    "other_expense": {"ar": "مصروفات أخرى", "en": "Other expenses"},
}


# ---- amounts ----------------------------------------------------------------------------------------------------------------------
def cents(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def other_of(currency: str) -> str:
    return "SYP" if currency == "USD" else "USD"


def to_other(amount: Decimal, currency: str, rate: Decimal) -> Decimal:
    """The same value in the other currency: dollars -> whole pounds, pounds -> cents, half up."""
    if currency == "USD":
        return (Decimal(amount) * Decimal(rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(CENT)
    return (Decimal(amount) / Decimal(rate)).quantize(CENT, rounding=ROUND_HALF_UP)


def text(currency: str, value: Decimal | None) -> str | None:
    """Dollars with cents; pounds whole (cents only when the amount really has them)."""
    if value is None:
        return None
    value = Decimal(value)
    if currency == "SYP" and value == value.to_integral_value():
        return str(int(value))
    return format(cents(value), "f")


def rate_text(rate: Decimal) -> str:
    shown = format(Decimal(rate), "f")
    return shown.rstrip("0").rstrip(".") if "." in shown else shown


def both(amount: Decimal, currency: str, other: Decimal) -> dict[str, str | None]:
    """The two columns of every table."""
    values = {currency: Decimal(amount), other_of(currency): Decimal(other)}
    return {"usd": text("USD", values["USD"]), "syp": text("SYP", values["SYP"])}


# ---- rates and months -------------------------------------------------------------------------------------------------------------
def rate_on(session: Session, day: date) -> CurrencyRate | None:
    """The rate that is valid on a day: the newest one that starts on or before it."""
    return session.scalar(
        select(CurrencyRate).where(CurrencyRate.valid_from <= day).order_by(CurrencyRate.valid_from.desc(), CurrencyRate.created_at.desc()).limit(1)
    )


# ---- the automatic rate -------------------------------------------------------------------------------------------------------------
RATE_FEED_URL = "https://open.er-api.com/v6/latest/USD"  # a free public daily rates feed (no key)
AUTO = "auto"  # `created_by` of a rate the system fetched itself
FEED_RETRY = timedelta(minutes=10)  # after a failed ask the feed is left alone for a while (a slow feed must not slow every page)
_feed_blocked_until: datetime | None = None


def fetch_online_rate() -> Decimal | None:
    """Pounds for one dollar from the public feed, or None when it cannot be reached.

    The feed quotes the NEW Syrian pound (1 new = 100 old, about 120 per dollar). The kindergarten counts in the old pound
    (amounts in the hundred thousands), so a quote below 1000 is multiplied by SYP_RATE_SCALE (default 100).
    Set SYP_RATE_SCALE=1 on the server once the books are kept in the new pound."""
    global _feed_blocked_until
    if _feed_blocked_until is not None and datetime.now(timezone.utc) < _feed_blocked_until:
        return None
    try:
        reply = httpx.get(RATE_FEED_URL, timeout=6.0)
        reply.raise_for_status()
        value = Decimal(str(reply.json()["rates"]["SYP"]))
    except Exception:  # offline, rate limited, changed format: the last stored rate stays in use
        _feed_blocked_until = datetime.now(timezone.utc) + FEED_RETRY
        return None
    if value <= 0:
        _feed_blocked_until = datetime.now(timezone.utc) + FEED_RETRY
        return None
    _feed_blocked_until = None
    try:
        scale = Decimal(os.getenv("SYP_RATE_SCALE", "100"))
    except Exception:
        scale = Decimal(100)
    if value < 1000 and scale > 0:
        value *= scale
    return value.quantize(Decimal("0.000001"))


def refresh_today(session: Session) -> None:
    """Once a day the rate is fetched by itself and stored, valid from today. A rate that is already stored for today
    (fetched, or typed by the management) is left alone; a feed that is down leaves the last rate in use."""
    today = local_today()
    if session.scalar(select(CurrencyRate.id).where(CurrencyRate.valid_from == today).limit(1)) is not None:
        return
    value = fetch_online_rate()
    if value is None:
        return
    session.add(CurrencyRate(valid_from=today, syp_per_usd=value, created_by=AUTO, created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    activity.record(session, actor_id=None, actor_name=AUTO, domain="finance", action="rate.auto", entity_type="rate", entity_id=today.isoformat(),
                    after={"valid_from": today.isoformat(), "syp_per_usd": rate_text(value)})
    session.commit()


def rate_info(row: CurrencyRate | None, today: date) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"syp_per_usd": rate_text(row.syp_per_usd), "valid_from": row.valid_from.isoformat(), "by": row.created_by,
            "source": "auto" if row.created_by == AUTO else "manual", "stale": row.valid_from < today}


def parse_month(value: str | None, today: date) -> tuple[int, int]:
    if not value:
        return today.year, today.month
    try:
        year, month = (int(part) for part in value.split("-"))
        date(year, month, 1)
    except ValueError as exc:
        raise HTTPException(422, "شهر غير صالح. استخدم الشكل 2026-10.") from exc
    return year, month


def month_range(year: int, month: int) -> tuple[date, date]:
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return date(year, month, 1), nxt - timedelta(days=1)


def closing_of(session: Session, year: int, month: int) -> MonthClosing | None:
    return session.scalar(select(MonthClosing).where(MonthClosing.year == year, MonthClosing.month == month, MonthClosing.reopened_at.is_(None)))


def is_closed(session: Session, day: date) -> bool:
    return closing_of(session, day.year, day.month) is not None


def ensure_open(session: Session, *days: date) -> None:
    for day in days:
        if is_closed(session, day):
            raise HTTPException(423, f"شهر {day.month}/{day.year} مغلق. لا تُسجَّل ولا تُعدَّل حركاته؛ التصحيح يكون بقيد عكسي في الشهر المفتوح.")


# ---- who may do what --------------------------------------------------------------------------------------------------------------
def rights(session: Session, actor: Actor) -> dict[str, bool]:
    lead = actor.role in ("manager", "admin")
    return {
        "record": True,
        "correct": lead or has_grant(session, actor, "books.correct"),
        "export": lead or has_grant(session, actor, "books.export"),
        "manage": lead,  # rate, month closing, income categories, staff export
    }


def need(session: Session, actor: Actor, what: str) -> None:
    if not rights(session, actor)[what]:
        messages = {
            "correct": "تعديل الحركات وإلغاؤها يحتاج صلاحية من الإدارة.",
            "export": "التصدير يحتاج صلاحية من الإدارة.",
            "manage": "هذا الإجراء للإدارة فقط.",
        }
        raise HTTPException(403, messages[what])


def audit(session: Session, actor: Actor, action: str, kind: str, entity_id: Any, before: dict | None = None, after: dict | None = None, reason: str = "") -> None:
    activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="finance", action=action, entity_type=kind,
                    entity_id=entity_id, before=before, after=after, reason=reason)


# ---- request models ---------------------------------------------------------------------------------------------------------------
Amount = Field(gt=0, max_digits=14, decimal_places=2)
Rate = Field(default=None, gt=0, max_digits=18, decimal_places=6)


class RateIn(BaseModel):
    valid_from: date
    syp_per_usd: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    is_active: bool | None = None


class IncomeIn(BaseModel):
    booked_on: date
    description: str = Field(min_length=2, max_length=300)
    category_id: uuid.UUID
    child_id: uuid.UUID | None = None
    payer_name: str = Field(default="", max_length=120)
    amount: Decimal = Amount
    currency: str = Field(pattern="^(USD|SYP)$")
    rate: Decimal | None = Rate
    note: str = Field(default="", max_length=500)


class ExpenseIn(BaseModel):
    booked_on: date
    description: str = Field(min_length=2, max_length=300)
    category: str = Field(max_length=30)
    recipient: str = Field(default="", max_length=120)
    employee_id: uuid.UUID | None = None
    salary_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Amount
    currency: str = Field(pattern="^(USD|SYP)$")
    rate: Decimal | None = Rate
    note: str = Field(default="", max_length=500)


class Versioned(BaseModel):
    expected_version: int | None = Field(default=None, ge=0, le=1_000_000_000)


class IncomeUpdate(IncomeIn, Versioned):
    pass


class ExpenseUpdate(ExpenseIn, Versioned):
    pass


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Decimal = Amount


class InvoiceIn(BaseModel):
    issued_on: date
    child_id: uuid.UUID | None = None
    payer_name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=300)
    currency: str = Field(pattern="^(USD|SYP)$")
    rate: Decimal | None = Rate
    items: list[ItemIn] = Field(min_length=1, max_length=20)


class PaymentIn(BaseModel):
    booked_on: date
    amount: Decimal = Amount
    currency: str = Field(pattern="^(USD|SYP)$")
    rate: Decimal | None = Rate
    payer_name: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=500)
    category_id: uuid.UUID | None = None  # default: kindergarten fees


class ClosingIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


# ---- invoices: everything about paid and open is calculated ----------------------------------------------------------------------
def credit(payment: IncomeEntry, invoice: Invoice) -> Decimal:
    """What a payment is worth for the invoice, in the currency of the invoice (converted with the rate of the payment)."""
    if payment.currency == invoice.currency:
        return cents(payment.amount)
    return to_other(payment.amount, payment.currency, payment.rate)


def invoice_state(invoice: Invoice) -> dict[str, Any]:
    total = sum((cents(i.amount) for i in invoice.items), ZERO)
    total_other = sum((cents(i.amount_other) for i in invoice.items), ZERO)
    paid = sum((credit(p, invoice) for p in invoice.payments if p.voided_at is None), ZERO)
    left = total - paid
    if left <= 0:
        paid_other = total_other  # fully paid: both columns close at zero
    elif paid <= 0:
        paid_other = ZERO
    else:
        paid_other = min(to_other(paid, invoice.currency, invoice.rate), total_other)
    status = "void" if invoice.voided_at is not None else "paid" if left <= 0 else "partial" if paid > 0 else "open"
    return {"total": total, "total_other": total_other, "paid": paid, "paid_other": paid_other, "open": left, "open_other": total_other - paid_other, "status": status}


def invoice_dict(invoice: Invoice, names: dict[uuid.UUID, str], with_payments: bool = False) -> dict[str, Any]:
    state = invoice_state(invoice)
    cur = invoice.currency
    data = {
        "id": str(invoice.id), "number": invoice.number, "issued_on": invoice.issued_on.isoformat(),
        "child_id": str(invoice.child_id) if invoice.child_id else "", "child": names.get(invoice.child_id, "") if invoice.child_id else "",
        "payer_name": invoice.payer_name, "description": invoice.description, "currency": cur, "rate": rate_text(invoice.rate),
        "items": [{"description": i.description, **both(i.amount, cur, i.amount_other)} for i in invoice.items],
        "total": both(state["total"], cur, state["total_other"]), "paid": both(state["paid"], cur, state["paid_other"]),
        "open": both(state["open"], cur, state["open_other"]), "status": state["status"],
        "voided": invoice.voided_at is not None, "void_reason": invoice.void_reason, "created_by": invoice.created_by,
    }
    if with_payments:
        data["payments"] = [
            {"id": str(p.id), "booked_on": p.booked_on.isoformat(), "currency": p.currency, "amount": text(p.currency, p.amount), "rate": rate_text(p.rate),
             "credited": text(cur, credit(p, invoice)), **both(p.amount, p.currency, p.amount_other), "payer_name": p.payer_name,
             "voided": p.voided_at is not None, "void_reason": p.void_reason, "is_reversal": p.reverses_id is not None}
            for p in invoice.payments
        ]
    return data


# ---- the figures of a month -------------------------------------------------------------------------------------------------------
def month_figures(session: Session, year: int, month: int) -> dict[str, Any]:
    """Per currency, from the money really paid in it. `converted` is the same money valued in one currency with the stored
    rates -- one more way to look at it, never a second sum on top."""
    first, last = month_range(year, month)
    incomes = session.scalars(select(IncomeEntry).where(IncomeEntry.booked_on >= first, IncomeEntry.booked_on <= last, IncomeEntry.voided_at.is_(None))).all()
    expenses = session.scalars(select(ExpenseEntry).where(ExpenseEntry.booked_on >= first, ExpenseEntry.booked_on <= last, ExpenseEntry.voided_at.is_(None))).all()

    def blank() -> dict[str, Decimal]:
        return {code: ZERO for code in CURRENCIES}

    income, expense, salaries, converted_in, converted_out = blank(), blank(), blank(), blank(), blank()
    income_cats: dict[uuid.UUID, dict[str, Any]] = {}
    expense_cats: dict[str, dict[str, Any]] = {}
    for e in incomes:
        income[e.currency] += e.amount
        converted_in[e.currency] += e.amount
        converted_in[other_of(e.currency)] += e.amount_other
        cat = income_cats.setdefault(e.category_id, {"USD": ZERO, "SYP": ZERO, "count": 0})
        cat[e.currency] += e.amount
        cat["count"] += 1
    for e in expenses:
        expense[e.currency] += e.amount
        converted_out[e.currency] += e.amount
        converted_out[other_of(e.currency)] += e.amount_other
        if e.category == "salaries":
            salaries[e.currency] += e.amount
        cat = expense_cats.setdefault(e.category, {"USD": ZERO, "SYP": ZERO, "count": 0})
        cat[e.currency] += e.amount
        cat["count"] += 1
    return {
        "income": income, "expense": expense, "surplus": {code: income[code] - expense[code] for code in CURRENCIES},
        "salaries": salaries, "other_expenses": {code: expense[code] - salaries[code] for code in CURRENCIES},
        "income_count": len(incomes), "expense_count": len(expenses), "income_cats": income_cats, "expense_cats": expense_cats,
        "converted": {"income": converted_in, "expense": converted_out, "surplus": {code: converted_in[code] - converted_out[code] for code in CURRENCIES}},
    }


def open_invoices(session: Session) -> dict[str, Any]:
    result = {"open": 0, "partial": 0, "amount": {code: ZERO for code in CURRENCIES}}
    for invoice in session.scalars(select(Invoice).where(Invoice.voided_at.is_(None))).all():
        state = invoice_state(invoice)
        if state["status"] in ("open", "partial"):
            result[state["status"]] += 1
            result["amount"][invoice.currency] += state["open"]
    return result


def build_router(guard: Callable[..., Actor]) -> APIRouter:
    """`guard`: the management, the admin and the accountant. Finer rights are checked per action (see `rights`)."""
    router = APIRouter(prefix="/api/admin/money", tags=["money"])

    # ---- small helpers ------------------------------------------------------------------------------------------------------------
    def chosen_rate(session: Session, actor: Actor, day: date, typed: Decimal | None) -> Decimal:
        """The rate of the day is taken; only the management may type another one."""
        if day == local_today():
            refresh_today(session)
        listed = rate_on(session, day)
        if typed is None:
            if listed is None:
                raise HTTPException(409, "لا يوجد سعر صرف لهذا التاريخ. تحدّد الإدارة سعر الصرف أولاً.")
            return Decimal(listed.syp_per_usd)
        if listed is not None and Decimal(typed) == Decimal(listed.syp_per_usd):
            return Decimal(typed)
        need(session, actor, "manage")
        return Decimal(typed)

    def check_day(day: date) -> None:
        if day > local_today():
            raise HTTPException(422, "لا يمكن تسجيل حركة بتاريخ مستقبلي.")

    def child_names(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
        wanted = [i for i in ids if i]
        return dict(session.execute(select(Child.id, Child.display_name).where(Child.id.in_(wanted))).all()) if wanted else {}

    def employee_names(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
        wanted = [i for i in ids if i]
        return dict(session.execute(select(Employee.id, Employee.name).where(Employee.id.in_(wanted))).all()) if wanted else {}

    def reversed_ids(session: Session, model: Any, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        return set(session.scalars(select(model.reverses_id).where(model.reverses_id.in_(ids), model.voided_at.is_(None))).all())

    def period(month: str | None, date_from: date | None, date_to: date | None) -> tuple[date, date]:
        if date_from or date_to:
            return date_from or date(2000, 1, 1), date_to or date(2100, 12, 31)
        return month_range(*parse_month(month, local_today()))

    def no_twin(session: Session, model: Any, actor: Actor, day: date, amount: Decimal, currency: str, description: str) -> None:
        """The same entry typed twice within seconds (a double click) is refused instead of booked twice."""
        since = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(tzinfo=None)
        twin = session.scalar(select(model.id).where(
            model.booked_on == day, model.amount == amount, model.currency == currency, model.description == description,
            model.created_by == actor.name[:80], model.voided_at.is_(None), model.created_at >= since,
        ))
        if twin is not None:
            raise HTTPException(409, "سُجّلت الحركة نفسها قبل لحظات. إن كانت حركة ثانية فعلاً، انتظر قليلاً ثم أعد المحاولة.")

    def stamp(row: Any, actor: Actor) -> None:
        row.version = (row.version or 1) + 1
        row.updated_at, row.updated_by = datetime.now(timezone.utc), actor.name[:80]

    def check_version(row: Any, expected: int | None) -> None:
        if expected is not None and expected != (row.version or 1):
            raise HTTPException(409, f"غيّر {row.updated_by or 'شخص آخر'} هذه الحركة بعد أن فتحتها. حدّث الصفحة ثم أعد التعديل.")

    def income_snapshot(e: IncomeEntry) -> dict[str, Any]:
        return {"booked_on": e.booked_on.isoformat(), "description": e.description, "category_id": str(e.category_id), "child_id": str(e.child_id) if e.child_id else None,
                "payer_name": e.payer_name, "amount": str(e.amount), "currency": e.currency, "rate": rate_text(e.rate), "amount_other": str(e.amount_other),
                "note": e.note, "invoice_id": str(e.invoice_id) if e.invoice_id else None, "voided": e.voided_at is not None}

    def expense_snapshot(e: ExpenseEntry) -> dict[str, Any]:
        return {"booked_on": e.booked_on.isoformat(), "description": e.description, "category": e.category, "recipient": e.recipient,
                "employee_id": str(e.employee_id) if e.employee_id else None, "salary_month": e.salary_month, "amount": str(e.amount), "currency": e.currency,
                "rate": rate_text(e.rate), "amount_other": str(e.amount_other), "note": e.note, "voided": e.voided_at is not None}

    def income_dict(e: IncomeEntry, cats: dict[uuid.UUID, IncomeCategory], children: dict[uuid.UUID, str], reversed_set: set[uuid.UUID], closed: bool) -> dict[str, Any]:
        cat = cats.get(e.category_id)
        return {
            "id": str(e.id), "booked_on": e.booked_on.isoformat(), "description": e.description,
            "category_id": str(e.category_id), "category_key": cat.key if cat else None, "category": cat.name if cat else "",
            "child_id": str(e.child_id) if e.child_id else "", "child": children.get(e.child_id, "") if e.child_id else "", "payer_name": e.payer_name,
            "amount": text(e.currency, e.amount), "currency": e.currency, "rate": rate_text(e.rate), **both(e.amount, e.currency, e.amount_other),
            "note": e.note, "invoice_id": str(e.invoice_id) if e.invoice_id else "", "invoice_number": e.invoice.number if e.invoice_id and e.invoice else "",
            "is_reversal": e.reverses_id is not None, "reversed": e.id in reversed_set, "voided": e.voided_at is not None, "void_reason": e.void_reason,
            "voided_by": e.voided_by, "created_by": e.created_by, "version": e.version or 1, "month_closed": closed,
        }

    def expense_dict(e: ExpenseEntry, staff: dict[uuid.UUID, str], reversed_set: set[uuid.UUID], closed: bool) -> dict[str, Any]:
        label = EXPENSE_CATEGORIES.get(e.category, {"ar": e.category, "en": e.category})
        return {
            "id": str(e.id), "booked_on": e.booked_on.isoformat(), "description": e.description, "category": e.category,
            "category_ar": label["ar"], "category_en": label["en"], "recipient": e.recipient,
            "employee_id": str(e.employee_id) if e.employee_id else "", "employee": staff.get(e.employee_id, "") if e.employee_id else "",
            "salary_month": e.salary_month or "", "amount": text(e.currency, e.amount), "currency": e.currency, "rate": rate_text(e.rate),
            **both(e.amount, e.currency, e.amount_other), "note": e.note, "is_reversal": e.reverses_id is not None, "reversed": e.id in reversed_set,
            "voided": e.voided_at is not None, "void_reason": e.void_reason, "voided_by": e.voided_by, "created_by": e.created_by,
            "version": e.version or 1, "month_closed": closed,
        }

    def closed_months(session: Session) -> set[tuple[int, int]]:
        return {(c.year, c.month) for c in session.scalars(select(MonthClosing).where(MonthClosing.reopened_at.is_(None))).all()}

    def totals(rows: list[Any]) -> dict[str, str]:
        return {code: text(code, sum((r.amount for r in rows if r.voided_at is None and r.currency == code), ZERO)) for code in CURRENCIES}

    def categories(session: Session) -> dict[uuid.UUID, IncomeCategory]:
        return {c.id: c for c in session.scalars(select(IncomeCategory)).all()}

    def cancel(session: Session, actor: Actor, model: Any, entry: Any, kind: str, snapshot: Callable[[Any], dict], reason: str) -> dict[str, Any]:
        """Open month: the entry is cancelled (it stays, crossed out). Closed month: it is left untouched and a reversal entry
        with the opposite amount is booked today, in the open month."""
        if entry.voided_at is not None:
            raise HTTPException(409, "الحركة ملغاة بالفعل.")
        if session.scalar(select(model.id).where(model.reverses_id == entry.id, model.voided_at.is_(None))) is not None:
            raise HTTPException(409, "صُحّحت هذه الحركة بقيد عكسي من قبل.")
        before = snapshot(entry)
        if not is_closed(session, entry.booked_on):
            entry.voided_at, entry.voided_by, entry.void_reason = datetime.now(timezone.utc), actor.name[:80], reason
            audit(session, actor, f"{kind}.void", kind, entry.id, before, snapshot(entry), reason)
            session.commit()
            return {"id": str(entry.id), "voided": True, "reversal_id": None}
        today = local_today()
        ensure_open(session, today)
        columns = {c.name for c in model.__table__.columns} - {"id", "created_at", "updated_at", "updated_by", "version", "voided_at", "voided_by", "void_reason"}
        values = {name: getattr(entry, name) for name in columns}
        values.update(booked_on=today, amount=-entry.amount, amount_other=-entry.amount_other, reverses_id=entry.id, created_by=actor.name[:80],
                      description=("عكس: " + entry.description)[:300], note=reason[:500])
        if "salary_month" in values:
            values["salary_month"] = None  # the reversal is not a salary payment itself
        reversal = model(**values)
        session.add(reversal)
        session.flush()
        audit(session, actor, f"{kind}.reverse", kind, entry.id, before, {**snapshot(reversal), "reversal_id": str(reversal.id)}, reason)
        session.commit()
        return {"id": str(entry.id), "voided": False, "reversal_id": str(reversal.id)}

    # ---- what the pages need to start -----------------------------------------------------------------------------------------------
    @router.get("/meta")
    def meta(response: Response, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        refresh_today(session)
        return {
            "role": actor.role, "name": actor.name, "rights": rights(session, actor), "today": today.isoformat(),
            "rate": rate_info(rate_on(session, today), today),
            "income_categories": [
                {"id": str(c.id), "key": c.key, "name": c.name, "is_active": c.is_active}
                for c in sorted(categories(session).values(), key=lambda c: (c.position, c.name))
            ],
            "expense_categories": [{"key": key, **label} for key, label in EXPENSE_CATEGORIES.items()],
        }

    # ---- the exchange rate (management) ---------------------------------------------------------------------------------------------
    @router.get("/rates")
    def rates(response: Response, day: date | None = None, _actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        refresh_today(session)
        listed = rate_on(session, day or local_today())
        rows = session.scalars(select(CurrencyRate).order_by(CurrencyRate.valid_from.desc(), CurrencyRate.created_at.desc()).limit(50)).all()
        return {
            "for_day": None if listed is None else rate_text(listed.syp_per_usd),
            "rates": [{"valid_from": r.valid_from.isoformat(), "syp_per_usd": rate_text(r.syp_per_usd), "by": r.created_by, "source": "auto" if r.created_by == AUTO else "manual",
                       "at": to_local(r.created_at).isoformat() if r.created_at else None} for r in rows],
        }

    @router.post("/rates", status_code=201)
    def set_rate(payload: RateIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """A correction by hand: a new rate from a day on (it beats the fetched rate of that day). Rates are only added;
        entries that exist keep the rate they were made with."""
        need(session, actor, "manage")
        old = rate_on(session, payload.valid_from)
        row = CurrencyRate(valid_from=payload.valid_from, syp_per_usd=payload.syp_per_usd, created_by=actor.name[:80],
                           created_at=datetime.now(timezone.utc).replace(tzinfo=None))  # to the microsecond: two rates of one day stay in order
        session.add(row)
        audit(session, actor, "rate.set", "rate", payload.valid_from.isoformat(),
              None if old is None else {"valid_from": old.valid_from.isoformat(), "syp_per_usd": rate_text(old.syp_per_usd)},
              {"valid_from": payload.valid_from.isoformat(), "syp_per_usd": rate_text(payload.syp_per_usd)})
        session.commit()
        return {"valid_from": row.valid_from.isoformat(), "syp_per_usd": rate_text(row.syp_per_usd)}

    # ---- income categories (management) ---------------------------------------------------------------------------------------------
    @router.post("/categories", status_code=201)
    def add_category(payload: CategoryIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "manage")
        name = payload.name.strip()
        if session.scalar(select(IncomeCategory.id).where(func.lower(IncomeCategory.name) == name.lower())) is not None:
            raise HTTPException(409, "توجد فئة بهذا الاسم.")
        row = IncomeCategory(name=name, position=200)
        session.add(row)
        session.flush()
        audit(session, actor, "category.create", "category", row.id, None, {"name": name})
        session.commit()
        return {"id": str(row.id), "key": None, "name": row.name, "is_active": True}

    @router.patch("/categories/{category_id}")
    def change_category(category_id: uuid.UUID, payload: CategoryUpdate, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "manage")
        row = session.get(IncomeCategory, category_id)
        if row is None:
            raise HTTPException(404, "الفئة غير موجودة.")
        before = {"name": row.name, "is_active": row.is_active}
        if payload.name is not None:
            row.name = payload.name.strip()
        if payload.is_active is not None:
            if not payload.is_active and row.key == "tuition":
                raise HTTPException(409, "فئة رسوم الروضة أساسية ولا تُعطَّل (تُسجَّل عليها دفعات الفواتير).")
            row.is_active = payload.is_active
        audit(session, actor, "category.update", "category", row.id, before, {"name": row.name, "is_active": row.is_active})
        session.commit()
        return {"id": str(row.id), "key": row.key, "name": row.name, "is_active": row.is_active}

    # ---- income ---------------------------------------------------------------------------------------------------------------------
    def check_income(session: Session, category_id: uuid.UUID, child_id: uuid.UUID | None, new: bool) -> None:
        cat = session.get(IncomeCategory, category_id)
        if cat is None or (new and not cat.is_active):
            raise HTTPException(422, "اختر فئة صالحة.")
        if child_id is not None and session.get(Child, child_id) is None:
            raise HTTPException(404, "الطفل غير موجود.")

    def income_rows(session: Session, start: date, end: date, category_id: uuid.UUID | None, q: str) -> list[IncomeEntry]:
        query = select(IncomeEntry).where(IncomeEntry.booked_on >= start, IncomeEntry.booked_on <= end)
        if category_id:
            query = query.where(IncomeEntry.category_id == category_id)
        if q.strip():
            like = "%" + q.strip().lower().replace("%", "").replace("_", "") + "%"
            query = query.where(or_(func.lower(IncomeEntry.description).like(like), func.lower(IncomeEntry.payer_name).like(like), func.lower(IncomeEntry.note).like(like)))
        return list(session.scalars(query.order_by(IncomeEntry.booked_on.desc(), IncomeEntry.created_at.desc())).all())

    def income_list(session: Session, rows: list[IncomeEntry]) -> list[dict[str, Any]]:
        cats, closed = categories(session), closed_months(session)
        children = child_names(session, {r.child_id for r in rows})
        done = reversed_ids(session, IncomeEntry, [r.id for r in rows])
        return [income_dict(r, cats, children, done, (r.booked_on.year, r.booked_on.month) in closed) for r in rows]

    @router.get("/income")
    def list_income(
        response: Response, month: str | None = None, date_from: date | None = None, date_to: date | None = None, category_id: uuid.UUID | None = None, q: str = "",
        _actor: Actor = Depends(guard), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        start, end = period(month, date_from, date_to)
        rows = income_rows(session, start, end, category_id, q)
        return {"rows": income_list(session, rows), "totals": totals(rows), "count": sum(1 for r in rows if r.voided_at is None)}

    def new_income(session: Session, actor: Actor, payload: IncomeIn | PaymentIn, description: str, category_id: uuid.UUID, child_id: uuid.UUID | None, invoice: Invoice | None) -> IncomeEntry:
        check_day(payload.booked_on)
        ensure_open(session, payload.booked_on)
        rate = chosen_rate(session, actor, payload.booked_on, payload.rate)
        amount = cents(payload.amount)
        no_twin(session, IncomeEntry, actor, payload.booked_on, amount, payload.currency, description)
        entry = IncomeEntry(
            booked_on=payload.booked_on, description=description, category_id=category_id, child_id=child_id, payer_name=payload.payer_name.strip(),
            amount=amount, currency=payload.currency, rate=rate, amount_other=to_other(amount, payload.currency, rate), note=payload.note.strip(),
            invoice_id=invoice.id if invoice else None, created_by=actor.name[:80],
        )
        session.add(entry)
        session.flush()
        audit(session, actor, "income.create", "income", entry.id, None, income_snapshot(entry))
        return entry

    @router.post("/income", status_code=201)
    def create_income(payload: IncomeIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        check_income(session, payload.category_id, payload.child_id, new=True)
        entry = new_income(session, actor, payload, payload.description.strip(), payload.category_id, payload.child_id, None)
        session.commit()
        return income_list(session, [entry])[0]

    def get_income(session: Session, entry_id: uuid.UUID) -> IncomeEntry:
        entry = session.scalar(select(IncomeEntry).where(IncomeEntry.id == entry_id).with_for_update())
        if entry is None:
            raise HTTPException(404, "الحركة غير موجودة.")
        return entry

    @router.patch("/income/{entry_id}")
    def change_income(entry_id: uuid.UUID, payload: IncomeUpdate, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "correct")
        entry = get_income(session, entry_id)
        if entry.voided_at is not None or entry.reverses_id is not None:
            raise HTTPException(409, "الحركات الملغاة والقيود العكسية لا تُعدَّل.")
        check_version(entry, payload.expected_version)
        check_day(payload.booked_on)
        ensure_open(session, entry.booked_on, payload.booked_on)
        check_income(session, payload.category_id, payload.child_id, new=payload.category_id != entry.category_id)
        before = income_snapshot(entry)
        rate = Decimal(entry.rate) if payload.rate is None else chosen_rate(session, actor, payload.booked_on, payload.rate) if Decimal(payload.rate) != Decimal(entry.rate) else Decimal(entry.rate)
        entry.booked_on, entry.description, entry.category_id, entry.child_id = payload.booked_on, payload.description.strip(), payload.category_id, payload.child_id
        entry.payer_name, entry.note = payload.payer_name.strip(), payload.note.strip()
        entry.amount, entry.currency, entry.rate = cents(payload.amount), payload.currency, rate
        entry.amount_other = to_other(entry.amount, entry.currency, rate)
        if entry.invoice_id is not None:
            session.flush()
            session.refresh(entry.invoice)
            if invoice_state(entry.invoice)["open"] < 0:
                raise HTTPException(422, "بعد هذا التعديل تصبح الدفعات أكبر من قيمة الفاتورة.")
        stamp(entry, actor)
        audit(session, actor, "income.update", "income", entry.id, before, income_snapshot(entry))
        session.commit()
        return income_list(session, [entry])[0]

    @router.post("/income/{entry_id}/void")
    def void_income(entry_id: uuid.UUID, payload: ReasonIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "correct")
        return cancel(session, actor, IncomeEntry, get_income(session, entry_id), "income", income_snapshot, payload.reason.strip())

    # ---- invoices (inside the income page) ----------------------------------------------------------------------------------------------
    def get_invoice(session: Session, invoice_id: uuid.UUID) -> Invoice:
        invoice = session.scalar(select(Invoice).where(Invoice.id == invoice_id).with_for_update())
        if invoice is None:
            raise HTTPException(404, "الفاتورة غير موجودة.")
        return invoice

    @router.get("/invoices")
    def list_invoices(response: Response, status: str = "", q: str = "", _actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.scalars(select(Invoice).order_by(Invoice.issued_on.desc(), Invoice.number.desc())).all()
        names = child_names(session, {r.child_id for r in rows})
        data = [invoice_dict(r, names) for r in rows]
        if status in ("open", "partial", "paid", "void"):
            data = [d for d in data if d["status"] == status]
        elif status == "unpaid":
            data = [d for d in data if d["status"] in ("open", "partial")]
        if q.strip():
            needle = q.strip().lower()
            data = [d for d in data if needle in (d["number"] + " " + d["child"] + " " + d["payer_name"] + " " + d["description"]).lower()]
        return {"rows": data}

    @router.get("/invoices/{invoice_id}")
    def one_invoice(invoice_id: uuid.UUID, response: Response, _actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise HTTPException(404, "الفاتورة غير موجودة.")
        return invoice_dict(invoice, child_names(session, {invoice.child_id}), with_payments=True)

    @router.post("/invoices", status_code=201)
    def create_invoice(payload: InvoiceIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        check_day(payload.issued_on)
        if payload.child_id is None and not payload.payer_name.strip():
            raise HTTPException(422, "اختر الطفل أو اكتب اسم الجهة الدافعة.")
        if payload.child_id is not None and session.get(Child, payload.child_id) is None:
            raise HTTPException(404, "الطفل غير موجود.")
        rate = chosen_rate(session, actor, payload.issued_on, payload.rate)
        year = payload.issued_on.year
        numbers = [int(n.rsplit("-", 1)[-1]) for n in session.scalars(select(Invoice.number).where(Invoice.number.like(f"INV-{year}-%"))).all() if n.rsplit("-", 1)[-1].isdigit()]
        invoice = Invoice(
            number=f"INV-{year}-{max(numbers or [0]) + 1:04d}", issued_on=payload.issued_on, child_id=payload.child_id, payer_name=payload.payer_name.strip(),
            description=payload.description.strip(), currency=payload.currency, rate=rate, created_by=actor.name[:80],
        )
        invoice.items = [
            InvoiceItem(position=n, description=item.description.strip(), amount=cents(item.amount), amount_other=to_other(cents(item.amount), payload.currency, rate))
            for n, item in enumerate(payload.items, start=1)
        ]
        session.add(invoice)
        session.flush()
        audit(session, actor, "invoice.create", "invoice", invoice.id, None,
              {"number": invoice.number, "currency": invoice.currency, "rate": rate_text(rate), "items": [{"description": i.description, "amount": str(i.amount)} for i in invoice.items]})
        session.commit()
        return invoice_dict(invoice, child_names(session, {invoice.child_id}), with_payments=True)

    @router.post("/invoices/{invoice_id}/payments", status_code=201)
    def pay_invoice(invoice_id: uuid.UUID, payload: PaymentIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """A payment of an invoice IS an income entry tied to it. It may be a part, and it may be in the other currency."""
        invoice = get_invoice(session, invoice_id)
        if invoice.voided_at is not None:
            raise HTTPException(409, "الفاتورة ملغاة.")
        if payload.category_id is not None:
            check_income(session, payload.category_id, None, new=True)
            category_id = payload.category_id
        else:
            category_id = session.scalar(select(IncomeCategory.id).where(IncomeCategory.key == "tuition"))
        state = invoice_state(invoice)
        entry = new_income(session, actor, payload, f"دفعة الفاتورة {invoice.number}", category_id, invoice.child_id, invoice)
        worth = credit(entry, invoice)
        if worth > state["open"]:
            session.rollback()
            raise HTTPException(422, f"قيمة الدفعة ({text(invoice.currency, worth)} {invoice.currency}) أكبر من المتبقي ({text(invoice.currency, state['open'])} {invoice.currency}). صحّح المبلغ؛ لا يُقتطع تلقائياً.")
        session.commit()
        session.refresh(invoice)
        return invoice_dict(invoice, child_names(session, {invoice.child_id}), with_payments=True)

    @router.post("/invoices/{invoice_id}/void")
    def void_invoice(invoice_id: uuid.UUID, payload: ReasonIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "correct")
        invoice = get_invoice(session, invoice_id)
        if invoice.voided_at is not None:
            raise HTTPException(409, "الفاتورة ملغاة بالفعل.")
        if invoice_state(invoice)["paid"] != 0:
            raise HTTPException(409, "على الفاتورة دفعات. ألغِ الدفعات أولاً ثم ألغِ الفاتورة.")
        invoice.voided_at, invoice.voided_by, invoice.void_reason = datetime.now(timezone.utc), actor.name[:80], payload.reason.strip()
        audit(session, actor, "invoice.void", "invoice", invoice.id, {"voided": False}, {"voided": True}, invoice.void_reason)
        session.commit()
        return {"id": str(invoice.id), "voided": True}

    # ---- expenses (salaries are expenses) -------------------------------------------------------------------------------------------
    def salary_paid(session: Session, employee_id: uuid.UUID, month: str, ignore: uuid.UUID | None = None) -> bool:
        """A person counts as paid for a month while a salary entry for it stands (not cancelled, not reversed)."""
        rows = session.scalars(select(ExpenseEntry).where(
            ExpenseEntry.employee_id == employee_id, ExpenseEntry.salary_month == month, ExpenseEntry.voided_at.is_(None), ExpenseEntry.reverses_id.is_(None),
        )).all()
        done = reversed_ids(session, ExpenseEntry, [r.id for r in rows])
        return any(r.id != ignore and r.id not in done for r in rows)

    def check_expense(session: Session, payload: ExpenseIn, ignore: uuid.UUID | None = None) -> None:
        if payload.category not in EXPENSE_CATEGORIES:
            raise HTTPException(422, "اختر فئة صالحة.")
        if payload.employee_id is not None and session.get(Employee, payload.employee_id) is None:
            raise HTTPException(404, "الموظف غير موجود.")
        if payload.category == "salaries":
            if payload.employee_id is None or not payload.salary_month:
                raise HTTPException(422, "للراتب اختر الموظف وشهر الاستحقاق.")
            if salary_paid(session, payload.employee_id, payload.salary_month, ignore):
                raise HTTPException(409, "صُرف راتب هذا الموظف عن هذا الشهر من قبل. ألغِ الحركة الأولى إن كانت خطأ.")
        elif payload.salary_month:
            raise HTTPException(422, "شهر الاستحقاق للرواتب فقط.")

    def expense_rows(session: Session, start: date, end: date, category: str, q: str) -> list[ExpenseEntry]:
        query = select(ExpenseEntry).where(ExpenseEntry.booked_on >= start, ExpenseEntry.booked_on <= end)
        if category:
            query = query.where(ExpenseEntry.category == category)
        if q.strip():
            like = "%" + q.strip().lower().replace("%", "").replace("_", "") + "%"
            query = query.where(or_(func.lower(ExpenseEntry.description).like(like), func.lower(ExpenseEntry.recipient).like(like), func.lower(ExpenseEntry.note).like(like)))
        return list(session.scalars(query.order_by(ExpenseEntry.booked_on.desc(), ExpenseEntry.created_at.desc())).all())

    def expense_list(session: Session, rows: list[ExpenseEntry]) -> list[dict[str, Any]]:
        closed = closed_months(session)
        staff = employee_names(session, {r.employee_id for r in rows})
        done = reversed_ids(session, ExpenseEntry, [r.id for r in rows])
        return [expense_dict(r, staff, done, (r.booked_on.year, r.booked_on.month) in closed) for r in rows]

    @router.get("/expenses")
    def list_expenses(
        response: Response, month: str | None = None, date_from: date | None = None, date_to: date | None = None, category: str = "", q: str = "",
        _actor: Actor = Depends(guard), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        start, end = period(month, date_from, date_to)
        rows = expense_rows(session, start, end, category, q)
        return {"rows": expense_list(session, rows), "totals": totals(rows), "count": sum(1 for r in rows if r.voided_at is None)}

    @router.post("/expenses", status_code=201)
    def create_expense(payload: ExpenseIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        check_day(payload.booked_on)
        ensure_open(session, payload.booked_on)
        check_expense(session, payload)
        rate = chosen_rate(session, actor, payload.booked_on, payload.rate)
        amount, description = cents(payload.amount), payload.description.strip()
        no_twin(session, ExpenseEntry, actor, payload.booked_on, amount, payload.currency, description)
        entry = ExpenseEntry(
            booked_on=payload.booked_on, description=description, category=payload.category, recipient=payload.recipient.strip(),
            employee_id=payload.employee_id, salary_month=payload.salary_month, amount=amount, currency=payload.currency, rate=rate,
            amount_other=to_other(amount, payload.currency, rate), note=payload.note.strip(), created_by=actor.name[:80],
        )
        session.add(entry)
        session.flush()
        audit(session, actor, "expense.create", "expense", entry.id, None, expense_snapshot(entry))
        session.commit()
        return expense_list(session, [entry])[0]

    def get_expense(session: Session, entry_id: uuid.UUID) -> ExpenseEntry:
        entry = session.scalar(select(ExpenseEntry).where(ExpenseEntry.id == entry_id).with_for_update())
        if entry is None:
            raise HTTPException(404, "الحركة غير موجودة.")
        return entry

    @router.patch("/expenses/{entry_id}")
    def change_expense(entry_id: uuid.UUID, payload: ExpenseUpdate, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "correct")
        entry = get_expense(session, entry_id)
        if entry.voided_at is not None or entry.reverses_id is not None:
            raise HTTPException(409, "الحركات الملغاة والقيود العكسية لا تُعدَّل.")
        check_version(entry, payload.expected_version)
        check_day(payload.booked_on)
        ensure_open(session, entry.booked_on, payload.booked_on)
        check_expense(session, payload, ignore=entry.id)
        before = expense_snapshot(entry)
        rate = Decimal(entry.rate) if payload.rate is None or Decimal(payload.rate) == Decimal(entry.rate) else chosen_rate(session, actor, payload.booked_on, payload.rate)
        entry.booked_on, entry.description, entry.category, entry.recipient = payload.booked_on, payload.description.strip(), payload.category, payload.recipient.strip()
        entry.employee_id, entry.salary_month, entry.note = payload.employee_id, payload.salary_month, payload.note.strip()
        entry.amount, entry.currency, entry.rate = cents(payload.amount), payload.currency, rate
        entry.amount_other = to_other(entry.amount, entry.currency, rate)
        stamp(entry, actor)
        audit(session, actor, "expense.update", "expense", entry.id, before, expense_snapshot(entry))
        session.commit()
        return expense_list(session, [entry])[0]

    @router.post("/expenses/{entry_id}/void")
    def void_expense(entry_id: uuid.UUID, payload: ReasonIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "correct")
        return cancel(session, actor, ExpenseEntry, get_expense(session, entry_id), "expense", expense_snapshot, payload.reason.strip())

    @router.get("/salaries")
    def salaries(response: Response, month: str | None = None, _actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """The staff for one month: who was paid and who was not yet. The staff list itself belongs to the management."""
        response.headers["Cache-Control"] = "no-store"
        year, mon = parse_month(month, local_today())
        key = f"{year}-{mon:02d}"
        paid_rows = session.scalars(select(ExpenseEntry).where(ExpenseEntry.salary_month == key, ExpenseEntry.voided_at.is_(None), ExpenseEntry.reverses_id.is_(None))).all()
        done = reversed_ids(session, ExpenseEntry, [r.id for r in paid_rows])
        paid = {r.employee_id: r for r in paid_rows if r.id not in done}
        people = session.scalars(select(Employee).order_by(Employee.name)).all()
        rows = []
        for person in people:
            entry = paid.get(person.id)
            if not person.is_active and entry is None:
                continue  # a person who left only appears where a payment exists
            rows.append({
                "employee_id": str(person.id), "name": person.name, "job_title": person.job_title, "is_active": person.is_active,
                "salary": None if person.salary is None else text(person.salary_currency, person.salary), "salary_currency": person.salary_currency,
                "paid": entry is not None, "entry_id": str(entry.id) if entry else "",
                "paid_on": entry.booked_on.isoformat() if entry else "", "paid_amount": text(entry.currency, entry.amount) if entry else "", "paid_currency": entry.currency if entry else "",
            })
        return {"month": key, "rows": rows, "paid": sum(1 for r in rows if r["paid"]), "unpaid": sum(1 for r in rows if not r["paid"])}

    # ---- one entry with its history -------------------------------------------------------------------------------------------------
    @router.get("/history/{entity_id}")
    def history(entity_id: uuid.UUID, response: Response, _actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        rows = session.scalars(select(FeeAuditLog).where(FeeAuditLog.domain == "finance", FeeAuditLog.entity_id == str(entity_id)).order_by(FeeAuditLog.at)).all()
        return [{"at": to_local(r.at).isoformat() if r.at else None, "actor": r.actor_name, "action": r.action, "reason": r.reason,
                 "before": r.before_json, "after": r.after_json} for r in rows]

    # ---- the month overview ---------------------------------------------------------------------------------------------------------
    def summary_data(session: Session, year: int, month: int) -> dict[str, Any]:
        now = month_figures(session, year, month)
        prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
        before = month_figures(session, prev_year, prev_month)
        cats = categories(session)

        def pair(values: dict[str, Decimal]) -> dict[str, str]:
            return {"usd": text("USD", values["USD"]), "syp": text("SYP", values["SYP"])}

        def change(key: str) -> dict[str, Any]:
            out = {}
            for code in CURRENCIES:
                new, old = now[key][code], before[key][code]
                out[code.lower()] = {"difference": text(code, new - old), "percent": None if old == 0 else str(((new - old) / abs(old) * 100).quantize(Decimal("0.1")))}
            return out

        closing = closing_of(session, year, month)
        invoices = open_invoices(session)
        return {
            "month": f"{year}-{month:02d}", "previous_month": f"{prev_year}-{prev_month:02d}",
            "income": pair(now["income"]), "expense": pair(now["expense"]), "surplus": pair(now["surplus"]),
            "salaries": pair(now["salaries"]), "other_expenses": pair(now["other_expenses"]),
            "income_count": now["income_count"], "expense_count": now["expense_count"],
            "income_by_category": sorted(
                [{"category_id": str(cid), "key": cats[cid].key if cid in cats else None, "name": cats[cid].name if cid in cats else "", "usd": text("USD", d["USD"]), "syp": text("SYP", d["SYP"]), "count": d["count"]}
                 for cid, d in now["income_cats"].items()], key=lambda r: r["name"]),
            "expense_by_category": [
                {"category": key, "ar": label["ar"], "en": label["en"], "usd": text("USD", now["expense_cats"][key]["USD"]), "syp": text("SYP", now["expense_cats"][key]["SYP"]), "count": now["expense_cats"][key]["count"]}
                for key, label in EXPENSE_CATEGORIES.items() if key in now["expense_cats"]
            ],
            "previous": {"income": pair(before["income"]), "expense": pair(before["expense"]), "surplus": pair(before["surplus"])},
            "change": {key: change(key) for key in ("income", "expense", "surplus")},
            "converted": {key: pair(now["converted"][key]) for key in ("income", "expense", "surplus")},
            "invoices": {"open": invoices["open"], "partial": invoices["partial"], "open_amount": pair(invoices["amount"])},
            "closed": closing is not None,
            "closing": None if closing is None else {"by": closing.closed_by, "at": to_local(closing.closed_at).isoformat() if closing.closed_at else None},
        }

    @router.get("/summary")
    def summary(response: Response, month: str | None = None, _actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return summary_data(session, *parse_month(month, local_today()))

    @router.post("/closings", status_code=201)
    def close_month(payload: ClosingIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Closes a month: nothing in it can be added, changed or cancelled any more. It can still be read and exported."""
        need(session, actor, "manage")
        today = local_today()
        if (payload.year, payload.month) >= (today.year, today.month):
            raise HTTPException(422, "يُغلق الشهر بعد انتهائه فقط.")
        if closing_of(session, payload.year, payload.month) is not None:
            raise HTTPException(409, "الشهر مغلق بالفعل.")
        session.add(MonthClosing(year=payload.year, month=payload.month, closed_by=actor.name[:80], closed_at=datetime.now(timezone.utc)))
        audit(session, actor, "month.close", "month", f"{payload.year}-{payload.month:02d}", None, {"closed": True})
        session.commit()
        return {"month": f"{payload.year}-{payload.month:02d}", "closed": True}

    @router.post("/closings/{year}/{month}/reopen")
    def reopen_month(year: int, month: int, payload: ReasonIn, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        need(session, actor, "manage")
        closing = closing_of(session, year, month)
        if closing is None:
            raise HTTPException(409, "الشهر غير مغلق.")
        closing.reopened_at, closing.reopened_by, closing.reopen_reason = datetime.now(timezone.utc), actor.name[:80], payload.reason.strip()
        audit(session, actor, "month.reopen", "month", f"{year}-{month:02d}", {"closed": True}, {"closed": False}, closing.reopen_reason)
        session.commit()
        return {"month": f"{year}-{month:02d}", "closed": False}

    # ---- exports (both currencies and the rate in every file) -----------------------------------------------------------------------
    def table(fmt: str, name: str, title: str, header: list[str], rows: list[list[Any]]) -> Response:
        if fmt not in ("xlsx", "csv"):
            raise HTTPException(422, "الصيغة xlsx أو csv.")
        return csv_response(f"{name}.csv", header, rows) if fmt == "csv" else xlsx_response(f"{name}.xlsx", [(title, header, rows)])

    def state_word(row: dict[str, Any]) -> str:
        return "ملغاة" if row["voided"] else "قيد عكسي" if row["is_reversal"] else "مصحَّحة بقيد عكسي" if row["reversed"] else "سارية"

    def money_cell(value: str | None) -> Decimal | str:
        return "" if value is None else Decimal(value)

    @router.get("/export/income.{fmt}")
    def export_income(fmt: str, month: str | None = None, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> Response:
        need(session, actor, "export")
        year, mon = parse_month(month, local_today())
        rows = income_list(session, income_rows(session, *month_range(year, mon), None, ""))
        audit(session, actor, "export.income", "export", f"{year}-{mon:02d}", None, {"format": fmt, "rows": len(rows)})
        session.commit()
        header = ["التاريخ", "الوصف", "الفئة", "USD", "SYP", "عملة الدفع", "المبلغ المدفوع", "سعر الصرف (ليرة لكل دولار)", "الدافع", "الطفل", "رقم الفاتورة", "ملاحظة", "الحالة"]
        body = [[r["booked_on"], r["description"], r["category"], money_cell(r["usd"]), money_cell(r["syp"]), r["currency"], money_cell(r["amount"]), money_cell(r["rate"]),
                 r["payer_name"], r["child"], r["invoice_number"], r["note"], state_word(r)] for r in rows]
        return table(fmt, f"income-{year}-{mon:02d}", "الإيرادات", header, body)

    @router.get("/export/expenses.{fmt}")
    def export_expenses(fmt: str, month: str | None = None, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> Response:
        need(session, actor, "export")
        year, mon = parse_month(month, local_today())
        rows = expense_list(session, expense_rows(session, *month_range(year, mon), "", ""))
        audit(session, actor, "export.expenses", "export", f"{year}-{mon:02d}", None, {"format": fmt, "rows": len(rows)})
        session.commit()
        header = ["التاريخ", "الوصف", "الفئة", "USD", "SYP", "عملة الدفع", "المبلغ المدفوع", "سعر الصرف (ليرة لكل دولار)", "المستلم", "الموظف", "شهر الراتب", "ملاحظة", "الحالة"]
        body = [[r["booked_on"], r["description"], r["category_ar"], money_cell(r["usd"]), money_cell(r["syp"]), r["currency"], money_cell(r["amount"]), money_cell(r["rate"]),
                 r["recipient"], r["employee"], r["salary_month"], r["note"], state_word(r)] for r in rows]
        return table(fmt, f"expenses-{year}-{mon:02d}", "المصروفات", header, body)

    @router.get("/export/summary.{fmt}")
    def export_summary(fmt: str, month: str | None = None, actor: Actor = Depends(guard), session: Session = Depends(get_session)) -> Response:
        need(session, actor, "export")
        year, mon = parse_month(month, local_today())
        data = summary_data(session, year, mon)
        audit(session, actor, "export.summary", "export", data["month"], None, {"format": fmt})
        session.commit()
        current = rate_on(session, month_range(year, mon)[1])
        header = ["البند", "USD (المدفوع بالدولار)", "SYP (المدفوع بالليرة)", "العدد"]
        body: list[list[Any]] = [
            ["إجمالي الإيرادات", money_cell(data["income"]["usd"]), money_cell(data["income"]["syp"]), data["income_count"]],
            ["إجمالي المصروفات", money_cell(data["expense"]["usd"]), money_cell(data["expense"]["syp"]), data["expense_count"]],
            ["الفائض / العجز", money_cell(data["surplus"]["usd"]), money_cell(data["surplus"]["syp"]), ""],
            ["الرواتب", money_cell(data["salaries"]["usd"]), money_cell(data["salaries"]["syp"]), ""],
            ["مصروفات أخرى", money_cell(data["other_expenses"]["usd"]), money_cell(data["other_expenses"]["syp"]), ""],
        ]
        body += [["إيراد: " + c["name"], money_cell(c["usd"]), money_cell(c["syp"]), c["count"]] for c in data["income_by_category"]]
        body += [["مصروف: " + c["ar"], money_cell(c["usd"]), money_cell(c["syp"]), c["count"]] for c in data["expense_by_category"]]
        body += [
            ["فواتير مفتوحة (المتبقي)", money_cell(data["invoices"]["open_amount"]["usd"]), money_cell(data["invoices"]["open_amount"]["syp"]), data["invoices"]["open"] + data["invoices"]["partial"]],
            ["القيمة الكلية محوّلة — الفائض (للمقارنة فقط)", money_cell(data["converted"]["surplus"]["usd"]), money_cell(data["converted"]["surplus"]["syp"]), ""],
            ["سعر الصرف في نهاية الشهر (ليرة لكل دولار)", "" if current is None else Decimal(rate_text(current.syp_per_usd)), "", ""],
            ["حالة الشهر", "مغلق" if data["closed"] else "مفتوح", "", ""],
        ]
        return table(fmt, f"summary-{data['month']}", "الملخص الشهري", header, body)

    return router
