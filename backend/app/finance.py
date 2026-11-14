"""The cash book as the accountant uses it: overview, book, bookings, cancellations, history.

Everything here answers from app.ledger, the one calculation of the cash balance. Bookings and cancellations are only possible once
the cash book is live. Nothing financial is deleted for good: a cancellation keeps the line visible with who, when and why.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import ledger as book
from app.database import get_session
from app.fees import CURRENCIES, FeesActor, check_version, ensure_open, money, month_of, touch
from app.legacy_migration import blockers_for_rollback
from app.models import (
    CashTransaction, EntryReceipt, Employee, FeeAuditLog, FeeCharge, FeePayment, SalaryLine,
)
from app.timeutil import local_today, to_local

RECEIPT_TYPES = {
    ".pdf": (b"%PDF-", "application/pdf"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".webp": (b"RIFF", "image/webp"),
}
MAX_RECEIPT_BYTES = 3 * 1024 * 1024
MAX_RECEIPTS_PER_BOOKING = 5


class BookingIn(BaseModel):
    currency: str = Field(pattern="^(USD|SYP)$")
    kind: str = Field(pattern="^(income|expense)$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    booked_on: date
    category: str = Field(max_length=30)
    description: str = Field(default="", max_length=500)
    counterparty: str = Field(default="", max_length=120)
    receipt_no: str = Field(default="", max_length=60)


class BookingUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    booked_on: date | None = None
    category: str | None = Field(default=None, max_length=30)
    description: str | None = Field(default=None, max_length=500)
    counterparty: str | None = Field(default=None, max_length=120)
    receipt_no: str | None = Field(default=None, max_length=60)
    expected_version: int | None = Field(default=None, ge=0, le=1_000_000_000)


class VoidIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class RemoveReceiptIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


def clean_reason(reason: str) -> str:
    text = reason.strip()
    if len(text) < 5:
        raise HTTPException(422, "اكتب سبب الإلغاء (5 أحرف على الأقل).")
    return text


def audit_row(row: FeeAuditLog) -> dict[str, Any]:
    def load(text: str) -> Any:
        try:
            return json.loads(text) if text else None
        except ValueError:
            return None

    return {
        "at": row.at.isoformat() if row.at else None, "at_local": to_local(row.at).isoformat() if row.at else None,
        "actor": row.actor_name, "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id,
        "reason": row.reason, "before": load(row.before_json), "after": load(row.after_json), "details": row.details,
    }


def build_router(guard: Callable[..., FeesActor]) -> APIRouter:
    router = APIRouter(prefix="/api/admin/accounting", tags=["cash-book"])

    def booking(session: Session, booking_id: uuid.UUID) -> CashTransaction:
        row = session.scalar(select(CashTransaction).where(CashTransaction.id == booking_id).with_for_update())
        if row is None:
            raise HTTPException(404, "الحركة غير موجودة.")
        return row

    def booking_months_open(session: Session, *days: date | None) -> None:
        ensure_open(session, *[month_of(d) for d in days if d is not None])

    # ---- reading ------------------------------------------------------------------------------------------------------
    @router.get("/finance/categories")
    def categories(_actor: FeesActor = Depends(guard)) -> dict[str, Any]:
        return book.category_list()

    @router.get("/finance/status")
    def status(response: Response, _actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        row = book.cutover_row(session)
        mode = book.ledger_mode(session)
        return {
            "mode": mode,
            "went_live_at": row.went_live_at.isoformat() if row and row.went_live_at else None,
            "live_writes": row.live_writes if row else 0,
            "way_back": mode == "live" and not blockers_for_rollback(session),
            "timezone": "Asia/Damascus", "today": local_today().isoformat(),
        }

    @router.get("/finance/overview")
    def overview(response: Response, _actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        return book.overview(session, local_today())

    @router.get("/finance/book")
    def cash_book(
        response: Response,
        currency: str,
        date_from: date | None = None,
        date_to: date | None = None,
        category: str | None = None,
        source: str | None = None,
        kind: str | None = None,
        only_missing_receipt: bool = False,
        only_estimated: bool = False,
        include_voided: bool = True,
        newest_first: bool = True,
        limit: int = 500,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        if currency not in CURRENCIES:
            raise HTTPException(422, "عملة غير صالحة.")
        if source and source not in book.SOURCES:
            raise HTTPException(422, "مصدر غير معروف.")
        return book.book(session, currency, date_from, date_to, category, source, kind, only_missing_receipt, only_estimated,
                         include_voided, newest_first, limit)

    @router.get("/finance/history/{entity_id}")
    def history(
        entity_id: str, response: Response, _actor: FeesActor = Depends(guard), session: Session = Depends(get_session),
    ) -> list[dict[str, Any]]:
        """Every logged action on one line (a booking, a payment, a salary): who, when, from which value to which, and why."""
        response.headers["Cache-Control"] = "no-store"
        rows = session.scalars(select(FeeAuditLog).where(FeeAuditLog.entity_id == entity_id).order_by(FeeAuditLog.at, FeeAuditLog.id)).all()
        return [audit_row(row) for row in rows]

    @router.get("/finance/voided")
    def voided(response: Response, _actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Cancelled fee lines and salary lines (they no longer show in the working lists, but nothing is lost)."""
        response.headers["Cache-Control"] = "no-store"
        charges = session.scalars(select(FeeCharge).where(FeeCharge.voided_at.is_not(None)).order_by(FeeCharge.voided_at.desc())).all()
        lines = session.execute(
            select(SalaryLine, Employee).join(Employee, Employee.id == SalaryLine.employee_id).where(SalaryLine.voided_at.is_not(None)).order_by(SalaryLine.voided_at.desc())
        ).all()
        return {
            "charges": [{"id": str(c.id), "month": f"{c.year}-{c.month:02d}", "currency": c.currency, "amount": None if c.amount is None else str(money(c.amount)),
                         "voided_by": c.voided_by, "voided_at": c.voided_at.isoformat(), "reason": c.void_reason} for c in charges],
            "salaries": [{"id": str(l.id), "employee": e.name, "month": f"{l.year}-{l.month:02d}", "currency": l.currency,
                          "voided_by": l.voided_by, "voided_at": l.voided_at.isoformat(), "reason": l.void_reason} for l, e in lines],
        }

    # ---- bookings -----------------------------------------------------------------------------------------------------
    @router.post("/bookings", status_code=201)
    def create_booking(payload: BookingIn, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        book.check_booking_fields(payload.kind, payload.category, payload.amount, payload.currency, payload.booked_on, local_today())
        booking_months_open(session, payload.booked_on)
        row = CashTransaction(
            currency=payload.currency, kind=payload.kind, amount=money(payload.amount), booked_on=payload.booked_on, date_basis="actual",
            category=payload.category, description=payload.description.strip(), counterparty=payload.counterparty.strip(),
            receipt_no=payload.receipt_no.strip(), origin="manual", created_by_id=actor.account_id, created_by=actor.name[:80],
        )
        session.add(row)
        session.flush()
        book.audit(session, actor, "booking.create", "booking", row.id, None, book.transaction_snapshot(row))
        book.count_live_write(session)
        session.commit()
        return one(session, row.id)

    def one(session: Session, booking_id: uuid.UUID) -> dict[str, Any]:
        row = session.get(CashTransaction, booking_id)
        rows = book.movements(session, row.currency, row.booked_on, row.booked_on, include_voided=True)
        return next(m.as_dict() for m in rows if m.source_id == str(booking_id))

    @router.patch("/bookings/{booking_id}")
    def update_booking(
        booking_id: uuid.UUID, payload: BookingUpdate, actor: FeesActor = Depends(guard), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        book.require_live(session)
        row = booking(session, booking_id)
        if row.origin != "manual":
            raise HTTPException(409, "الحركات المنقولة من الجداول القديمة وحركات التسوية لا تُعدَّل؛ ألغِها وسجّل حركة جديدة.")
        if row.voided_at is not None:
            raise HTTPException(409, "الحركة ملغاة.")
        check_version(row, payload.expected_version, f"{money(row.amount)} {row.currency}")
        sent = payload.model_fields_set
        before = book.transaction_snapshot(row)
        new_day = payload.booked_on if "booked_on" in sent and payload.booked_on is not None else row.booked_on
        new_category = payload.category if "category" in sent and payload.category is not None else row.category
        new_amount = payload.amount if "amount" in sent and payload.amount is not None else row.amount
        book.check_booking_fields(row.kind, new_category, new_amount, row.currency, new_day, local_today())
        booking_months_open(session, row.booked_on, new_day)
        row.amount, row.booked_on, row.category = money(new_amount), new_day, new_category
        if "description" in sent and payload.description is not None:
            row.description = payload.description.strip()
        if "counterparty" in sent and payload.counterparty is not None:
            row.counterparty = payload.counterparty.strip()
        if "receipt_no" in sent and payload.receipt_no is not None:
            row.receipt_no = payload.receipt_no.strip()
        touch(row, actor.name)
        book.audit(session, actor, "booking.update", "booking", row.id, before, book.transaction_snapshot(row))
        book.count_live_write(session)
        session.commit()
        return one(session, row.id)

    @router.post("/bookings/{booking_id}/void")
    def void_booking(booking_id: uuid.UUID, payload: VoidIn, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        row = booking(session, booking_id)
        if row.voided_at is not None:
            raise HTTPException(409, "الحركة ملغاة بالفعل.")
        if row.origin == "legacy_adjustment":
            raise HTTPException(409, "تسوية تاريخية لا تُلغى يدوياً؛ يلغيها النظام عند تسجيل الدفع الفعلي.")
        booking_months_open(session, row.booked_on)
        book.void_transaction(session, actor, row, clean_reason(payload.reason))
        book.count_live_write(session)
        session.commit()
        return one(session, row.id)

    # ---- receipts of bookings: never deleted, only taken out of view with a reason ------------------------------------------
    def receipt_view(item: EntryReceipt) -> dict[str, Any]:
        return {
            "id": str(item.id), "name": item.original_name, "size": item.byte_size, "type": item.media_type, "uploaded_by": item.uploaded_by,
            "created_at": item.created_at.isoformat() if item.created_at else "", "removed": item.removed_at is not None,
            "removed_by": item.removed_by, "remove_reason": item.remove_reason,
        }

    @router.get("/bookings/{booking_id}/receipts")
    def list_booking_receipts(booking_id: uuid.UUID, response: Response, _actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        row = session.get(CashTransaction, booking_id)
        if row is None:
            raise HTTPException(404, "الحركة غير موجودة.")
        owners = [EntryReceipt.transaction_id == row.id]
        if row.legacy_entry_id:
            owners.append(EntryReceipt.entry_id == row.legacy_entry_id)
        items = session.scalars(select(EntryReceipt).where(or_(*owners)).order_by(EntryReceipt.created_at)).all()
        return [receipt_view(item) for item in items]

    @router.post("/bookings/{booking_id}/receipts", status_code=201)
    async def add_booking_receipt(
        booking_id: uuid.UUID, file: UploadFile = File(...), actor: FeesActor = Depends(guard), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        book.require_live(session)
        row = booking(session, booking_id)
        if row.voided_at is not None:
            raise HTTPException(409, "الحركة ملغاة.")
        booking_months_open(session, row.booked_on)
        name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        extension = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
        known = RECEIPT_TYPES.get(extension)
        if not name or len(name) > 180 or known is None:
            raise HTTPException(422, "الملفات المقبولة للإيصالات: PDF أو صورة (JPG, PNG, WEBP).")
        contents = await file.read(MAX_RECEIPT_BYTES + 1)
        await file.close()
        if not contents:
            raise HTTPException(422, "الملف فارغ.")
        if len(contents) > MAX_RECEIPT_BYTES:
            raise HTTPException(413, "حجم الإيصال أكبر من 3 ميغابايت.")
        if not contents.startswith(known[0]):
            raise HTTPException(422, "محتوى الملف لا يطابق نوعه.")
        count = session.scalar(select(func.count()).select_from(EntryReceipt).where(EntryReceipt.transaction_id == row.id, EntryReceipt.removed_at.is_(None))) or 0
        if count >= MAX_RECEIPTS_PER_BOOKING:
            raise HTTPException(409, "الحد الأقصى 5 إيصالات للحركة الواحدة.")
        item = EntryReceipt(transaction_id=row.id, original_name=name, media_type=known[1], byte_size=len(contents), contents=contents, uploaded_by=actor.name[:80])
        session.add(item)
        session.flush()
        book.audit(session, actor, "receipt.add", "booking", row.id, None, {"receipt": name, "bytes": len(contents)})
        book.count_live_write(session)
        session.commit()
        session.refresh(item)
        return receipt_view(item)

    @router.get("/booking-receipts/{receipt_id}/download")
    def download_booking_receipt(receipt_id: uuid.UUID, _actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> Response:
        item = session.get(EntryReceipt, receipt_id)
        if item is None:
            raise HTTPException(404, "الإيصال غير موجود.")
        return Response(
            content=item.contents, media_type=item.media_type,
            headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(item.original_name, safe=""), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.post("/booking-receipts/{receipt_id}/remove")
    def remove_booking_receipt(receipt_id: uuid.UUID, payload: RemoveReceiptIn, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Takes a receipt out of view with a reason. The file itself stays stored."""
        book.require_live(session)
        item = session.get(EntryReceipt, receipt_id)
        if item is None:
            raise HTTPException(404, "الإيصال غير موجود.")
        if item.removed_at is not None:
            raise HTTPException(409, "الإيصال مُزال بالفعل.")
        owner_day = None
        if item.transaction_id is not None:
            owner = session.get(CashTransaction, item.transaction_id)
            owner_day = owner.booked_on if owner else None
        booking_months_open(session, owner_day)
        item.removed_at, item.removed_by, item.remove_reason = datetime.now(timezone.utc), actor.name[:80], clean_reason(payload.reason)
        book.audit(session, actor, "receipt.remove", "receipt", item.id, {"receipt": item.original_name, "removed": False}, {"removed": True}, item.remove_reason)
        book.count_live_write(session)
        session.commit()
        return receipt_view(item)

    # ---- cancelling fee payments, fee lines and salary lines ----------------------------------------------------------------
    @router.post("/finance/payments/{payment_id}/void")
    def void_payment(payment_id: uuid.UUID, payload: VoidIn, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        payment = session.scalar(select(FeePayment).where(FeePayment.id == payment_id).with_for_update())
        if payment is None:
            raise HTTPException(404, "الدفعة غير موجودة.")
        if payment.deleted_at is not None:
            raise HTTPException(409, "الدفعة ملغاة بالفعل.")
        charge = session.get(FeeCharge, payment.charge_id)
        ensure_open(session, month_of(payment.paid_on) or (charge.year, charge.month))
        before = {"amount": str(money(payment.amount)), "paid_on": payment.paid_on.isoformat() if payment.paid_on else None, "receipt_no": payment.receipt_no, "voided": False}
        payment.deleted_at, payment.voided_by, payment.void_reason = datetime.now(timezone.utc), actor.name[:80], clean_reason(payload.reason)
        book.audit(session, actor, "payment.void", "payment", payment.id, before, {**before, "voided": True}, payment.void_reason)
        book.count_live_write(session)
        session.commit()
        return {"id": str(payment.id), "voided": True, "reason": payment.void_reason}

    @router.post("/finance/charges/{charge_id}/void")
    def void_charge(charge_id: uuid.UUID, payload: VoidIn, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        charge = session.scalar(select(FeeCharge).where(FeeCharge.id == charge_id).with_for_update())
        if charge is None:
            raise HTTPException(404, "الرسم غير موجود.")
        if charge.voided_at is not None:
            raise HTTPException(409, "الرسم ملغى بالفعل.")
        ensure_open(session, (charge.year, charge.month))
        if any(p.deleted_at is None for p in charge.payments):
            raise HTTPException(409, "عليه دفعات فعّالة. ألغِ الدفعات أولاً.")
        before = {"amount": None if charge.amount is None else str(money(charge.amount)), "month": f"{charge.year}-{charge.month:02d}", "currency": charge.currency, "voided": False}
        charge.voided_at, charge.voided_by, charge.void_reason = datetime.now(timezone.utc), actor.name[:80], clean_reason(payload.reason)
        book.audit(session, actor, "charge.void", "charge", charge.id, before, {**before, "voided": True}, charge.void_reason)
        book.count_live_write(session)
        session.commit()
        return {"id": str(charge.id), "voided": True, "reason": charge.void_reason}

    @router.post("/finance/salaries/{line_id}/void")
    def void_salary(line_id: uuid.UUID, payload: VoidIn, actor: FeesActor = Depends(guard), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        line = session.scalar(select(SalaryLine).where(SalaryLine.id == line_id).with_for_update())
        if line is None:
            raise HTTPException(404, "سطر الراتب غير موجود.")
        if line.voided_at is not None:
            raise HTTPException(409, "سطر الراتب ملغى بالفعل.")
        ensure_open(session, (line.year, line.month), month_of(line.paid_on))
        reason = clean_reason(payload.reason)
        before = {"base": None if line.base is None else str(money(line.base)), "paid_on": line.paid_on.isoformat() if line.paid_on else None,
                  "month": f"{line.year}-{line.month:02d}", "currency": line.currency, "voided": False}
        line.voided_at, line.voided_by, line.void_reason = datetime.now(timezone.utc), actor.name[:80], reason
        adjustment = book.active_unpaid_adjustment(session, line.id)
        if adjustment is not None:  # the taken-over adjustment of this salary goes with it
            book.void_transaction(session, actor, adjustment, f"Gehaltszeile storniert: {reason}", automatic=True)
        book.audit(session, actor, "salary.void", "salary", line.id, before, {**before, "voided": True}, reason)
        book.count_live_write(session)
        session.commit()
        return {"id": str(line.id), "voided": True, "reason": reason}

    return router
