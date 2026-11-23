"""The accounting: income, expenses, invoices, salaries, the month overview, closing, exports and rights."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CurrencyRate, ExpenseEntry, FeeAuditLog, IncomeEntry
from app.timeutil import local_today
from tests.base import MONEY, PEOPLE, ControlsBase

C = "/api/admin/control"


def month_of(day):
    return f"{day.year}-{day.month:02d}"


def last_month(today):
    first = today.replace(day=1)
    return first - timedelta(days=1)


class MoneyBase(ControlsBase):
    def setUp(self):
        super().setUp()
        self.set_rate("12000")

    def grant(self, name, username="acc"):
        return self.client.post(C + "/grants", headers=self.admin, json={"username": username, "grant": name})

    def invoice(self, items=(("fee", "25"),), currency="USD", headers=None, **extra):
        body = {"issued_on": local_today().isoformat(), "child_id": str(self.child_id()), "currency": currency,
                "items": [{"description": d, "amount": a} for d, a in items], **extra}
        return self.client.post(MONEY + "/invoices", headers=headers or self.acc, json=body)

    def pay(self, invoice_id, amount, currency="USD", **extra):
        body = {"booked_on": local_today().isoformat(), "amount": amount, "currency": currency, **extra}
        return self.client.post(f"{MONEY}/invoices/{invoice_id}/payments", headers=self.acc, json=body)

    def summary(self, month=None, headers=None):
        return self.client.get(f"{MONEY}/summary?month={month or month_of(local_today())}", headers=headers or self.acc).json()

    def close(self, day, headers=None):
        return self.client.post(MONEY + "/closings", headers=headers or self.mgr, json={"year": day.year, "month": day.month})


class IncomeExpenseTests(MoneyBase):
    def test_an_income_in_dollars_and_one_in_pounds_show_both_columns_and_keep_what_was_paid(self):
        dollars = self.income("20", "USD").json()
        pounds = self.income("120000", "SYP").json()
        self.assertEqual((dollars["usd"], dollars["syp"], dollars["currency"], dollars["amount"], dollars["rate"]), ("20.00", "240000", "USD", "20.00", "12000"))
        self.assertEqual((pounds["usd"], pounds["syp"], pounds["currency"], pounds["amount"]), ("10.00", "120000", "SYP", "120000"))
        with Session(self.engine) as s:
            row = s.get(IncomeEntry, __import__("uuid").UUID(pounds["id"]))
            self.assertEqual((row.amount, row.currency, row.rate, row.amount_other), (Decimal("120000.00"), "SYP", Decimal("12000"), Decimal("10.00")))

    def test_an_expense_in_both_currencies(self):
        made = self.expense("5", "USD", recipient="baker").json()
        self.assertEqual((made["usd"], made["syp"], made["recipient"], made["category_ar"]), ("5.00", "60000", "baker", "الطعام"))
        self.assertEqual(self.expense("60000", "SYP").json()["usd"], "5.00")

    def test_a_later_rate_never_changes_what_was_booked(self):
        first = self.income("20", "USD").json()
        self.set_rate("15000", day=local_today())
        again = next(r for r in self.client.get(MONEY + "/income", headers=self.acc).json()["rows"] if r["id"] == first["id"])
        self.assertEqual((again["syp"], again["rate"]), ("240000", "12000"))
        self.assertEqual(self.income("20", "USD", description="second").json()["syp"], "300000")

    def test_the_rate_of_the_day_of_the_entry_is_proposed_and_used(self):
        yesterday = local_today() - timedelta(days=1)
        self.set_rate("10000", day=yesterday)
        self.set_rate("13000", day=local_today())
        self.assertEqual(self.income("10", "USD", day=yesterday).json()["syp"], "100000")
        self.assertEqual(self.client.get(f"{MONEY}/rates?day={yesterday.isoformat()}", headers=self.acc).json()["for_day"], "10000")

    def test_rounding_is_half_up_whole_pounds_and_cents(self):
        self.set_rate("12345", day=local_today())
        self.assertEqual(self.income("0.50", "USD").json()["syp"], "6173")  # 6172.5
        self.set_rate("3", day=local_today() + timedelta(days=0))
        with Session(self.engine) as s:  # the newest rate of the same day wins
            self.assertEqual(s.scalars(select(CurrencyRate).order_by(CurrencyRate.created_at.desc())).first().syp_per_usd, Decimal("3"))
        self.assertEqual(self.income("5", "SYP", description="second").json()["usd"], "1.67")

    def test_wrong_input_is_refused_by_the_server(self):
        self.assertEqual(self.income("0").status_code, 422)
        self.assertEqual(self.income("-5").status_code, 422)
        self.assertEqual(self.income("5", "EUR").status_code, 422)
        self.assertEqual(self.income("5", day=local_today() + timedelta(days=1)).status_code, 422)
        self.assertEqual(self.income("5", description="").status_code, 422)
        self.assertEqual(self.expense("5", category="parties").status_code, 422)
        self.assertEqual(self.income("5", rate="0", headers=self.mgr).status_code, 422)
        self.assertEqual(self.client.post(MONEY + "/rates", headers=self.mgr, json={"valid_from": "2026-01-01", "syp_per_usd": "-1"}).status_code, 422)

    def test_no_entry_without_a_rate(self):
        with Session(self.engine) as s:
            for row in s.scalars(select(CurrencyRate)):
                s.delete(row)
            s.commit()
        refused = self.income("5")
        self.assertEqual(refused.status_code, 409)
        self.assertIn("سعر", refused.json()["detail"])

    def test_the_accounting_may_type_a_rate_of_its_own(self):
        self.assertEqual(self.income("10", "USD", rate="11000").json()["syp"], "110000")
        self.assertEqual(self.income("10", "USD", rate="12000", description="same").json()["syp"], "120000")  # the rate of the day may be sent
        self.assertEqual(self.income("10", "USD", rate="11500", headers=self.mgr, description="mgr").json()["syp"], "115000")

    def test_a_double_click_books_once(self):
        self.assertEqual(self.income("20").status_code, 201)
        self.assertEqual(self.income("20").status_code, 409)
        self.assertEqual(self.client.get(MONEY + "/income", headers=self.acc).json()["count"], 1)

    def test_the_list_total_shows_the_value_in_both_currencies(self):
        self.income("120000", "SYP")  # all paid in pounds
        self.income("5", "USD", description="second")
        data = self.client.get(MONEY + "/income", headers=self.acc).json()
        self.assertEqual((data["totals"]["USD"], data["totals"]["SYP"]), ("5.00", "120000"))  # really paid
        self.assertEqual(data["totals"]["value"], {"USD": "15.00", "SYP": "180000"})  # the value of everything, in each currency

    def test_search_and_filters(self):
        today = local_today()
        self.income("10", description="bus", key="extra_fees", payer_name="Mona")
        self.income("7", description="gift", key="other_income")
        cat = self.category("extra_fees")
        rows = self.client.get(f"{MONEY}/income?category_id={cat}", headers=self.acc).json()["rows"]
        self.assertEqual([r["description"] for r in rows], ["bus"])
        self.assertEqual([r["description"] for r in self.client.get(MONEY + "/income?q=mon", headers=self.acc).json()["rows"]], ["bus"])
        span = self.client.get(f"{MONEY}/income?date_from={today.isoformat()}&date_to={today.isoformat()}", headers=self.acc).json()
        self.assertEqual(span["count"], 2)
        self.assertEqual(self.client.get(f"{MONEY}/income?month={month_of(today - timedelta(days=400))}", headers=self.acc).json()["count"], 0)
        self.assertEqual(self.client.get(MONEY + "/income?month=2026-13", headers=self.acc).status_code, 422)


class CorrectionTests(MoneyBase):
    def test_the_accountant_changes_an_entry_and_it_keeps_the_rate(self):
        made = self.income("20", "USD").json()
        body = {"booked_on": made["booked_on"], "description": "fee corrected", "category_id": made["category_id"], "amount": "30", "currency": "USD", "expected_version": 1}
        self.set_rate("15000", day=local_today())
        changed = self.client.patch(f"{MONEY}/income/{made['id']}", headers=self.acc, json=body)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual((changed.json()["usd"], changed.json()["syp"], changed.json()["rate"]), ("30.00", "360000", "12000"))
        self.assertEqual(self.client.patch(f"{MONEY}/income/{made['id']}", headers=self.acc, json=body).status_code, 409)  # an old copy
        with Session(self.engine) as s:
            line = s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "income.update")).one()
            self.assertIn('"amount": "20.00"', line.before_json)
            self.assertIn('"amount": "30.00"', line.after_json)
            self.assertEqual(line.actor_name, "acc")

    def test_cancelling_keeps_the_entry_visible_and_out_of_the_totals(self):
        keep, drop = self.income("20").json(), self.income("5", description="second").json()
        self.assertEqual(self.client.post(f"{MONEY}/income/{drop['id']}/void", headers=self.mgr, json={"reason": "x"}).status_code, 422)
        self.assertEqual(self.client.post(f"{MONEY}/income/{drop['id']}/void", headers=self.mgr, json={"reason": "booked twice"}).status_code, 200)
        data = self.client.get(MONEY + "/income", headers=self.acc).json()
        self.assertEqual((data["count"], data["totals"]["USD"]), (1, "20.00"))
        crossed = next(r for r in data["rows"] if r["id"] == drop["id"])
        self.assertEqual((crossed["voided"], crossed["void_reason"], crossed["voided_by"]), (True, "booked twice", "mgr0"))
        self.assertEqual(self.client.post(f"{MONEY}/income/{drop['id']}/void", headers=self.mgr, json={"reason": "again again"}).status_code, 409)
        with Session(self.engine) as s:
            self.assertEqual(len(s.scalars(select(IncomeEntry)).all()), 2)  # nothing was deleted

    def test_a_closed_month_is_locked_and_corrected_by_a_reversal_in_the_open_month(self):
        old = last_month(local_today())
        made = self.expense("5", "USD", day=old).json()
        self.assertEqual(self.close(local_today()).status_code, 422)  # the running month cannot be closed
        self.assertEqual(self.close(old).status_code, 201)
        self.assertEqual(self.close(old).status_code, 409)
        self.assertEqual(self.expense("1", "USD", day=old).status_code, 423)  # nothing new in a closed month
        body = {"booked_on": old.isoformat(), "description": "x2", "category": "food", "amount": "6", "currency": "USD"}
        self.assertEqual(self.client.patch(f"{MONEY}/expenses/{made['id']}", headers=self.mgr, json=body).status_code, 423)
        fixed = self.client.post(f"{MONEY}/expenses/{made['id']}/void", headers=self.mgr, json={"reason": "wrong amount"})
        self.assertEqual(fixed.status_code, 200)
        self.assertIsNotNone(fixed.json()["reversal_id"])
        self.assertEqual(self.summary(month_of(old))["expense"]["usd"], "5.00")  # the closed month did not change
        self.assertEqual(self.summary()["expense"]["usd"], "-5.00")  # the reversal sits in the open month
        self.assertEqual(self.client.post(f"{MONEY}/expenses/{made['id']}/void", headers=self.mgr, json={"reason": "wrong amount"}).status_code, 409)
        self.assertTrue(self.summary(month_of(old))["closed"])
        # reopening with a reason, and logged; the accountant may do it too
        self.assertEqual(self.client.post(f"{MONEY}/closings/{old.year}/{old.month}/reopen", headers=self.acc, json={"reason": "x"}).status_code, 422)
        self.assertEqual(self.client.post(f"{MONEY}/closings/{old.year}/{old.month}/reopen", headers=self.acc, json={"reason": "audit found"}).status_code, 200)
        self.assertEqual(self.expense("1", "USD", day=old, description="late").status_code, 201)
        self.assertIn("month.reopen", self.actions())


class InvoiceTests(MoneyBase):
    def test_an_invoice_is_changed_and_its_old_version_stays_in_the_history(self):
        made = self.invoice(items=(("fee", "20"),)).json()
        body = {"issued_on": made["issued_on"], "child_id": made["child_id"], "payer_name": "", "description": "November", "currency": "USD",
                "items": [{"description": "fee", "amount": "20"}, {"description": "bus", "amount": "6"}]}
        changed = self.client.patch(f"{MONEY}/invoices/{made['id']}", headers=self.acc, json=body)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual((changed.json()["total"]["usd"], changed.json()["description"], changed.json()["number"]), ("26.00", "November", made["number"]))
        self.pay(made["id"], "20")
        self.assertEqual(self.client.patch(f"{MONEY}/invoices/{made['id']}", headers=self.acc, json={**body, "currency": "SYP"}).status_code, 409)  # paid in dollars
        lower = {**body, "items": [{"description": "fee", "amount": "15"}]}
        self.assertEqual(self.client.patch(f"{MONEY}/invoices/{made['id']}", headers=self.acc, json=lower).status_code, 422)  # below what was paid
        self.assertEqual(self.client.get(f"{MONEY}/invoices/{made['id']}", headers=self.acc).json()["total"]["usd"], "26.00")
        history = self.client.get(f"{MONEY}/history/{made['id']}", headers=self.acc).json()
        self.assertEqual([h["action"] for h in history], ["invoice.create", "invoice.update"])
        self.assertIn('"amount": "20.00"', str(history[1]["before"]))
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.patch(f"{MONEY}/invoices/{made['id']}", headers=headers, json=body).status_code, 403)

    def test_an_invoice_is_a_claim_not_an_income(self):
        made = self.invoice(items=(("fee", "20"), ("bus", "5"))).json()
        self.assertEqual((made["status"], made["total"]["usd"], made["total"]["syp"], made["open"]["syp"]), ("open", "25.00", "300000", "300000"))
        self.assertTrue(made["number"].startswith("INV-"))
        self.assertEqual(self.summary()["income"]["usd"], "0.00")  # no money came in yet
        self.assertEqual(self.client.get(MONEY + "/income", headers=self.acc).json()["count"], 0)

    def test_open_partly_paid_fully_paid_and_never_more(self):
        made = self.invoice().json()
        part = self.pay(made["id"], "10").json()
        self.assertEqual((part["status"], part["paid"]["usd"], part["paid"]["syp"], part["open"]["usd"], part["open"]["syp"]), ("partial", "10.00", "120000", "15.00", "180000"))
        self.assertEqual(self.pay(made["id"], "15.01", payer_name="x").status_code, 422)  # more than is open, never cut off
        rest = self.pay(made["id"], "180000", "SYP").json()  # the rest in pounds, at the rate of the payment
        self.assertEqual((rest["status"], rest["open"]["usd"], rest["open"]["syp"]), ("paid", "0.00", "0"))
        self.assertEqual([(p["currency"], p["amount"], p["credited"]) for p in rest["payments"]], [("USD", "10.00", "10.00"), ("SYP", "180000", "15.00")])
        summary = self.summary()
        self.assertEqual((summary["income"]["usd"], summary["income"]["syp"]), ("10.00", "180000"))  # each payment once, in its real currency
        self.assertEqual(self.client.get(MONEY + "/income", headers=self.acc).json()["count"], 2)

    def test_the_status_is_never_typed_and_a_cancelled_payment_opens_the_invoice_again(self):
        made = self.invoice(status="paid").json()  # an unknown field changes nothing
        self.assertEqual(made["status"], "open")
        paid = self.pay(made["id"], "25").json()
        self.assertEqual(paid["status"], "paid")
        payment = paid["payments"][0]["id"]
        self.client.post(f"{MONEY}/income/{payment}/void", headers=self.mgr, json={"reason": "wrong receipt"})
        again = self.client.get(f"{MONEY}/invoices/{made['id']}", headers=self.acc).json()
        self.assertEqual((again["status"], again["open"]["usd"]), ("open", "25.00"))

    def test_a_later_rate_never_changes_an_invoice(self):
        made = self.invoice().json()
        self.set_rate("15000", day=local_today())
        again = self.client.get(f"{MONEY}/invoices/{made['id']}", headers=self.acc).json()
        self.assertEqual((again["total"]["syp"], again["rate"]), ("300000", "12000"))

    def test_an_invoice_with_payments_cannot_be_cancelled_and_lists_filter(self):
        made = self.invoice().json()
        self.pay(made["id"], "5")
        self.assertEqual(self.client.post(f"{MONEY}/invoices/{made['id']}/void", headers=self.mgr, json={"reason": "not needed"}).status_code, 409)
        other = self.invoice(items=(("x", "3"),)).json()
        self.assertEqual(self.client.post(f"{MONEY}/invoices/{other['id']}/void", headers=self.mgr, json={"reason": "not needed"}).status_code, 200)
        self.assertEqual([r["number"] for r in self.client.get(MONEY + "/invoices?status=unpaid", headers=self.acc).json()["rows"]], [made["number"]])
        self.assertEqual(self.summary()["invoices"]["partial"], 1)


class SalaryTests(MoneyBase):
    def test_a_salary_is_an_expense_once_per_person_and_month(self):
        person = self.hire("Lina", salary="300000", salary_currency="SYP").json()
        key = month_of(local_today())
        before = self.client.get(f"{MONEY}/salaries?month={key}", headers=self.acc).json()
        self.assertEqual((before["paid"], before["unpaid"], before["rows"][0]["salary"]), (0, 1, "300000"))
        self.assertEqual(self.expense("300000", "SYP", category="salaries").status_code, 422)  # person and month are needed
        paid = self.expense("300000", "SYP", category="salaries", employee_id=person["id"], salary_month=key, description="salary")
        self.assertEqual(paid.status_code, 201, paid.text)
        self.assertEqual(paid.json()["employee"], "Lina")
        twice = self.expense("300000", "SYP", category="salaries", employee_id=person["id"], salary_month=key, description="salary again")
        self.assertEqual(twice.status_code, 409)
        after = self.client.get(f"{MONEY}/salaries?month={key}", headers=self.acc).json()
        self.assertEqual((after["paid"], after["unpaid"]), (1, 0))
        self.assertEqual(self.summary()["salaries"]["syp"], "300000")
        # cancelled: the person counts as not paid again, and can be paid
        self.client.post(f"{MONEY}/expenses/{paid.json()['id']}/void", headers=self.mgr, json={"reason": "wrong amount"})
        self.assertEqual(self.client.get(f"{MONEY}/salaries?month={key}", headers=self.acc).json()["unpaid"], 1)
        self.assertEqual(self.expense("310000", "SYP", category="salaries", employee_id=person["id"], salary_month=key, description="salary new").status_code, 201)

    def test_a_person_who_left_stays_in_the_old_payments(self):
        person = self.hire("Lina").json()
        key = month_of(local_today())
        made = self.expense("100", "USD", category="salaries", employee_id=person["id"], salary_month=key, description="salary").json()
        self.client.delete(f"{PEOPLE}/employees/{person['id']}", headers=self.mgr)
        row = next(r for r in self.client.get(MONEY + "/expenses", headers=self.acc).json()["rows"] if r["id"] == made["id"])
        self.assertEqual(row["employee"], "Lina")
        self.assertEqual([r["name"] for r in self.client.get(f"{MONEY}/salaries?month={key}", headers=self.acc).json()["rows"]], ["Lina"])

    def test_the_staff_list_is_read_only_for_the_accounting(self):
        self.assertEqual(self.client.post(PEOPLE + "/employees", headers=self.acc, json={"name": "New"}).status_code, 403)
        self.assertEqual(self.client.get(PEOPLE + "/employees", headers=self.acc).status_code, 200)
        self.assertEqual(self.client.get(PEOPLE + "/employees/export.pdf", headers=self.acc).status_code, 200)  # the staff list as PDF for the accounting


class SummaryTests(MoneyBase):
    def test_each_currency_is_added_on_its_own_from_the_money_really_paid(self):
        self.income("20", "USD")
        self.income("120000", "SYP")
        self.expense("5", "USD")
        self.expense("60000", "SYP", category="rent")
        data = self.summary()
        self.assertEqual((data["income"]["usd"], data["income"]["syp"]), ("20.00", "120000"))
        self.assertEqual((data["expense"]["usd"], data["expense"]["syp"]), ("5.00", "60000"))
        self.assertEqual((data["surplus"]["usd"], data["surplus"]["syp"]), ("15.00", "60000"))
        # the same money valued in one currency with the stored rates, shown apart and never added on top
        self.assertEqual((data["converted"]["income"]["usd"], data["converted"]["income"]["syp"]), ("30.00", "360000"))
        self.assertEqual((data["income_count"], data["expense_count"]), (2, 2))
        self.assertEqual({c["category"] for c in data["expense_by_category"]}, {"food", "rent"})
        self.assertEqual(data["other_expenses"]["usd"], "5.00")

    def test_comparison_with_the_month_before_and_older_months(self):
        old = last_month(local_today())
        self.income("10", "USD", day=old)
        self.income("15", "USD")
        data = self.summary()
        self.assertEqual((data["previous_month"], data["previous"]["income"]["usd"]), (month_of(old), "10.00"))
        self.assertEqual((data["change"]["income"]["usd"]["difference"], data["change"]["income"]["usd"]["percent"]), ("5.00", "50.0"))
        self.assertEqual(self.summary(month_of(old))["income"]["usd"], "10.00")


    def test_the_result_of_each_currency_is_also_given_in_the_other_currency(self):
        self.income("20", "USD")
        self.expense("5", "USD")
        self.income("120000", "SYP", description="pounds in")
        data = self.summary()
        self.assertEqual((data["surplus"]["usd"], data["surplus_value"]["usd"]), ("15.00", "180000"))  # 15 dollars at 12000
        self.assertEqual((data["surplus"]["syp"], data["surplus_value"]["syp"]), ("120000", "10.00"))  # 120000 pounds at 12000

class ExportTests(MoneyBase):
    def test_income_expenses_and_the_month_are_separate_signed_pdfs(self):
        self.income("20", "USD")
        self.expense("60000", "SYP")
        for kind, name in (("income", "income-"), ("expenses", "expenses-"), ("summary", "report-")):
            response = self.client.get(f"{MONEY}/export/{kind}.pdf", headers=self.acc)
            self.assertEqual(response.status_code, 200, kind)
            self.assertEqual(response.headers["content-type"], "application/pdf")
            self.assertIn(name, response.headers["content-disposition"])
            self.assertTrue(response.content.startswith(b"%PDF"))
            for other in ("csv", "xlsx", "doc"):
                self.assertEqual(self.client.get(f"{MONEY}/export/{kind}.{other}", headers=self.acc).status_code, 422)
        self.assertTrue({"export.income", "export.expenses", "export.summary"} <= set(self.actions()))
        empty = self.client.get(f"{MONEY}/export/income.pdf?month=2020-01", headers=self.mgr)
        self.assertTrue(empty.content.startswith(b"%PDF"))  # a month without entries is still a document

    def test_the_list_totals_count_only_money_really_paid_in_each_currency(self):
        from app import pdfs

        rows = [{"booked_on": "2026-11-01", "description": "a", "category": "x", "usd": "20.00", "syp": "240000", "amount": "20.00", "currency": "USD", "voided": False},
                {"booked_on": "2026-11-02", "description": "b", "category": "x", "usd": "10.00", "syp": "120000", "amount": "120000", "currency": "SYP", "voided": False},
                {"booked_on": "2026-11-03", "description": "c", "category": "x", "usd": "5.00", "syp": "60000", "amount": "5.00", "currency": "USD", "voided": True}]
        signer = pdfs.signer_of("acc", "accountant")
        same = pdfs.verification(["income", "2026-11", "20.00", "120000", "2"])
        self.assertTrue(pdfs.entries_pdf("income", "2026-11", rows, signer).startswith(b"%PDF"))
        self.assertEqual(same, pdfs.verification(["income", "2026-11", "20.00", "120000", "2"]))  # the code of exactly these totals


class RightsTests(MoneyBase):
    def test_who_may_do_what(self):
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(MONEY + "/meta", headers=headers).status_code, 403)
            self.assertEqual(self.income("5", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(MONEY + "/meta").status_code, 401)
        meta = self.client.get(MONEY + "/meta", headers=self.acc).json()
        self.assertEqual(meta["rights"], {"record": True, "correct": True, "export": True, "manage": True})  # the accountant may do everything
        self.assertTrue(all(self.client.get(MONEY + "/meta", headers=self.mgr).json()["rights"].values()))
        self.assertEqual(self.set_rate("13000", headers=self.acc).status_code, 201)
        made = self.client.post(MONEY + "/categories", headers=self.acc, json={"name": "Trips"})
        self.assertEqual(made.status_code, 201)
        renamed = self.client.patch(f"{MONEY}/categories/{made.json()['id']}", headers=self.acc, json={"name": "School trips"})
        self.assertEqual(renamed.json()["name"], "School trips")
        self.assertEqual(self.client.patch(f"{MONEY}/categories/{self.category('tuition')}", headers=self.mgr, json={"is_active": False}).status_code, 409)

    def test_every_change_is_logged_with_user_and_time(self):
        made = self.income("20").json()
        self.client.post(f"{MONEY}/income/{made['id']}/void", headers=self.mgr, json={"reason": "booked twice"})
        history = self.client.get(f"{MONEY}/history/{made['id']}", headers=self.acc).json()
        self.assertEqual([(h["action"], h["actor"]) for h in history], [("income.create", "acc"), ("income.void", "mgr0")])
        self.assertTrue(all(h["at"] for h in history))
        self.assertEqual(history[1]["reason"], "booked twice")
        mine = self.client.get("/api/admin/activity", headers=self.acc).json()
        self.assertEqual({r["actor"] for r in mine}, {"acc"})  # an accountant sees only their own lines


class AutomaticRateTests(ControlsBase):
    """No rate typed by anyone: the system fetches today's rate by itself, once a day."""

    def test_the_rate_of_today_is_fetched_by_itself_once_and_stored(self):
        from unittest.mock import patch

        with patch("app.money.fetch_online_rate", return_value=Decimal("12500")) as feed:
            meta = self.client.get(MONEY + "/meta", headers=self.acc).json()
            self.assertEqual((meta["rate"]["syp_per_usd"], meta["rate"]["source"], meta["rate"]["stale"]), ("12500", "auto", False))
            self.client.get(MONEY + "/meta", headers=self.acc)
            self.assertEqual(feed.call_count, 1)  # stored for the day: the feed is not asked again
            made = self.income("10", "USD").json()  # the accountant can book at once
            self.assertEqual((made["syp"], made["rate"]), ("125000", "12500"))
        self.assertIn("rate.auto", self.actions())

    def test_a_correction_by_the_management_beats_the_fetched_rate(self):
        from unittest.mock import patch

        with patch("app.money.fetch_online_rate", return_value=Decimal("12500")):
            self.client.get(MONEY + "/meta", headers=self.acc)
        self.set_rate("13000", day=local_today())
        meta = self.client.get(MONEY + "/meta", headers=self.acc).json()
        self.assertEqual((meta["rate"]["syp_per_usd"], meta["rate"]["source"]), ("13000", "manual"))

    def test_a_feed_that_is_down_keeps_the_last_rate_and_says_it_is_old(self):
        self.set_rate("12000", day=local_today() - timedelta(days=3))
        meta = self.client.get(MONEY + "/meta", headers=self.acc).json()  # the feed answers nothing (the test patch)
        self.assertEqual((meta["rate"]["syp_per_usd"], meta["rate"]["stale"]), ("12000", True))

    def test_the_feed_quote_in_new_pounds_is_turned_into_old_pounds(self):
        from unittest.mock import MagicMock, patch

        from app import money

        real = self.feed.temp_original  # the real function (the test base replaces it so nothing reaches the internet)
        money._feed_blocked_until = None
        reply = MagicMock()
        reply.json.return_value = {"rates": {"SYP": 121.66}}
        with patch("app.money.httpx.get", return_value=reply):
            self.assertEqual(real(), Decimal("12166"))
        reply.json.return_value = {"rates": {"SYP": 12950.5}}
        with patch("app.money.httpx.get", return_value=reply):
            self.assertEqual(real(), Decimal("12951"))  # already old pounds: only rounded to whole pounds
        with patch("app.money.httpx.get", side_effect=RuntimeError("offline")):
            self.assertIsNone(real())
        money._feed_blocked_until = None


class PdfTests(MoneyBase):
    def test_an_invoice_is_a_signed_pdf_with_the_logo(self):
        made = self.invoice(items=(("fee", "20"), ("bus", "5"))).json()
        self.pay(made["id"], "10")
        response = self.client.get(f"{MONEY}/invoices/{made['id']}.pdf", headers=self.acc)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn(made["number"] + ".pdf", response.headers["content-disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(b"/Subtype /Image", response.content)  # the logo is in the file
        self.assertIn("export.invoice_pdf", self.actions())
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(f"{MONEY}/invoices/{made['id']}.pdf", headers=headers).status_code, 403)

    def test_the_month_report_is_a_signed_pdf_for_those_who_may_export(self):
        self.income("20", "USD")
        self.expense("60000", "SYP")
        response = self.client.get(MONEY + "/export/summary.pdf", headers=self.mgr)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_the_verification_code_follows_the_figures(self):
        from app import pdfs

        a = pdfs.verification(["invoice", "INV-2026-0001", "25.00"])
        self.assertEqual(a, pdfs.verification(["invoice", "INV-2026-0001", "25.00"]))
        self.assertNotEqual(a, pdfs.verification(["invoice", "INV-2026-0001", "26.00"]))  # a changed number no longer matches
        self.assertRegex(a, r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")


class AutomaticSalaryTests(MoneyBase):
    """On the 1st of a month the salaries of the month before are booked by themselves."""

    def at(self, day):
        from unittest.mock import patch

        return patch("app.money.local_today", return_value=day)

    def meta(self):
        return self.client.get(MONEY + "/meta", headers=self.acc).json()

    def salary_rows(self):
        with Session(self.engine) as s:
            return s.scalars(select(ExpenseEntry).where(ExpenseEntry.category == "salaries").order_by(ExpenseEntry.recipient)).all()

    def test_nothing_older_is_booked_and_the_next_month_is_booked_on_the_first(self):
        self.hire("Lina", salary="300000", salary_currency="SYP")
        self.hire("Rana", salary="150", salary_currency="USD")
        self.hire("NoSalary")
        with self.at(date(2026, 11, 16)):
            self.meta()  # the first visit only marks November as the start
        self.assertEqual(self.salary_rows(), [])
        with self.at(date(2026, 12, 1)):
            self.meta()
            self.meta()  # a second visit books nothing twice
        rows = self.salary_rows()
        self.assertEqual([(r.recipient, r.amount, r.currency, r.salary_month, r.booked_on, r.created_by) for r in rows], [
            ("Lina", Decimal("300000.00"), "SYP", "2026-11", date(2026, 12, 1), "auto"),
            ("Rana", Decimal("150.00"), "USD", "2026-11", date(2026, 12, 1), "auto"),
        ])
        self.assertEqual((rows[0].rate, rows[1].amount_other), (Decimal("12000"), Decimal("1800000.00")))
        with self.at(date(2026, 12, 5)):
            data = self.client.get(f"{MONEY}/summary?month=2026-12", headers=self.acc).json()
            self.assertEqual((data["salaries"]["usd"], data["salaries"]["syp"]), ("150.00", "300000"))
            listed = self.client.get(f"{MONEY}/salaries?month=2026-11", headers=self.acc).json()
            self.assertEqual((listed["paid"], listed["unpaid"]), (2, 1))  # the person without a salary is not paid
            self.assertTrue(all(r["automatic"] for r in listed["rows"] if r["paid"]))
        self.assertIn("salary.auto", self.actions())

    def test_a_salary_paid_by_hand_or_cancelled_is_not_booked_again(self):
        lina = self.hire("Lina", salary="300000", salary_currency="SYP").json()
        rana = self.hire("Rana", salary="150", salary_currency="USD").json()
        with self.at(date(2026, 11, 16)):
            self.meta()
            self.expense("280000", "SYP", category="salaries", employee_id=lina["id"], salary_month="2026-11", description="salary with advance", day=date(2026, 11, 16))
        with self.at(date(2026, 12, 1)):
            self.meta()
        self.assertEqual(sorted((str(r.employee_id), r.amount, r.created_by) for r in self.salary_rows()), sorted([(lina["id"], Decimal("280000.00"), "acc"), (rana["id"], Decimal("150.00"), "auto")]))
        auto = next(r for r in self.salary_rows() if r.recipient == "Rana")
        with self.at(date(2026, 12, 2)):
            self.assertEqual(self.client.post(f"{MONEY}/expenses/{auto.id}/void", headers=self.mgr, json={"reason": "left in October"}).status_code, 200)
            self.meta()
        self.assertEqual(len(self.salary_rows()), 2)  # the cancelled one is not made again
        self.assertIsNotNone(rana)

    def test_people_who_left_or_start_later_are_not_paid_and_no_rate_means_later(self):
        self.hire("Lina", salary="300000", salary_currency="SYP")
        gone = self.hire("Old", salary="100", salary_currency="USD").json()
        self.client.delete(f"{PEOPLE}/employees/{gone['id']}", headers=self.mgr)
        self.hire("New", salary="200", salary_currency="USD", hired_on="2026-12-10")
        with self.at(date(2026, 11, 16)):
            self.meta()
        with Session(self.engine) as s:
            for row in s.scalars(select(CurrencyRate)):
                s.delete(row)
            s.commit()
        with self.at(date(2026, 12, 1)):
            self.meta()
        self.assertEqual(self.salary_rows(), [])  # no rate: nothing yet
        self.set_rate("12500", day=date(2026, 12, 1))
        with self.at(date(2026, 12, 3)):
            self.meta()
        self.assertEqual([(r.recipient, r.rate) for r in self.salary_rows()], [("Lina", Decimal("12500"))])


    def test_a_salary_deleted_as_a_test_is_not_booked_again_by_the_automatic_run(self):
        lina = self.hire("Lina", salary="300000", salary_currency="SYP").json()
        with self.at(date(2026, 11, 16)):
            self.meta()
        with self.at(date(2026, 12, 1)):
            self.meta()
        auto = self.salary_rows()[0]
        with self.at(date(2026, 12, 2)):
            self.assertEqual(self.client.post(f"{MONEY}/expenses/{auto.id}/test", headers=self.mgr, json={"test": True}).status_code, 200)
            self.client.post(MONEY + "/test-data/purge", headers=self.mgr)
            self.assertEqual(self.salary_rows(), [])
            self.meta()
        self.assertEqual(self.salary_rows(), [])  # nobody wanted it: it stays deleted
        self.assertIsNotNone(lina)


class OpeningBalanceTests(MoneyBase):
    """The money the kindergarten has; income and expenses are added to it, month by month."""

    def opening(self, usd="1000", syp="5000000", day=None, headers=None):
        return self.client.post(MONEY + "/opening", headers=headers or self.mgr, json={"as_of": (day or local_today()).isoformat(), "usd": usd, "syp": syp})

    def test_only_the_management_enters_it_and_it_is_logged(self):
        self.assertEqual(self.opening(headers=self.teacher).status_code, 403)
        self.assertEqual(self.opening(day=local_today() + timedelta(days=1)).status_code, 422)
        self.assertEqual(self.opening(usd="-1").status_code, 422)
        made = self.opening()
        self.assertEqual(made.status_code, 201, made.text)
        self.assertEqual(made.json()["today"], {"USD": "1000.00", "SYP": "5000000"})
        self.assertEqual(self.actions().count("opening.set"), 2)  # one line per currency

    def test_the_month_starts_with_the_money_and_ends_with_it_plus_the_result(self):
        today = local_today()
        self.opening("1000", "5000000", day=today.replace(day=1))
        self.income("200", "USD")
        self.expense("1500000", "SYP")
        self.expense("50", "USD")
        data = self.client.get(f"{MONEY}/summary?month={month_of(today)}", headers=self.acc).json()["balance"]
        self.assertEqual((data["start"]["usd"], data["start"]["syp"]), ("1000.00", "5000000"))
        self.assertEqual((data["profit"]["usd"], data["profit"]["syp"]), ("150.00", "-1500000"))  # profit in dollars, loss in pounds
        self.assertEqual((data["end"]["usd"], data["end"]["syp"]), ("1150.00", "3500000"))
        state = self.client.get(MONEY + "/opening", headers=self.acc).json()
        self.assertEqual(state["today"], {"USD": "1150.00", "SYP": "3500000"})
        self.assertEqual(state["value_today"], {"usd": "1441.67", "syp": "17300000"})  # one value at today's rate, for orientation

    def test_the_next_month_starts_where_the_last_one_ended_and_cancelled_entries_do_not_count(self):
        old = last_month(local_today())
        self.opening("100", "0", day=old.replace(day=1))
        self.income("40", "USD", day=old)
        drop = self.expense("10", "USD", day=old).json()
        self.client.post(f"{MONEY}/expenses/{drop['id']}/void", headers=self.mgr, json={"reason": "booked twice"})
        data = self.client.get(f"{MONEY}/summary?month={month_of(local_today())}", headers=self.acc).json()["balance"]
        self.assertEqual(data["start"]["usd"], "140.00")

    def test_without_an_opening_balance_nothing_is_guessed(self):
        data = self.client.get(MONEY + "/summary", headers=self.acc).json()["balance"]
        self.assertEqual((data["start"]["usd"], data["end"]["syp"]), (None, None))
        self.assertTrue(self.client.get(MONEY + "/export/summary.pdf", headers=self.mgr).content.startswith(b"%PDF"))

    def test_a_correction_is_a_new_entry_and_the_old_one_stays(self):
        self.opening("1000", "0")
        self.opening("1200", "0")
        state = self.client.get(MONEY + "/opening", headers=self.mgr).json()
        self.assertEqual(state["opening"]["USD"]["amount"], "1200.00")
        self.assertEqual([h["amount"] for h in state["history"] if h["currency"] == "USD"], ["1200.00", "1000.00"])


class TestDataTests(MoneyBase):
    def test_trial_entries_are_marked_and_deleted_for_good_without_touching_real_ones(self):
        real = self.income("30", "USD", description="real income").json()
        trial = self.income("20", "USD", description="trial income", test=True).json()
        self.assertEqual((real["is_test"], trial["is_test"]), (False, True))
        self.assertTrue(self.expense("5", "USD", description="trial expense", test=True).json()["is_test"])
        invoice = self.invoice(test=True).json()
        self.assertTrue(invoice["is_test"])
        paid = self.pay(invoice["id"], "10").json()  # a payment of a trial invoice is a trial entry too
        self.assertTrue(all(p["id"] for p in paid["payments"]))
        counts = self.client.get(MONEY + "/test-data", headers=self.acc).json()
        self.assertEqual((counts["income"], counts["expenses"], counts["invoices"], counts["total"]), (2, 1, 1, 4))
        # a trial entry in a cancelled state is deleted as well
        self.client.post(f"{MONEY}/income/{trial['id']}/void", headers=self.acc, json={"reason": "trial cancelled"})
        done = self.client.post(MONEY + "/test-data/purge", headers=self.acc)
        self.assertEqual((done.status_code, done.json()["total"]), (200, 4))
        rows = self.client.get(MONEY + "/income", headers=self.acc).json()["rows"]
        self.assertEqual([r["description"] for r in rows], ["real income"])
        self.assertEqual(self.client.get(MONEY + "/expenses", headers=self.acc).json()["count"], 0)
        self.assertEqual(self.client.get(MONEY + "/invoices", headers=self.acc).json()["rows"], [])
        self.assertEqual(self.client.get(MONEY + "/test-data", headers=self.acc).json()["total"], 0)

    def test_without_the_mark_nothing_is_a_trial(self):
        self.income("20", "USD")
        self.assertEqual(self.client.post(MONEY + "/test-data/purge", headers=self.acc).json()["total"], 0)
        self.assertEqual(self.client.get(MONEY + "/income", headers=self.acc).json()["count"], 1)

    def test_an_old_entry_can_be_marked_as_test_and_then_deleted_and_a_deleted_salary_is_not_booked_again(self):
        old = self.income("30", "USD", description="old by mistake").json()
        keep = self.income("11", "USD", description="keep").json()
        self.client.post(f"{MONEY}/income/{old['id']}/void", headers=self.acc, json={"reason": "cancelled before"})
        marked = self.client.post(f"{MONEY}/income/{old['id']}/test", headers=self.acc, json={"test": True})
        self.assertEqual((marked.status_code, marked.json().get("is_test")), (200, True), marked.text)
        self.assertEqual(self.client.get(MONEY + "/test-data", headers=self.acc).json()["income"], 1)
        self.client.post(MONEY + "/test-data/purge", headers=self.acc)
        rows = self.client.get(MONEY + "/income", headers=self.acc).json()["rows"]
        self.assertEqual([r["id"] for r in rows], [keep["id"]])

    def test_an_invoice_is_marked_with_its_payments_and_the_mark_can_be_taken_away(self):
        invoice = self.invoice().json()
        self.pay(invoice["id"], "10")
        done = self.client.post(f"{MONEY}/invoices/{invoice['id']}/test", headers=self.acc, json={"test": True})
        self.assertTrue(done.json()["is_test"])
        self.assertEqual(self.client.get(MONEY + "/test-data", headers=self.acc).json()["income"], 1)
        payment = self.client.get(MONEY + "/income", headers=self.acc).json()["rows"][0]
        self.assertEqual(self.client.post(f"{MONEY}/income/{payment['id']}/test", headers=self.acc, json={"test": False}).status_code, 409)
        self.client.post(f"{MONEY}/invoices/{invoice['id']}/test", headers=self.acc, json={"test": False})
        self.assertEqual(self.client.get(MONEY + "/test-data", headers=self.acc).json()["total"], 0)


    def test_a_cancelled_entry_is_deleted_for_good_but_a_live_one_is_not(self):
        live = self.income("30", "USD", description="live").json()
        old = self.income("11", "USD", description="old").json()
        self.client.post(f"{MONEY}/income/{old['id']}/void", headers=self.acc, json={"reason": "cancelled before"})
        self.assertEqual(self.client.delete(f"{MONEY}/income/{live['id']}", headers=self.acc).status_code, 409)
        done = self.client.delete(f"{MONEY}/income/{old['id']}", headers=self.acc)
        self.assertEqual((done.status_code, done.json()["deleted"]), (200, True))
        rows = self.client.get(MONEY + "/income", headers=self.acc).json()["rows"]
        self.assertEqual([r["id"] for r in rows], [live["id"]])
        self.assertIn("income.delete", self.actions())

    def test_a_cancelled_invoice_is_deleted_with_its_cancelled_payments_and_one_with_live_payments_is_not(self):
        invoice = self.invoice().json()
        self.assertEqual(self.client.delete(f"{MONEY}/invoices/{invoice['id']}", headers=self.acc).status_code, 409)  # not cancelled
        paid = self.pay(invoice["id"], "10").json()
        pay_id = paid["payments"][0]["id"]
        self.client.post(f"{MONEY}/income/{pay_id}/void", headers=self.acc, json={"reason": "wrong payment"})
        self.client.post(f"{MONEY}/invoices/{invoice['id']}/void", headers=self.acc, json={"reason": "wrong invoice"})
        self.assertEqual(self.client.delete(f"{MONEY}/invoices/{invoice['id']}", headers=self.acc).status_code, 200)
        self.assertEqual(self.client.get(MONEY + "/invoices", headers=self.acc).json()["rows"], [])
        self.assertEqual(self.client.get(MONEY + "/income", headers=self.acc).json()["rows"], [])
