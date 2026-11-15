"""Staff master data and the staff export: only the management writes and exports; numbers and phones stay text."""

import csv
import io
from datetime import date

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, FeeAuditLog
from app.timeutil import local_today
from tests.test_ledger import LedgerBase

E = "/api/admin/accounting/employees"


class StaffTests(LedgerBase):
    def add(self, name, **extra):
        return self.client.post(E, headers=self.mgr, json={"name": name, "job_title": "teacher", **extra})

    def test_only_the_management_changes_staff_and_the_accountant_reads_without_notes(self):
        self.assertEqual(self.client.post(E, headers=self.acc, json={"name": "Lina Ali"}).status_code, 403)
        made = self.add("Lina Ali", phone="0933123456", hired_on="2024-09-01", notes="private note")
        self.assertEqual(made.status_code, 201)
        self.assertEqual(made.json()["employee_no"], "M-0001")
        self.assertEqual(self.add("Hana Omar").json()["employee_no"], "M-0002")
        seen = {e["name"]: e for e in self.client.get(E, headers=self.acc).json()}
        self.assertEqual((seen["Lina Ali"]["phone"], seen["Lina Ali"]["notes"]), ("0933123456", ""))
        full = {e["name"]: e for e in self.client.get(E, headers=self.mgr).json()}
        self.assertEqual(full["Lina Ali"]["notes"], "private note")
        self.assertEqual(self.client.patch(f"{E}/{made.json()['id']}", headers=self.acc, json={"name": "Lina Ali", "phone": "1"}).status_code, 403)

    def test_deactivating_keeps_the_person_with_an_end_date_and_coming_back_clears_it(self):
        made = self.add("Lina Ali").json()
        self.assertEqual(self.client.delete(f"{E}/{made['id']}", headers=self.mgr).status_code, 204)
        with Session(self.engine) as s:
            row = s.scalar(select(Employee).where(Employee.name == "Lina Ali"))
            self.assertEqual((row.is_active, row.left_on), (False, local_today()))
        again = self.add("Lina Ali")
        self.assertEqual((again.status_code, again.json()["employee_no"], again.json()["left_on"]), (201, "M-0001", None))

    def test_the_export_is_for_the_management_only_and_logged(self):
        self.add("Lina Ali")
        for headers in (self.acc, self.teacher, self.parent):
            self.assertEqual(self.client.get(E + "/export.csv", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(E + "/export.pdf", headers=self.mgr).status_code, 422)
        self.assertEqual(self.client.get(E + "/export.csv?scope=weird", headers=self.mgr).status_code, 422)
        self.assertEqual(self.client.get(E + "/export.csv", headers=self.mgr).status_code, 200)
        with Session(self.engine) as s:
            self.assertEqual([r.action for r in s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "employee.export"))], ["employee.export"])

    def test_csv_and_xlsx_match_the_table_keep_text_and_respect_the_scope(self):
        self.add("Lina Ali", phone="+963933123456", hired_on="2024-09-01", salary="500000", salary_currency="SYP")
        gone = self.add("Hana Omar", phone="0944000111", notes="=HYPERLINK(1)").json()
        self.client.delete(f"{E}/{gone['id']}", headers=self.mgr)

        csv_all = self.client.get(E + "/export.csv", headers=self.mgr)
        self.assertTrue(csv_all.content.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(csv_all.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows) - 1, 2)
        body = {r[1]: r for r in rows[1:]}
        self.assertEqual(body["Lina Ali"][3], '="+963933123456"')  # Excel keeps the plus sign
        self.assertEqual(body["Hana Omar"][3], '="0944000111"')  # and the leading zero
        self.assertEqual(body["Hana Omar"][9], "'=HYPERLINK(1)")  # no formula can start from a note
        self.assertEqual((body["Lina Ali"][6], body["Hana Omar"][6]), ("active", "inactive"))
        self.assertEqual((body["Lina Ali"][7], body["Lina Ali"][8]), ("500000.00", "SYP"))

        only_active = list(csv.reader(io.StringIO(self.client.get(E + "/export.csv?scope=active", headers=self.mgr).content.decode("utf-8-sig"))))
        self.assertEqual([r[1] for r in only_active[1:]], ["Lina Ali"])

        sheet = load_workbook(io.BytesIO(self.client.get(E + "/export.xlsx", headers=self.mgr).content)).active
        data = {row[1].value: row for row in sheet.iter_rows(min_row=2)}
        self.assertEqual(data["Hana Omar"][3].value, "0944000111")
        self.assertEqual(data["Hana Omar"][3].data_type, "s")
        self.assertEqual(data["Lina Ali"][3].value, "+963933123456")
        self.assertEqual(data["Lina Ali"][0].value, "M-0001")
        self.assertEqual(data["Hana Omar"][9].data_type, "s")  # text, so "=…" is not a formula
        # the export equals the central table
        with Session(self.engine) as s:
            self.assertEqual(sorted(s.scalars(select(Employee.name)).all()), sorted(data))
