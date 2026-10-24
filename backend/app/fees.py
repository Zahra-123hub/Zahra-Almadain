"""Monthly child fees (كشف اشتراكات ورسوم الأطفال): charges, partial payments, totals.

Paid and remaining amounts are always calculated from the payments, never stored.
USD and SYP are kept strictly apart; amounts of different currencies are never added.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Child, FeeAuditLog, FeeCharge, FeePayment

CURRENCIES = ("USD", "SYP")
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
Money = Field(ge=0, max_digits=14, decimal_places=2)


@dataclass
class FeesActor:
    """Who is acting: a platform account (accountant/admin) or the legacy admin login."""

    account_id: uuid.UUID | None
    name: str
    role: str


# --- calculations (pure functions, covered by unit tests) -------------------


def money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def active_payments(charge: FeeCharge) -> list[FeePayment]:
    return [payment for payment in charge.payments if payment.deleted_at is None]


def paid_amount(charge: FeeCharge) -> Decimal:
    return money(sum((money(p.amount) for p in active_payments(charge)), ZERO))


def remaining_amount(charge: FeeCharge) -> Decimal | None:
    """Open amount, or None while the amount due is unknown (empty)."""
    if charge.amount is None:
        return None
    return money(money(charge.amount) - paid_amount(charge))


def status_of(amount: Decimal | None, paid: Decimal, needs_review: bool = False) -> str:
    """review / paid / partial / open.

    "paid" only when an amount > 0 is due and nothing is left to pay. A row that needs review,
    or whose amount is empty or 0, is never "paid" (0 due / 0 paid / 0 open is "review")."""
    if needs_review or amount is None or money(amount) <= 0:
        return "review"
    if money(amount) - money(paid) <= 0:
        return "paid"
    return "partial" if paid > 0 else "open"


def totals_by_currency(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, Decimal]] = {
        code: {"amount": ZERO, "paid": ZERO, "remaining": ZERO} for code in CURRENCIES
    }
    for row in rows:
        bucket = result[row["currency"]]
        if row["amount"] is not None:
            bucket["amount"] += Decimal(row["amount"])
            bucket["remaining"] += Decimal(row["remaining"])
        bucket["paid"] += Decimal(row["paid"])
    return {
        code: {key: str(money(value)) for key, value in bucket.items()}
        for code, bucket in result.items()
    }


# --- request models ----------------------------------------------------------


class PaymentIn(BaseModel):
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    paid_on: date
    receipt_no: str | None = Field(default=None, max_length=40)
    note: str = Field(default="", max_length=500)


class ChargeCreate(BaseModel):
    """A new table row: an existing child (child_id) or a new one (child_name + class_name),
    the amount due, and optionally a first payment."""

    child_id: uuid.UUID | None = None
    child_name: str = Field(default="", max_length=120)
    class_name: str = Field(default="", max_length=60)
    payment: PaymentIn | None = None
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Money
    currency: str = Field(pattern="^(USD|SYP)$")


class ChargeUpdate(BaseModel):
    amount: Decimal = Money


class GenerateRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Money
    currency: str = Field(pattern="^(USD|SYP)$")
    class_name: str = Field(default="", max_length=60)


class ChildClassIn(BaseModel):
    class_name: str = Field(max_length=60)
    display_name: str | None = Field(default=None, max_length=120)


# --- serialisation -----------------------------------------------------------


def charge_row(charge: FeeCharge, child: Child) -> dict[str, Any]:
    payments = sorted(
        active_payments(charge), key=lambda p: (p.paid_on or date.min, p.created_at)
    )
    paid = paid_amount(charge)
    remaining = remaining_amount(charge)
    return {
        "id": str(charge.id),
        "child_id": str(child.id),
        "child_name": child.display_name,
        "class_name": child.class_name,
        "year": charge.year,
        "month": charge.month,
        "currency": charge.currency,
        "amount": None if charge.amount is None else str(money(charge.amount)),
        "paid": str(paid),
        "remaining": None if remaining is None else str(remaining),
        "status": status_of(charge.amount, paid, charge.needs_review),
        "note": charge.note,
        "needs_review": charge.needs_review,
        "raw_text": charge.raw_text,
        "source": charge.source,
        "last_paid_on": next((p.paid_on.isoformat() for p in reversed(payments) if p.paid_on), None),
        "receipts": [p.receipt_no for p in payments if p.receipt_no],
        "notes": ([charge.note] if charge.note else []) + [p.note for p in payments if p.note],
        "payments": [
            {
                "id": str(p.id),
                "amount": str(money(p.amount)),
                "paid_on": p.paid_on.isoformat() if p.paid_on else None,
                "receipt_no": p.receipt_no or "",
                "note": p.note,
                "created_by": p.created_by_name,
            }
            for p in payments
        ],
    }


def log(session: Session, actor: FeesActor, action: str, entity_id: Any, details: str) -> None:
    session.add(
        FeeAuditLog(
            actor_id=actor.account_id,
            actor_name=actor.name[:80],
            action=action,
            entity_id=str(entity_id),
            details=details[:1000],
        )
    )


def build_router(guard: Callable[..., FeesActor]) -> APIRouter:
    """All fee routes are protected by `guard` (accountant or admin only)."""
    router = APIRouter(prefix="/api/admin/fees")

    def get_charge(session: Session, charge_id: uuid.UUID) -> FeeCharge:
        charge = session.scalar(
            select(FeeCharge).where(FeeCharge.id == charge_id).with_for_update()
        )
        if charge is None:
            raise HTTPException(404, "الرسم المطلوب غير موجود.")
        return charge

    def check_receipt(session: Session, receipt_no: str | None, own_id: uuid.UUID | None) -> None:
        if not receipt_no:
            return
        clash = session.scalar(
            select(FeePayment.id).where(
                FeePayment.receipt_no == receipt_no,
                FeePayment.deleted_at.is_(None),
                FeePayment.id != own_id if own_id else True,
            )
        )
        if clash is not None:
            raise HTTPException(409, "رقم الإيصال مستخدم من قبل.")

    def check_not_over(charge: FeeCharge, amount: Decimal, ignore: FeePayment | None = None) -> None:
        remaining = remaining_amount(charge)
        if remaining is None:
            raise HTTPException(422, "الرسم المطلوب غير محدد بعد. أدخله أولاً ثم سجّل الدفعة.")
        if ignore is not None and ignore.deleted_at is None:
            remaining += money(ignore.amount)
        if amount > remaining:
            raise HTTPException(
                422,
                f"المبلغ أكبر من المتبقي ({remaining} {charge.currency}). "
                "صحّح المبلغ؛ لن يتم اقتطاعه تلقائياً.",
            )

    @router.get("/me")
    def me(actor: FeesActor = Depends(guard)) -> dict[str, str]:
        return {"name": actor.name, "role": actor.role}

    @router.get("")
    def list_fees(
        response: Response,
        year: int | None = None,
        month: int | None = None,
        class_name: str = "",
        currency: str = "",
        status: str = "",
        needs_review: bool | None = None,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        query = select(FeeCharge, Child).join(Child, Child.id == FeeCharge.child_id)
        if year:
            query = query.where(FeeCharge.year == year)
        if month:
            query = query.where(FeeCharge.month == month)
        if currency in CURRENCIES:
            query = query.where(FeeCharge.currency == currency)
        if class_name:
            query = query.where(Child.class_name == class_name)
        rows = [charge_row(charge, child) for charge, child in session.execute(query).all()]
        if needs_review is not None:
            rows = [row for row in rows if row["needs_review"] == needs_review]
        if status in ("paid", "partial", "open", "review"):
            rows = [row for row in rows if row["status"] == status]
        rows.sort(key=lambda row: (row["class_name"], row["child_name"]))
        for number, row in enumerate(rows, start=1):
            row["n"] = number
        classes = sorted(
            {value for (value,) in session.execute(select(Child.class_name).distinct()) if value}
        )
        return {
            "rows": rows,
            "totals": totals_by_currency(rows),
            "classes": classes,
        }

    @router.get("/children")
    def fee_children(
        response: Response,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, str]]:
        response.headers["Cache-Control"] = "no-store"
        children = session.scalars(
            select(Child).where(Child.is_active.is_(True)).order_by(Child.display_name)
        ).all()
        return [
            {"id": str(c.id), "display_name": c.display_name, "class_name": c.class_name}
            for c in children
        ]

    @router.patch("/children/{child_id}")
    def set_child_class(
        child_id: uuid.UUID,
        payload: ChildClassIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, str]:
        child = session.get(Child, child_id)
        if child is None:
            raise HTTPException(404, "الطفل غير موجود.")
        child.class_name = payload.class_name.strip()
        if payload.display_name is not None:
            child.display_name = payload.display_name.strip()
        log(session, actor, "child.update", child.id, f"الصف: {child.class_name}")
        session.commit()
        return {"id": str(child.id), "class_name": child.class_name}

    @router.post("/charges", status_code=201)
    def create_charge(
        payload: ChargeCreate,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        if payload.child_id is not None:
            child = session.get(Child, payload.child_id)
            if child is None or not child.is_active:
                raise HTTPException(404, "الطفل غير موجود.")
        else:
            name = payload.child_name.strip()
            if len(name) < 2:
                raise HTTPException(422, "اكتب اسم الطفل أو اختر طفلاً من القائمة.")
            class_name = payload.class_name.strip()
            child = session.scalar(
                select(Child).where(
                    func.lower(Child.display_name) == name.lower(),
                    Child.is_active.is_(True),
                )
            )
            if child is None:
                child = Child(display_name=name, class_name=class_name)
                session.add(child)
                session.flush()
                log(session, actor, "child.create", child.id, f"{class_name or '-'}")
            elif class_name and child.class_name != class_name:
                child.class_name = class_name
        charge = FeeCharge(
            child_id=child.id,
            year=payload.year,
            month=payload.month,
            currency=payload.currency,
            amount=money(payload.amount),
        )
        session.add(charge)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "يوجد رسم لهذا الطفل في الشهر والعملة نفسيهما.") from exc
        log(
            session, actor, "charge.create", charge.id,
            f"{payload.month}/{payload.year} {payload.amount} {payload.currency}",
        )
        first = payload.payment
        if first is not None and money(first.amount) > 0:
            amount = money(first.amount)
            receipt = (first.receipt_no or "").strip() or None
            check_receipt(session, receipt, None)
            check_not_over(charge, amount)
            payment = FeePayment(
                charge_id=charge.id,
                amount=amount,
                paid_on=first.paid_on,
                receipt_no=receipt,
                note=first.note.strip(),
                created_by_id=actor.account_id,
                created_by_name=actor.name[:80],
            )
            charge.payments.append(payment)
            session.flush()
            log(session, actor, "payment.create", payment.id, f"{amount} {charge.currency} إيصال {receipt or '-'}")
        session.commit()
        session.refresh(charge)
        return charge_row(charge, child)

    @router.post("/generate")
    def generate_charges(
        payload: GenerateRequest,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, int]:
        """Create the same charge for every active child that has none for that month/currency."""
        query = select(Child).where(Child.is_active.is_(True))
        if payload.class_name:
            query = query.where(Child.class_name == payload.class_name)
        created = skipped = 0
        for child in session.scalars(query).all():
            exists = session.scalar(
                select(FeeCharge.id).where(
                    FeeCharge.child_id == child.id,
                    FeeCharge.year == payload.year,
                    FeeCharge.month == payload.month,
                    FeeCharge.currency == payload.currency,
                )
            )
            if exists is not None:
                skipped += 1
                continue
            session.add(
                FeeCharge(
                    child_id=child.id,
                    year=payload.year,
                    month=payload.month,
                    currency=payload.currency,
                    amount=money(payload.amount),
                )
            )
            created += 1
        log(
            session, actor, "charge.generate", f"{payload.month}/{payload.year}",
            f"{created} رسم، {payload.amount} {payload.currency}",
        )
        session.commit()
        return {"created": created, "skipped": skipped}

    @router.patch("/charges/{charge_id}")
    def update_charge(
        charge_id: uuid.UUID,
        payload: ChargeUpdate,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        charge = get_charge(session, charge_id)
        if money(payload.amount) < paid_amount(charge):
            raise HTTPException(422, "الرسم المطلوب لا يمكن أن يكون أقل من المبلغ المدفوع.")
        old = charge.amount
        charge.amount = money(payload.amount)
        log(session, actor, "charge.update", charge.id, f"{old} → {charge.amount} {charge.currency}")
        session.commit()
        session.refresh(charge)
        return charge_row(charge, session.get(Child, charge.child_id))

    @router.post("/charges/{charge_id}/reviewed")
    def charge_reviewed(
        charge_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        charge = get_charge(session, charge_id)
        charge.needs_review = False
        log(session, actor, "charge.reviewed", charge.id, "")
        session.commit()
        session.refresh(charge)
        return charge_row(charge, session.get(Child, charge.child_id))

    @router.delete("/charges/{charge_id}", status_code=204)
    def delete_charge(
        charge_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> Response:
        charge = get_charge(session, charge_id)
        if active_payments(charge):
            raise HTTPException(409, "لا يمكن حذف رسم عليه دفعات. احذف الدفعات أولاً.")
        log(session, actor, "charge.delete", charge.id, f"{charge.month}/{charge.year} {charge.currency}")
        session.delete(charge)
        session.commit()
        return Response(status_code=204)

    @router.post("/charges/{charge_id}/payments", status_code=201)
    def add_payment(
        charge_id: uuid.UUID,
        payload: PaymentIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        charge = get_charge(session, charge_id)
        amount = money(payload.amount)
        if amount <= 0:
            raise HTTPException(422, "مبلغ الدفعة يجب أن يكون أكبر من صفر.")
        receipt = (payload.receipt_no or "").strip() or None
        check_receipt(session, receipt, None)
        check_not_over(charge, amount)
        payment = FeePayment(
            charge_id=charge.id,
            amount=amount,
            paid_on=payload.paid_on,
            receipt_no=receipt,
            note=payload.note.strip(),
            created_by_id=actor.account_id,
            created_by_name=actor.name[:80],
        )
        charge.payments.append(payment)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "رقم الإيصال مستخدم من قبل.") from exc
        log(session, actor, "payment.create", payment.id, f"{amount} {charge.currency} إيصال {receipt or '-'}")
        session.commit()
        session.refresh(charge)
        return charge_row(charge, session.get(Child, charge.child_id))

    def get_payment(session: Session, payment_id: uuid.UUID) -> FeePayment:
        payment = session.scalar(
            select(FeePayment)
            .where(FeePayment.id == payment_id, FeePayment.deleted_at.is_(None))
            .with_for_update()
        )
        if payment is None:
            raise HTTPException(404, "الدفعة غير موجودة.")
        return payment

    @router.patch("/payments/{payment_id}")
    def update_payment(
        payment_id: uuid.UUID,
        payload: PaymentIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        payment = get_payment(session, payment_id)
        charge = get_charge(session, payment.charge_id)
        amount = money(payload.amount)
        if amount <= 0:
            raise HTTPException(422, "مبلغ الدفعة يجب أن يكون أكبر من صفر.")
        receipt = (payload.receipt_no or "").strip() or None
        check_receipt(session, receipt, payment.id)
        check_not_over(charge, amount, ignore=payment)
        before = f"{payment.amount} إيصال {payment.receipt_no or '-'}"
        payment.amount = amount
        payment.paid_on = payload.paid_on
        payment.receipt_no = receipt
        payment.note = payload.note.strip()
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "رقم الإيصال مستخدم من قبل.") from exc
        log(session, actor, "payment.update", payment.id, f"{before} → {amount} إيصال {receipt or '-'}")
        session.commit()
        session.refresh(charge)
        return charge_row(charge, session.get(Child, charge.child_id))

    @router.delete("/payments/{payment_id}")
    def delete_payment(
        payment_id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        payment = get_payment(session, payment_id)
        charge = get_charge(session, payment.charge_id)
        payment.deleted_at = datetime.now(timezone.utc)  # soft delete: kept for the audit trail
        log(session, actor, "payment.delete", payment.id, f"{payment.amount} إيصال {payment.receipt_no or '-'}")
        session.commit()
        session.refresh(charge)
        return charge_row(charge, session.get(Child, charge.child_id))

    @router.get("/summary")
    def summary(
        response: Response,
        year: int | None = None,
        month: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """Money received, per currency — the value for the accounting line
        "رسوم التسجيل والاشتراكات". Use year/month for a fee period, or
        date_from/date_to to sum by the date the money was received (week or month)."""
        response.headers["Cache-Control"] = "no-store"
        query = (
            select(FeeCharge.currency, func.coalesce(func.sum(FeePayment.amount), 0))
            .join(FeePayment, FeePayment.charge_id == FeeCharge.id)
            .where(FeePayment.deleted_at.is_(None))
            .group_by(FeeCharge.currency)
        )
        if year:
            query = query.where(FeeCharge.year == year)
        if month:
            query = query.where(FeeCharge.month == month)
        if date_from:
            query = query.where(FeePayment.paid_on >= date_from)
        if date_to:
            query = query.where(FeePayment.paid_on <= date_to)
        paid = {code: ZERO for code in CURRENCIES}
        for code, total in session.execute(query).all():
            paid[code] = money(total)
        return {"paid": {code: str(value) for code, value in paid.items()}}

    @router.get("/audit")
    def audit(
        response: Response,
        limit: int = 100,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, str]]:
        response.headers["Cache-Control"] = "no-store"
        entries = session.scalars(
            select(FeeAuditLog).order_by(FeeAuditLog.at.desc()).limit(min(max(limit, 1), 500))
        ).all()
        return [
            {
                "at": entry.at.isoformat() if entry.at else "",
                "actor": entry.actor_name,
                "action": entry.action,
                "entity_id": entry.entity_id,
                "details": entry.details,
            }
            for entry in entries
        ]

    return router
