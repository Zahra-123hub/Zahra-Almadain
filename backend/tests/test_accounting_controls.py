"""Month closing, cash reconciliation, refunds and double-click protection of the accounting area."""

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_session
from app.models import Account, Child, FeeAuditLog, FeePayment, PeriodLock, Role

A = "/api/admin/accounting"
F = "/api/admin/fees"
PASSWORD = "Qx5a6ba62b7e4b-9"


class ControlsBase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "test-controls-secret-long-enough",
                "ADMIN_USERNAME": "legacy-admin",
                "ADMIN_PASSWORD": "Qx9edbcb5679ea-9",
            },
        )
        self.env.start()
        self.feed = patch("app.accounting.fetch_online_rate", return_value=None)  # the tests never touch the internet
        self.feed.start()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)

        def override():
            with Session(self.engine) as session:
                yield session

        main.app.dependency_overrides[get_session] = override
        main.app.dependency_overrides[main.optional_session] = override
        self.client = TestClient(main.app)
        with Session(self.engine) as session:
            roles = {n: Role(name=n) for n in ("admin", "teacher", "parent", "accountant")}
            session.add_all(roles.values())
            for username, role in (("acc", "accountant"), ("teacher1", "teacher"), ("parent1", "parent")):
                session.add(Account(username=username, password_hash=main.PASSWORD_HASHER.hash(PASSWORD), roles=[roles[role]]))
            session.add(Child(display_name="Amal", class_name="KG1"))
            session.commit()

        def token(name):
            return {"Authorization": "Bearer " + self.client.post(
                "/api/platform/auth/login", json={"username": name, "password": PASSWORD}
            ).json()["access_token"]}

        self.acc, self.teacher, self.parent = token("acc"), token("teacher1"), token("parent1")
        self.admin = {"Authorization": "Bearer " + self.client.post(
            "/api/auth/login", json={"username": "legacy-admin", "password": "Qx9edbcb5679ea-9"}
        ).json()["access_token"]}

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.optional_session, None)
        self.engine.dispose()
        self.feed.stop()
        self.env.stop()

    # ---- helpers ----
    def charge(self, month=1, amount="1000", year=2026, currency="SYP"):
        child_id = self.client.get(F + "/children", headers=self.acc).json()[0]["id"]
        response = self.client.post(F + "/charges", headers=self.acc, json={
            "child_id": child_id, "year": year, "month": month, "amount": amount, "currency": currency})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def pay(self, charge, amount, paid_on, **extra):
        return self.client.post(f"{F}/charges/{charge['id']}/payments", headers=self.acc,
                                json={"amount": amount, "paid_on": paid_on, **extra})

    def refund(self, charge, amount, paid_on, note="تراجع الأهل", headers=None):
        return self.client.post(f"{F}/charges/{charge['id']}/refunds", headers=headers or self.acc,
                                json={"amount": amount, "paid_on": paid_on, "note": note})

    def entry(self, day, item="buffet", income="0", expense="0", currency="SYP", **extra):
        body = {"period_type": "day", "year": int(day[:4]), "week_start": day, "currency": currency,
                "item_key": item, "income": income, "expense": expense, **extra}
        return self.client.put(A + "/entries", headers=self.acc, json=body)

    def sheet(self, day):
        return self.client.get(f"{A}/sheet-all?period_type=day&year={day[:4]}&week_start={day}", headers=self.acc).json()

    def close(self, year=2026, month=1, headers=None, note="تم التدقيق"):
        return self.client.post(A + "/periods/close", headers=headers or self.acc, json={"year": year, "month": month, "note": note})

    def reopen(self, year=2026, month=1, headers=None, note="خطأ في الإيصال رقم 5"):
        return self.client.post(A + "/periods/reopen", headers=headers or self.admin, json={"year": year, "month": month, "note": note})

    def actions(self):
        with Session(self.engine) as session:
            return [row.action for row in session.scalars(select(FeeAuditLog).order_by(FeeAuditLog.at)).all()]


class ClosedMonthTests(ControlsBase):
    def test_only_a_finished_month_can_be_closed_and_only_once(self):
        today = __import__("datetime").date.today()
        self.assertEqual(self.close(today.year, today.month).status_code, 422)  # the running month is not finished
        first = self.close()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["closed_by"], "acc")
        self.assertEqual(self.close().status_code, 409)
        listed = self.client.get(A + "/periods?year=2026", headers=self.acc).json()["locks"]
        self.assertEqual([(row["year"], row["month"]) for row in listed], [(2026, 1)])

    def test_the_close_keeps_the_totals_of_that_moment(self):
        self.entry("2026-01-10", "buffet", income="300")
        self.entry("2026-01-11", "operating", expense="120.50")
        snapshot = self.close().json()["snapshot"]
        self.assertEqual(snapshot["SYP"], {"income": "300.00", "expense": "120.50"})
        self.assertEqual(snapshot["USD"], {"income": "0.00", "expense": "0.00"})

    def test_nothing_dated_in_a_closed_month_can_change(self):
        charge = self.charge(month=1)
        paid = self.pay(charge, "400", "2026-01-10")
        self.assertEqual(paid.status_code, 201)
        payment_id = paid.json()["payments"][0]["id"]
        saved = self.entry("2026-01-12", "buffet", income="50")
        entry_id = next(line["id"] for item in saved.json()["rows"] if item["key"] == "buffet" for line in [item] if line["id"])
        salary = self.client.post(A + "/salaries", headers=self.acc, json={
            "employee_name": "Rima", "year": 2026, "month": 1, "currency": "SYP", "base": "500", "paid_on": "2026-01-28"}).json()
        self.assertEqual(self.close().status_code, 201)
        # payments
        self.assertEqual(self.pay(charge, "10", "2026-01-20").status_code, 423)
        self.assertEqual(self.client.patch(f"{F}/payments/{payment_id}", headers=self.acc, json={"amount": "300", "paid_on": "2026-01-10"}).status_code, 423)
        self.assertEqual(self.client.patch(f"{F}/payments/{payment_id}", headers=self.acc, json={"amount": "300", "paid_on": "2026-02-10"}).status_code, 423)
        self.assertEqual(self.client.delete(f"{F}/payments/{payment_id}", headers=self.acc).status_code, 423)
        self.assertEqual(self.refund(charge, "50", "2026-01-25").status_code, 423)
        # fees owed in that month
        self.assertEqual(self.client.patch(f"{F}/charges/{charge['id']}", headers=self.acc, json={"amount": "2000"}).status_code, 423)
        self.assertEqual(self.client.delete(f"{F}/charges/{charge['id']}", headers=self.acc).status_code, 423)
        self.assertEqual(self.client.post(F + "/generate", headers=self.acc, json={"year": 2026, "month": 1, "amount": "10", "currency": "SYP"}).status_code, 423)
        # sheets
        self.assertEqual(self.entry("2026-01-12", "buffet", income="60").status_code, 423)
        self.assertEqual(self.entry("2026-01-13", "custom", expense="5", item_label="Repair").status_code, 423)
        self.assertEqual(self.client.delete(f"{A}/entries/{entry_id}", headers=self.acc).status_code, 423)
        weekly = self.client.put(A + "/entries", headers=self.acc, json={
            "period_type": "week", "year": 2026, "week_start": "2026-01-12", "currency": "SYP", "item_key": "misc", "expense": "1"})
        self.assertEqual(weekly.status_code, 423)
        monthly = self.client.put(A + "/entries", headers=self.acc, json={
            "period_type": "month", "year": 2026, "month": 1, "currency": "SYP", "item_key": "misc", "expense": "1"})
        self.assertEqual(monthly.status_code, 423)
        # a week that only touches the closed month with its first days is closed as well
        straddling = self.client.put(A + "/entries", headers=self.acc, json={
            "period_type": "week", "year": 2026, "week_start": "2026-01-26", "currency": "SYP", "item_key": "misc", "expense": "1"})
        self.assertEqual(straddling.status_code, 423)
        # payroll
        self.assertEqual(self.client.post(A + "/salaries", headers=self.acc, json={
            "employee_name": "Dina", "year": 2026, "month": 1, "currency": "SYP", "base": "100"}).status_code, 423)
        self.assertEqual(self.client.post(A + "/salaries", headers=self.acc, json={
            "employee_name": "Dina", "year": 2025, "month": 12, "currency": "SYP", "base": "100", "paid_on": "2026-01-05"}).status_code, 423)
        self.assertEqual(self.client.patch(f"{A}/salaries/{salary['id']}", headers=self.acc, json={"base": "900"}).status_code, 423)
        self.assertEqual(self.client.delete(f"{A}/salaries/{salary['id']}", headers=self.acc).status_code, 423)
        self.assertEqual(self.client.post(A + "/salaries/generate", headers=self.acc, json={"year": 2026, "month": 1, "currency": "SYP"}).status_code, 423)
        # nothing of it went through
        row = self.client.get(f"{F}?year=2026&month=1", headers=self.acc).json()["rows"][0]
        self.assertEqual((row["amount"], row["paid"]), ("1000.00", "400.00"))
        self.assertEqual(len(row["payments"]), 1)

    def test_other_months_stay_open_and_the_sheet_says_when_it_is_closed(self):
        self.close()
        january, february = self.sheet("2026-01-15"), self.sheet("2026-02-15")
        self.assertTrue(january["locked"])
        self.assertFalse(february["locked"])
        self.assertEqual(self.entry("2026-02-15", "buffet", income="70").status_code, 200)
        self.assertEqual(self.pay(self.charge(month=2), "100", "2026-02-03").status_code, 201)
        # a correction of January is booked as its own row in the open period
        correction = self.entry("2026-02-16", "custom", expense="25", item_label="تصحيح كانون الثاني", details="إيصال 5 مكرر")
        self.assertEqual(correction.status_code, 200)

    def test_only_the_admin_reopens_and_must_give_a_reason(self):
        charge = self.charge(month=1)
        self.close()
        self.assertEqual(self.reopen(headers=self.acc).status_code, 403)
        self.assertEqual(self.reopen(note="").status_code, 422)
        self.assertEqual(self.reopen(note="abc").status_code, 422)
        self.assertEqual(self.pay(charge, "10", "2026-01-20").status_code, 423)
        self.assertEqual(self.reopen(month=2).status_code, 404)  # a month that was never closed
        done = self.reopen()
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()["locks"], [])
        self.assertEqual(self.pay(charge, "10", "2026-01-20").status_code, 201)
        trail = self.actions()
        self.assertIn("period.close", trail)
        self.assertIn("period.reopen", trail)
        with Session(self.engine) as session:
            reason = session.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "period.reopen")).one().details
        self.assertIn("خطأ في الإيصال", reason)

    def test_the_opening_capital_cannot_restate_a_closed_month(self):
        put = lambda amount: self.client.put(A + "/cash", headers=self.acc, json={
            "currency": "SYP", "opening": amount, "start_year": 2026, "start_month": 1})
        self.assertEqual(put("1000").status_code, 200)
        self.close(month=2)
        self.assertEqual(put("5000").status_code, 423)
        self.assertEqual(self.client.get(A + "/cash", headers=self.acc).json()["SYP"]["opening"], "1000.00")
        # a start after the closed month is not affected
        later = self.client.put(A + "/cash", headers=self.acc, json={"currency": "USD", "opening": "5", "start_year": 2026, "start_month": 3})
        self.assertEqual(later.status_code, 200)

    def test_changed_values_are_written_to_the_audit_log(self):
        self.entry("2026-02-10", "buffet", income="100", details="before")
        self.entry("2026-02-10", "buffet", income="150", details="after")
        sheet = self.sheet("2026-02-10")
        entry_id = next(line["id"] for item in sheet["items"] if item["key"] == "buffet" for line in item["lines"] if line["id"])
        self.client.delete(f"{A}/entries/{entry_id}", headers=self.acc)
        with Session(self.engine) as session:
            details = {row.action: row.details for row in session.scalars(select(FeeAuditLog)).all()}
        self.assertIn("100.00/0.00 «before» → 150.00/0.00", details["entry.update"])
        self.assertIn("150.00/0.00 «after»", details["entry.delete"])

    def test_closing_is_only_for_accountant_and_admin(self):
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.close(headers=headers).status_code, 403)
            self.assertEqual(self.client.get(A + "/periods", headers=headers).status_code, 403)
            self.assertEqual(self.reopen(headers=headers).status_code, 403)
        self.assertEqual(self.client.get(A + "/periods").status_code, 401)
        self.assertEqual(self.close(headers=self.admin).status_code, 201)


class RefundTests(ControlsBase):
    def test_a_refund_is_its_own_booking_and_the_payment_stays(self):
        charge = self.charge(month=2, amount="1000")
        self.pay(charge, "600", "2026-02-05", receipt_no="R-1")
        row = self.refund(charge, "100", "2026-02-09").json()
        self.assertEqual((row["paid"], row["remaining"]), ("500.00", "500.00"))
        amounts = [(p["amount"], p["refund"]) for p in row["payments"]]
        self.assertEqual(amounts, [("600.00", False), ("-100.00", True)])
        with Session(self.engine) as session:
            kept = session.scalars(select(FeePayment).where(FeePayment.receipt_no == "R-1")).one()
            self.assertIsNone(kept.deleted_at)
            self.assertEqual(Decimal(kept.amount), Decimal("600"))
        self.assertIn("payment.refund", self.actions())

    def test_the_cash_follows_the_refund_by_its_date(self):
        charge = self.charge(month=2)
        self.pay(charge, "600", "2026-02-05")
        self.refund(charge, "100", "2026-02-09")
        income = lambda day: next(i for i in self.sheet(day)["items"] if i["key"] == "registration")["lines"][0]["income"]
        self.assertEqual(income("2026-02-05"), "600.00")
        self.assertEqual(income("2026-02-09"), "-100.00")
        monthly = self.client.get(f"{A}/sheet-all?period_type=month&year=2026&month=2", headers=self.acc).json()
        self.assertEqual(monthly["totals"]["SYP"]["income"], "500.00")

    def test_a_refund_has_rules(self):
        charge = self.charge(month=2)
        self.pay(charge, "300", "2026-02-05")
        self.assertEqual(self.refund(charge, "300.01", "2026-02-09").status_code, 422)  # more than was paid
        self.assertEqual(self.refund(charge, "0", "2026-02-09").status_code, 422)
        self.assertEqual(self.refund(charge, "50", "2026-02-09", note="  ").status_code, 422)  # a reason is needed
        self.assertEqual(self.client.post(f"{F}/charges/{charge['id']}/refunds", headers=self.acc, json={"amount": "5", "note": "x"}).status_code, 422)  # date
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.refund(charge, "5", "2026-02-09", headers=headers).status_code, 403)
        ok = self.refund(charge, "300", "2026-02-09")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["paid"], "0.00")
        self.assertEqual(self.refund(charge, "1", "2026-02-10").status_code, 422)  # nothing left to give back

    def test_a_refund_cannot_be_edited_but_can_be_removed(self):
        charge = self.charge(month=2)
        self.pay(charge, "300", "2026-02-05")
        row = self.refund(charge, "100", "2026-02-09").json()
        refund_id = next(p["id"] for p in row["payments"] if p["refund"])
        edit = self.client.patch(f"{F}/payments/{refund_id}", headers=self.acc, json={"amount": "50", "paid_on": "2026-02-09"})
        self.assertEqual(edit.status_code, 422)
        back = self.client.delete(f"{F}/payments/{refund_id}", headers=self.acc).json()
        self.assertEqual(back["paid"], "300.00")


class DoubleClickTests(ControlsBase):
    def test_the_same_payment_twice_in_a_row_is_booked_once(self):
        charge = self.charge(month=2)
        first = self.pay(charge, "100", "2026-02-05", payer_name="Mama")
        second = self.pay(charge, "100", "2026-02-05", payer_name="Mama")
        self.assertEqual((first.status_code, second.status_code), (201, 409))
        self.assertEqual(self.pay(charge, "150", "2026-02-05", payer_name="Mama").status_code, 201)  # another amount is a new payment
        self.assertEqual(self.pay(charge, "100", "2026-02-06", payer_name="Mama").status_code, 201)  # another day too
        row = self.client.get(f"{F}?year=2026&month=2", headers=self.acc).json()["rows"][0]
        self.assertEqual(row["paid"], "350.00")

    def test_the_same_refund_twice_in_a_row_is_booked_once(self):
        charge = self.charge(month=2)
        self.pay(charge, "500", "2026-02-05")
        self.assertEqual(self.refund(charge, "100", "2026-02-09").status_code, 201)
        self.assertEqual(self.refund(charge, "100", "2026-02-09").status_code, 409)


class CashCountTests(ControlsBase):
    def capital(self, amount="1000", currency="SYP"):
        return self.client.put(A + "/cash", headers=self.acc, json={
            "currency": currency, "opening": amount, "start_year": 2026, "start_month": 1})

    def count(self, amount, day="2026-01-12", currency="SYP", headers=None, note=""):
        return self.client.post(A + "/cash/counts", headers=headers or self.acc, json={
            "currency": currency, "counted_on": day, "counted_amount": amount, "note": note})

    def test_a_count_needs_the_opening_capital(self):
        self.assertEqual(self.count("100").status_code, 409)

    def test_the_count_is_compared_with_the_books_of_that_day(self):
        self.capital("1000")
        self.entry("2026-01-10", "buffet", income="200")
        self.entry("2026-01-11", "operating", expense="50")
        self.entry("2026-01-13", "buffet", income="999")  # after the counted day: must not count
        short = self.count("1140", "2026-01-12", note="ناقص عشرة")
        self.assertEqual(short.status_code, 201, short.text)
        self.assertEqual(short.json()["book_amount"], "1150.00")
        self.assertEqual(short.json()["difference"], "-10.00")
        exact = self.count("1150", "2026-01-12")
        self.assertEqual(exact.json()["difference"], "0.00")
        over = self.count("1155.50", "2026-01-12")
        self.assertEqual(over.json()["difference"], "5.50")
        listing = self.client.get(A + "/cash/counts", headers=self.acc).json()
        self.assertEqual(len(listing), 3)
        self.assertEqual(listing[0]["counted_by"], "acc")
        self.assertIn("cash.count", self.actions())

    def test_currencies_are_counted_apart(self):
        self.capital("1000", "SYP")
        self.capital("20", "USD")
        self.entry("2026-01-10", "buffet", income="5", currency="USD")
        self.assertEqual(self.count("25", "2026-01-12", "USD").json()["difference"], "0.00")
        self.assertEqual(self.count("1000", "2026-01-12", "SYP").json()["difference"], "0.00")

    def test_a_count_in_the_future_or_by_the_wrong_role_is_refused(self):
        self.capital()
        self.assertEqual(self.count("10", "2099-01-01").status_code, 422)
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.count("10", headers=headers).status_code, 403)
            self.assertEqual(self.client.get(A + "/cash/counts", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(A + "/cash/counts").status_code, 401)
        self.assertEqual(self.count("-1").status_code, 422)


if __name__ == "__main__":
    unittest.main()
