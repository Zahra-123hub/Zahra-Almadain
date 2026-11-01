"""The guided accounting workflow: step statuses, receipts, the closing check, the weekly check and the archive file."""

import io

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
