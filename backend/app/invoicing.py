"""Invoices that show US dollars and Syrian pounds side by side.

An invoice is the fee line of one child for one month (FeeCharge) with its positions (FeeChargeLine). The rate that turns one
currency into the other is frozen on the invoice when it is made; a later rate never changes it. A payment keeps what was really
handed over (currency, amount, rate of that day) and the value credited to the invoice. Nothing is deleted: a wrong invoice or
payment is cancelled (storno) with a reason.

Rounding (one rule everywhere, half up): the other-currency side of a position is rounded when it is made -- whole pounds for
SYP, cents for USD. Totals are the sum of the rounded positions, so every table adds up exactly.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import activity
from app.database import get_session
from app.fees import (
    CURRENCIES, ZERO, FeesActor, RateBook, active_payments, check_version, convert, ensure_open, exact, money, month_of,
    paid_amount, rate_text, remaining_amount, status_of, to_other, touch,
)
from app.ledger import last_day
from app.models import Child, FeeCharge, FeeChargeLine, FeePayment
from app.timeutil import local_today

WHOLE = Decimal("1")


def other_of(currency: str) -> str:
    return "SYP" if currency == "USD" else "USD"


def text(currency: str, value: Decimal | None) -> str | None:
    """USD with cents, SYP in whole pounds (cents only when the stored amount really has them)."""
    if value is None:
        return None
    if currency == "SYP":
        return str(int(value)) if value == value.to_integral_value() else format(money(value), "f")
    return format(money(value), "f")


def pair(base: str, base_value: Decimal | None, other_value: Decimal | None) -> dict[str, str | None]:
    """The two columns of a table: USD and SYP."""
    values = {base: base_value, other_of(base): other_value}
    return {code: text(code, values[code]) for code in ("USD", "SYP")}


def frozen_rate(charge: FeeCharge, book: RateBook) -> tuple[Decimal, date | None, str] | None:
    """The rate of an invoice: the frozen one, or (for an old fee line never frozen) the rate of the last day of its month,
    marked "reconstructed" -- shown, but not stored until the checked backfill runs."""
    if charge.rate_syp_per_usd is not None:
        return Decimal(charge.rate_syp_per_usd), charge.rate_date, charge.rate_source
    found = book.on(last_day(charge.year, charge.month))
    if found is None:
        return None
    return found[0], found[1], "reconstructed"


def rate_source_of(book: RateBook, day: date) -> str:
    row = next((r for r in book.rows if r.effective_date == day), None)
    return "auto" if row is not None and row.created_by == "auto-rate" else "manual"


def invoice_view(charge: FeeCharge, child: Child, book: RateBook, with_payments: bool = True) -> dict[str, Any]:
    base = charge.currency
    other = other_of(base)
    rate = frozen_rate(charge, book)
    r = rate[0] if rate else None
    lines: list[dict[str, Any]] = []
    total_base = None if charge.amount is None else money(charge.amount)
    total_other: Decimal | None = None
    if charge.lines:
        for position in charge.lines:
            amount_other = position.amount_other if position.amount_other is not None else (to_other(position.amount, base, r) if r else None)
            lines.append({"description": position.description, "amount": pair(base, money(position.amount), amount_other)})
        parts = [position.amount_other if position.amount_other is not None else (to_other(position.amount, base, r) if r else None) for position in charge.lines]
        total_other = None if any(part is None for part in parts) else sum(parts, ZERO)
    elif total_base is not None:
        total_other = to_other(total_base, base, r) if r else None
        lines.append({"description": "", "amount": pair(base, total_base, total_other)})
    paid_base = paid_amount(charge)
    open_base = None if total_base is None else money(total_base - paid_base)
    paid_other: Decimal | None = None
    open_other: Decimal | None = None
    if total_other is not None and r is not None:
        if open_base is not None and open_base <= 0 and total_base and total_base > 0:
            paid_other = total_other  # fully paid: both columns close at zero
        elif paid_base <= 0:
            paid_other = ZERO
        else:
            paid_other = min(to_other(paid_base, base, r), total_other)
        open_other = total_other - paid_other
    payments: list[dict[str, Any]] = []
    if with_payments:
        for p in sorted(charge.payments, key=lambda p: (p.paid_on or date.min, p.created_at)):
            actual_cur = p.paid_currency or base
            actual = money(p.paid_amount if p.paid_currency else p.amount)
            used = Decimal(p.pay_rate) if p.pay_rate else r
            actual_other = to_other(actual, actual_cur, used) if used else None
            payments.append({
                "id": str(p.id), "paid_on": p.paid_on.isoformat() if p.paid_on else None, "receipt_no": p.receipt_no or "",
                "payer": p.payer_name, "note": p.note, "currency": actual_cur, "amount": text(actual_cur, actual),
                "credited": text(base, money(p.amount)), "rate": rate_text(Decimal(p.pay_rate)) if p.pay_rate else None,
                "value": pair(actual_cur, actual, actual_other), "voided": p.deleted_at is not None,
                "void_reason": p.void_reason or "", "refund": money(p.amount) < 0,
            })
    return {
        "id": str(charge.id), "number": charge.invoice_no or "", "child": {"id": str(child.id), "name": child.display_name, "class_name": child.class_name},
        "year": charge.year, "month": charge.month, "base_currency": base,
        "rate": None if rate is None else {"syp_per_usd": rate_text(rate[0]), "date": rate[1].isoformat() if rate[1] else None, "source": rate[2], "frozen": charge.rate_syp_per_usd is not None},
        "lines": lines,
        "total": pair(base, total_base, total_other),
        "paid": pair(base, paid_base, paid_other),
        "open": pair(base, open_base, open_other),
        "status": status_of(charge.amount, paid_base, charge.needs_review),
        "payments": payments, "version": charge.version or 1, "needs_review": charge.needs_review,
        "voided": charge.voided_at is not None, "void_reason": charge.void_reason or "",
    }


# --- request models -------------------------------------------------------------------------------------------------


class LineIn(BaseModel):
    description: str = Field(default="", max_length=200)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class InvoiceCreate(BaseModel):
    child_id: uuid.UUID
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    currency: str = Field(pattern="^(USD|SYP)$")
    lines: list[LineIn] = Field(min_length=1, max_length=20)


class LinesReplace(BaseModel):
    lines: list[LineIn] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=5, max_length=300)
    expected_version: int | None = Field(default=None, ge=0, le=1_000_000_000)


class PayIn(BaseModel):
    paid_currency: str = Field(pattern="^(USD|SYP)$")
    paid_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    paid_on: date
    receipt_no: str | None = Field(default=None, max_length=40)
    payer_name: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=500)
    rate: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)  # only to deviate from the rate list
    rate_reason: str = Field(default="", max_length=300)


def snapshot(item: FeeCharge) -> dict[str, Any]:
    return {
        "number": item.invoice_no, "currency": item.currency, "year": item.year, "month": item.month,
        "total": None if item.amount is None else str(money(item.amount)),
        "rate": None if item.rate_syp_per_usd is None else rate_text(Decimal(item.rate_syp_per_usd)),
        "lines": [{"description": p.description, "amount": str(money(p.amount))} for p in item.lines],
    }


def build_router(user_guard: Callable[..., FeesActor], finance_guard: Callable[..., FeesActor], admin_guard: Callable[..., FeesActor]) -> APIRouter:
    """user_guard: accountant, management and admin. finance_guard: accountant and admin. admin_guard: admin only."""
    router = APIRouter(prefix="/api/admin/invoices")

    def charge_of(session: Session, charge_id: uuid.UUID, lock: bool = False) -> FeeCharge:
        query = select(FeeCharge).where(FeeCharge.id == charge_id).options(selectinload(FeeCharge.payments), selectinload(FeeCharge.lines))
        if lock:
            query = query.with_for_update()
        charge = session.scalar(query)
        if charge is None:
            raise HTTPException(404, "الفاتورة غير موجودة.")
        return charge

    def frozen_lines(charge: FeeCharge, lines: list[LineIn], rate: Decimal) -> list[FeeChargeLine]:
        return [
            FeeChargeLine(position=i, description=l.description.strip(), amount=money(l.amount), amount_other=to_other(l.amount, charge.currency, rate))
            for i, l in enumerate(lines, start=1)
        ]

    @router.get("")
    def list_invoices(
        response: Response, year: int | None = None, month: int | None = None, currency: str = "", status: str = "", child_id: uuid.UUID | None = None,
        _actor: FeesActor = Depends(user_guard), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        query = select(FeeCharge, Child).join(Child, Child.id == FeeCharge.child_id).where(FeeCharge.voided_at.is_(None)).options(
            selectinload(FeeCharge.payments), selectinload(FeeCharge.lines)
        )
        if year:
            query = query.where(FeeCharge.year == year)
        if month:
            query = query.where(FeeCharge.month == month)
        if currency in CURRENCIES:
            query = query.where(FeeCharge.currency == currency)
        if child_id:
            query = query.where(FeeCharge.child_id == child_id)
        book = RateBook.load(session)
        rows = [invoice_view(charge, child, book, with_payments=False) for charge, child in session.execute(query).all()]
        if status in ("paid", "partial", "open", "review"):
            rows = [row for row in rows if row["status"] == status]
        rows.sort(key=lambda row: (row["year"], row["month"], row["child"]["name"]), reverse=False)
        totals: dict[str, dict[str, str]] = {}
        for code in CURRENCIES:  # each currency is summed in its own currency only (the invoices that are due in it)
            own = [r for r in rows if r["base_currency"] == code]
            def add(key: str) -> str:
                return text(code, sum((Decimal(r[key][code]) for r in own if r[key][code] is not None), ZERO)) or "0"
            totals[code] = {"count": str(len(own)), "total": add("total"), "paid": add("paid"), "open": add("open")}
        return {"rows": rows, "totals": totals}

    @router.get("/{charge_id}")
    def get_invoice(charge_id: uuid.UUID, response: Response, _actor: FeesActor = Depends(user_guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        charge = charge_of(session, charge_id)
        return invoice_view(charge, session.get(Child, charge.child_id), RateBook.load(session))

    @router.post("", status_code=201)
    def create_invoice(payload: InvoiceCreate, actor: FeesActor = Depends(user_guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        child = session.get(Child, payload.child_id)
        if child is None or not child.is_active:
            raise HTTPException(404, "الطفل غير موجود.")
        ensure_open(session, (payload.year, payload.month))
        book = RateBook.load(session)
        found = book.on(local_today())
        if found is None:
            raise HTTPException(409, "لا يوجد سعر صرف. أدخل سعر الصرف أولاً (تبويب «سعر الصرف») ثم أنشئ الفاتورة.")
        charge = FeeCharge(
            child_id=child.id, year=payload.year, month=payload.month, currency=payload.currency,
            amount=sum((money(l.amount) for l in payload.lines), ZERO),
            rate_syp_per_usd=found[0], rate_date=found[1], rate_source=rate_source_of(book, found[1]),
        )
        charge.lines = frozen_lines(charge, payload.lines, found[0])
        session.add(charge)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "توجد فاتورة لهذا الطفل في الشهر والعملة نفسيهما. عدّل بنودها بدل إنشاء أخرى.") from exc
        activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="finance", action="invoice.create", entity_type="invoice",
                        entity_id=charge.id, after=snapshot(charge))
        session.commit()
        session.refresh(charge)
        return invoice_view(charge_of(session, charge.id), child, book)

    @router.put("/{charge_id}/lines")
    def replace_lines(charge_id: uuid.UUID, payload: LinesReplace, actor: FeesActor = Depends(user_guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """New positions for an invoice. The frozen rate stays; the reason and the old values are logged."""
        charge = charge_of(session, charge_id, lock=True)
        if charge.voided_at is not None:
            raise HTTPException(409, "الفاتورة ملغاة.")
        ensure_open(session, (charge.year, charge.month))
        check_version(charge, payload.expected_version, f"{charge.amount} {charge.currency}")
        book = RateBook.load(session)
        before = snapshot(charge)
        if charge.rate_syp_per_usd is None:  # an old fee line: it is frozen now, with the rate of today
            found = book.on(local_today())
            if found is None:
                raise HTTPException(409, "لا يوجد سعر صرف. أدخل سعر الصرف أولاً.")
            charge.rate_syp_per_usd, charge.rate_date, charge.rate_source = found[0], found[1], rate_source_of(book, found[1])
        total = sum((money(l.amount) for l in payload.lines), ZERO)
        if total < paid_amount(charge):
            raise HTTPException(422, "مجموع البنود لا يمكن أن يكون أقل من المبلغ المدفوع.")
        charge.lines.clear()
        session.flush()
        charge.lines.extend(frozen_lines(charge, payload.lines, Decimal(charge.rate_syp_per_usd)))
        charge.amount = total
        charge.needs_review = False
        touch(charge, actor.name)
        activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="finance", action="invoice.update", entity_type="invoice",
                        entity_id=charge.id, before=before, after=snapshot(charge), reason=payload.reason.strip())
        session.commit()
        return invoice_view(charge_of(session, charge.id), session.get(Child, charge.child_id), book)

    @router.post("/{charge_id}/payments", status_code=201)
    def pay(charge_id: uuid.UUID, payload: PayIn, actor: FeesActor = Depends(user_guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """A payment in USD or SYP. What was handed over is stored as it is; the value credited to the invoice is calculated
        with the rate of the day of payment (or the rate typed here, with a reason)."""
        charge = charge_of(session, charge_id, lock=True)
        if charge.voided_at is not None:
            raise HTTPException(409, "الفاتورة ملغاة.")
        ensure_open(session, month_of(payload.paid_on))
        book = RateBook.load(session)
        base = charge.currency
        used: Decimal | None = None
        if payload.paid_currency == base:
            applied = money(payload.paid_amount)
        else:
            listed = book.on(payload.paid_on)
            if payload.rate is not None and (listed is None or Decimal(payload.rate) != listed[0]):
                if len(payload.rate_reason.strip()) < 5:
                    raise HTTPException(422, "اكتب سبب سعر الصرف المختلف عن القائمة (5 أحرف على الأقل).")
                used = Decimal(payload.rate)
            elif listed is not None:
                used = listed[0]
            if used is None:
                raise HTTPException(409, "لا يوجد سعر صرف لهذا اليوم. أدخل سعر الصرف أولاً.")
            applied = convert(payload.paid_amount, payload.paid_currency, base, used)
        if applied <= 0:
            raise HTTPException(422, "قيمة الدفعة بعد التحويل صفر.")
        remaining = remaining_amount(charge)
        if remaining is None:
            raise HTTPException(422, "المبلغ المطلوب غير محدد بعد.")
        if applied > remaining:
            raise HTTPException(422, f"قيمة الدفعة ({text(base, applied)} {base}) أكبر من المتبقي ({text(base, remaining)} {base}). صحّح المبلغ؛ لن يُقتطع تلقائياً.")
        receipt = (payload.receipt_no or "").strip() or None
        if receipt and session.scalar(select(FeePayment.id).where(FeePayment.receipt_no == receipt, FeePayment.deleted_at.is_(None))) is not None:
            raise HTTPException(409, "رقم الإيصال مستخدم من قبل.")
        since = (datetime.now(timezone.utc) - timedelta(seconds=20)).replace(tzinfo=None)
        twin = session.scalar(select(FeePayment.id).where(
            FeePayment.charge_id == charge.id, FeePayment.deleted_at.is_(None), FeePayment.amount == applied, FeePayment.paid_on == payload.paid_on,
            FeePayment.payer_name == payload.payer_name.strip(), FeePayment.created_by_name == actor.name[:80], FeePayment.created_at >= since,
        ))
        if twin is not None:
            raise HTTPException(409, "سُجّلت الدفعة نفسها قبل لحظات. إن كانت دفعة ثانية فعلاً، انتظر قليلاً ثم أعد المحاولة.")
        foreign = payload.paid_currency != base
        payment = FeePayment(
            charge_id=charge.id, amount=applied, paid_on=payload.paid_on, receipt_no=receipt, note=payload.note.strip(),
            payer_name=payload.payer_name.strip(), created_by_id=actor.account_id, created_by_name=actor.name[:80],
            paid_currency=payload.paid_currency if foreign else None, paid_amount=money(payload.paid_amount) if foreign else None,
            pay_rate=used if foreign else None,
        )
        charge.payments.append(payment)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "رقم الإيصال مستخدم من قبل.") from exc
        activity.record(
            session, actor_id=actor.account_id, actor_name=actor.name, domain="finance", action="payment.create", entity_type="payment", entity_id=payment.id,
            after={"invoice": charge.invoice_no, "paid": f"{money(payload.paid_amount)} {payload.paid_currency}", "credited": f"{applied} {base}",
                   "rate": None if used is None else rate_text(used), "receipt": receipt},
            reason=payload.rate_reason.strip() if foreign and payload.rate is not None else "",
        )
        session.commit()
        return invoice_view(charge_of(session, charge.id), session.get(Child, charge.child_id), book)

    @router.post("/backfill")
    def backfill_route(apply: bool = False, actor: FeesActor = Depends(admin_guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Admin only. apply=false only looks. apply=true freezes the rate and gives a number to every old fee line."""
        return backfill(session, apply, actor)

    return router


def backfill(session: Session, apply: bool, actor: FeesActor) -> dict[str, Any]:
    """Old fee lines get an invoice number and a frozen rate (the rate of the last day of their month, source "reconstructed").
    Nothing else changes: amounts, payments and dates stay exactly as they are. Safe to run twice (it skips what is done)."""
    book = RateBook.load(session)
    todo = list(session.scalars(select(FeeCharge).where((FeeCharge.rate_syp_per_usd.is_(None)) | (FeeCharge.invoice_no.is_(None))).order_by(FeeCharge.year, FeeCharge.month, FeeCharge.created_at)))
    without_rate = 0
    frozen = numbered = 0
    counters: dict[int, int] = {}

    def next_number(year: int) -> str:
        if year not in counters:
            counters[year] = max([int(n.rsplit("-", 1)[-1]) for (n,) in session.execute(select(FeeCharge.invoice_no).where(FeeCharge.invoice_no.like(f"INV-{year}-%"))) if n and n.rsplit("-", 1)[-1].isdigit()] or [0])
        counters[year] += 1
        return f"INV-{year}-{counters[year]:04d}"

    for charge in todo:
        if charge.rate_syp_per_usd is None:
            found = book.on(last_day(charge.year, charge.month))
            if found is None:
                without_rate += 1
            else:
                frozen += 1
                if apply:
                    charge.rate_syp_per_usd, charge.rate_date, charge.rate_source = found[0], found[1], "reconstructed"
        if charge.invoice_no is None:
            numbered += 1
            if apply:
                charge.invoice_no = next_number(charge.year)
    result = {"applied": apply, "fee_lines_checked": len(todo), "rate_frozen": frozen, "numbered": numbered, "without_any_rate": without_rate}
    if apply:
        activity.record(session, actor_id=actor.account_id, actor_name=actor.name, domain="finance", action="invoice.backfill", entity_type="invoice", after=result)
        session.commit()
    return result
