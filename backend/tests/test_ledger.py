"""The cash book: one calculation of the money, the take-over of the old sheets, cancellations instead of deletions."""

import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger as book
from app import legacy_migration as migration
from app.accounting import Ledger, legacy_cash_report, net_pay as legacy_net_pay
from app.fees import FeesActor
from app.models import (
    AccountingEntry, CashOpening, CashTransaction, Child, Employee, EntryReceipt, FeeAuditLog, FeeCharge, FeePayment,
    LedgerCutover, PeriodLock, SalaryLine,
)
from app.timeutil import local_today, to_local
from tests.test_accounting_controls import ControlsBase

A = "/api/admin/accounting"
ADMIN = FeesActor(None, "tester", "admin")
D = Decimal


class LedgerBase(ControlsBase):
    # ---- data straight into the tables (the old way of working) ----
    def db(self) -> Session:
        return Session(self.engine)

    def child_id(self):
        with self.db() as s:
            return s.scalar(select(Child.id))

    def opening(self, currency="SYP", amount="1000", year=2026, month=1):
        with self.db() as s:
            s.add(CashOpening(currency=currency, amount=D(amount), start_year=year, start_month=month))
            s.commit()

    def entry(self, period="month", item="operating", income="0", expense="0", year=2026, month=1, week_start=None, currency="SYP",
              manual=True, label="", details="", receipt_no=""):
        with self.db() as s:
            row = AccountingEntry(
                period_type=period, year=year, month=month if period == "month" else 0, week_start=week_start, currency=currency, item_key=item,
                item_label=label, details=details, income=D(income), expense=D(expense), manual=manual, entered_by="clerk", receipt_no=receipt_no,
            )
            s.add(row)
            s.commit()
            return row.id

    def payment(self, amount, paid_on, year=2026, month=1, currency="SYP"):
        with self.db() as s:
            charge = s.scalar(select(FeeCharge).where(FeeCharge.child_id == self.child_id(), FeeCharge.year == year, FeeCharge.month == month, FeeCharge.currency == currency))
            if charge is None:
                charge = FeeCharge(child_id=self.child_id(), year=year, month=month, currency=currency, amount=D("100000"))
                s.add(charge)
                s.flush()
            payment = FeePayment(charge_id=charge.id, amount=D(amount), paid_on=paid_on, created_by_name="clerk")
            s.add(payment)
            s.commit()
            return payment.id

    def salary(self, name, base, year=2026, month=1, paid_on=None, currency="SYP"):
        with self.db() as s:
            person = s.scalar(select(Employee).where(Employee.name == name))
            if person is None:
                person = Employee(name=name, job_title="teacher")
                s.add(person)
                s.flush()
            line = SalaryLine(employee_id=person.id, year=year, month=month, currency=currency, base=D(base), paid_on=paid_on, recorded_by="clerk")
            s.add(line)
            s.commit()
            return line.id

    # ---- the switch ----
    def migrate(self, today=None, go_live=True, refresh=False):
        with self.db() as s:
            return migration.apply(s, ADMIN, today or local_today(), refresh=refresh, go_live=go_live)

    def bookings(self, currency="SYP", **filters):
        with self.db() as s:
            return book.book(s, currency, **filters)

    def cash(self, currency="SYP", today=None):
        with self.db() as s:
            return book.cash_report(s, currency, today or local_today())

    def mode(self):
        with self.db() as s:
            return book.ledger_mode(s)

    def make_live(self):
        self.opening()
        self.migrate()

    def new_booking(self, **extra):
        body = {"currency": "SYP", "kind": "expense", "amount": "100", "booked_on": local_today().isoformat(), "category": "material", "description": "paper", **extra}
        return self.client.post(A + "/bookings", headers=self.acc, json=body)


class MigrationTests(LedgerBase):
    TODAY = date(2026, 6, 15)

    def old_data(self):
        """A messy set of old sheets: all three levels, overlaps, customs, a hand-typed month, paid and unpaid salaries."""
        self.opening()
        # January
        self.payment("500", date(2026, 1, 10), month=1)
        self.payment("200", None, month=1)  # an imported payment without a date
        self.entry("month", "buffet", expense="100", month=1)
        self.entry("day", "buffet", expense="7", week_start=date(2026, 1, 5))  # covered by the month row of the same item
        self.entry("week", "purchases", expense="50", week_start=date(2026, 1, 12))
        self.entry("day", "purchases", expense="30", week_start=date(2026, 1, 14))  # covered by the week row
        self.entry("day", "purchases", expense="40", week_start=date(2026, 1, 20))  # counts
        self.entry("day", "custom", expense="25", week_start=date(2026, 1, 21), label="Repair")
        self.entry("week", "custom", expense="10", week_start=date(2026, 1, 19), label="Repair")  # customs add up, no overlap rule
        self.entry("month", "transport", income="80", month=1)
        # February: a month value typed by hand over the automatic fees
        self.payment("400", date(2026, 2, 12), month=2)
        self.entry("month", "registration", income="900", month=2, manual=True)
        self.entry("week", "registration", income="55", week_start=date(2026, 2, 2), manual=True)  # automatic items never count on a week row
        # salaries
        self.salary("Rima", "300", month=1, paid_on=date(2026, 2, 5))
        self.salary("Sami", "200", month=1)  # nobody paid it out: a month that is over
        self.salary("Rima", "300", month=2)
        self.salary("Rima", "150", month=6)  # the running month: the old sheet counts it, the new rule does not

    def test_old_and_new_books_agree_month_by_month_before_anything_is_written(self):
        self.old_data()
        with self.db() as s:
            report = migration.dry_run(s, self.TODAY)
        self.assertTrue(report["ok"], report["parity"]["unexplained"])
        rows = report["parity"]["currencies"]["SYP"]["months"]
        self.assertTrue(all(row["ok"] for row in rows))
        self.assertEqual(self.mode(), "legacy")  # the dry run wrote nothing
        with self.db() as s:
            self.assertEqual(s.scalars(select(CashTransaction)).all(), [])

    def test_rows_that_counted_become_collective_bookings_and_the_rest_stays_in_the_archive(self):
        self.old_data()
        self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            legacy = s.scalars(select(CashTransaction).where(CashTransaction.origin == "legacy")).all()
            notes = sorted(t.legacy_note for t in legacy)
            # counted: month buffet, month transport, week purchases, day purchases (20th), both customs
            self.assertEqual(len(legacy), 6, notes)
            by_date = {(t.legacy_note.split(":")[0].split()[0], t.date_basis) for t in legacy}
            self.assertEqual(by_date, {("Monatsblatt", "legacy_month_end"), ("Wochenblatt", "legacy_week_mid"), ("Tagesblatt", "actual")})
            week = next(t for t in legacy if t.date_basis == "legacy_week_mid")
            self.assertEqual(week.booked_on, date(2026, 1, 12) + timedelta(days=3))
            month_row = next(t for t in legacy if t.category == "food")
            self.assertEqual(month_row.booked_on, date(2026, 1, 31))
            # the old rows are all still there, untouched
            self.assertEqual(len(s.scalars(select(AccountingEntry)).all()), 10)
            report = json.loads(s.get(LedgerCutover, 1).report_json)
        reasons = {row["reason"] for row in report["not_counted"]}
        self.assertTrue(any("month row" in r for r in reasons) and any("week row" in r for r in reasons) and any(r == "automatic" for r in reasons), reasons)

    def test_a_hand_typed_month_value_becomes_an_adjustment_and_the_money_stays_real(self):
        self.old_data()
        self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            adjustment = s.scalar(select(CashTransaction).where(CashTransaction.adjustment_kind == "manual_override"))
            self.assertEqual((adjustment.kind, adjustment.amount, adjustment.category, adjustment.counts_in_cash), ("income", D("500.00"), "fees", True))
            self.assertEqual(adjustment.booked_on, date(2026, 2, 28))
            self.assertEqual(adjustment.date_basis, "legacy_month_end")

    def test_salaries_nobody_paid_never_reduce_the_cash_balance(self):
        self.old_data()
        with self.db() as s:
            old = D(legacy_cash_report(s, "SYP", self.TODAY)["balance"])
        self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            adjustments = s.scalars(select(CashTransaction).where(CashTransaction.adjustment_kind == "salary_unpaid")).all()
            self.assertEqual(sorted(a.amount for a in adjustments), [D("200.00"), D("300.00")])  # the running month has none
            self.assertTrue(all(not a.counts_in_cash and a.origin == "legacy_adjustment" and a.category == "salaries" for a in adjustments))
            report = book.cash_report(s, "SYP", self.TODAY)
        # old: counted all three unpaid salaries; new cash: none of them (200 + 300 as adjustments, 150 of the running month)
        self.assertEqual(D(report["balance"]) - old, D("650.00"))
        # the historical balance is the old one apart from the running month
        self.assertEqual(D(report["historical_balance"]) - old, D("150.00"))

    def test_the_cash_balance_differs_from_the_historical_one_by_exactly_the_adjustments_that_moved_no_money(self):
        self.old_data()
        self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            overview = book.overview(s, self.TODAY)["currencies"]["SYP"]
        self.assertEqual(D(overview["historical"]["difference"]), D("-500.00"))
        self.assertEqual(D(overview["historical"]["adjustments_not_in_cash"]), D("-500.00"))

    def test_applying_twice_is_refused_and_a_refresh_rebuilds_the_same_rows(self):
        self.old_data()
        self.migrate(self.TODAY, go_live=False)
        with self.assertRaises(migration.MigrationAborted):
            self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            before = sorted((t.legacy_note, str(t.amount), t.kind) for t in s.scalars(select(CashTransaction)))
        self.migrate(self.TODAY, go_live=False, refresh=True)
        with self.db() as s:
            after = sorted((t.legacy_note, str(t.amount), t.kind) for t in s.scalars(select(CashTransaction)))
        self.assertEqual(before, after)

    def test_the_old_data_and_the_receipt_files_are_byte_for_byte_the_same_afterwards(self):
        self.old_data()
        entry_id = self.entry("month", "operating", expense="60", month=3, receipt_no="R-1")
        with self.db() as s:
            s.add(EntryReceipt(entry_id=entry_id, original_name="r.pdf", media_type="application/pdf", byte_size=9, contents=b"%PDF-1.4 x", uploaded_by="clerk"))
            s.commit()
            before = migration.fingerprint(s)
        self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            self.assertEqual(migration.fingerprint(s), before)
            self.assertEqual(before["entry_receipts"]["rows"], 1)
        # the receipt of a taken-over row shows at its booking
        with self.db() as s:
            tx = s.scalar(select(CashTransaction).where(CashTransaction.legacy_entry_id == entry_id))
            self.assertEqual(book.receipt_counts(s, [tx])[tx.id], 1)

    def test_a_difference_nobody_can_explain_stops_the_migration_and_nothing_is_written(self):
        self.old_data()
        real = migration.build_plan

        def lossy(session, today):
            plan = real(session, today)
            plan.planned = [p for p in plan.planned if not (p.origin == "legacy" and p.category == "food")]  # a booking goes missing
            return plan

        with patch.object(migration, "build_plan", lossy):
            with self.assertRaises(migration.MigrationAborted) as caught:
                self.migrate(self.TODAY, go_live=False)
        self.assertTrue(caught.exception.report["parity"]["unexplained"])
        with self.db() as s:
            self.assertEqual(s.scalars(select(CashTransaction)).all(), [])
            self.assertIsNone(s.get(LedgerCutover, 1))

    def test_a_closed_month_must_still_match_what_the_books_said_when_it_was_closed(self):
        self.old_data()
        with self.db() as s:
            totals = Ledger.load(s, "SYP").sheet("month", 2026, 1, None)["totals"]
            s.add(PeriodLock(year=2026, month=1, closed_by="acc", snapshot=json.dumps({"SYP": {"income": totals["income"], "expense": totals["expense"]}})))
            s.commit()
            report = migration.dry_run(s, self.TODAY)
        self.assertTrue(report["ok"], report["parity"]["unexplained"])

    def test_every_movement_has_exactly_one_known_source_and_date_basis(self):
        self.old_data()
        self.migrate(self.TODAY, go_live=False)
        with self.db() as s:
            rows = book.movements(s, "SYP", include_voided=True)
        self.assertTrue(rows)
        self.assertTrue(all(m.source in book.SOURCES and m.date_basis in book.DATE_BASES for m in rows))
        estimated = [m for m in rows if m.date_basis == "estimated_fee_month"]
        self.assertEqual((len(estimated), estimated[0].source, estimated[0].day), (1, "fee_payment", date(2026, 1, 31)))

    def test_pounds_and_dollars_are_never_mixed(self):
        self.opening("SYP", "1000")
        self.opening("USD", "50")
        self.payment("30", date(2026, 1, 10), currency="USD")
        self.payment("700", date(2026, 1, 11), currency="SYP", month=1)
        self.migrate(self.TODAY, go_live=False)
        syp, usd = self.cash("SYP", self.TODAY), self.cash("USD", self.TODAY)
        self.assertEqual((syp["balance"], usd["balance"]), ("1700.00", "80.00"))
        with self.db() as s:
            overview = book.overview(s, self.TODAY)
        self.assertEqual(set(overview["currencies"]), {"SYP", "USD"})
        self.assertNotIn("total", overview)

    def test_many_random_old_books_always_agree_with_the_new_calculation(self):
        """The strongest proof: messy random sheets (every level, every item, duplicates, hand-typed values, undated payments,
        paid and unpaid salaries) must reproduce the old figures month by month, whatever they look like."""
        import random

        items = ["registration", "operating", "salaries", "activities", "purchases", "buffet", "transport", "advertising", "misc", "custom"]
        for seed in range(12):
            rng = random.Random(seed)
            self.tearDown()
            self.setUp()
            self.opening("SYP", str(rng.choice([0, 500, 12345])), 2026, rng.choice([1, 2]))
            for _ in range(rng.randint(10, 40)):
                period = rng.choice(["month", "week", "day"])
                item = rng.choice(items)
                currency = rng.choice(["SYP", "SYP", "USD"])
                kwargs = dict(item=item, income=str(rng.choice([0, 0, 10, 55, 120])), expense=str(rng.choice([0, 0, 5, 40, 75])), currency=currency,
                              manual=rng.random() < 0.7, label="Misc" if item == "custom" else "")
                if period == "month":
                    self.entry("month", month=rng.randint(1, 5), **kwargs)
                else:
                    day = date(2026, 1, 1) + timedelta(days=rng.randint(0, 150))
                    if period == "week":
                        day = day - timedelta(days=day.weekday())  # the Monday the app would store
                    self.entry(period, week_start=day, **kwargs)
            for _ in range(rng.randint(0, 8)):
                month = rng.randint(1, 6)
                paid = None if rng.random() < 0.3 else date(2026, rng.randint(1, 6), rng.randint(1, 28))
                self.payment(str(rng.choice([100, 250, -40, 75])), paid, month=month, currency=rng.choice(["SYP", "USD"]))
            for i in range(rng.randint(0, 6)):
                paid = None if rng.random() < 0.5 else date(2026, rng.randint(1, 6), rng.randint(1, 28))
                self.salary(f"Person{i}", str(rng.choice([100, 300])), month=rng.randint(1, 6), paid_on=paid, currency=rng.choice(["SYP", "USD"]))
            with self.db() as s:
                report = migration.dry_run(s, self.TODAY)
            self.assertTrue(report["ok"], f"seed {seed}: {report['parity']['unexplained']}")
            if seed % 4 == 0:  # and what is really written reproduces the old books too
                self.migrate(self.TODAY, go_live=False)
                with self.db() as s:
                    self.assertTrue(migration.parity(s, None, self.TODAY)["ok"], f"seed {seed} after writing")

    def test_the_two_net_pay_rules_stay_equal(self):
        for values in [(D("100"), None, None, None), (D("100"), D("10"), D("5"), D("1.5")), (None, D("1"), None, None)]:
            self.assertEqual(book.net_pay(*values), legacy_net_pay(*values))


class SwitchTests(LedgerBase):
    def test_before_the_switch_nothing_changes_and_bookings_are_not_possible(self):
        self.opening()
        self.assertEqual(self.mode(), "legacy")
        self.assertEqual(self.new_booking().status_code, 409)
        self.assertEqual(self.client.get(A + "/finance/status", headers=self.acc).json()["mode"], "legacy")

    def test_going_back_is_possible_only_while_nothing_new_exists(self):
        self.make_live()
        with self.db() as s:
            self.assertEqual(migration.blockers_for_rollback(s), [])
        self.assertTrue(self.client.get(A + "/finance/status", headers=self.acc).json()["way_back"])
        self.assertEqual(self.new_booking().status_code, 201)
        with self.db() as s:
            blockers = migration.blockers_for_rollback(s)
        self.assertTrue(any("new bookings" in b for b in blockers) and any("manual" in b for b in blockers), blockers)
        with self.db() as s:
            with self.assertRaises(migration.MigrationAborted):
                migration.rollback(s, ADMIN)
        self.assertFalse(self.client.get(A + "/finance/status", headers=self.acc).json()["way_back"])

    def test_rollback_works_when_the_cash_book_is_still_untouched(self):
        self.make_live()
        with self.db() as s:
            migration.rollback(s, ADMIN)
        self.assertEqual(self.mode(), "shadow")
        self.assertEqual(self.new_booking().status_code, 409)  # the old sheets are the truth again

    def test_the_old_sheets_are_read_only_and_nothing_is_deleted_once_live(self):
        entry_id = self.entry("day", "buffet", expense="10", week_start=local_today())
        self.make_live()
        put = self.client.put(A + "/entries", headers=self.acc, json={"period_type": "day", "year": local_today().year, "week_start": local_today().isoformat(), "currency": "SYP", "item_key": "buffet", "expense": "5"})
        self.assertEqual(put.status_code, 409)
        self.assertEqual(self.client.delete(f"{A}/entries/{entry_id}", headers=self.acc).status_code, 409)
        line = self.salary("Rima", "300", month=1)
        self.assertEqual(self.client.delete(f"{A}/salaries/{line}", headers=self.acc).status_code, 409)
        pid = self.payment("10", local_today())
        self.assertEqual(self.client.delete(f"/api/admin/fees/payments/{pid}", headers=self.acc).status_code, 409)

    def test_a_reset_is_blocked_once_live_and_only_possible_in_an_isolated_test_database(self):
        self.make_live()
        body = {"year": 2026, "month": 1, "scopes": ["entries"], "confirm": "RESET"}
        self.assertEqual(self.client.post(A + "/reset-part", headers=self.admin, json=body).status_code, 423)
        self.assertEqual(self.client.post(A + "/reset", headers=self.admin, json={"confirm": "RESET"}).status_code, 423)
        with patch.dict(os.environ, {"ALLOW_FINANCE_RESET": "1"}):
            self.assertEqual(self.client.post(A + "/reset-part", headers=self.admin, json=body).status_code, 200)  # SQLite + the variable
            with patch("app.ledger.is_live", return_value=True):
                from sqlalchemy.engine import default

                with patch.object(default.DefaultDialect, "name", "postgresql", create=True):
                    pass
        # a PostgreSQL database never allows it, whatever the variable says
        class Dialect:
            name = "postgresql"

        class Bind:
            dialect = Dialect()

        class Fake:
            def get_bind(self):
                return Bind()

        with patch.dict(os.environ, {"ALLOW_FINANCE_RESET": "1"}), patch("app.ledger.is_live", return_value=True):
            with self.assertRaises(Exception) as caught:
                book.guard_reset(Fake())
        self.assertEqual(getattr(caught.exception, "status_code", None), 423)


class BookingTests(LedgerBase):
    def setUp(self):
        super().setUp()
        self.make_live()

    def test_a_booking_has_a_category_that_fits_and_never_a_system_category(self):
        self.assertEqual(self.new_booking(category="fees", kind="income").status_code, 422)
        self.assertEqual(self.new_booking(category="salaries").status_code, 422)
        self.assertEqual(self.new_booking(category="donations").status_code, 422)  # an income category on an expense
        self.assertEqual(self.new_booking(amount="0").status_code, 422)
        self.assertEqual(self.new_booking(booked_on=(local_today() + timedelta(days=1)).isoformat()).status_code, 422)
        self.assertEqual(self.new_booking(kind="income", category="donations", amount="250").status_code, 201)
        categories = self.client.get(A + "/finance/categories", headers=self.acc).json()
        self.assertEqual([c["key"] for c in categories["income"]], ["fees", "donations", "other_income"])
        self.assertEqual(len(categories["expense"]), 9)

    def test_the_balance_follows_the_bookings_and_both_figures_are_shown_apart_per_currency(self):
        self.new_booking(kind="income", category="donations", amount="250")
        self.new_booking(amount="100")
        usd = self.new_booking(currency="USD", kind="income", category="other_income", amount="5")
        self.assertEqual(usd.status_code, 201)
        overview = self.client.get(A + "/finance/overview", headers=self.acc).json()
        syp, dollars = overview["currencies"]["SYP"], overview["currencies"]["USD"]
        self.assertEqual((syp["balance"], syp["total_income"], syp["total_expense"]), ("1150.00", "250.00", "100.00"))
        self.assertEqual(dollars["total_income"], "5.00")
        self.assertEqual(syp["this_month"]["net"], "150.00")
        self.assertEqual(len(syp["recent"]), 2)

    def test_a_booking_changes_with_version_check_and_the_log_keeps_before_and_after(self):
        made = self.new_booking(amount="100", description="paper").json()
        changed = self.client.patch(f"{A}/bookings/{made['source_id']}", headers=self.acc, json={"amount": "120", "description": "paper and glue", "expected_version": made["version"]})
        self.assertEqual(changed.status_code, 200, changed.text)
        stale = self.client.patch(f"{A}/bookings/{made['source_id']}", headers=self.acc2, json={"amount": "999", "expected_version": made["version"]})
        self.assertEqual(stale.status_code, 409)
        trail = self.client.get(f"{A}/finance/history/{made['source_id']}", headers=self.acc).json()
        self.assertEqual([t["action"] for t in trail], ["booking.create", "booking.update"])
        update = trail[1]
        self.assertEqual((update["actor"], update["before"]["amount"], update["after"]["amount"]), ("acc", "100.00", "120.00"))
        self.assertEqual((update["before"]["description"], update["after"]["description"]), ("paper", "paper and glue"))
        self.assertTrue(update["at"])

    def test_cancelling_needs_a_reason_keeps_the_line_and_the_receipts_and_takes_it_out_of_the_balance(self):
        made = self.new_booking(amount="100").json()
        bid = made["source_id"]
        pdf = ("r.pdf", b"%PDF-1.4 receipt", "application/pdf")
        receipt = self.client.post(f"{A}/bookings/{bid}/receipts", headers=self.acc, files={"file": pdf})
        self.assertEqual(receipt.status_code, 201, receipt.text)
        self.assertEqual(self.client.post(f"{A}/bookings/{bid}/void", headers=self.acc, json={"reason": "no"}).status_code, 422)
        voided = self.client.post(f"{A}/bookings/{bid}/void", headers=self.acc, json={"reason": "typed twice by mistake"})
        self.assertEqual(voided.status_code, 200, voided.text)
        self.assertTrue(voided.json()["voided"])
        self.assertEqual(self.cash()["balance"], "1000.00")  # the 100 is back
        rows = self.bookings()["rows"]
        self.assertEqual(len(rows), 1)  # still in the book, crossed out
        self.assertEqual((rows[0]["voided"], rows[0]["void_reason"], rows[0]["voided_by"]), (True, "typed twice by mistake", "acc"))
        self.assertEqual(self.client.post(f"{A}/bookings/{bid}/void", headers=self.acc, json={"reason": "again please"}).status_code, 409)
        self.assertEqual(self.client.patch(f"{A}/bookings/{bid}", headers=self.acc, json={"amount": "1"}).status_code, 409)
        # the receipt stays; "removing" only takes it out of view, with a reason
        listing = self.client.get(f"{A}/bookings/{bid}/receipts", headers=self.acc).json()
        self.assertEqual(len(listing), 1)
        trail = self.client.get(f"{A}/finance/history/{bid}", headers=self.acc).json()
        self.assertEqual(trail[-1]["action"], "booking.void")
        self.assertEqual((trail[-1]["reason"], trail[-1]["before"]["voided"], trail[-1]["after"]["voided"]), ("typed twice by mistake", False, True))

    def test_a_receipt_is_never_deleted_only_removed_from_view_with_a_reason(self):
        bid = self.new_booking().json()["source_id"]
        item = self.client.post(f"{A}/bookings/{bid}/receipts", headers=self.acc, files={"file": ("r.pdf", b"%PDF-1.4 a", "application/pdf")}).json()
        self.assertEqual(self.bookings()["rows"][0]["receipts"], 1)
        self.assertEqual(self.client.post(f"{A}/booking-receipts/{item['id']}/remove", headers=self.acc, json={"reason": "x"}).status_code, 422)
        removed = self.client.post(f"{A}/booking-receipts/{item['id']}/remove", headers=self.acc, json={"reason": "wrong file uploaded"})
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.bookings()["rows"][0]["receipts"], 0)
        with self.db() as s:
            stored = s.get(EntryReceipt, __import__("uuid").UUID(item["id"]))
            self.assertEqual((stored.contents, stored.removed_by, stored.remove_reason), (b"%PDF-1.4 a", "acc", "wrong file uploaded"))
        self.assertEqual(self.client.get(f"{A}/booking-receipts/{item['id']}/download", headers=self.acc).status_code, 200)
        self.assertEqual(self.client.delete(f"{A}/receipts/{item['id']}", headers=self.acc).status_code, 409)

    def test_expenses_without_a_receipt_are_marked_and_filterable(self):
        bare = self.new_booking(amount="10").json()
        numbered = self.new_booking(amount="20", receipt_no="R-7").json()
        self.assertTrue(bare["needs_receipt"] and not numbered["needs_receipt"])
        rows = self.bookings(only_missing_receipt=True)["rows"]
        self.assertEqual([r["source_id"] for r in rows], [bare["source_id"]])
        self.assertEqual(self.bookings(source="booking")["count"], 2)

    def test_a_booking_in_a_closed_month_is_refused_and_so_is_cancelling_it(self):
        today = local_today()
        old_day = date(today.year - 1, 3, 10)
        made = self.new_booking(booked_on=old_day.isoformat())
        self.assertEqual(made.status_code, 201)
        close = self.client.post(A + "/periods/close", headers=self.acc, json={"year": old_day.year, "month": 3, "note": "checked"})
        self.assertEqual(close.status_code, 201, close.text)
        self.assertEqual(self.new_booking(booked_on=date(old_day.year, 3, 20).isoformat()).status_code, 423)
        self.assertEqual(self.client.post(f"{A}/bookings/{made.json()['source_id']}/void", headers=self.acc, json={"reason": "should not work"}).status_code, 423)
        with self.db() as s:
            snapshot = json.loads(s.scalar(select(PeriodLock)).snapshot)
        self.assertEqual(snapshot["SYP"]["expense"], "100.00")  # the closing kept the live books' totals

    def test_a_fee_payment_is_cancelled_with_a_reason_and_stays_visible(self):
        pid = self.payment("300", local_today())
        self.assertEqual(self.cash()["balance"], "1300.00")
        self.assertEqual(self.client.post(f"{A}/finance/payments/{pid}/void", headers=self.acc, json={"reason": "no"}).status_code, 422)
        done = self.client.post(f"{A}/finance/payments/{pid}/void", headers=self.acc, json={"reason": "bounced cheque"})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(self.cash()["balance"], "1000.00")
        row = next(r for r in self.bookings()["rows"] if r["source"] == "fee_payment")
        self.assertEqual((row["voided"], row["void_reason"], row["voided_by"]), (True, "bounced cheque", "acc"))
        trail = self.client.get(f"{A}/finance/history/{pid}", headers=self.acc).json()
        self.assertEqual((trail[-1]["action"], trail[-1]["before"]["amount"], trail[-1]["reason"]), ("payment.void", "300.00", "bounced cheque"))
        self.assertEqual(self.client.post(f"{A}/finance/payments/{pid}/void", headers=self.acc, json={"reason": "once more"}).status_code, 409)

    def test_a_fee_line_with_payments_cannot_be_cancelled_and_one_without_leaves_the_lists_but_not_the_log(self):
        pid = self.payment("300", local_today(), month=local_today().month, year=local_today().year)
        with self.db() as s:
            charge_id = s.scalar(select(FeePayment.charge_id).where(FeePayment.id == pid))
        self.assertEqual(self.client.post(f"{A}/finance/charges/{charge_id}/void", headers=self.acc, json={"reason": "wrong child"}).status_code, 409)
        self.client.post(f"{A}/finance/payments/{pid}/void", headers=self.acc, json={"reason": "wrong child"})
        done = self.client.post(f"{A}/finance/charges/{charge_id}/void", headers=self.acc, json={"reason": "wrong child"})
        self.assertEqual(done.status_code, 200, done.text)
        listed = self.client.get(f"/api/admin/fees?year={local_today().year}&month={local_today().month}", headers=self.acc).json()
        self.assertNotIn(str(charge_id), [r["id"] for r in listed["rows"]] if isinstance(listed, dict) and "rows" in listed else [r["id"] for r in listed])
        gone = self.client.get(A + "/finance/voided", headers=self.acc).json()
        self.assertEqual([c["id"] for c in gone["charges"]], [str(charge_id)])

    def test_the_cash_count_compares_with_the_real_cash_not_with_historical_adjustments(self):
        today = local_today()
        self.salary("Sami", "200", year=today.year - 1, month=3)  # unpaid, in a month that is over
        with self.db() as s:
            migration.rollback(s, ADMIN)
            s.execute(__import__("sqlalchemy").delete(CashTransaction))
            s.delete(s.get(LedgerCutover, 1))
            s.commit()
        self.migrate()
        counted = self.client.post(A + "/cash/counts", headers=self.acc, json={"currency": "SYP", "counted_on": today.isoformat(), "counted_amount": "1000"})
        self.assertEqual(counted.status_code, 201, counted.text)
        self.assertEqual((counted.json()["book_amount"], counted.json()["difference"]), ("1000.00", "0.00"))  # the unpaid salary is not in the cash box


class SalaryPaymentTests(LedgerBase):
    """A salary taken over as unpaid is settled when it is really paid out, without ever touching a closed month."""

    def setUp(self):
        super().setUp()
        today = local_today()
        self.year = today.year - 1  # a year that is over
        self.opening(year=self.year, month=1)
        self.line = self.salary("Sami", "200", year=self.year, month=3)
        self.migrate()
        with self.db() as s:
            self.adjustment = s.scalar(select(CashTransaction.id).where(CashTransaction.adjustment_kind == "salary_unpaid"))

    def pay(self, day):
        return self.client.patch(f"{A}/salaries/{self.line}", headers=self.acc, json={"paid_on": day.isoformat()})

    def adjustments(self):
        with self.db() as s:
            return {t.id: t for t in s.scalars(select(CashTransaction).where(CashTransaction.adjustment_kind != ""))}

    def historical(self):
        with self.db() as s:
            return D(book.cash_report(s, "SYP", local_today())["historical_balance"]), D(book.cash_report(s, "SYP", local_today())["balance"])

    def test_before_the_payment_the_adjustment_counts_only_in_the_historical_balance(self):
        hist, cash = self.historical()
        self.assertEqual(hist - cash, D("-200.00"))

    def test_paid_out_in_an_open_month_the_adjustment_is_cancelled_automatically_and_never_counts_twice(self):
        paid = self.pay(local_today())
        self.assertEqual(paid.status_code, 200, paid.text)
        adjustment = self.adjustments()[self.adjustment]
        self.assertIsNotNone(adjustment.voided_at)
        self.assertIn("ausgezahlt", adjustment.void_reason)
        hist, cash = self.historical()
        self.assertEqual((hist, cash), (D("800.00") - D("0"), D("800.00")))  # real money out once, the history agrees with the cash
        trail = self.client.get(f"{A}/finance/history/{self.adjustment}", headers=self.acc).json()
        self.assertEqual(trail[-1]["action"], "booking.void.auto")
        self.assertEqual((trail[-1]["before"]["voided"], trail[-1]["after"]["voided"]), (False, True))

    def test_in_a_closed_month_the_adjustment_stays_and_a_counter_booking_in_the_payment_month_cancels_it_historically(self):
        close = self.client.post(A + "/periods/close", headers=self.acc, json={"year": self.year, "month": 3, "note": "done"})
        self.assertEqual(close.status_code, 201, close.text)
        with self.db() as s:
            before = json.loads(s.scalar(select(PeriodLock)).snapshot)
        paid = self.pay(local_today())  # the one thing allowed on a salary of a closed month: its payment date
        self.assertEqual(paid.status_code, 200, paid.text)
        rows = self.adjustments()
        self.assertIsNone(rows[self.adjustment].voided_at)  # the closed month did not change
        counter = next(t for t in rows.values() if t.adjustment_kind == "salary_counter")
        self.assertEqual((counter.kind, counter.amount, counter.booked_on, counter.date_basis, counter.counts_in_cash),
                         ("income", D("200.00"), local_today(), "derived_payment_date", False))
        self.assertEqual(counter.reverses_adjustment_id, self.adjustment)
        hist, cash = self.historical()
        self.assertEqual(cash, D("800.00"))  # 1000 - 200 paid now
        self.assertEqual(hist, D("800.00"))  # the history counts the salary once, not twice
        with self.db() as s:
            self.assertEqual(book.month_totals(s, "SYP", self.year, 3)["expense"], before["SYP"]["expense"])  # the closed month is exactly as closed
        self.assertEqual(self.client.get(f"{A}/finance/history/{counter.id}", headers=self.acc).json()[0]["action"], "booking.counter.auto")

    def test_the_month_of_the_payment_must_be_open(self):
        today = local_today()
        self.client.post(A + "/periods/close", headers=self.acc, json={"year": self.year, "month": 3, "note": "done"})
        self.client.post(A + "/periods/close", headers=self.acc, json={"year": self.year, "month": 4, "note": "done"})
        refused = self.client.patch(f"{A}/salaries/{self.line}", headers=self.acc, json={"paid_on": date(self.year, 4, 10).isoformat()})
        self.assertEqual(refused.status_code, 423)
        self.assertIsNone(self.adjustments()[self.adjustment].voided_at)
        self.assertEqual(today.year - 1, self.year)

    def test_nothing_else_on_a_salary_of_a_closed_month_is_allowed(self):
        self.client.post(A + "/periods/close", headers=self.acc, json={"year": self.year, "month": 3, "note": "done"})
        self.assertEqual(self.client.patch(f"{A}/salaries/{self.line}", headers=self.acc, json={"base": "999"}).status_code, 423)
        self.assertEqual(self.client.patch(f"{A}/salaries/{self.line}", headers=self.acc, json={"paid_on": local_today().isoformat(), "base": "999"}).status_code, 423)

    def test_if_the_settling_ever_fails_a_paid_salary_still_never_counts_twice(self):
        with self.db() as s:  # the date is written straight into the table, as if the automatic cancellation had not run
            line = s.get(SalaryLine, self.line)
            line.paid_on = local_today()
            s.commit()
        hist, cash = self.historical()
        self.assertEqual((hist, cash), (D("800.00"), D("800.00")))

    def test_cancelling_a_salary_line_takes_its_adjustment_with_it(self):
        done = self.client.post(f"{A}/finance/salaries/{self.line}/void", headers=self.acc, json={"reason": "employee left before"})
        self.assertEqual(done.status_code, 200, done.text)
        hist, cash = self.historical()
        self.assertEqual((hist, cash), (D("1000.00"), D("1000.00")))
        voided = self.client.get(A + "/finance/voided", headers=self.acc).json()
        self.assertEqual([s["id"] for s in voided["salaries"]], [str(self.line)])
        self.assertEqual(self.client.get(f"{A}/salaries?year={self.year}&month=3", headers=self.acc).json()["rows"], [])


class TimeTests(LedgerBase):
    def test_business_dates_follow_damascus_not_the_server(self):
        late = datetime(2026, 1, 31, 22, 30, tzinfo=timezone.utc)  # 00:30 on 1 February in Damascus
        with patch.dict(os.environ, {"APP_TIMEZONE": "Asia/Damascus"}):
            self.assertEqual(to_local(late).date(), date(2026, 2, 1))
            self.assertEqual(to_local(late).utcoffset(), timedelta(hours=3))
            self.assertEqual(to_local(late.replace(tzinfo=None)).date(), date(2026, 2, 1))  # a stored (naive) time stamp is UTC
        with patch.dict(os.environ, {"APP_TIMEZONE": "UTC"}):
            self.assertEqual(to_local(late).date(), date(2026, 1, 31))

    def test_the_audit_log_shows_local_time(self):
        self.make_live()
        bid = self.new_booking().json()["source_id"]
        with patch.dict(os.environ, {"APP_TIMEZONE": "Asia/Damascus"}):
            entry = self.client.get(f"{A}/finance/history/{bid}", headers=self.acc).json()[0]
        self.assertTrue(entry["at"].endswith("+00:00") is False or entry["at_local"].endswith("+03:00"))
        self.assertTrue(entry["at_local"].endswith("+03:00"))


class RightsTests(LedgerBase):
    def test_only_accountant_and_admin_use_the_cash_book(self):
        self.make_live()
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(A + "/finance/overview", headers=headers).status_code, 403)
            self.assertEqual(self.client.post(A + "/bookings", headers=headers, json={"currency": "SYP", "kind": "expense", "amount": "1", "booked_on": local_today().isoformat(), "category": "material"}).status_code, 403)
        self.assertEqual(self.client.get(A + "/finance/overview", headers=self.admin).status_code, 200)
        self.assertEqual(self.client.get(A + "/finance/overview", headers=self.mgr).status_code, 403)
