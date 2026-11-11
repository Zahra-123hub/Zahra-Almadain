"""The guided accounting workflow: step statuses, receipts, the closing check, the weekly check and the archive file."""

import io
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FeeAuditLog
from tests.test_accounting_controls import A, ControlsBase, F

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40
STEP_ORDER = ["basics", "staff", "fees", "income", "expenses", "payroll", "reconcile", "summary", "reports", "close", "archive"]


class WorkflowTests(ControlsBase):
    def flow(self, year=2026, month=1, headers=None):
        response = self.client.get(f"{A}/workflow?year={year}&month={month}", headers=headers or self.acc)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def status(self, key, **kw):
        return {step["key"]: step for step in self.flow(**kw)["steps"]}[key]

    def capital(self, amount="1000"):
        return self.client.put(A + "/cash", headers=self.acc, json={"currency": "SYP", "opening": amount, "start_year": 2026, "start_month": 1})

    def count(self, amount, day="2026-01-12", currency="SYP", headers=None):
        return self.client.post(A + "/cash/counts", headers=headers or self.acc, json={"currency": currency, "counted_on": day, "counted_amount": amount})

    def flag_for_review(self, charge_id):
        from app.models import FeeCharge

        with Session(self.engine) as session:
            row = session.get(FeeCharge, __import__("uuid").UUID(charge_id))
            row.needs_review = True
            session.commit()

    def saved_row(self, response, key):
        return next(row for row in response.json()["rows"] if row["key"] == key and row["id"])

    def upload(self, entry_id, name="bill.pdf", content=PDF, headers=None):
        return self.client.post(f"{A}/entries/{entry_id}/receipts", headers=headers or self.acc, files={"file": (name, content)})

    # ---- the order and the first state ----
    def test_the_steps_come_in_working_order_and_start_pending(self):
        data = self.flow()
        self.assertEqual([s["key"] for s in data["steps"]], STEP_ORDER)
        self.assertEqual([s["n"] for s in data["steps"]], list(range(1, 12)))
        self.assertEqual({s["status"] for s in data["steps"]}, {"pending"})
        self.assertEqual(data["next"], "basics")
        self.assertTrue(data["ended"])
        self.assertFalse(data["locked"])

    def test_both_accountant_and_admin_see_the_same_list_nobody_else(self):
        self.assertEqual(self.flow(headers=self.admin)["steps"], self.flow(headers=self.acc)["steps"])
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(f"{A}/workflow", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(f"{A}/workflow").status_code, 401)
        self.assertEqual(self.client.get(f"{A}/workflow?year=2026&month=13", headers=self.acc).status_code, 422)

    # ---- the statuses follow the work ----
    def test_basics_fees_and_income_follow_the_work(self):
        self.assertEqual(self.status("basics")["status"], "pending")
        self.capital()
        self.assertEqual(self.status("basics")["status"], "in_progress")
        self.client.put(A + "/rates", headers=self.acc, json={"effective_date": "2026-01-02", "syp_per_usd": "15000"})
        self.assertEqual(self.status("basics")["status"], "done")
        self.assertEqual(self.status("fees")["status"], "pending")
        charge = self.charge(month=1, amount="1000")
        self.assertEqual(self.status("fees")["status"], "done")
        self.assertEqual((self.status("income")["status"], self.status("income")["issues"]), ("pending", [{"kind": "open_fees", "count": 1}]))
        self.pay(charge, "400", "2026-01-10")
        self.assertEqual(self.status("income")["status"], "in_progress")
        self.pay(charge, "600", "2026-01-11")
        self.assertEqual((self.status("income")["status"], self.status("income")["issues"]), ("done", []))

    def test_expenses_without_a_receipt_are_flagged_until_one_is_added(self):
        self.capital()
        saved = self.entry("2026-01-12", "operating", expense="40")
        row = self.saved_row(saved, "operating")
        step = self.status("expenses")
        self.assertEqual((step["status"], step["issues"]), ("in_progress", [{"kind": "missing_receipts", "count": 1}]))
        sheet_line = [line for item in self.sheet("2026-01-12")["items"] if item["key"] == "operating" for line in item["lines"]][0]
        self.assertTrue(sheet_line["needs_receipt"])
        self.assertEqual((sheet_line["receipts"], sheet_line["receipt_no"]), (0, ""))
        # a receipt number is enough ...
        again = self.entry("2026-01-12", "operating", expense="40", receipt_no="R-17")
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(self.status("expenses")["status"], "done")
        # ... and so is an attached file
        self.entry("2026-01-13", "purchases", expense="10")
        self.assertEqual(self.status("expenses")["status"], "in_progress")
        other = self.saved_row(self.entry("2026-01-13", "purchases", expense="10"), "purchases")
        self.assertEqual(self.upload(other["id"]).status_code, 201)
        self.assertEqual(self.status("expenses")["status"], "done")
        self.assertEqual(row["id"], self.saved_row(again, "operating")["id"])

    def test_salaries_and_cash_count_statuses(self):
        self.capital()
        self.assertEqual(self.status("staff")["status"], "pending")
        self.hire("Rima")
        salary = self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Rima", "year": 2026, "month": 1, "currency": "SYP", "base": "500"})
        self.assertEqual(salary.status_code, 201, salary.text)
        self.assertEqual((self.status("staff")["status"], self.status("payroll")["status"]), ("done", "pending"))
        self.client.patch(f"{A}/salaries/{salary.json()['id']}", headers=self.acc, json={"paid_on": "2026-01-28"})
        self.assertEqual(self.status("payroll")["status"], "done")
        self.assertEqual(self.status("reconcile")["status"], "pending")
        self.assertEqual(self.count("1", "2026-01-12").status_code, 201)
        step = self.status("reconcile")
        self.assertEqual((step["status"], step["issues"]), ("in_progress", [{"kind": "cash_difference", "count": 1}]))
        book = self.client.get(A + "/cash/counts", headers=self.acc).json()[0]["book_amount"]
        self.count(book, "2026-01-13")
        self.assertEqual(self.status("reconcile")["status"], "done")

    def test_next_step_moves_on_and_a_whole_month_ends_closed_and_archived(self):
        self.capital()
        self.client.put(A + "/rates", headers=self.acc, json={"effective_date": "2026-01-02", "syp_per_usd": "15000"})
        charge = self.charge(month=1, amount="1000")
        self.pay(charge, "1000", "2026-01-10")
        self.entry("2026-01-12", "operating", expense="40", receipt_no="R-1")
        self.hire("Rima")
        salary = self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Rima", "year": 2026, "month": 1, "currency": "SYP", "base": "500", "paid_on": "2026-01-28"})
        self.assertEqual(salary.status_code, 201)
        book = self.count("1", "2026-01-30").json()["book_amount"]
        self.count(book, "2026-01-31")
        data = self.flow()
        self.assertEqual(data["next"], "summary" if data["steps"][7]["status"] != "done" else "reports")
        self.assertEqual({s["key"]: s["status"] for s in data["steps"]}["close"], "in_progress")  # ready to close
        self.assertEqual(data["close"]["blockers"], [])
        self.assertEqual(self.status("archive")["status"], "pending")
        self.assertEqual(self.close().status_code, 201)
        data = self.flow()
        self.assertTrue(data["locked"])
        self.assertEqual(({s["key"]: s["status"] for s in data["steps"]}["close"], {s["key"]: s["status"] for s in data["steps"]}["archive"]), ("done", "in_progress"))
        self.assertEqual(self.client.get(f"{A}/periods/2026/1/export.xlsx", headers=self.acc).status_code, 200)
        self.assertEqual(self.status("archive")["status"], "done")

    # ---- closing ----
    def test_closing_is_refused_while_flagged_lines_wait_for_review(self):
        made = self.charge(month=1)
        self.flag_for_review(made["id"])
        data = self.flow()
        self.assertEqual([b["kind"] for b in data["close"]["blockers"]], ["review_fees"])
        refused = self.close()
        self.assertEqual(refused.status_code, 422, refused.text)
        self.client.post(f"{F}/charges/{made['id']}/reviewed", headers=self.acc)
        self.assertEqual(self.close().status_code, 201)

    def test_warnings_are_listed_but_do_not_block(self):
        self.capital()
        self.entry("2026-01-12", "operating", expense="40")
        self.hire("Rima")
        self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Rima", "year": 2026, "month": 1, "currency": "SYP", "base": "500"})
        warnings = {w["kind"]: w["count"] for w in self.flow()["close"]["warnings"]}
        self.assertEqual(warnings, {"missing_receipts": 1, "unpaid_salaries": 1, "no_cash_count": 1})
        self.assertEqual(self.close().status_code, 201)

    def test_the_current_month_cannot_be_closed_yet(self):
        from datetime import date

        today = date.today()
        data = self.flow(today.year, today.month)
        self.assertFalse(data["ended"])
        self.assertEqual([b["kind"] for b in data["close"]["blockers"]], ["not_ended"])

    # ---- receipts ----
    def test_receipt_files_are_checked_and_listed_and_removed(self):
        self.capital()
        entry_id = self.saved_row(self.entry("2026-01-12", "operating", expense="40"), "operating")["id"]
        good = self.upload(entry_id)
        self.assertEqual(good.status_code, 201, good.text)
        self.assertEqual((good.json()["name"], good.json()["type"]), ("bill.pdf", "application/pdf"))
        self.assertEqual(self.upload(entry_id, "photo.png", PNG).status_code, 201)
        self.assertEqual(self.upload(entry_id, "evil.exe", b"MZ....").status_code, 422)  # not a receipt type
        self.assertEqual(self.upload(entry_id, "fake.pdf", b"this is not a pdf").status_code, 422)  # the content must match
        self.assertEqual(self.upload(entry_id, "empty.pdf", b"").status_code, 422)
        self.assertEqual(self.upload(entry_id, "big.pdf", b"%PDF-" + b"0" * (3 * 1024 * 1024)).status_code, 413)
        listing = self.client.get(f"{A}/entries/{entry_id}/receipts", headers=self.acc).json()
        self.assertEqual([r["name"] for r in listing], ["bill.pdf", "photo.png"])
        download = self.client.get(f"{A}/receipts/{listing[0]['id']}/download", headers=self.acc)
        self.assertEqual((download.status_code, download.content), (200, PDF))
        self.assertIn("attachment", download.headers["content-disposition"])
        for _ in range(3):
            self.upload(entry_id)
        self.assertEqual(self.upload(entry_id).status_code, 409)  # five at most
        self.assertEqual(self.client.delete(f"{A}/receipts/{listing[0]['id']}", headers=self.acc).status_code, 204)
        self.assertEqual(self.client.delete(f"{A}/receipts/{listing[0]['id']}", headers=self.acc).status_code, 404)

    def test_receipts_follow_the_same_rights_and_the_month_lock(self):
        self.capital()
        entry_id = self.saved_row(self.entry("2026-01-12", "operating", expense="40"), "operating")["id"]
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.upload(entry_id, headers=headers).status_code, 403)
            self.assertEqual(self.client.get(f"{A}/entries/{entry_id}/receipts", headers=headers).status_code, 403)
        receipt = self.upload(entry_id).json()
        self.assertEqual(self.close().status_code, 201)
        self.assertEqual(self.upload(entry_id).status_code, 423)  # a closed month stays as it was
        self.assertEqual(self.client.delete(f"{A}/receipts/{receipt['id']}", headers=self.acc).status_code, 423)
        self.assertEqual(self.client.get(f"{A}/receipts/{receipt['id']}/download", headers=self.acc).status_code, 200)  # reading is fine

    def test_deleting_a_row_removes_its_receipts(self):
        self.capital()
        entry_id = self.saved_row(self.entry("2026-01-12", "operating", expense="40"), "operating")["id"]
        receipt = self.upload(entry_id).json()
        self.assertEqual(self.client.delete(f"{A}/entries/{entry_id}", headers=self.acc).status_code, 200)
        self.assertEqual(self.client.get(f"{A}/receipts/{receipt['id']}/download", headers=self.acc).status_code, 404)

    # ---- the weekly check ----
    def test_week_check_shows_the_week_without_locking_it(self):
        self.capital()
        charge = self.charge(month=1, amount="1000")
        self.pay(charge, "300", "2026-01-13")
        self.entry("2026-01-14", "operating", expense="40")
        self.count("1", "2026-01-15")
        data = self.client.get(f"{A}/week-check?week_start=2026-01-15", headers=self.acc).json()
        self.assertEqual((data["week_start"], data["week_end"]), ("2026-01-12", "2026-01-18"))
        self.assertEqual(data["payments"]["SYP"], {"count": 1, "amount": "300.00"})
        self.assertEqual(data["totals"]["SYP"]["expense"], "40.00")
        checks = {c["kind"]: c for c in data["checks"]}
        self.assertTrue(checks["entries"]["ok"])
        self.assertEqual((checks["missing_receipts"]["ok"], checks["missing_receipts"]["count"]), (False, 1))
        self.assertTrue(checks["cash_count"]["ok"])
        self.assertFalse(checks["cash_difference"]["ok"])
        self.assertEqual(len(data["cash_counts"]), 1)
        self.assertEqual(self.entry("2026-01-15", "operating", expense="5").status_code, 200)  # still editable
        self.assertIn(self.client.get(f"{A}/week-check?week_start=2026-01-15", headers=self.teacher).status_code, (401, 403))

    # ---- the archive file ----
    def test_month_archive_is_an_excel_file_and_every_export_is_logged(self):
        from openpyxl import load_workbook

        self.capital()
        charge = self.charge(month=1, amount="1000")
        self.pay(charge, "1000", "2026-01-10")
        entry_id = self.saved_row(self.entry("2026-01-12", "operating", expense="40"), "operating")["id"]
        self.upload(entry_id)
        self.assertEqual(self.close().status_code, 201)
        response = self.client.get(f"{A}/periods/2026/1/export.xlsx", headers=self.acc)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("attachment", response.headers["content-disposition"])
        book = load_workbook(io.BytesIO(response.content))
        self.assertEqual(book.sheetnames, ["Summary", "Fees", "Salaries", "Entries", "Cash counts"])
        summary = {row[0].value: row[1].value for row in book["Summary"].iter_rows(min_row=2)}
        self.assertEqual((summary["Month"], summary["Status"]), ("1/2026", "closed"))
        self.assertEqual(summary["SYP expense at closing"], 40)
        rows = [[c.value for c in row] for row in book["Entries"].iter_rows(min_row=2)]
        self.assertTrue(any(row[8] == 40 and row[9] == 1 and row[1] == "2026-01-12" for row in rows))  # the row, its amount, its date and the receipt file
        self.assertEqual(book["Fees"]["A2"].value, "Amal")
        with Session(self.engine) as session:
            logged = session.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "export.month")).all()
        self.assertEqual([(row.entity_id, row.details) for row in logged], [("1/2026", "closed")])
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(f"{A}/periods/2026/1/export.xlsx", headers=headers).status_code, 403)

    # ---- the exchange rate knows itself ----
    def test_the_rate_of_today_is_fetched_by_the_system_and_kept(self):
        from datetime import date
        from decimal import Decimal
        from unittest.mock import patch

        self.assertIsNone(self.client.get(A + "/rates", headers=self.acc).json()["current"])  # no feed, nothing stored: nothing guessed
        with patch("app.accounting.fetch_online_rate", return_value=Decimal("12200")):
            state = self.client.get(A + "/rates", headers=self.acc).json()
        self.assertEqual((state["current"]["rate"], state["current"]["source"], state["current"]["stale"]), ("12200", "auto", False))
        self.assertEqual((state["current"]["date"], state["rates"][0]["source"]), (date.today().isoformat(), "auto"))
        again = self.client.get(A + "/rates", headers=self.acc).json()  # kept for the day: the feed is not asked again
        self.assertEqual(again["current"]["rate"], "12200")
        # a typed rate for the same day is never replaced by the feed unless that is asked for
        self.client.put(A + "/rates", headers=self.acc, json={"effective_date": date.today().isoformat(), "syp_per_usd": "13000"})
        with patch("app.accounting.fetch_online_rate", return_value=Decimal("12300")):
            self.assertEqual(self.client.post(A + "/rates/refresh", headers=self.acc).status_code, 409)
            forced = self.client.post(A + "/rates/refresh?force=true", headers=self.acc)
        self.assertEqual((forced.status_code, forced.json()["current"]["rate"], forced.json()["current"]["source"]), (200, "12300", "auto"))
        self.assertEqual(self.client.post(A + "/rates/refresh", headers=self.acc).status_code, 503)  # the feed is down (the test patch): said honestly
        self.assertEqual(self.client.post(A + "/rates/refresh", headers=self.teacher).status_code, 403)

    def test_the_status_list_counts_the_automatic_rate(self):
        from decimal import Decimal
        from unittest.mock import patch

        self.capital()
        self.assertEqual(self.status("basics")["status"], "in_progress")  # no rate yet, no feed
        with patch("app.accounting.fetch_online_rate", return_value=Decimal("12200")):
            self.assertEqual(self.status("basics")["status"], "done")

    # ---- people belong to the management ----
    def test_employees_are_added_by_the_management_and_only_read_by_the_accountant(self):
        E = A + "/employees"
        for headers in (self.acc, self.teacher, self.parent):
            self.assertEqual(self.client.post(E, headers=headers, json={"name": "Hana"}).status_code, 403)
        self.assertEqual(self.client.post(E, headers=self.mgr, json={"name": "Hana", "job_title": "Teacher", "salary": "300", "salary_currency": "SYP"}).status_code, 201)
        self.assertEqual(self.client.post(E, headers=self.admin, json={"name": "Dina"}).status_code, 201)
        listing = self.client.get(E, headers=self.acc).json()  # the accountant still sees the names
        self.assertEqual(sorted(p["name"] for p in listing), ["Dina", "Hana"])
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(E, headers=headers).status_code, 403)
        person = next(p for p in listing if p["name"] == "Hana")
        self.assertEqual(self.client.patch(f"{E}/{person['id']}", headers=self.acc, json={"name": "Hana", "salary": "999"}).status_code, 403)
        self.assertEqual(self.client.delete(f"{E}/{person['id']}", headers=self.acc).status_code, 403)
        self.assertEqual(self.client.patch(f"{E}/{person['id']}", headers=self.mgr, json={"name": "Hana", "salary": "400"}).status_code, 200)
        # the accountant picks a saved person for a salary line; an unknown name is refused (nobody is created by it)
        ok = self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "hana", "year": 2026, "month": 1, "currency": "SYP", "base": "400"})
        self.assertEqual(ok.status_code, 201, ok.text)
        unknown = self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Nobody", "year": 2026, "month": 1, "currency": "SYP", "base": "1"})
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(sorted(p["name"] for p in self.client.get(E, headers=self.acc).json()), ["Dina", "Hana"])
        # a person that was removed comes back only through the management
        self.client.delete(f"{E}/{person['id']}", headers=self.mgr)
        again = self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Hana", "year": 2026, "month": 2, "currency": "SYP", "base": "1"})
        self.assertEqual(again.status_code, 404)

    def test_a_child_that_is_not_saved_cannot_get_a_fee_by_typing_the_name(self):
        made = self.client.post(F + "/charges", headers=self.acc, json={"child_name": "Typed Only", "year": 2026, "month": 1, "amount": "10", "currency": "SYP"})
        self.assertEqual(made.status_code, 404, made.text)
        self.assertNotIn("Typed Only", [c["display_name"] for c in self.client.get(F + "/children", headers=self.acc).json()])
        self.enroll("Typed Only")
        self.assertEqual(self.client.post(F + "/charges", headers=self.acc, json={"child_name": "typed only", "year": 2026, "month": 1, "amount": "10", "currency": "SYP"}).status_code, 201)

    # ---- the net after the conversion is exact ----
    def test_the_converted_net_is_made_from_exact_amounts(self):
        self.client.put(A + "/rates", headers=self.acc, json={"effective_date": "2026-01-01", "syp_per_usd": "12181.8547"})
        self.entry("2026-01-12", "buffet", income="555")
        self.entry("2026-01-12", "buffet", income="0.51", currency="USD")
        self.entry("2026-01-12", "operating", expense="30000")
        sheet = self.sheet("2026-01-12")
        dollars = sheet["converted"]["USD"]
        # 0.5556 - 2.4627 = -1.9071: the rounded income and expense (0.56 and 2.46) must not be subtracted again
        self.assertEqual((dollars["income"], dollars["expense"], dollars["net"]), ("0.56", "2.46", "-1.91"))
        pounds = sheet["converted"]["SYP"]
        self.assertEqual((pounds["income"], pounds["expense"], pounds["net"]), ("6767.75", "30000.00", "-23232.25"))
        self.assertEqual((sheet["totals"]["SYP"]["net"], sheet["totals"]["USD"]["net"]), ("-29445.00", "0.51"))

    # ---- zeroing a table on purpose ----
    def reset_part(self, scopes, year=2026, month=1, confirm="RESET", headers=None):
        return self.client.post(A + "/reset-part", headers=headers or self.admin, json={"year": year, "month": month, "scopes": scopes, "confirm": confirm})

    def test_the_administrator_can_zero_one_part_of_one_month(self):
        self.capital()
        charge = self.charge(month=1, amount="1000")
        self.pay(charge, "400", "2026-01-10")
        self.charge(month=2, amount="500")
        self.hire("Rima")
        self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Rima", "year": 2026, "month": 1, "currency": "SYP", "base": "500"})
        entry_id = self.saved_row(self.entry("2026-01-12", "operating", expense="40"), "operating")["id"]
        self.upload(entry_id)
        self.entry("2026-02-03", "operating", expense="7")
        # only the sheet rows (and their receipts): the fees and the salary stay
        done = self.reset_part(["entries"])
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual((done.json()["entries"], done.json()["receipts"], done.json()["salaries"], done.json()["fees"]), (1, 1, 0, 0))
        self.assertEqual(self.client.get(f"{A}/entries/{entry_id}/receipts", headers=self.acc).status_code, 404)
        self.assertEqual(self.sheet("2026-02-03")["totals"]["SYP"]["expense"], "7.00")  # another month is untouched
        again = self.reset_part(["salaries", "fees"])
        self.assertEqual((again.json()["salaries"], again.json()["fees"], again.json()["payments"]), (1, 1, 1))
        listing = self.client.get(F + "?year=2026&month=2", headers=self.acc).json()["rows"]
        self.assertEqual(len(listing), 1)  # February still has its fee line
        self.assertEqual(self.client.get(f"{F}?year=2026&month=1", headers=self.acc).json()["rows"], [])

    def test_zeroing_needs_the_administrator_the_word_and_an_open_month(self):
        self.charge(month=1, amount="1000")
        for headers in (self.acc, self.mgr, self.teacher, self.parent):
            self.assertIn(self.reset_part(["fees"], headers=headers).status_code, (401, 403))
        self.assertEqual(self.reset_part(["fees"], confirm="").status_code, 422)
        self.assertEqual(self.reset_part(["fees"], confirm="reset").status_code, 422)
        self.assertEqual(self.reset_part(["everything"]).status_code, 422)
        self.assertEqual(self.reset_part([]).status_code, 422)
        self.assertEqual(self.reset_part(["fees"], month=13).status_code, 422)
        self.assertEqual(len(self.client.get(F + "?year=2026&month=1", headers=self.acc).json()["rows"]), 1)  # nothing was removed
        self.assertEqual(self.close().status_code, 201)
        self.assertEqual(self.reset_part(["fees"]).status_code, 423)  # a closed month stays as it was
        self.assertEqual(len(self.client.get(F + "?year=2026&month=1", headers=self.acc).json()["rows"]), 1)

    # ---- two accountants on the same work ----
    def line_of(self, day, key):
        return [line for item in self.sheet(day)["items"] if item["key"] == key for line in item["lines"]][0]

    def save_as(self, headers, day, key, expense, expected=None, **extra):
        body = {"period_type": "day", "year": int(day[:4]), "week_start": day, "currency": "SYP", "item_key": key, "income": "0", "expense": expense, **extra}
        if expected is not None:
            body["expected_version"] = expected
        return self.client.put(A + "/entries", headers=headers, json=body)

    def test_a_row_says_who_changed_it_last_and_when(self):
        self.save_as(self.acc, "2026-01-12", "operating", "40")
        line = self.line_of("2026-01-12", "operating")
        self.assertEqual((line["version"], line["updated_by"]), (1, "acc"))
        self.assertTrue(line["updated_at"])
        self.save_as(self.acc2, "2026-01-12", "operating", "55")
        line = self.line_of("2026-01-12", "operating")
        self.assertEqual((line["version"], line["updated_by"], line["expense"]), (2, "acc2", "55.00"))
        self.assertEqual(self.line_of("2026-01-12", "activities")["version"], 0)  # a row that does not exist yet

    def test_the_second_save_on_an_old_copy_of_a_row_is_refused_and_says_who(self):
        self.save_as(self.acc, "2026-01-12", "operating", "40")
        seen = self.line_of("2026-01-12", "operating")["version"]  # both accountants have this copy open
        self.assertEqual(self.save_as(self.acc2, "2026-01-12", "operating", "50", expected=seen).status_code, 200)
        late = self.save_as(self.acc, "2026-01-12", "operating", "60", expected=seen)
        self.assertEqual(late.status_code, 409, late.text)
        self.assertIn("acc2", late.json()["detail"])  # who changed it
        self.assertIn("50.00", late.json()["detail"])  # and what it says now
        self.assertEqual(self.line_of("2026-01-12", "operating")["expense"], "50.00")  # nothing was overwritten
        again = self.save_as(self.acc, "2026-01-12", "operating", "60", expected=self.line_of("2026-01-12", "operating")["version"])
        self.assertEqual(again.status_code, 200)  # after reading the new state the save works
        self.assertEqual(self.line_of("2026-01-12", "operating")["expense"], "60.00")

    def test_two_people_creating_the_same_row_at_once_are_noticed(self):
        self.assertEqual(self.save_as(self.acc, "2026-01-12", "purchases", "10", expected=0).status_code, 200)
        second = self.save_as(self.acc2, "2026-01-12", "purchases", "20", expected=0)  # saw an empty row
        self.assertEqual(second.status_code, 409, second.text)
        self.assertEqual(self.line_of("2026-01-12", "purchases")["expense"], "10.00")
        # a caller that does not ask for the check still works (older screens)
        self.assertEqual(self.save_as(self.acc2, "2026-01-12", "purchases", "20").status_code, 200)
        # a row that was deleted meanwhile
        row_id = self.line_of("2026-01-12", "purchases")["id"]
        self.client.delete(f"{A}/entries/{row_id}", headers=self.acc)
        self.assertEqual(self.save_as(self.acc2, "2026-01-12", "purchases", "30", expected=5).status_code, 409)

    def test_salary_lines_and_fee_lines_are_protected_the_same_way(self):
        self.hire("Rima")
        made = self.client.post(A + "/salaries", headers=self.acc, json={"employee_name": "Rima", "year": 2026, "month": 1, "currency": "SYP", "base": "500"}).json()
        seen = made["version"]
        self.assertEqual(self.client.patch(f"{A}/salaries/{made['id']}", headers=self.acc2, json={"base": "600", "expected_version": seen}).status_code, 200)
        late = self.client.patch(f"{A}/salaries/{made['id']}", headers=self.acc, json={"base": "700", "expected_version": seen})
        self.assertEqual(late.status_code, 409, late.text)
        self.assertIn("acc2", late.json()["detail"])
        row = [r for r in self.client.get(f"{A}/salaries?year=2026&month=1", headers=self.acc).json()["rows"]][0]
        self.assertEqual((row["base"], row["updated_by"], row["version"]), ("600.00", "acc2", seen + 1))
        charge = self.charge(month=1, amount="1000")
        self.assertEqual(self.client.patch(f"{F}/charges/{charge['id']}", headers=self.acc2, json={"amount": "1100", "expected_version": charge["version"]}).status_code, 200)
        late = self.client.patch(f"{F}/charges/{charge['id']}", headers=self.acc, json={"amount": "1200", "expected_version": charge["version"]})
        self.assertEqual(late.status_code, 409)
        self.assertIn("acc2", late.json()["detail"])
        self.assertEqual(self.client.patch(f"{F}/charges/{charge['id']}", headers=self.acc, json={"amount": "1200"}).status_code, 200)  # no check asked

    # ---- who did what ----
    def test_the_history_of_a_row_shows_every_person(self):
        self.save_as(self.acc, "2026-01-12", "operating", "40")
        self.save_as(self.acc2, "2026-01-12", "operating", "55")
        row_id = self.line_of("2026-01-12", "operating")["id"]
        for headers in (self.acc, self.acc2, self.admin):
            steps = self.client.get(f"{A}/history?kind=entry&id={row_id}", headers=headers).json()
            self.assertEqual([(s["actor"], s["action"]) for s in steps], [("acc2", "entry.update"), ("acc", "entry.create")])
        self.assertIn("40.00", steps[0]["details"])
        for headers in (self.teacher, self.parent, self.mgr):
            self.assertEqual(self.client.get(f"{A}/history?kind=entry&id={row_id}", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(f"{A}/history?kind=wrong&id={row_id}", headers=self.acc).status_code, 422)
        # a fee line shows its payments too
        charge = self.charge(month=1, amount="1000")
        self.pay(charge, "300", "2026-01-10")
        kinds = [s["action"] for s in self.client.get(f"{A}/history?kind=charge&id={charge['id']}", headers=self.acc).json()]
        self.assertEqual(sorted(kinds), ["charge.create", "payment.create"])

    def test_the_log_can_be_filtered_and_an_accountant_sees_only_their_own_work(self):
        self.save_as(self.acc, "2026-01-12", "operating", "40")
        self.save_as(self.acc2, "2026-01-13", "purchases", "15")
        self.client.put(A + "/rates", headers=self.acc2, json={"effective_date": "2026-01-02", "syp_per_usd": "15000"})
        L = "/api/admin/fees/audit"
        mine = self.client.get(L, headers=self.acc).json()
        self.assertEqual({row["actor"] for row in mine}, {"acc"})
        self.assertEqual({row["actor"] for row in self.client.get(L, headers=self.acc2).json()}, {"acc2"})
        self.assertEqual({row["actor"] for row in self.client.get(L + "?actor_name=acc2", headers=self.acc).json()}, {"acc"})  # asking for somebody else changes nothing
        everyone = self.client.get(L, headers=self.admin).json()
        self.assertEqual({row["actor"] for row in everyone}, {"acc", "acc2"})
        self.assertEqual({row["actor"] for row in self.client.get(L + "?actor_name=acc2", headers=self.admin).json()}, {"acc2"})
        self.assertEqual({row["action"] for row in self.client.get(L + "?action=rate.set", headers=self.admin).json()}, {"rate.set"})
        self.assertEqual(len(self.client.get(L + "?q=purchases", headers=self.admin).json()), 1)
        from datetime import date

        today = date.today().isoformat()
        self.assertEqual(len(self.client.get(f"{L}?date_from={today}&date_to={today}", headers=self.admin).json()), len(everyone))
        self.assertEqual(self.client.get(f"{L}?date_to=2000-01-01", headers=self.admin).json(), [])
        self.assertEqual(self.client.get(L + "/actors", headers=self.admin).json(), ["acc", "acc2"])
        self.assertEqual(self.client.get(L + "/actors", headers=self.acc).json(), ["acc"])
        for headers in (self.teacher, self.parent, self.mgr):
            self.assertEqual(self.client.get(L, headers=headers).status_code, 403)
        from openpyxl import load_workbook

        book = load_workbook(io.BytesIO(self.client.get(L + ".xlsx?actor_name=acc2", headers=self.acc).content)).active
        self.assertEqual({row[1].value for row in book.iter_rows(min_row=2)}, {"acc"})  # the export obeys the same rule

    # ---- a step can be confirmed as complete on purpose ----
    def confirm(self, step, year=2026, month=1, note="", headers=None):
        return self.client.post(A + "/workflow/confirm", headers=headers or self.acc, json={"year": year, "month": month, "step": step, "note": note})

    def test_a_step_that_cannot_complete_by_itself_is_confirmed_on_purpose(self):
        # no expenses at all this month: the step would wait for ever
        self.assertEqual(self.status("expenses")["status"], "pending")
        done = self.confirm("expenses", note="لا توجد مصروفات هذا الشهر")
        self.assertEqual(done.status_code, 200, done.text)
        step = self.status("expenses")
        self.assertEqual((step["status"], step["confirmed"]["by"], step["confirmed"]["note"]), ("done", "acc", "لا توجد مصروفات هذا الشهر"))
        # open fees: the step is complete on purpose, the open points stay listed
        self.charge(month=1, amount="1000")
        self.assertEqual(self.status("income")["status"], "pending")
        self.confirm("income", headers=self.acc2)
        income = self.status("income")
        self.assertEqual((income["status"], income["confirmed"]["by"]), ("done", "acc2"))
        self.assertEqual(income["issues"], [{"kind": "open_fees", "count": 1}])
        # the same person can confirm again with a new note, and it can be taken back
        self.confirm("income", note="new")
        self.assertEqual(self.status("income")["confirmed"]["note"], "new")
        self.assertEqual(self.client.delete(f"{A}/workflow/confirm?year=2026&month=1&step=income", headers=self.acc).status_code, 204)
        self.assertEqual(self.status("income")["status"], "pending")
        self.assertNotIn("confirmed", self.status("income"))
        self.assertEqual(self.client.delete(f"{A}/workflow/confirm?year=2026&month=1&step=income", headers=self.acc).status_code, 404)
        # another month is not touched
        self.assertEqual(self.status("expenses", month=2)["status"], "pending")

    def test_only_the_steps_that_need_a_person_can_be_confirmed_and_only_by_the_right_people(self):
        for step in ("summary", "reports", "close", "archive", "nonsense"):
            self.assertEqual(self.confirm(step).status_code, 422, step)
        for headers in (self.teacher, self.parent, self.mgr):
            self.assertEqual(self.confirm("expenses", headers=headers).status_code, 403)
        self.assertEqual(self.client.post(A + "/workflow/confirm", json={"year": 2026, "month": 1, "step": "expenses"}).status_code, 401)
        self.assertEqual(self.confirm("expenses", month=13).status_code, 422)
        self.assertEqual(self.confirm("expenses", headers=self.admin).status_code, 200)

    def test_confirmed_steps_open_the_way_to_closing_but_flagged_lines_still_block(self):
        self.capital()
        self.client.put(A + "/rates", headers=self.acc, json={"effective_date": "2026-01-02", "syp_per_usd": "15000"})
        for step in ("staff", "fees", "income", "expenses", "payroll", "reconcile"):
            self.confirm(step)
        data = self.flow()
        statuses = {s["key"]: s["status"] for s in data["steps"]}
        self.assertEqual((statuses["summary"], statuses["close"]), ("done", "in_progress"))
        self.assertEqual(data["close"]["blockers"], [])
        # a flagged line is a blocker whatever was confirmed
        charge = self.charge(month=1)
        self.flag_for_review(charge["id"])
        self.assertEqual([b["kind"] for b in self.flow()["close"]["blockers"]], ["review_fees"])
        self.assertEqual(self.close().status_code, 422)
        self.client.post(f"{F}/charges/{charge['id']}/reviewed", headers=self.acc)
        self.assertEqual(self.close().status_code, 201)
        # a closed month keeps what was confirmed: nothing can be changed any more
        self.assertEqual(self.confirm("expenses").status_code, 423)
        self.assertEqual(self.client.delete(f"{A}/workflow/confirm?year=2026&month=1&step=expenses", headers=self.acc).status_code, 423)

    def test_confirming_and_taking_back_are_written_to_the_log(self):
        self.confirm("expenses", note="none")
        self.client.delete(f"{A}/workflow/confirm?year=2026&month=1&step=expenses", headers=self.acc)
        actions = [row["action"] for row in self.client.get("/api/admin/fees/audit", headers=self.acc).json()]
        self.assertIn("step.confirm", actions)
        self.assertIn("step.unconfirm", actions)

    # ---- converting pounds and dollars ----
    def convert(self, amounts, source="USD", target="SYP", on=None):
        body = {"amounts": amounts, "source": source, "target": target}
        if on is not None:
            body["on"] = on
        return self.client.post(A + "/convert", headers=self.acc, json=body)

    def set_rate(self, day, rate):
        self.assertEqual(self.client.put(A + "/rates", headers=self.acc, json={"effective_date": day, "syp_per_usd": rate}).status_code, 200)

    def test_a_past_day_is_converted_with_the_rate_of_that_day_not_with_todays(self):
        from datetime import date

        self.set_rate("2026-01-01", "10000")
        self.set_rate("2026-01-20", "12000")
        self.set_rate(date.today().isoformat(), "13000")
        early = self.convert(["1", "2.5"], on="2026-01-10").json()
        self.assertEqual((early["amounts"], early["rate"], early["rate_date"], early["historical"], early["stale"]), (["10000.00", "25000.00"], "10000", "2026-01-01", True, False))
        later = self.convert(["1"], on="2026-01-25").json()
        self.assertEqual((later["amounts"], later["rate_date"]), (["12000.00"], "2026-01-20"))
        backwards = self.convert(["12000"], source="SYP", target="USD", on="2026-01-25").json()
        self.assertEqual(backwards["amounts"], ["1.00"])
        # today, and a call that names no day, use the rate of today
        for on in (None, date.today().isoformat(), "2999-01-01"):
            now = self.convert(["1"], on=on).json()
            self.assertEqual((now["amounts"], now["historical"]), (["13000.00"], False))
        # a day before the very first stored rate can only be approximated with that first rate, and says so
        old = self.convert(["1"], on="2025-12-01").json()
        self.assertEqual((old["amounts"], old["rate_date"], old["stale"], old["historical"]), (["10000.00"], "2026-01-01", True, True))
        self.assertEqual(self.convert(["1"], on="2026-01-10", ).status_code, 200)

    def test_a_sheet_before_the_first_rate_is_marked_as_approximate(self):
        self.set_rate("2026-01-01", "10000")
        self.entry("2025-12-15", "buffet", income="1", currency="USD")
        self.entry("2026-01-10", "buffet", income="1", currency="USD")
        before = self.sheet("2025-12-15")["converted"]
        after = self.sheet("2026-01-10")["converted"]
        self.assertEqual((before["stale"], before["rate_date"]), (True, "2026-01-01"))
        self.assertEqual((after["stale"], after["rate_date"]), (False, "2026-01-01"))

    def test_the_converted_balances_add_up_exactly(self):
        self.client.put(A + "/cash", headers=self.acc, json={"currency": "SYP", "opening": "1000", "start_year": 2026, "start_month": 1})
        self.client.put(A + "/cash", headers=self.acc, json={"currency": "USD", "opening": "800", "start_year": 2026, "start_month": 1})
        self.set_rate("2026-01-01", "12181.8547")
        self.entry("2026-01-12", "buffet", income="555")
        self.entry("2026-01-12", "buffet", income="0.51", currency="USD")
        self.entry("2026-01-12", "operating", expense="30000")
        sheet = self.sheet("2026-01-12")
        for target in ("SYP", "USD"):
            converted = sheet["converted"][target]
            opening, closing, net = (Decimal(converted[key]) for key in ("opening", "closing", "net"))
            self.assertEqual(closing - opening, net, target)  # the table adds up: opening + net = closing
        self.assertEqual(sheet["converted"]["USD"]["net"], "-1.91")
