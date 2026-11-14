"""The accounting as a guided workflow: the steps of a month in their working order, each with a status,
the weekly check, and the file that archives a month.

Nothing here changes data except writing one line in the log when an archive file is made. All numbers come from
the same tables as the sheets, so the screens, the exports and this list can never disagree.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import ledger as book
from app.accounting import AUTO_ITEMS, STANDARD_ITEMS, salary_row, sheet_range, todays_rate, unified_sheet, week_monday
from app.database import get_session
from app.timeutil import local_today
from app.fees import (
    CURRENCIES,
    ZERO,
    FeesActor,
    active_payments,
    charge_row,
    ensure_open,
    log,
    money,
    paid_amount,
    remaining_amount,
    status_of,
    workbook_response,
)
from app.models import (
    AccountingEntry,
    CashCount,
    CashOpening,
    Child,
    Employee,
    EntryReceipt,
    ExchangeRate,
    FeeAuditLog,
    FeeCharge,
    FeePayment,
    PeriodLock,
    SalaryLine,
    StepConfirmation,
)

# the steps in their working order (the keys are used by the screens)
STEPS = [
    "basics",       # 1 currencies, rates, categories, cash accounts
    "staff",        # 2 employees and the salaries they are owed
    "fees",         # 3 the fees of the children and what is still open
    "income",       # 4 money that came in
    "expenses",     # 5 money that went out, with receipts
    "payroll",      # 6 salaries actually paid
    "reconcile",    # 7 counting the cash box against the books
    "summary",      # 8 where the money stands
    "reports",      # 9 day, week, month and year reports
    "close",        # 10 lock the month
    "archive",      # 11 export and keep the closed month
]


# the steps a person can confirm as complete (the others follow from these, from the closing and from the export)
CONFIRMABLE = ("basics", "staff", "fees", "income", "expenses", "payroll", "reconcile")


def month_facts(session: Session, year: int, month: int) -> dict[str, Any]:
    """Everything the workflow needs to know about one month, counted from the tables."""
    first, last = sheet_range("month", year, month, None)

    children = session.scalar(select(func.count()).select_from(Child).where(Child.is_active.is_(True))) or 0
    charges = session.scalars(
        select(FeeCharge).where(FeeCharge.year == year, FeeCharge.month == month, FeeCharge.voided_at.is_(None)).options(selectinload(FeeCharge.payments))
    ).all()
    charged_children = {charge.child_id for charge in charges}
    open_charges = 0
    for charge in charges:
        remaining = remaining_amount(charge)
        if status_of(charge.amount, paid_amount(charge), charge.needs_review) in ("open", "partial") and remaining is not None and remaining > 0:
            open_charges += 1
    payments_in_month = sum(1 for charge in charges for payment in active_payments(charge) if payment.paid_on and first <= payment.paid_on <= last)

    employees = session.scalar(select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))) or 0
    salary_lines = session.scalars(select(SalaryLine).where(SalaryLine.year == year, SalaryLine.month == month, SalaryLine.voided_at.is_(None))).all()

    entry_filter = (
        ((AccountingEntry.period_type == "month") & (AccountingEntry.year == year) & (AccountingEntry.month == month))
        | ((AccountingEntry.period_type != "month") & (AccountingEntry.week_start >= first) & (AccountingEntry.week_start <= last))
    )
    entries = session.scalars(select(AccountingEntry).where(entry_filter)).all()
    with_receipt = {
        entry_id
        for (entry_id,) in session.execute(
            select(EntryReceipt.entry_id).where(EntryReceipt.entry_id.in_([e.id for e in entries] or [None])).distinct()
        ).all()
    }
    expense_rows = [e for e in entries if money(e.expense) > 0 and e.item_key not in AUTO_ITEMS]
    missing_receipts = [e for e in expense_rows if e.id not in with_receipt and not e.receipt_no.strip()]
    if book.is_live(session):  # once the cash book is live, the expenses to check are its bookings
        expense_rows = [m for code in CURRENCIES for m in book.movements(session, code, first, last) if m.kind == "expense" and m.source in ("booking", "legacy")]
        missing_receipts = [m for m in expense_rows if m.needs_receipt]

    counts = session.scalars(
        select(CashCount).where(CashCount.counted_on >= first, CashCount.counted_on <= last).order_by(CashCount.counted_on, CashCount.created_at)
    ).all()
    latest_count: dict[str, CashCount] = {}
    for count in counts:
        latest_count[count.currency] = count
    cash_differences = [c for c in latest_count.values() if money(c.difference) != 0]

    lock = session.scalar(select(PeriodLock).where(PeriodLock.year == year, PeriodLock.month == month))
    exported = bool(
        session.scalar(select(func.count()).select_from(FeeAuditLog).where(FeeAuditLog.action == "export.month", FeeAuditLog.entity_id == f"{month}/{year}"))
    )
    openings = {row.currency for row in session.scalars(select(CashOpening)).all()}
    rates = session.scalar(select(func.count()).select_from(ExchangeRate)) or 0
    if local_today() <= last or not rates:
        # the system knows today's rate by itself: it asks the online feed when nothing is stored for today (at most every few minutes)
        try:
            if todays_rate(session, local_today()) is not None:
                rates = max(rates, 1)
        except Exception:  # the status list must work even when the feed or the table is not reachable
            session.rollback()
    confirmed = {
        row.step: {"by": row.confirmed_by, "at": row.confirmed_at.isoformat() if row.confirmed_at else "", "note": row.note}
        for row in session.scalars(select(StepConfirmation).where(StepConfirmation.year == year, StepConfirmation.month == month)).all()
    }
    return {
        "confirmed": confirmed,
        "first": first, "last": last, "children": children, "charged_children": len(charged_children), "charges": len(charges),
        "open_charges": open_charges, "review_fees": sum(1 for c in charges if c.needs_review), "payments_in_month": payments_in_month,
        "employees": employees, "salaries": len(salary_lines), "salaries_paid": sum(1 for line in salary_lines if line.paid_on),
        "review_salaries": sum(1 for line in salary_lines if line.needs_review),
        "expense_rows": len(expense_rows), "missing_receipts": len(missing_receipts),
        "counts": len(counts), "cash_differences": len(cash_differences),
        "locked": lock is not None, "exported": exported, "openings": openings, "rates": rates,
        "ended": last < local_today(),
    }


def close_check(facts: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """What stops a month from being closed (blockers) and what should be looked at first (warnings)."""
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not facts["ended"]:
        blockers.append({"kind": "not_ended", "count": 1})
    if facts["review_fees"]:
        blockers.append({"kind": "review_fees", "count": facts["review_fees"]})
    if facts["review_salaries"]:
        blockers.append({"kind": "review_salaries", "count": facts["review_salaries"]})
    if facts["missing_receipts"]:
        warnings.append({"kind": "missing_receipts", "count": facts["missing_receipts"]})
    if facts["salaries"] - facts["salaries_paid"] > 0:
        warnings.append({"kind": "unpaid_salaries", "count": facts["salaries"] - facts["salaries_paid"]})
    if not facts["counts"]:
        warnings.append({"kind": "no_cash_count", "count": 1})
    if facts["cash_differences"]:
        warnings.append({"kind": "cash_difference", "count": facts["cash_differences"]})
    return {"blockers": blockers, "warnings": warnings}


def close_blockers(session: Session, year: int, month: int) -> list[dict[str, Any]]:
    return close_check(month_facts(session, year, month))["blockers"]


def build_steps(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Status of every step: pending (not started), in_progress, done. Issues are things that need a look."""
    f = facts
    steps: dict[str, dict[str, Any]] = {}

    def put(key: str, status: str, done: int | None = None, total: int | None = None, issues: list[dict[str, Any]] | None = None) -> None:
        steps[key] = {"key": key, "status": status, "done": done, "total": total, "issues": [i for i in (issues or []) if i["count"]]}

    ready = ("SYP" in f["openings"]) + (f["rates"] > 0)
    put("basics", "done" if ready == 2 else "in_progress" if ready else "pending", ready, 2)

    if not f["employees"]:
        put("staff", "pending", 0, 0)
    elif not f["salaries"]:
        put("staff", "in_progress", 0, f["employees"])
    else:
        put("staff", "done", f["salaries"], f["employees"], [{"kind": "review_salaries", "count": f["review_salaries"]}])
        if f["review_salaries"]:
            steps["staff"]["status"] = "in_progress"

    if not f["children"]:
        put("fees", "pending", 0, 0)
    else:
        status = "done" if f["charged_children"] >= f["children"] else "in_progress" if f["charged_children"] else "pending"
        put("fees", status, f["charged_children"], f["children"], [{"kind": "review_fees", "count": f["review_fees"]}])
        if f["review_fees"] and status == "done":
            steps["fees"]["status"] = "in_progress"

    if not f["charges"]:
        put("income", "pending", 0, 0)
    elif f["open_charges"] == 0:
        put("income", "done", f["charges"], f["charges"])
    else:
        put("income", "in_progress" if f["payments_in_month"] else "pending", f["charges"] - f["open_charges"], f["charges"], [{"kind": "open_fees", "count": f["open_charges"]}])

    if not f["expense_rows"]:
        put("expenses", "pending", 0, 0)
    else:
        put("expenses", "in_progress" if f["missing_receipts"] else "done", f["expense_rows"] - f["missing_receipts"], f["expense_rows"],
            [{"kind": "missing_receipts", "count": f["missing_receipts"]}])

    if not f["salaries"]:
        put("payroll", "pending", 0, 0)
    else:
        put("payroll", "done" if f["salaries_paid"] == f["salaries"] else "in_progress" if f["salaries_paid"] else "pending", f["salaries_paid"], f["salaries"])

    if not f["counts"]:
        put("reconcile", "pending", 0, 1, [{"kind": "no_cash_count", "count": 0}])
    else:
        put("reconcile", "in_progress" if f["cash_differences"] else "done", 1, 1, [{"kind": "cash_difference", "count": f["cash_differences"]}])

    for key, who in f["confirmed"].items():  # a person said on purpose that this step is complete; the open points stay listed
        if key in steps:
            steps[key]["confirmed"] = who
            steps[key]["status"] = "done"
    core = ["fees", "income", "expenses", "payroll", "reconcile"]
    finished = [steps[k]["status"] == "done" for k in core]
    put("summary", "done" if all(finished) else "in_progress" if any(finished) else "pending")
    if f["locked"]:
        put("reports", "done")
    else:
        put("reports", "in_progress" if steps["summary"]["status"] == "done" else "pending")
    check = close_check(f)
    if f["locked"]:
        put("close", "done")
    elif steps["summary"]["status"] == "done" and not check["blockers"]:
        put("close", "in_progress")
    else:
        put("close", "pending", issues=[{"kind": b["kind"], "count": b["count"]} for b in check["blockers"]])
    put("archive", "done" if f["locked"] and f["exported"] else "in_progress" if f["locked"] else "pending")
    return [steps[key] | {"n": number} for number, key in enumerate(STEPS, start=1)]


class StepConfirmIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    step: str = Field(max_length=20)
    note: str = Field(default="", max_length=500)


def build_router(guard: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/admin/accounting", tags=["accounting-workflow"])

    @router.get("/workflow")
    def workflow(
        response: Response,
        year: int | None = None,
        month: int | None = None,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        today = local_today()
        year, month = year or today.year, month or today.month
        if not 1 <= month <= 12 or not 2000 <= year <= 2100:
            raise HTTPException(422, "الشهر أو السنة غير صالحة.")
        facts = month_facts(session, year, month)
        steps = build_steps(facts)
        upcoming = next((step["key"] for step in steps if step["status"] != "done"), None)
        return {
            "year": year, "month": month, "locked": facts["locked"], "ended": facts["ended"], "steps": steps, "next": upcoming,
            "close": close_check(facts),
        }

    @router.post("/workflow/confirm")
    def confirm_step(
        payload: StepConfirmIn,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """Says on purpose that a step of a month is complete (for example: there were no expenses). Changes nothing else."""
        if payload.step not in CONFIRMABLE:
            raise HTTPException(422, "هذه الخطوة تكتمل تلقائياً ولا تُؤكَّد يدوياً.")
        ensure_open(session, (payload.year, payload.month))
        row = session.scalar(select(StepConfirmation).where(StepConfirmation.year == payload.year, StepConfirmation.month == payload.month, StepConfirmation.step == payload.step))
        if row is None:
            row = StepConfirmation(year=payload.year, month=payload.month, step=payload.step)
            session.add(row)
        row.confirmed_by = actor.name[:80]
        row.note = payload.note.strip()
        row.confirmed_at = datetime.now(timezone.utc)
        log(session, actor, "step.confirm", f"{payload.month}/{payload.year}", f"{payload.step} {payload.note.strip()[:200]}")
        session.commit()
        return {"ok": True}

    @router.delete("/workflow/confirm", status_code=204)
    def unconfirm_step(
        year: int,
        month: int,
        step: str,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> Response:
        ensure_open(session, (year, month))
        row = session.scalar(select(StepConfirmation).where(StepConfirmation.year == year, StepConfirmation.month == month, StepConfirmation.step == step))
        if row is None:
            raise HTTPException(404, "لا يوجد تأكيد لهذه الخطوة.")
        log(session, actor, "step.unconfirm", f"{month}/{year}", step)
        session.delete(row)
        session.commit()
        return Response(status_code=204)

    @router.get("/history")
    def history(
        response: Response,
        kind: str,
        id: uuid.UUID,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> list[dict[str, str]]:
        """Everything that was done to one row (a sheet row, a salary line or a fee line with its payments), newest first.
        Everyone who works on the accounting sees every step of the row (who did what), so two people on one row understand each other."""
        response.headers["Cache-Control"] = "no-store"
        if kind not in ("entry", "salary", "charge"):
            raise HTTPException(422, "نوع غير معروف.")
        ids = [str(id)]
        if kind == "charge":
            ids += [str(payment_id) for payment_id in session.scalars(select(FeePayment.id).where(FeePayment.charge_id == id)).all()]
        query = select(FeeAuditLog).where(FeeAuditLog.entity_id.in_(ids)).order_by(FeeAuditLog.at.desc()).limit(100)
        return [
            {"at": row.at.isoformat() if row.at else "", "actor": row.actor_name, "action": row.action, "details": row.details}
            for row in session.scalars(query).all()
        ]

    @router.get("/week-check")
    def week_check(
        response: Response,
        week_start: date,
        _actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> dict[str, Any]:
        """The week at a glance (no locking): money in and out, payments, receipts still missing, cash counts."""
        response.headers["Cache-Control"] = "no-store"
        monday = week_monday(week_start)
        sunday = monday + timedelta(days=6)
        sheet = unified_sheet(session, "week", monday.year, 0, monday)
        paid: dict[str, dict[str, Any]] = {code: {"count": 0, "amount": ZERO} for code in CURRENCIES}
        rows = session.execute(
            select(FeePayment, FeeCharge).join(FeeCharge, FeeCharge.id == FeePayment.charge_id).where(
                FeePayment.deleted_at.is_(None), FeePayment.paid_on >= monday, FeePayment.paid_on <= sunday
            )
        ).all()
        for payment, charge in rows:
            paid[charge.currency]["count"] += 1
            paid[charge.currency]["amount"] += money(payment.amount)
        entries = session.scalars(
            select(AccountingEntry).where(AccountingEntry.period_type != "month", AccountingEntry.week_start >= monday, AccountingEntry.week_start <= sunday)
        ).all()
        with_receipt = {
            entry_id
            for (entry_id,) in session.execute(select(EntryReceipt.entry_id).where(EntryReceipt.entry_id.in_([e.id for e in entries] or [None])).distinct()).all()
        }
        missing = sum(1 for e in entries if money(e.expense) > 0 and e.item_key not in AUTO_ITEMS and e.id not in with_receipt and not e.receipt_no.strip())
        counts = session.scalars(select(CashCount).where(CashCount.counted_on >= monday, CashCount.counted_on <= sunday).order_by(CashCount.counted_on)).all()
        checks = [
            {"kind": "entries", "ok": bool(entries), "count": len(entries)},
            {"kind": "missing_receipts", "ok": missing == 0, "count": missing},
            {"kind": "cash_count", "ok": bool(counts), "count": len(counts)},
            {"kind": "cash_difference", "ok": all(money(c.difference) == 0 for c in counts), "count": sum(1 for c in counts if money(c.difference) != 0)},
        ]
        return {
            "week_start": monday.isoformat(), "week_end": sunday.isoformat(),
            "totals": sheet["totals"], "balance": sheet.get("balance"),
            "payments": {code: {"count": value["count"], "amount": str(money(value["amount"]))} for code, value in paid.items()},
            "cash_counts": [
                {"currency": c.currency, "counted_on": c.counted_on.isoformat(), "counted": str(money(c.counted_amount)), "book": str(money(c.book_amount)), "difference": str(money(c.difference))}
                for c in counts
            ],
            "checks": checks,
        }

    @router.get("/periods/{year}/{month}/export.xlsx")
    def export_month(
        year: int,
        month: int,
        actor: FeesActor = Depends(guard),
        session: Session = Depends(get_session),
    ) -> Response:
        """The archive file of a month: totals, fees, salaries, sheet rows with receipts, cash counts. Every export is logged."""
        if not 1 <= month <= 12 or not 2000 <= year <= 2100:
            raise HTTPException(422, "الشهر أو السنة غير صالحة.")
        first, last = sheet_range("month", year, month, None)
        lock = session.scalar(select(PeriodLock).where(PeriodLock.year == year, PeriodLock.month == month))
        try:
            snapshot = json.loads(lock.snapshot) if lock and lock.snapshot else {}
        except ValueError:
            snapshot = {}

        summary: list[list[Any]] = [
            ["Month", f"{month}/{year}"],
            ["Status", "closed" if lock else "open (provisional)"],
            ["Closed by", lock.closed_by if lock else ""],
            ["Closed at", lock.closed_at.strftime("%Y-%m-%d %H:%M") if lock and lock.closed_at else ""],
            ["Note", lock.note if lock else ""],
            ["Exported by", actor.name],
        ]
        live = book.is_live(session)
        for code in CURRENCIES:
            totals = book.month_totals(session, code, year, month) if live else unified_sheet(session, "month", year, month, None)["totals"][code]
            summary.append([f"{code} income now", totals["income"]])
            summary.append([f"{code} expense now", totals["expense"]])
            if code in snapshot:
                summary.append([f"{code} income at closing", snapshot[code].get("income", "")])
                summary.append([f"{code} expense at closing", snapshot[code].get("expense", "")])

        fee_rows = []
        for charge, child in session.execute(
            select(FeeCharge, Child).join(Child, Child.id == FeeCharge.child_id).where(FeeCharge.year == year, FeeCharge.month == month, FeeCharge.voided_at.is_(None)).options(selectinload(FeeCharge.payments))
        ).all():
            r = charge_row(charge, child)
            fee_rows.append([r["child_name"], r["class_name"], r["currency"], r["amount"] or "", r["paid"], r["remaining"] or "", r["status"], r["last_paid_on"] or "", " ".join(r["receipts"])])
        fee_rows.sort(key=lambda row: (row[1], row[0]))

        salary_rows = [
            [r["employee_name"], r["job_title"], r["currency"], r["base"] or "", r["bonus"] or "", r["advance"] or "", r["deduction"] or "", r["net"] or "", r["paid_on"] or "", r["paid_by"]]
            for r in (salary_row(line) for line in session.scalars(select(SalaryLine).where(SalaryLine.year == year, SalaryLine.month == month, SalaryLine.voided_at.is_(None))).unique().all())
        ]
        salary_rows.sort(key=lambda row: row[0])

        # the rows exactly as they were typed (day, week or month level), each with the number of receipt files kept for it
        stored = session.scalars(
            select(AccountingEntry).where(
                ((AccountingEntry.period_type == "month") & (AccountingEntry.year == year) & (AccountingEntry.month == month))
                | ((AccountingEntry.period_type != "month") & (AccountingEntry.week_start >= first) & (AccountingEntry.week_start <= last))
            ).order_by(AccountingEntry.period_type, AccountingEntry.week_start, AccountingEntry.item_key)
        ).all()
        receipt_counts = {
            entry_id: number
            for entry_id, number in session.execute(
                select(EntryReceipt.entry_id, func.count()).where(EntryReceipt.entry_id.in_([e.id for e in stored] or [None])).group_by(EntryReceipt.entry_id)
            ).all()
        }
        labels = {key: label for key, label, _kind in STANDARD_ITEMS}
        sheet_rows = [
            [e.period_type, e.week_start.isoformat() if e.week_start else "", labels.get(e.item_key) or e.item_label, e.currency, e.details, e.note, e.person,
             str(money(e.income)), str(money(e.expense)), receipt_counts.get(e.id, 0), e.receipt_no]
            for e in stored
        ]
        counts = session.scalars(select(CashCount).where(CashCount.counted_on >= first, CashCount.counted_on <= last).order_by(CashCount.counted_on)).all()
        count_rows = [[c.counted_on.isoformat(), c.currency, str(money(c.counted_amount)), str(money(c.book_amount)), str(money(c.difference)), c.counted_by, c.note] for c in counts]

        log(session, actor, "export.month", f"{month}/{year}", "closed" if lock else "open")
        session.commit()
        book_rows = [
            [m.day.isoformat(), m.currency, "income" if m.kind == "income" else "expense", str(money(m.amount)), m.category, m.description, m.counterparty, m.source,
             m.date_basis, "yes" if m.counts_in_cash else "no (historical adjustment)", m.receipt_no, m.receipts, m.actor]
            for code in CURRENCIES for m in book.movements(session, code, first, last, include_voided=False)
        ] if live else []
        sheets = [
                ("Summary", ["Item", "Value"], summary),
                ("Fees", ["Child", "Class", "Currency", "Amount", "Paid", "Remaining", "Status", "Last payment", "Receipts"], fee_rows),
                ("Salaries", ["Employee", "Job", "Currency", "Base", "Bonus", "Advance", "Deduction", "Net", "Paid on", "Paid by"], salary_rows),
                ("Entries", ["Level", "Date", "Item", "Currency", "Details", "Note", "Person", "Income", "Expense", "Receipt files", "Receipt no."], sheet_rows),
                ("Cash counts", ["Date", "Currency", "Counted", "Books", "Difference", "By", "Note"], count_rows),
        ]
        if live:
            sheets.insert(1, ("Cash book", ["Date", "Currency", "Kind", "Amount", "Category", "Description", "Counterparty", "Source", "Date basis", "In cash", "Receipt no.", "Receipt files", "By"], book_rows))
        return workbook_response(f"accounting-{year}-{month:02d}.xlsx", sheets)

    return router
