"""The three accounting pages: income (الإيرادات), expenses (المصروفات) and the month overview (الملخص الشهري).

Every booking lives in the cash book (cash_transactions). It keeps what was really handed over (currency and amount), the rate of its day
and the value in the other currency, so every row and every total shows US dollars and Syrian pounds side by side. A later rate never
changes an old booking. Nothing is deleted: a wrong booking is cancelled with a reason. The two columns are never merged into one number.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger as book
from app.database import get_session
from app.fees import CURRENCIES, ZERO, FeesActor, RateBook, check_version, ensure_open, money, month_of, rate_text, to_other, touch
from app.invoicing import other_of, rate_source_of, text
from app.ledger import CATEGORY_LABELS, Movement
from app.models import CashTransaction, Child, Employee, FeeCharge, FeePayment
from app.timeutil import local_today

INCOME_PAGE = ("fees", "registration", "donations", "other_income")
EXPENSE_PAGE = ("salaries", "rent", "food", "utilities", "operating", "activities", "material", "transport", "advertising", "other_expense")


def month_bounds(value: str | None, today: date) -> tuple[date, date, str]:
    if not value:
        value = f"{today.year}-{today.month:02d}"
    try:
        year, month = (int(part) for part in value.split("-"))
        first = date(year, month, 1)
    except ValueError as exc:
        raise HTTPException(422, "شهر غير صالح. استخدم الشكل 2026-10.") from exc
    return first, book.last_day(year, month), f"{year}-{month:02d}"


def previous_month(first: date) -> str:
    return f"{first.year - 1}-12" if first.month == 1 else f"{first.year}-{first.month - 1:02d}"


def editable_from(today: date) -> date:
    """Entries of the current and of the previous month may still be changed; older months only by cancelling with a reason."""
    year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return date(year, month, 1)


class EntryIn(BaseModel):
    kind: str = Field(pattern="^(income|expense)$")
    booked_on: date
    description: str = Field(min_length=2, max_length=500)
    category: str = Field(max_length=30)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern="^(USD|SYP)$")  # the currency that was really used
    counterparty: str = Field(default="", max_length=120)
    receipt_no: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=500)
    employee_id: uuid.UUID | None = None
    child_id: uuid.UUID | None = None


class EntryUpdate(BaseModel):
    reason: str = Field(min_length=5, max_length=300)
    expected_version: int | None = Field(default=None, ge=0, le=1_000_000_000)
    booked_on: date | None = None
    description: str | None = Field(default=None, min_length=2, max_length=500)
    category: str | None = Field(default=None, max_length=30)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, pattern="^(USD|SYP)$")
    counterparty: str | None = Field(default=None, max_length=120)
    receipt_no: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=500)
    employee_id: uuid.UUID | None = None
    child_id: uuid.UUID | None = None
    refresh_rate: bool = False  # only on request the rate is taken again (of the day of the booking)


class VoidIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


def values_of(m: Movement, rates: RateBook) -> dict[str, Any]:
    """One movement as the two columns USD and SYP, with the rate behind them (frozen, or reconstructed for old rows)."""
    other_value: Decimal | None = None
    rate: Decimal | None = None
    source = "none"
    if m.extra.get("rate") and m.extra.get("amount_other") is not None:
        rate, other_value, source = Decimal(m.extra["rate"]), Decimal(m.extra["amount_other"]), m.extra.get("rate_source") or "manual"
    else:
        found = rates.on(m.day)
        if found is not None:
            rate, source = found[0], "reconstructed"
            other_value = to_other(m.amount, m.currency, rate)
    cols = {m.currency: money(m.amount), other_of(m.currency): other_value}
    return {"usd": cols["USD"], "syp": cols["SYP"], "rate": rate, "rate_source": source}


def entry_dict(m: Movement, rates: RateBook, names: dict[str, str], can_write: bool, floor: date) -> dict[str, Any]:
    v = values_of(m, rates)
    label = CATEGORY_LABELS.get(m.category, {"ar": m.category, "de": m.category})
    editable = can_write and m.source == "booking" and m.editable and not m.voided and m.day >= floor
    return {
        "id": m.source_id, "source": m.source, "kind": m.kind, "day": m.day.isoformat(), "description": m.description, "category": m.category,
        "category_ar": label["ar"], "category_de": label["de"], "counterparty": m.counterparty, "receipt_no": m.receipt_no,
        "note": m.extra.get("note") or "", "paid_currency": m.currency, "paid_amount": text(m.currency, money(m.amount)),
        "usd": text("USD", v["usd"]), "syp": text("SYP", v["syp"]),
        "rate": None if v["rate"] is None else {"syp_per_usd": rate_text(v["rate"]), "source": v["rate_source"]},
        "voided": m.voided, "void_reason": m.void_reason, "editable": editable, "voidable": can_write and not m.voided and m.source in ("booking", "fee_payment"),
        "version": m.version, "employee": names.get(m.extra.get("employee_id") or "", ""), "employee_id": m.extra.get("employee_id") or "",
        "child": names.get(m.extra.get("child_id") or "", m.extra.get("child") or ""), "child_id": m.extra.get("child_id") or "",
        "historical": m.source in ("legacy", "legacy_adjustment"), "from_fees": m.source == "fee_payment", "from_salary": m.source == "salary_payment",
    }


def collect(session: Session, start: date, end: date, include_voided: bool = False) -> list[Movement]:
    rows: list[Movement] = []
    for code in CURRENCIES:
        rows += [m for m in book.movements(session, code, start, end, include_voided=include_voided) if m.counts_in_cash]
    rows.sort(key=lambda m: (m.day, m.created_at.isoformat() if m.created_at else "", m.source_id), reverse=True)
    return rows


def build_router(reader: Callable[..., FeesActor], writer: Callable[..., FeesActor], rate_setter: Callable[..., FeesActor]) -> APIRouter:
    """reader: management, admin and accountants with `books.view`. writer: management, admin and accountants with `books.write`."""
    router = APIRouter(prefix="/api/admin/books", tags=["books"])

    def names_of(session: Session, rows: list[Movement]) -> dict[str, str]:
        ids = {m.extra.get("employee_id") for m in rows} | {m.extra.get("child_id") for m in rows}
        ids.discard(None)
        names: dict[str, str] = {}
        if ids:
            wanted = [uuid.UUID(i) for i in ids]
            names.update({str(i): n for i, n in session.execute(select(Employee.id, Employee.name).where(Employee.id.in_(wanted)))})
            names.update({str(i): n for i, n in session.execute(select(Child.id, Child.display_name).where(Child.id.in_(wanted)))})
        return names

    def check_entry(kind: str, category: str, employee_id: uuid.UUID | None, child_id: uuid.UUID | None, session: Session) -> None:
        if category not in (INCOME_PAGE if kind == "income" else EXPENSE_PAGE):
            raise HTTPException(422, "التصنيف لا يناسب نوع الحركة.")
        if employee_id is not None:
            if kind != "expense" or category != "salaries":
                raise HTTPException(422, "الموظف يُربط بمصروف الرواتب فقط.")
            if session.get(Employee, employee_id) is None:
                raise HTTPException(404, "الموظف غير موجود.")
        if child_id is not None:
            if kind != "income":
                raise HTTPException(422, "الطفل يُربط بالإيرادات فقط.")
            child = session.get(Child, child_id)
            if child is None:
                raise HTTPException(404, "الطفل غير موجود.")

    def frozen(session: Session, day: date) -> tuple[RateBook, Decimal, date, str]:
        rates = RateBook.load(session)
        found = rates.on(day)
        if found is None:
            raise HTTPException(409, "لا يوجد سعر صرف. تحدّد الإدارة سعر الصرف أولاً (الملخص الشهري).")
        return rates, found[0], found[1], rate_source_of(rates, found[1])

    def snapshot(t: CashTransaction) -> dict[str, Any]:
        return {**book.transaction_snapshot(t), "amount_other": None if t.amount_other is None else str(money(t.amount_other)),
                "rate": None if t.rate_syp_per_usd is None else rate_text(Decimal(t.rate_syp_per_usd)), "note": t.note,
                "employee_id": str(t.employee_id) if t.employee_id else None, "child_id": str(t.child_id) if t.child_id else None}

    def one(session: Session, entry_id: uuid.UUID, actor: FeesActor) -> dict[str, Any]:
        row = session.get(CashTransaction, entry_id)
        rates = RateBook.load(session)
        rows = [m for m in book.movements(session, row.currency, row.booked_on, row.booked_on, include_voided=True) if m.source_id == str(entry_id)]
        return entry_dict(rows[0], rates, names_of(session, rows), True, editable_from(local_today()))

    @router.get("/status")
    def status(response: Response, actor: FeesActor = Depends(reader), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        found = RateBook.load(session).on(today)
        mode = book.ledger_mode(session)
        return {
            "mode": mode, "live": mode == "live", "role": actor.role, "today": today.isoformat(), "editable_from": editable_from(today).isoformat(),
            "rate": None if found is None else {"syp_per_usd": rate_text(found[0]), "date": found[1].isoformat()},
            "can_set_rate": actor.role in ("manager", "admin"),
            "can_write": actor.role in ("manager", "admin") or writer_allowed(session, actor),
            "categories": {
                "income": [{"key": k, "ar": CATEGORY_LABELS[k]["ar"], "de": CATEGORY_LABELS[k]["de"]} for k in INCOME_PAGE],
                "expense": [{"key": k, "ar": CATEGORY_LABELS[k]["ar"], "de": CATEGORY_LABELS[k]["de"]} for k in EXPENSE_PAGE],
            },
        }

    @router.get("/entries")
    def entries(
        response: Response, kind: str, month: str | None = None, date_from: date | None = None, date_to: date | None = None, category: str = "",
        actor: FeesActor = Depends(reader), session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        if kind not in ("income", "expense"):
            raise HTTPException(422, "اختر إيراداً أو مصروفاً.")
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        first, last, key = month_bounds(month, today)
        start, end = (date_from or first, date_to or last) if (date_from or date_to) else (first, last)
        rows = [m for m in collect(session, start, end, include_voided=True) if m.kind == kind and (not category or m.category == category)]
        rates = RateBook.load(session)
        can_write = actor.role in ("manager", "admin") or writer_allowed(session, actor)
        names = names_of(session, rows)
        data = [entry_dict(m, rates, names, can_write, editable_from(today)) for m in rows]
        live = [(values_of(m, rates), m) for m in rows if not m.voided]
        total_usd = sum((v["usd"] for v, _ in live if v["usd"] is not None), ZERO)
        total_syp = sum((v["syp"] for v, _ in live if v["syp"] is not None), ZERO)
        return {
            "month": key, "rows": data, "count": len(live), "missing_rate": sum(1 for v, _ in live if v["usd"] is None or v["syp"] is None),
            "total": {"usd": text("USD", total_usd), "syp": text("SYP", total_syp)}, "mode": book.ledger_mode(session), "can_write": can_write,
        }

    def writer_allowed(session: Session, actor: FeesActor) -> bool:
        from app.control import has_grant

        return has_grant(session, actor, "books.write")

    @router.post("/entries", status_code=201)
    def create_entry(payload: EntryIn, actor: FeesActor = Depends(writer), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        today = local_today()
        if payload.booked_on > today:
            raise HTTPException(422, "لا يمكن تسجيل حركة بتاريخ مستقبلي.")
        check_entry(payload.kind, payload.category, payload.employee_id, payload.child_id, session)
        ensure_open(session, month_of(payload.booked_on))
        _, rate, rate_day, source = frozen(session, payload.booked_on)
        row = CashTransaction(
            currency=payload.currency, kind=payload.kind, amount=money(payload.amount), booked_on=payload.booked_on, date_basis="actual",
            category=payload.category, description=payload.description.strip(), counterparty=payload.counterparty.strip(),
            receipt_no=payload.receipt_no.strip(), note=payload.note.strip(), origin="manual", created_by_id=actor.account_id, created_by=actor.name[:80],
            amount_other=to_other(payload.amount, payload.currency, rate), rate_syp_per_usd=rate, rate_date=rate_day, rate_source=source,
            employee_id=payload.employee_id, child_id=payload.child_id,
        )
        session.add(row)
        session.flush()
        book.audit(session, actor, "booking.create", "booking", row.id, None, snapshot(row))
        book.count_live_write(session)
        session.commit()
        return one(session, row.id, actor)

    @router.patch("/entries/{entry_id}")
    def update_entry(entry_id: uuid.UUID, payload: EntryUpdate, actor: FeesActor = Depends(writer), session: Session = Depends(get_session)) -> dict[str, Any]:
        book.require_live(session)
        row = session.scalar(select(CashTransaction).where(CashTransaction.id == entry_id).with_for_update())
        if row is None:
            raise HTTPException(404, "الحركة غير موجودة.")
        if row.origin != "manual":
            raise HTTPException(409, "هذه الحركة منقولة من النظام القديم ولا تُعدَّل. يمكن إلغاؤها بسبب.")
        if row.voided_at is not None:
            raise HTTPException(409, "الحركة ملغاة.")
        today = local_today()
        if row.booked_on < editable_from(today):
            raise HTTPException(423, "لا تُعدَّل إلا حركات الشهر الحالي والسابق. صحّح الأقدم بالإلغاء مع ذكر السبب.")
        check_version(row, payload.expected_version, f"{money(row.amount)} {row.currency}")
        sent = payload.model_fields_set
        before = snapshot(row)
        new_day = payload.booked_on if "booked_on" in sent and payload.booked_on is not None else row.booked_on
        if new_day > today:
            raise HTTPException(422, "لا يمكن تسجيل حركة بتاريخ مستقبلي.")
        if new_day < editable_from(today):
            raise HTTPException(423, "لا يمكن نقل الحركة إلى شهر أقدم من الشهر السابق.")
        category = payload.category if "category" in sent and payload.category is not None else row.category
        employee_id = payload.employee_id if "employee_id" in sent else row.employee_id
        child_id = payload.child_id if "child_id" in sent else row.child_id
        check_entry(row.kind, category, employee_id, child_id, session)
        ensure_open(session, month_of(row.booked_on), month_of(new_day))
        row.booked_on, row.category, row.employee_id, row.child_id = new_day, category, employee_id, child_id
        if "amount" in sent and payload.amount is not None:
            row.amount = money(payload.amount)
        if "currency" in sent and payload.currency is not None:
            row.currency = payload.currency
        for field in ("description", "counterparty", "receipt_no", "note"):
            if field in sent and getattr(payload, field) is not None:
                setattr(row, field, getattr(payload, field).strip())
        if payload.refresh_rate or row.rate_syp_per_usd is None:
            _, rate, rate_day, source = frozen(session, new_day)
            row.rate_syp_per_usd, row.rate_date, row.rate_source = rate, rate_day, source
        row.amount_other = to_other(row.amount, row.currency, Decimal(row.rate_syp_per_usd))  # the frozen rate stays; only the amount follows
        touch(row, actor.name)
        book.audit(session, actor, "booking.update", "booking", row.id, before, snapshot(row), payload.reason.strip())
        book.count_live_write(session)
        session.commit()
        return one(session, row.id, actor)

    @router.post("/entries/{entry_id}/void")
    def void_entry(entry_id: uuid.UUID, payload: VoidIn, actor: FeesActor = Depends(writer), session: Session = Depends(get_session)) -> dict[str, Any]:
        """Cancels a booking or a fee payment: it stays visible, crossed out, with the reason. Nothing is deleted."""
        book.require_live(session)
        row = session.scalar(select(CashTransaction).where(CashTransaction.id == entry_id).with_for_update())
        if row is not None:
            if row.voided_at is not None:
                raise HTTPException(409, "الحركة ملغاة بالفعل.")
            ensure_open(session, month_of(row.booked_on))
            book.void_transaction(session, actor, row, payload.reason)
        else:
            payment = session.scalar(select(FeePayment).where(FeePayment.id == entry_id).with_for_update())
            if payment is None:
                raise HTTPException(404, "الحركة غير موجودة.")
            if payment.deleted_at is not None:
                raise HTTPException(409, "الدفعة ملغاة بالفعل.")
            charge = session.get(FeeCharge, payment.charge_id)
            ensure_open(session, month_of(payment.paid_on) or (charge.year, charge.month))
            from datetime import datetime, timezone

            before = {"amount": str(money(payment.amount)), "paid_on": payment.paid_on.isoformat() if payment.paid_on else None, "voided": False}
            payment.deleted_at, payment.voided_by, payment.void_reason = datetime.now(timezone.utc), actor.name[:80], payload.reason.strip()
            book.audit(session, actor, "payment.void", "payment", payment.id, before, {**before, "voided": True}, payment.void_reason)
        book.count_live_write(session)
        session.commit()
        return {"id": str(entry_id), "voided": True, "reason": payload.reason.strip()}

    @router.get("/summary")
    def summary(response: Response, month: str | None = None, actor: FeesActor = Depends(reader), session: Session = Depends(get_session)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        first, last, key = month_bounds(month, today)
        rates = RateBook.load(session)

        def figures(start: date, end: date) -> dict[str, Any]:
            rows = [m for m in collect(session, start, end) if not m.voided]
            cols = {"income": {"usd": ZERO, "syp": ZERO, "count": 0}, "expense": {"usd": ZERO, "syp": ZERO, "count": 0}}
            real: dict[str, dict[str, Decimal]] = {code: {"income": ZERO, "expense": ZERO} for code in CURRENCIES}
            by_cat: dict[tuple[str, str], dict[str, Any]] = {}
            missing = 0
            for m in rows:
                v = values_of(m, rates)
                cols[m.kind]["count"] += 1
                real[m.currency][m.kind] += money(m.amount)
                cat = by_cat.setdefault((m.kind, m.category), {"usd": ZERO, "syp": ZERO, "count": 0})
                cat["count"] += 1
                if v["usd"] is None or v["syp"] is None:
                    missing += 1
                    continue
                cols[m.kind]["usd"] += v["usd"]
                cols[m.kind]["syp"] += v["syp"]
                cat["usd"] += v["usd"]
                cat["syp"] += v["syp"]
            return {"cols": cols, "real": real, "by_cat": by_cat, "missing": missing}

        now = figures(first, last)
        prev_first, prev_last, prev_key = month_bounds(previous_month(first), today)
        before = figures(prev_first, prev_last)

        def pair(f: dict[str, Any]) -> dict[str, Any]:
            c = f["cols"]
            return {
                "income": {"usd": c["income"]["usd"], "syp": c["income"]["syp"]},
                "expense": {"usd": c["expense"]["usd"], "syp": c["expense"]["syp"]},
                "surplus": {"usd": c["income"]["usd"] - c["expense"]["usd"], "syp": c["income"]["syp"] - c["expense"]["syp"]},
            }

        a, b = pair(now), pair(before)

        def out(p: dict[str, Any]) -> dict[str, Any]:
            return {k: {"usd": text("USD", v["usd"]), "syp": text("SYP", v["syp"])} for k, v in p.items()}

        def change(new: Decimal, old: Decimal) -> dict[str, Any]:
            return {"difference": str(money(new - old)), "percent": None if old == 0 else str(((new - old) / abs(old) * 100).quantize(Decimal("0.1")))}

        def categories(kind: str) -> list[dict[str, Any]]:
            rows = [
                {"category": cat, "category_ar": CATEGORY_LABELS.get(cat, {"ar": cat})["ar"], "category_de": CATEGORY_LABELS.get(cat, {"de": cat})["de"],
                 "usd": text("USD", d["usd"]), "syp": text("SYP", d["syp"]), "count": d["count"]}
                for (k, cat), d in now["by_cat"].items() if k == kind
            ]
            return sorted(rows, key=lambda r: -Decimal(r["usd"]))

        mode = book.ledger_mode(session)
        found = rates.on(today)
        return {
            "month": key, "previous_month": prev_key, "mode": mode,
            **out(a), "counts": {"income": now["cols"]["income"]["count"], "expense": now["cols"]["expense"]["count"]},
            "previous": out(b),
            "change": {k: {"usd": change(a[k]["usd"], b[k]["usd"]), "syp": change(a[k]["syp"], b[k]["syp"])} for k in a},
            "real_cash": {code: {"income": text(code, d["income"]), "expense": text(code, d["expense"])} for code, d in now["real"].items()},
            "income_by_category": categories("income"), "expense_by_category": categories("expense"),
            "missing_rate": now["missing"],
            "rate": None if found is None else {"syp_per_usd": rate_text(found[0]), "date": found[1].isoformat()},
        }

    return router
