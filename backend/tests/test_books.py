"""The three accounting pages: income, expenses and the month overview, every amount in US dollars and Syrian pounds."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashTransaction, ExchangeRate, FeeAuditLog
from app.timeutil import local_today
from tests.test_ledger import LedgerBase

B = "/api/admin/books"
A = "/api/admin/accounting"
C = "/api/admin/control"
D = Decimal


def month_of(day):
    return f"{day.year}-{day.month:02d}"


class BooksTests(LedgerBase):
    def setUp(self):
        super().setUp()
        self.make_live()
        self.set_rate("12000")

    def set_rate(self, value, day=None, reason="", headers=None):
        return self.client.put(A + "/rates", headers=headers or self.mgr, json={"effective_date": (day or local_today()).isoformat(), "syp_per_usd": value, "reason": reason})

    def grant(self, name, username="acc"):
        return self.client.post(C + "/grants", headers=self.admin, json={"username": username, "grant": name})

    def add(self, kind="income", amount="20", currency="USD", category=None, day=None, headers=None, **extra):
        body = {"kind": kind, "booked_on": (day or local_today()).isoformat(), "description": "test", "category": category or ("donations" if kind == "income" else "material"),
                "amount": amount, "currency": currency, **extra}
        return self.client.post(B + "/entries", headers=headers or self.mgr, json=body)

    def rows(self, kind="income", month=None, headers=None, query=""):
        return self.client.get(f"{B}/entries?kind={kind}&month={month or month_of(local_today())}{query}", headers=headers or self.mgr).json()

    # ---- rights ----
    def test_nobody_sees_the_pages_without_the_right(self):
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(B + "/status", headers=headers).status_code, 403)
            self.assertEqual(self.add(headers=headers).status_code, 403)
        self.assertEqual(self.client.get(B + "/status", headers=self.acc).status_code, 403)  # an accountant needs the grant
        self.assertEqual(self.client.get(B + "/status", headers=self.mgr).status_code, 200)
        self.assertEqual(self.client.get(B + "/status", headers=self.admin).status_code, 200)

    def test_an_accountant_reads_with_books_view_and_writes_only_with_books_write(self):
        self.assertEqual(self.grant("books.view").status_code, 201)
        self.assertEqual(self.client.get(f"{B}/entries?kind=income", headers=self.acc).status_code, 200)
        self.assertEqual(self.add(headers=self.acc).status_code, 403)
        self.assertEqual(self.grant("books.write").status_code, 201)
        self.assertEqual(self.add(headers=self.acc).status_code, 201)
        self.assertFalse(self.client.get(B + "/status", headers=self.acc).json()["can_set_rate"])  # the rate is the management's

    def test_the_rate_is_set_by_the_management_and_only_looked_at_by_the_accountant(self):
        self.grant("books.view")
        self.assertEqual(self.set_rate("13000", reason="new market rate", headers=self.acc).status_code, 403)
        self.assertEqual(self.set_rate("13000", reason="new market rate").status_code, 200)

    # ---- both currencies and the frozen rate ----
    def test_every_entry_shows_both_currencies_and_keeps_what_was_really_paid(self):
        dollars = self.add(amount="20", currency="USD").json()
        pounds = self.add(amount="120000", currency="SYP").json()
        self.assertEqual((dollars["usd"], dollars["syp"], dollars["paid_currency"], dollars["paid_amount"]), ("20.00", "240000", "USD", "20.00"))
        self.assertEqual((pounds["usd"], pounds["syp"], pounds["paid_currency"], pounds["paid_amount"]), ("10.00", "120000", "SYP", "120000"))
        self.assertEqual((dollars["rate"]["syp_per_usd"], dollars["rate"]["source"]), ("12000", "manual"))

    def test_a_later_rate_never_changes_an_old_entry(self):
        made = self.add(amount="20", currency="USD").json()
        self.set_rate("15000", reason="the market moved")
        again = next(r for r in self.rows()["rows"] if r["id"] == made["id"])
        self.assertEqual((again["syp"], again["rate"]["syp_per_usd"]), ("240000", "12000"))
        self.assertEqual(self.add(amount="20", currency="USD").json()["syp"], "300000")  # a new entry uses the new rate

    def test_the_rate_of_the_day_of_the_booking_is_used(self):
        yesterday = local_today() - timedelta(days=1)
        self.set_rate("10000", day=yesterday)
        old = self.add(amount="10", currency="USD", day=yesterday).json()
        self.assertEqual((old["syp"], old["rate"]["syp_per_usd"]), ("100000", "10000"))

    def test_rounding_is_half_up_whole_pounds_and_cents(self):
        self.set_rate("12345", reason="odd rate for the test")
        self.assertEqual(self.add(amount="0.50", currency="USD").json()["syp"], "6173")  # 6172.5
        self.set_rate("3", reason="another test rate")
        self.assertEqual(self.add(amount="5", currency="SYP").json()["usd"], "1.67")  # 1.666...

    # ---- checks ----
    def test_wrong_entries_are_refused(self):
        self.assertEqual(self.add(day=local_today() + timedelta(days=1)).status_code, 422)  # a future date
        self.assertEqual(self.add(kind="income", category="rent").status_code, 422)  # a category of the other page
        self.assertEqual(self.add(amount="0").status_code, 422)
        child = self.child_id()
        self.assertEqual(self.add(kind="expense", category="material", child_id=str(child)).status_code, 422)  # a child belongs to income
        self.assertEqual(self.add(kind="income", category="donations", employee_id=str(child)).status_code, 422)  # a person of the staff belongs to salaries

    def test_no_entry_without_a_rate(self):
        with Session(self.engine) as s:
            for row in s.scalars(select(ExchangeRate)):
                s.delete(row)
            s.commit()
        refused = self.add()
        self.assertEqual(refused.status_code, 409)
        self.assertIn("سعر", refused.json()["detail"])

    def test_a_salary_is_tied_to_a_person_of_the_staff_and_a_fee_to_a_child(self):
        person = self.client.post(A + "/employees", headers=self.mgr, json={"name": "Lina Ali", "job_title": "teacher"}).json()
        pay = self.add(kind="expense", category="salaries", amount="300000", currency="SYP", employee_id=person["id"]).json()
        self.assertEqual(pay["employee"], "Lina Ali")
        fee = self.add(kind="income", category="fees", amount="25", currency="USD", child_id=str(self.child_id())).json()
        self.assertEqual(fee["child"], "Amal")
        self.client.delete(f"{A}/employees/{person['id']}", headers=self.mgr)  # a person who leaves stays in the old bookings
        again = next(r for r in self.rows("expense")["rows"] if r["id"] == pay["id"])
        self.assertEqual(again["employee"], "Lina Ali")

    # ---- changing and cancelling ----
    def test_an_entry_is_changed_with_a_reason_and_the_frozen_rate_stays(self):
        made = self.add(amount="20", currency="USD").json()
        self.set_rate("15000", reason="the market moved")
        body = {"amount": "30", "reason": "typing mistake", "expected_version": made["version"]}
        self.assertEqual(self.client.patch(f"{B}/entries/{made['id']}", headers=self.mgr, json={"amount": "30"}).status_code, 422)  # no reason
        changed = self.client.patch(f"{B}/entries/{made['id']}", headers=self.mgr, json=body)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual((changed.json()["usd"], changed.json()["syp"], changed.json()["rate"]["syp_per_usd"]), ("30.00", "360000", "12000"))
        self.assertEqual(self.client.patch(f"{B}/entries/{made['id']}", headers=self.mgr, json=body).status_code, 409)  # an old copy
        fresh = self.client.patch(f"{B}/entries/{made['id']}", headers=self.mgr, json={"amount": "30", "reason": "take today's rate", "refresh_rate": True}).json()
        self.assertEqual((fresh["syp"], fresh["rate"]["syp_per_usd"]), ("450000", "15000"))
        with Session(self.engine) as s:
            line = s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "booking.update").order_by(FeeAuditLog.at)).first()
            self.assertIn('"amount": "20.00"', line.before_json)
            self.assertIn('"amount": "30.00"', line.after_json)
            self.assertEqual(line.reason, "typing mistake")

    def test_only_this_and_last_month_can_be_changed_and_older_ones_only_cancelled(self):
        old_day = (local_today().replace(day=1) - timedelta(days=70))
        self.set_rate("12000", day=old_day)
        made = self.add(day=old_day)
        self.assertEqual(made.status_code, 201)  # booking late is allowed while the month is open
        refused = self.client.patch(f"{B}/entries/{made.json()['id']}", headers=self.mgr, json={"amount": "21", "reason": "typing mistake"})
        self.assertEqual(refused.status_code, 423)
        self.assertFalse(next(r for r in self.rows(month=month_of(old_day))["rows"] if r["id"] == made.json()["id"])["editable"])
        gone = self.client.post(f"{B}/entries/{made.json()['id']}/void", headers=self.mgr, json={"reason": "booked twice"})
        self.assertEqual(gone.status_code, 200)

    def test_a_cancelled_entry_stays_visible_and_leaves_the_totals(self):
        keep, drop = self.add(amount="20").json(), self.add(amount="5").json()
        self.assertEqual(self.client.post(f"{B}/entries/{drop['id']}/void", headers=self.mgr, json={"reason": "x"}).status_code, 422)
        self.assertEqual(self.client.post(f"{B}/entries/{drop['id']}/void", headers=self.mgr, json={"reason": "booked twice"}).status_code, 200)
        data = self.rows()
        self.assertEqual((data["count"], data["total"]["usd"], data["total"]["syp"]), (1, "20.00", "240000"))
        crossed = next(r for r in data["rows"] if r["id"] == drop["id"])
        self.assertEqual((crossed["voided"], crossed["void_reason"]), (True, "booked twice"))
        self.assertEqual(self.client.post(f"{B}/entries/{drop['id']}/void", headers=self.mgr, json={"reason": "again again"}).status_code, 409)
        with Session(self.engine) as s:
            self.assertEqual(s.scalars(select(CashTransaction)).all().__len__(), 2)  # nothing was deleted

    # ---- filters ----
    def test_filter_by_category_and_by_dates(self):
        today = local_today()
        self.add(category="donations", amount="10")
        self.add(category="other_income", amount="7")
        self.add(category="donations", amount="3", day=today - timedelta(days=1) if today.day > 1 else today)
        self.assertEqual({r["category"] for r in self.rows(query="&category=donations")["rows"]}, {"donations"})
        start = today.isoformat()
        only_today = self.client.get(f"{B}/entries?kind=income&date_from={start}&date_to={start}", headers=self.mgr).json()
        self.assertTrue(all(r["day"] == start for r in only_today["rows"]))

    # ---- the month overview ----
    def test_the_overview_adds_each_column_alone_and_shows_the_real_cash_apart(self):
        self.add("income", "20", "USD", category="donations")
        self.add("income", "120000", "SYP", category="other_income")
        self.add("expense", "5", "USD", category="material")
        self.add("expense", "60000", "SYP", category="rent")
        data = self.client.get(f"{B}/summary?month={month_of(local_today())}", headers=self.mgr).json()
        self.assertEqual((data["income"]["usd"], data["income"]["syp"]), ("30.00", "360000"))  # 20 + 10, 240000 + 120000
        self.assertEqual((data["expense"]["usd"], data["expense"]["syp"]), ("10.00", "120000"))
        self.assertEqual((data["surplus"]["usd"], data["surplus"]["syp"]), ("20.00", "240000"))
        self.assertEqual(data["real_cash"]["USD"], {"income": "20.00", "expense": "5.00"})  # the money that really came in dollars
        self.assertEqual(data["real_cash"]["SYP"], {"income": "120000", "expense": "60000"})
        self.assertEqual(data["counts"], {"income": 2, "expense": 2})
        self.assertEqual({c["category"] for c in data["income_by_category"]}, {"donations", "other_income"})
        self.assertEqual(data["missing_rate"], 0)

    def test_the_overview_compares_with_the_month_before(self):
        today = local_today()
        first = today.replace(day=1)
        last_month = first - timedelta(days=1)
        self.set_rate("12000", day=last_month.replace(day=1))
        self.add("income", "10", "USD", day=last_month)
        self.add("income", "15", "USD")
        data = self.client.get(f"{B}/summary?month={month_of(today)}", headers=self.mgr).json()
        self.assertEqual(data["previous_month"], month_of(last_month))
        self.assertEqual(data["previous"]["income"]["usd"], "10.00")
        self.assertEqual((data["change"]["income"]["usd"]["difference"], data["change"]["income"]["usd"]["percent"]), ("5.00", "50.0"))
        empty = self.client.get(f"{B}/summary?month={month_of(last_month - timedelta(days=200))}", headers=self.mgr).json()
        self.assertEqual(empty["income"]["usd"], "0.00")
        self.assertEqual(self.client.get(f"{B}/summary?month=2026-13", headers=self.mgr).status_code, 422)

    # ---- the old data appear in the same pages ----
    def test_old_fee_and_salary_payments_show_up_with_both_currencies(self):
        self.payment("50000", local_today(), year=local_today().year, month=local_today().month)  # a fee payment in pounds (old way)
        self.salary("Rima", "300000", year=local_today().year, month=local_today().month, paid_on=local_today())
        income = self.rows("income")
        fee = next(r for r in income["rows"] if r["from_fees"])
        self.assertEqual((fee["syp"], fee["usd"], fee["rate"]["source"]), ("50000", "4.17", "reconstructed"))
        self.assertFalse(fee["editable"])
        salary = next(r for r in self.rows("expense")["rows"] if r["from_salary"])
        self.assertEqual((salary["syp"], salary["usd"]), ("300000", "25.00"))
        # an old fee payment can be cancelled from the income page (with a reason)
        gone = self.client.post(f"{B}/entries/{fee['id']}/void", headers=self.mgr, json={"reason": "wrong receipt"})
        self.assertEqual(gone.status_code, 200, gone.text)
        self.assertEqual(self.rows("income")["count"], 0)

    def test_the_pages_work_read_only_before_the_cash_book_is_live(self):
        with Session(self.engine) as s:
            from app.models import LedgerCutover

            s.delete(s.get(LedgerCutover, 1))
            s.commit()
        self.assertFalse(self.client.get(B + "/status", headers=self.mgr).json()["live"])
        refused = self.add()
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(self.client.get(f"{B}/entries?kind=income", headers=self.mgr).status_code, 200)
