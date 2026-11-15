"""Invoices with US dollars and Syrian pounds side by side: a frozen rate, one rounding rule, payments in either currency."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger as book
from app.models import FeeAuditLog, FeeCharge, FeePayment
from app.timeutil import local_today
from tests.test_ledger import LedgerBase

I = "/api/admin/invoices"
A = "/api/admin/accounting"
D = Decimal


class InvoiceTests(LedgerBase):
    def set_rate(self, value, day=None, reason="", headers=None):
        return self.client.put(A + "/rates", headers=headers or self.mgr, json={"effective_date": (day or local_today()).isoformat(), "syp_per_usd": value, "reason": reason})

    def invoice(self, currency="USD", lines=(("fee", "20"), ("extra", "5")), month=1, year=2026, headers=None):
        body = {"child_id": str(self.child_id()), "year": year, "month": month, "currency": currency,
                "lines": [{"description": d, "amount": a} for d, a in lines]}
        return self.client.post(I, headers=headers or self.acc, json=body)

    def pay(self, invoice_id, currency, amount, on=None, **extra):
        body = {"paid_currency": currency, "paid_amount": amount, "paid_on": (on or local_today()).isoformat(), **extra}
        return self.client.post(f"{I}/{invoice_id}/payments", headers=self.acc, json=body)

    def get(self, invoice_id):
        return self.client.get(f"{I}/{invoice_id}", headers=self.acc).json()

    # ---- both currencies, frozen rate ----
    def test_every_amount_of_an_invoice_is_shown_in_both_currencies(self):
        self.set_rate("12000")
        made = self.invoice()
        self.assertEqual(made.status_code, 201, made.text)
        view = made.json()
        self.assertEqual(view["base_currency"], "USD")
        self.assertTrue(view["number"].startswith("INV-"))
        self.assertEqual([(l["description"], l["amount"]["USD"], l["amount"]["SYP"]) for l in view["lines"]], [("fee", "20.00", "240000"), ("extra", "5.00", "60000")])
        self.assertEqual((view["total"]["USD"], view["total"]["SYP"]), ("25.00", "300000"))
        self.assertEqual((view["paid"]["USD"], view["paid"]["SYP"], view["open"]["USD"], view["open"]["SYP"]), ("0.00", "0", "25.00", "300000"))
        self.assertEqual((view["rate"]["syp_per_usd"], view["rate"]["frozen"], view["rate"]["source"]), ("12000", True, "manual"))

    def test_a_later_rate_never_changes_an_invoice_that_exists(self):
        self.set_rate("12000")
        first = self.invoice(month=1).json()
        self.set_rate("15000", reason="the market moved")
        again = self.get(first["id"])
        self.assertEqual((again["total"]["SYP"], again["rate"]["syp_per_usd"]), ("300000", "12000"))
        second = self.invoice(month=2).json()
        self.assertEqual((second["total"]["SYP"], second["rate"]["syp_per_usd"]), ("375000", "15000"))

    def test_an_invoice_without_any_rate_is_refused_with_a_clear_message(self):
        refused = self.invoice()
        self.assertEqual(refused.status_code, 409)
        self.assertIn("سعر", refused.json()["detail"])

    def test_rounding_is_half_up_once_per_position_and_the_totals_add_up(self):
        self.set_rate("12345")
        usd = self.invoice("USD", lines=(("a", "0.50"), ("b", "0.50"))).json()  # 6172.5 each -> 6173 each (half up), total = the sum
        self.assertEqual([l["amount"]["SYP"] for l in usd["lines"]], ["6173", "6173"])
        self.assertEqual(usd["total"]["SYP"], "12346")
        self.set_rate("3", reason="test rate for rounding")
        syp = self.invoice("SYP", lines=(("a", "5"), ("b", "5")), month=3).json()  # 5/3 = 1.666 -> 1.67 each
        self.assertEqual([l["amount"]["USD"] for l in syp["lines"]], ["1.67", "1.67"])
        self.assertEqual(syp["total"]["USD"], "3.34")

    # ---- payments in either currency ----
    def test_a_payment_in_dollars_reduces_both_columns_and_closes_at_zero(self):
        self.set_rate("12000")
        view = self.invoice().json()
        step1 = self.pay(view["id"], "USD", "10").json()
        self.assertEqual((step1["paid"]["USD"], step1["paid"]["SYP"], step1["open"]["USD"], step1["open"]["SYP"]), ("10.00", "120000", "15.00", "180000"))
        step2 = self.pay(view["id"], "SYP", "60000", payer_name="mother").json()  # 5 dollars at the rate of the day
        self.assertEqual((step2["open"]["USD"], step2["open"]["SYP"]), ("10.00", "120000"))
        self.assertEqual([(p["currency"], p["amount"], p["credited"]) for p in step2["payments"]], [("USD", "10.00", "10.00"), ("SYP", "60000", "5.00")])
        done = self.pay(view["id"], "USD", "10", payer_name="father").json()
        self.assertEqual((done["open"]["USD"], done["open"]["SYP"], done["paid"]["SYP"], done["status"]), ("0.00", "0", "300000", "paid"))

    def test_a_pound_invoice_paid_in_dollars_keeps_the_dollars_that_were_handed_over(self):
        self.set_rate("12000")
        view = self.invoice("SYP", lines=(("fee", "300000"),)).json()
        self.assertEqual((view["total"]["USD"], view["total"]["SYP"]), ("25.00", "300000"))
        after = self.pay(view["id"], "USD", "10").json()
        self.assertEqual((after["paid"]["SYP"], after["paid"]["USD"], after["open"]["SYP"], after["open"]["USD"]), ("120000", "10.00", "180000", "15.00"))
        payment = after["payments"][0]
        self.assertEqual((payment["currency"], payment["amount"], payment["credited"], payment["rate"]), ("USD", "10.00", "120000", "12000"))
        with Session(self.engine) as s:
            row = s.scalars(select(FeePayment)).one()
            self.assertEqual((row.paid_currency, row.paid_amount, row.amount, row.pay_rate), ("USD", D("10.00"), D("120000.00"), D("12000")))

    def test_the_payment_uses_the_rate_of_its_own_day_and_a_different_rate_needs_a_reason(self):
        yesterday = local_today() - timedelta(days=1)
        self.set_rate("10000", day=yesterday)
        self.set_rate("12000")
        view = self.invoice("SYP", lines=(("fee", "300000"),)).json()
        old = self.pay(view["id"], "USD", "10", on=yesterday).json()
        self.assertEqual(old["payments"][0]["credited"], "100000")  # the rate that was valid that day
        silent = self.pay(view["id"], "USD", "1", rate="11000")
        self.assertEqual(silent.status_code, 422)
        stated = self.pay(view["id"], "USD", "1", rate="11000", rate_reason="agreed with the parent")
        self.assertEqual(stated.status_code, 201, stated.text)
        self.assertEqual(stated.json()["payments"][-1]["rate"], "11000")
        with Session(self.engine) as s:
            line = s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "payment.create").order_by(FeeAuditLog.at.desc())).first()
            self.assertEqual(line.reason, "agreed with the parent")

    def test_too_much_is_refused_and_nothing_is_cut_off(self):
        self.set_rate("12000")
        view = self.invoice().json()
        over = self.pay(view["id"], "USD", "25.01")
        self.assertEqual(over.status_code, 422)
        self.assertEqual(self.pay(view["id"], "SYP", "301000").status_code, 422)
        self.assertEqual(self.get(view["id"])["paid"]["USD"], "0.00")

    def test_a_payment_in_the_other_currency_needs_a_rate(self):
        self.payment("1000", date(2026, 1, 5))  # an old pound fee line, and no rate has ever been saved
        with Session(self.engine) as s:
            charge_id = str(s.scalars(select(FeeCharge)).one().id)
        refused = self.pay(charge_id, "USD", "1", on=date(2026, 1, 6))
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(self.pay(charge_id, "SYP", "500", on=date(2026, 1, 7)).status_code, 201)  # same currency: no rate needed

    # ---- the cash book counts the money that really arrived ----
    def test_the_cash_book_counts_the_currency_that_was_handed_over(self):
        self.set_rate("12000")
        view = self.invoice("SYP", lines=(("fee", "300000"),)).json()
        self.pay(view["id"], "USD", "10")
        with Session(self.engine) as s:
            usd = [m for m in book.movements(s, "USD") if m.source == "fee_payment"]
            syp = [m for m in book.movements(s, "SYP") if m.source == "fee_payment"]
        self.assertEqual([m.amount for m in usd], [D("10.00")])
        self.assertEqual(syp, [])

    def test_a_cancelled_payment_leaves_the_invoice_open_again_and_stays_visible(self):
        self.set_rate("12000")
        self.make_live()
        view = self.invoice().json()
        paid = self.pay(view["id"], "USD", "10").json()
        gone = self.client.post(f"/api/admin/accounting/finance/payments/{paid['payments'][0]['id']}/void", headers=self.acc, json={"reason": "wrong receipt"})
        self.assertEqual(gone.status_code, 200, gone.text)
        after = self.get(view["id"])
        self.assertEqual((after["paid"]["USD"], after["open"]["USD"]), ("0.00", "25.00"))
        self.assertEqual([(p["voided"], p["void_reason"]) for p in after["payments"]], [(True, "wrong receipt")])

    # ---- rights ----
    def test_who_may_use_invoices(self):
        self.set_rate("12000")
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(I, headers=headers).status_code, 403)
            self.assertEqual(self.invoice(headers=headers).status_code, 403)
        self.assertEqual(self.invoice(headers=self.mgr).status_code, 201)  # the management may manage invoices
        self.assertEqual(self.client.get(I, headers=self.mgr).status_code, 200)
        self.assertEqual(self.client.get(A + "/rates", headers=self.mgr).status_code, 200)  # and the accountant look at the rate
        self.assertEqual(self.set_rate("13000", reason="not allowed", headers=self.acc).status_code, 403)  # the accountant cannot set it: the management does

    def test_the_list_sums_each_currency_in_its_own_currency_only(self):
        self.set_rate("12000")
        self.invoice("USD", month=1)
        self.invoice("SYP", lines=(("fee", "100000"),), month=2)
        data = self.client.get(I, headers=self.acc).json()
        self.assertEqual((data["totals"]["USD"]["total"], data["totals"]["SYP"]["total"]), ("25.00", "100000"))
        self.assertEqual(len(data["rows"]), 2)

    # ---- changing positions, numbers, history ----
    def test_changing_positions_needs_a_reason_keeps_the_frozen_rate_and_logs_before_and_after(self):
        self.set_rate("12000")
        view = self.invoice().json()
        self.set_rate("15000", reason="moved again")
        body = {"lines": [{"description": "fee", "amount": "30"}], "reason": "price corrected", "expected_version": view["version"]}
        self.assertEqual(self.client.put(f"{I}/{view['id']}/lines", headers=self.acc, json={**body, "reason": "x"}).status_code, 422)
        changed = self.client.put(f"{I}/{view['id']}/lines", headers=self.acc, json=body)
        self.assertEqual(changed.status_code, 200, changed.text)
        data = changed.json()
        self.assertEqual((data["total"]["USD"], data["total"]["SYP"], data["rate"]["syp_per_usd"]), ("30.00", "360000", "12000"))
        stale = self.client.put(f"{I}/{view['id']}/lines", headers=self.acc, json=body)
        self.assertEqual(stale.status_code, 409)  # somebody else (or an earlier save) changed it
        with Session(self.engine) as s:
            line = s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "invoice.update")).one()
            self.assertIn('"total": "25.00"', line.before_json)
            self.assertIn('"total": "30.00"', line.after_json)
            self.assertEqual(line.reason, "price corrected")

    def test_the_total_cannot_fall_below_what_is_paid(self):
        self.set_rate("12000")
        view = self.invoice().json()
        self.pay(view["id"], "USD", "20")
        low = self.client.put(f"{I}/{view['id']}/lines", headers=self.acc, json={"lines": [{"description": "x", "amount": "10"}], "reason": "price corrected"})
        self.assertEqual(low.status_code, 422)

    def test_invoice_numbers_run_on_and_one_invoice_per_child_month_and_currency(self):
        self.set_rate("12000")
        first, second = self.invoice(month=1).json(), self.invoice(month=2).json()
        self.assertEqual((first["number"], second["number"]), ("INV-2026-0001", "INV-2026-0002"))
        self.assertEqual(self.invoice(month=1).status_code, 409)

    def test_changing_a_saved_rate_needs_a_reason_and_is_logged_with_old_and_new_value(self):
        self.set_rate("12000")
        self.assertEqual(self.set_rate("12500").status_code, 422)
        self.assertEqual(self.set_rate("12500", reason="new market rate").status_code, 200)
        history = self.client.get(A + "/rates", headers=self.acc).json()
        self.assertEqual((history["rates"][0]["rate"], history["rates"][0]["reason"]), ("12500", "new market rate"))
        with Session(self.engine) as s:
            line = s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "rate.set").order_by(FeeAuditLog.at.desc())).first()
            self.assertIn("12000", line.before_json)
            self.assertIn("12500", line.after_json)

    # ---- old fee lines ----
    def test_an_old_fee_line_shows_both_currencies_and_the_backfill_freezes_it_without_touching_money(self):
        self.payment("1000", date(2026, 1, 5))  # an old line: 100000 SYP, 1000 paid, made before any rate existed
        with Session(self.engine) as s:
            old = s.scalars(select(FeeCharge)).one()
            self.assertIsNone(old.rate_syp_per_usd)
            charge_id = str(old.id)
        self.set_rate("12000", day=date(2026, 1, 1))
        seen = self.get(charge_id)
        self.assertEqual((seen["rate"]["source"], seen["rate"]["frozen"]), ("reconstructed", False))
        self.assertEqual((seen["total"]["SYP"], seen["total"]["USD"], seen["paid"]["SYP"], seen["open"]["SYP"]), ("100000", "8.33", "1000", "99000"))
        self.assertEqual(self.client.post(I + "/backfill", headers=self.acc).status_code, 403)
        look = self.client.post(I + "/backfill", headers=self.admin).json()
        self.assertEqual((look["applied"], look["rate_frozen"]), (False, 1))
        with Session(self.engine) as s:
            self.assertIsNone(s.scalars(select(FeeCharge)).one().rate_syp_per_usd)  # a look changes nothing
        done = self.client.post(I + "/backfill?apply=true", headers=self.admin).json()
        self.assertEqual((done["applied"], done["rate_frozen"]), (True, 1))
        again = self.client.post(I + "/backfill?apply=true", headers=self.admin).json()
        self.assertEqual((again["rate_frozen"], again["numbered"]), (0, 0))
        with Session(self.engine) as s:
            row = s.scalars(select(FeeCharge)).one()
            self.assertEqual((row.rate_syp_per_usd, row.rate_source, row.amount), (D("12000"), "reconstructed", D("100000.00")))
            self.assertTrue(row.invoice_no.startswith("INV-2026-"))
            self.assertEqual(s.scalars(select(FeePayment)).one().amount, D("1000.00"))
        self.set_rate("20000", day=date(2026, 1, 20), reason="later")
        self.assertEqual(self.get(charge_id)["total"]["USD"], "8.33")  # frozen now
