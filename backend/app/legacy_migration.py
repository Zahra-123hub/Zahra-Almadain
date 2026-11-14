"""Taking the old day / week / month sheets over into the cash book, and proving that nothing changed.

The old sheets are never touched. Every sheet row that counted in the old books becomes one historical collective booking
(origin "legacy", date: last day of the month / the middle day of the week / the stored day). Rows that did not count (older
duplicates, rows covered by a higher sheet, automatic rows) stay in the archive only. Two kinds of historical adjustments keep the
old figures explainable: a hand-typed month value for an automatic item (fees, salaries), and a salary without a payment date in a
month that is over (it moved no money, so it never counts in the cash balance).

Before anything is written, the new calculation is compared with the old one for every currency and every month. A difference that
cannot be explained stops everything and nothing is written."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import ledger as book
from app.accounting import AUTO_ITEMS, CHOICE_ITEMS, STANDARD_ITEMS, Ledger, legacy_cash_report
from app.fees import CURRENCIES, ZERO, FeesActor, money
from app.models import (
    AccountingEntry, CashCount, CashOpening, CashTransaction, Child, Employee, EntryReceipt, ExchangeRate, FeeCharge, FeePayment,
    LedgerCutover, PeriodLock, SalaryLine,
)

ITEM_LABELS = {key: label for key, label, _kind in STANDARD_ITEMS}
EXPENSE_CATEGORY = {
    "operating": "operating", "activities": "activities", "purchases": "material", "buffet": "food",
    "transport": "transport", "advertising": "advertising", "misc": "other_expense",
}
KIND_NOTE = {"month": "Monatsblatt", "week": "Wochenblatt", "day": "Tagesblatt"}


class MigrationAborted(Exception):
    """A difference that cannot be explained: nothing is written."""

    def __init__(self, message: str, report: dict[str, Any] | None = None):
        super().__init__(message)
        self.report = report or {}


@dataclass
class Planned:
    currency: str
    kind: str
    amount: Decimal
    day: date
    basis: str
    category: str
    description: str
    origin: str
    counterparty: str = ""
    receipt_no: str = ""
    created_by: str = ""
    legacy_entry_id: Any = None
    legacy_note: str = ""
    adjustment_kind: str = ""
    counts_in_cash: bool = True
    salary_line_id: Any = None
    adjusts_period: str = ""

    def as_row(self) -> CashTransaction:
        return CashTransaction(
            currency=self.currency, kind=self.kind, amount=self.amount, booked_on=self.day, date_basis=self.basis, category=self.category,
            description=self.description[:500], counterparty=self.counterparty[:120], receipt_no=self.receipt_no[:60], origin=self.origin,
            adjustment_kind=self.adjustment_kind, counts_in_cash=self.counts_in_cash, legacy_entry_id=self.legacy_entry_id,
            legacy_note=self.legacy_note[:200], adjusts_salary_line_id=self.salary_line_id, adjusts_period=self.adjusts_period,
            created_by=self.created_by[:80] or "Übernahme", updated_by="", version=1,
        )

    def as_movement(self) -> book.Movement:
        source = self.origin if self.origin in ("legacy", "legacy_adjustment") else "booking"
        return book.Movement(
            day=self.day, currency=self.currency, kind=self.kind, amount=self.amount, category=self.category, description=self.description,
            source=source, source_id="planned", date_basis=self.basis, counts_in_cash=self.counts_in_cash, adjustment_kind=self.adjustment_kind,
        )


@dataclass
class Plan:
    today: date
    planned: list[Planned] = field(default_factory=list)
    counted_entries: dict[str, int] = field(default_factory=dict)
    not_counted: list[dict[str, Any]] = field(default_factory=list)
    classified: dict[str, int] = field(default_factory=dict)  # counted / superseded / automatic / ignored


def _mid(week_start: date) -> date:
    return week_start + timedelta(days=3)


def _category(item_key: str, kind: str) -> str:
    if kind == "income":
        return "other_income"
    return EXPENSE_CATEGORY.get(item_key, "other_expense")


def _text(entry: AccountingEntry) -> str:
    label = (entry.item_label or ITEM_LABELS.get(entry.item_key, entry.item_key)).strip()
    parts = [label, (entry.details or "").strip(), (entry.note or "").strip()]
    return " · ".join(p for p in parts if p)


def _note(entry: AccountingEntry, where: str) -> str:
    label = (entry.item_label or ITEM_LABELS.get(entry.item_key, entry.item_key)).strip()
    return f"{KIND_NOTE[entry.period_type]} {where}: {label}"


# ---- the plan ------------------------------------------------------------------------------------------------------------------
def build_plan(session: Session, today: date) -> Plan:
    plan = Plan(today=today)
    plan.classified = {"counted": 0, "superseded": 0, "automatic": 0, "ignored": 0}
    for currency in CURRENCIES:
        old = Ledger.load(session, currency)
        entries = list(session.scalars(select(AccountingEntry).where(AccountingEntry.currency == currency)))
        weeks_with = {key: [ws for ws, items in old.week_items.items() if key in items] for key, _l, _k in STANDARD_ITEMS}

        def newest(entry: AccountingEntry) -> bool:
            if entry.item_key == "custom":
                return True
            if entry.period_type == "month":
                return old.month_items.get((entry.year, entry.month), {}).get(entry.item_key) is entry
            if entry.period_type == "week":
                return old.week_items.get(entry.week_start, {}).get(entry.item_key) is entry
            return old.day_items.get(entry.week_start, {}).get(entry.item_key) is entry

        for entry in entries:
            key = entry.item_key
            income, expense = money(entry.income), money(entry.expense)
            reason = ""
            counted = False
            day: date | None = None
            basis = "actual"
            where = ""
            if entry.period_type == "month":
                day, basis, where = book.last_day(entry.year, entry.month), "legacy_month_end", f"{entry.month:02d}/{entry.year}"
                if key == "custom":
                    counted = True
                elif key in AUTO_ITEMS:
                    reason = "automatic" if not (newest(entry) and entry.manual) else "manual_override"
                elif newest(entry):
                    counted = True
                else:
                    reason = "superseded: an older duplicate of the same item"
            elif entry.period_type in ("week", "day") and entry.week_start is not None:
                if entry.period_type == "week":
                    mid = _mid(entry.week_start)
                    day, basis, where = mid, "legacy_week_mid", f"ab {entry.week_start.isoformat()}"
                    target = (mid.year, mid.month)
                else:
                    day, basis, where = entry.week_start, "actual", entry.week_start.isoformat()
                    target = (day.year, day.month)
                if key == "custom":
                    counted = True
                elif key in AUTO_ITEMS:
                    reason = "automatic"
                elif not newest(entry):
                    reason = "superseded: an older duplicate of the same item"
                elif old.month_items.get(target, {}).get(key) is not None:
                    reason = "covered by the month row of the same item"
                elif entry.period_type == "day" and any(ws <= day <= ws + timedelta(days=6) for ws in weeks_with.get(key, [])):
                    reason = "covered by a week row of the same item"
                else:
                    counted = True
            else:
                plan.classified["ignored"] += 1
                plan.not_counted.append({"entry": str(entry.id), "reason": "no valid period"})
                continue

            if reason == "manual_override":
                plan.classified["automatic"] += 1  # handled below as a historical adjustment
                continue
            if not counted:
                plan.classified["superseded" if reason.startswith("superseded") or reason.startswith("covered") else "automatic"] += 1
                plan.not_counted.append({"entry": str(entry.id), "currency": currency, "period": entry.period_type, "item": key,
                                         "income": str(income), "expense": str(expense), "reason": reason})
                continue
            plan.classified["counted"] += 1
            for amount, kind in ((income, "income"), (expense, "expense")):
                if amount <= 0:
                    continue
                plan.planned.append(Planned(
                    currency=currency, kind=kind, amount=amount, day=day, basis=basis, category=_category(key, kind),
                    description=_text(entry), origin="legacy", counterparty=entry.person or "", receipt_no=entry.receipt_no or "",
                    created_by=entry.entered_by or "", legacy_entry_id=entry.id, legacy_note=_note(entry, where),
                ))

        # salaries nobody has paid out yet, in months that are over: historical adjustments, never real money
        current = (today.year, today.month)
        for line, employee in session.execute(
            select(SalaryLine, Employee).join(Employee, Employee.id == SalaryLine.employee_id)
            .where(SalaryLine.currency == currency, SalaryLine.paid_on.is_(None), SalaryLine.voided_at.is_(None))
        ).all():
            net = book.net_pay(line.base, line.bonus, line.advance, line.deduction)
            if net is None or net == 0 or (line.year, line.month) >= current:
                continue
            plan.planned.append(Planned(
                currency=currency, kind="expense", amount=net, day=book.last_day(line.year, line.month), basis="legacy_month_end",
                category="salaries", origin="legacy_adjustment", adjustment_kind="salary_unpaid", counts_in_cash=False,
                description=f"Historische Ausgleichsbuchung (keine Auszahlung): Gehalt {employee.name} {line.month:02d}/{line.year} ohne Auszahlungsdatum",
                counterparty=employee.name, salary_line_id=line.id, adjusts_period=f"{line.year}-{line.month:02d} salaries",
                legacy_note="Gehalt ohne Auszahlungsdatum in einem abgeschlossenen Monat",
            ))

        # a month value typed by hand over an automatic item: the difference to what the real payments show
        base_rows = book.movements(session, currency) + [p.as_movement() for p in plan.planned if p.currency == currency]
        for (year, month), items in old.month_items.items():
            for key in AUTO_ITEMS:
                entry = items.get(key)
                if entry is None or not entry.manual:
                    continue
                first, last = date(year, month, 1), book.last_day(year, month)
                in_month = [m for m in base_rows if first <= m.day <= last]
                if key == "registration":
                    auto_income = sum((m.amount for m in in_month if m.category == "fees" and m.kind == "income"), ZERO)
                    auto_expense = ZERO
                else:
                    auto_income = ZERO
                    auto_expense = sum((m.amount for m in in_month if m.category == "salaries" and m.kind == "expense"), ZERO)
                category = "fees" if key == "registration" else "salaries"
                for kind, delta in (("income", money(entry.income) - auto_income), ("expense", money(entry.expense) - auto_expense)):
                    if delta == 0:
                        continue
                    plan.planned.append(Planned(
                        currency=currency, kind=kind, amount=money(delta), day=last, basis="legacy_month_end", category=category,
                        description=f"Historische Ausgleichsbuchung: Monatswert von Hand statt Einzelposten ({ITEM_LABELS[key]})",
                        origin="legacy_adjustment", adjustment_kind="manual_override", counts_in_cash=True, legacy_entry_id=None,
                        adjusts_period=f"{year}-{month:02d} {key}", created_by=entry.entered_by or "",
                        legacy_note=f"Monatsblatt {month:02d}/{year}: Wert von Hand überschrieben",
                    ))
    return plan


# ---- proof ---------------------------------------------------------------------------------------------------------------------------
def unpaid_current_months(session: Session, currency: str, today: date, manual_months: set[tuple[int, int]]) -> dict[tuple[int, int], Decimal]:
    """Unpaid salaries of the running and later months: the old sheet counted them, the new rule does not (that difference is explained)."""
    found: dict[tuple[int, int], Decimal] = {}
    current = (today.year, today.month)
    for line in session.scalars(select(SalaryLine).where(SalaryLine.currency == currency, SalaryLine.paid_on.is_(None), SalaryLine.voided_at.is_(None))):
        net = book.net_pay(line.base, line.bonus, line.advance, line.deduction)
        key = (line.year, line.month)
        if net is None or key < current or key in manual_months:
            continue
        found[key] = found.get(key, ZERO) + net
    return found


def parity(session: Session, plan: Plan | None, today: date) -> dict[str, Any]:
    """Old and new books, month by month and currency by currency. `plan` None: the planned rows are already stored."""
    report: dict[str, Any] = {"today": today.isoformat(), "currencies": {}, "unexplained": [], "warnings": []}
    for currency in CURRENCIES:
        old_report = legacy_cash_report(session, currency, today)
        old_months = {(m["year"], m["month"]): m for m in old_report["months"]}
        rows = book.movements(session, currency)
        if plan is not None:
            rows += [p.as_movement() for p in plan.planned if p.currency == currency]
        new_series = book.month_series(session, currency, today, rows=rows)
        new_months = {(m["year"], m["month"]): m for m in new_series["months"]}
        old_ledger = Ledger.load(session, currency)
        manual_months = {
            (year, month) for (year, month), items in old_ledger.month_items.items()
            if items.get("salaries") is not None and items["salaries"].manual
        }
        explained = unpaid_current_months(session, currency, today, manual_months)
        table: list[dict[str, Any]] = []
        cumulative = ZERO
        for key in sorted(set(old_months) | set(new_months)):
            o, n = old_months.get(key), new_months.get(key)
            o_inc, o_exp = Decimal(o["income"]) if o else ZERO, Decimal(o["expense"]) if o else ZERO
            n_inc, n_exp = Decimal(n["hist_income"]) if n else ZERO, Decimal(n["hist_expense"]) if n else ZERO
            unpaid = explained.get(key, ZERO)
            cumulative += unpaid
            o_close = Decimal(o["closing"]) if o else None
            n_close = Decimal(n["hist_closing"]) if n else None
            cash_close = Decimal(n["closing"]) if n else None
            row = {
                "month": f"{key[0]}-{key[1]:02d}", "old_income": str(o_inc), "old_expense": str(o_exp), "old_closing": None if o_close is None else str(o_close),
                "new_income": str(n_inc), "new_expense": str(n_exp), "new_historical_closing": None if n_close is None else str(n_close),
                "new_cash_closing": None if cash_close is None else str(cash_close),
                "explained_unpaid_current_salaries": str(unpaid), "ok": True,
            }
            if o_inc != n_inc or (o_exp - unpaid) != n_exp:
                row["ok"] = False
                report["unexplained"].append({"currency": currency, "month": row["month"], "reason": "income/expense differ",
                                              "old": [str(o_inc), str(o_exp)], "new": [str(n_inc), str(n_exp)], "explained": str(unpaid)})
            if o_close is not None and n_close is not None and (n_close - o_close) != cumulative:
                row["ok"] = False
                report["unexplained"].append({"currency": currency, "month": row["month"], "reason": "closing balance differs",
                                              "old": str(o_close), "new": str(n_close), "explained": str(cumulative)})
            table.append(row)
        not_in_cash = sum(  # only what lies inside the books (from the opening month on), like the monthly series itself
            (m.amount if m.kind == "income" else -m.amount for m in rows
             if m.source == "legacy_adjustment" and not m.counts_in_cash and book.month_key(m.day) >= new_series["start"]), ZERO,
        )
        report["currencies"][currency] = {
            "months": table, "old_balance": old_report["balance"], "new_historical_balance": new_series["months"][-1]["hist_closing"] if new_series["months"] else new_series["opening"],
            "new_cash_balance": new_series["months"][-1]["closing"] if new_series["months"] else new_series["opening"],
            "adjustments_not_in_cash": str(money(not_in_cash)),
        }
        # the cash balance may differ from the historical balance by exactly the adjustments that moved no money
        if new_series["months"]:
            diff = Decimal(new_series["months"][-1]["hist_closing"]) - Decimal(new_series["months"][-1]["closing"])
            if diff != money(not_in_cash):
                report["unexplained"].append({"currency": currency, "month": "end", "reason": "historical minus cash is not the sum of the adjustments",
                                              "difference": str(diff), "adjustments": str(money(not_in_cash))})
        # closed months: what the books said when they were closed is a second, independent witness
        for lock in session.scalars(select(PeriodLock)):
            try:
                snapshot = json.loads(lock.snapshot) if lock.snapshot else {}
            except ValueError:
                snapshot = {}
            saved = snapshot.get(currency)
            n = new_months.get((lock.year, lock.month))
            if not saved or n is None:
                continue
            same_new = Decimal(saved["income"]) == Decimal(n["hist_income"]) and Decimal(saved["expense"]) == Decimal(n["hist_expense"])
            o = old_months.get((lock.year, lock.month))
            same_old = o is not None and Decimal(saved["income"]) == Decimal(o["income"]) and Decimal(saved["expense"]) == Decimal(o["expense"])
            if not same_new and same_old:
                report["unexplained"].append({"currency": currency, "month": f"{lock.year}-{lock.month:02d}", "reason": "closed month differs from its snapshot",
                                              "snapshot": saved, "new": [n["hist_income"], n["hist_expense"]]})
            elif not same_new:
                report["warnings"].append({"currency": currency, "month": f"{lock.year}-{lock.month:02d}", "note": "the old books already differ from the snapshot of the closed month"})
    report["ok"] = not report["unexplained"]
    return report


# ---- fingerprint of the old data ---------------------------------------------------------------------------------------------------
NEW_COLUMNS = {"voided_at", "voided_by", "void_reason", "removed_at", "removed_by", "remove_reason", "transaction_id"}


def fingerprint(session: Session) -> dict[str, Any]:
    """Row count and a hash over the content of every table the migration must leave alone (receipt files included)."""
    result: dict[str, Any] = {}
    for model in (AccountingEntry, EntryReceipt, SalaryLine, FeeCharge, FeePayment, CashOpening, PeriodLock, CashCount, ExchangeRate, Employee, Child):
        columns = [c.name for c in model.__table__.columns if c.name not in NEW_COLUMNS]
        digest = hashlib.sha256()
        rows = session.execute(select(*[getattr(model, c) for c in columns]).order_by(model.__table__.c.id)).all()
        for row in rows:
            for value in row:
                digest.update(value if isinstance(value, bytes) else str(value).encode("utf-8"))
                digest.update(b"\x1f")
            digest.update(b"\x1e")
        result[model.__tablename__] = {"rows": len(rows), "sha256": digest.hexdigest()}
    return result


# ---- apply, go live, go back -----------------------------------------------------------------------------------------------------------
def report_for(plan: Plan, proof: dict[str, Any]) -> dict[str, Any]:
    per_currency: dict[str, Any] = {}
    for p in plan.planned:
        bucket = per_currency.setdefault(p.currency, {"legacy": 0, "adjustments": 0, "legacy_income": ZERO, "legacy_expense": ZERO})
        if p.origin == "legacy":
            bucket["legacy"] += 1
            bucket["legacy_income" if p.kind == "income" else "legacy_expense"] += p.amount
        else:
            bucket["adjustments"] += 1
    return {
        "planned": {c: {"legacy": b["legacy"], "adjustments": b["adjustments"], "legacy_income": str(b["legacy_income"]), "legacy_expense": str(b["legacy_expense"])}
                    for c, b in per_currency.items()},
        "entries": plan.classified, "not_counted": plan.not_counted, "parity": proof,
    }


def dry_run(session: Session, today: date) -> dict[str, Any]:
    """The whole proof without writing anything (rows taken over earlier are set aside inside a transaction that is rolled back)."""
    nested = session.begin_nested()
    try:
        if book.cutover_row(session) is not None:
            session.execute(delete(CashTransaction).where(CashTransaction.origin.in_(("legacy", "legacy_adjustment"))))
            session.flush()
        plan = build_plan(session, today)
        proof = parity(session, plan, today)
        return {**report_for(plan, proof), "fingerprint": fingerprint(session), "ok": proof["ok"]}
    finally:
        nested.rollback()


def apply(session: Session, actor: FeesActor, today: date, refresh: bool = False, go_live: bool = False) -> dict[str, Any]:
    """Writes the historical bookings and the cutover row in ONE transaction. Any unexplained difference raises and nothing is saved."""
    row = book.cutover_row(session)
    if row is not None and row.state == "live":
        raise MigrationAborted("The cash book is already live.")
    if row is not None and not refresh:
        raise MigrationAborted("Already applied. Use refresh to rebuild the taken-over rows (only possible before going live).")
    before = fingerprint(session)
    if row is not None:  # refresh: the derived rows are rebuilt (they are never user data while the switch is not live)
        session.execute(delete(CashTransaction).where(CashTransaction.origin.in_(("legacy", "legacy_adjustment"))))
        session.flush()
    plan = build_plan(session, today)
    proof = parity(session, plan, today)
    if not proof["ok"]:
        session.rollback()
        raise MigrationAborted("Differences between the old and the new books could not be explained. Nothing was written.", {**report_for(plan, proof), "fingerprint": before})
    for planned in plan.planned:
        session.add(planned.as_row())
    session.flush()
    after_proof = parity(session, None, today)
    if not after_proof["ok"]:
        session.rollback()
        raise MigrationAborted("The stored bookings do not reproduce the old books. Nothing was written.", {**report_for(plan, after_proof), "fingerprint": before})
    after = fingerprint(session)
    if after != before:
        session.rollback()
        raise MigrationAborted("The old data changed during the migration. Nothing was written.", {"before": before, "after": after})
    report = {**report_for(plan, after_proof), "fingerprint": before, "ok": True}
    now = datetime.now(timezone.utc)
    if row is None:
        row = LedgerCutover(id=1, state="shadow", applied_by=actor.name[:80])
        session.add(row)
    row.state, row.applied_by, row.applied_at = "shadow", actor.name[:80], now
    row.report_json, row.fingerprint_json, row.live_writes, row.went_live_at = json.dumps(report, ensure_ascii=False, default=str), json.dumps(before), 0, None
    book.audit(session, actor, "ledger.migrate", "ledger", "cutover", None, {"state": "shadow", "bookings": len(plan.planned), "fingerprint": before},
               details=f"{len(plan.planned)} bookings taken over; parity ok")
    if go_live:
        row.state, row.went_live_at = "live", now
        book.audit(session, actor, "ledger.live", "ledger", "cutover", {"state": "shadow"}, {"state": "live"}, details="cash book is now the truth")
    session.commit()
    return report


def go_live(session: Session, actor: FeesActor, today: date) -> dict[str, Any]:
    """Shadow -> live after proving the parity once more with today's data."""
    row = book.cutover_row(session)
    if row is None or row.state != "shadow":
        raise MigrationAborted("There is no applied migration to switch on.")
    proof = parity(session, None, today)
    if not proof["ok"]:
        raise MigrationAborted("The old sheets changed since the migration. Rebuild with refresh first.", {"parity": proof})
    row.state, row.went_live_at, row.live_writes = "live", datetime.now(timezone.utc), 0
    book.audit(session, actor, "ledger.live", "ledger", "cutover", {"state": "shadow"}, {"state": "live"}, details="cash book is now the truth")
    session.commit()
    return {"state": "live"}


def blockers_for_rollback(session: Session) -> list[str]:
    row = book.cutover_row(session)
    if row is None or row.state != "live":
        return ["The cash book is not live."]
    found: list[str] = []
    if (row.live_writes or 0) > 0:
        found.append(f"{row.live_writes} new bookings or cancellations were made in the cash book.")
    if session.scalar(select(CashTransaction.id).where(CashTransaction.origin == "manual")) is not None:
        found.append("manual bookings exist.")
    if session.scalar(select(CashTransaction.id).where(CashTransaction.voided_at.is_not(None))) is not None:
        found.append("bookings were cancelled.")
    return found


def rollback(session: Session, actor: FeesActor) -> dict[str, Any]:
    """Live -> shadow, only while nothing new exists in the cash book."""
    blockers = blockers_for_rollback(session)
    if blockers:
        raise MigrationAborted("No way back to the old sheets: " + " ".join(blockers), {"blockers": blockers})
    row = book.cutover_row(session)
    row.state, row.went_live_at = "shadow", None
    book.audit(session, actor, "ledger.rollback", "ledger", "cutover", {"state": "live"}, {"state": "shadow"}, details="back to the old sheets")
    session.commit()
    return {"state": "shadow"}


def discard(session: Session, actor: FeesActor) -> dict[str, Any]:
    """Shadow -> nothing: removes the taken-over rows again (they are derived and can be rebuilt) and the cutover row."""
    row = book.cutover_row(session)
    if row is None:
        return {"state": "legacy"}
    if row.state == "live":
        raise MigrationAborted("Go back to shadow first (only possible while nothing new exists).")
    removed = session.execute(delete(CashTransaction).where(CashTransaction.origin.in_(("legacy", "legacy_adjustment")))).rowcount or 0
    session.delete(row)
    book.audit(session, actor, "ledger.discard", "ledger", "cutover", {"state": "shadow"}, {"state": "legacy"}, details=f"{removed} taken-over rows removed")
    session.commit()
    return {"state": "legacy", "removed": removed}
