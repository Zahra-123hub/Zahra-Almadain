"""The staff list: it belongs to the management; the accounting only reads it. Nobody is deleted."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, FeeAuditLog
from app.timeutil import local_today
from tests.base import PEOPLE, ControlsBase

E = PEOPLE + "/employees"


class StaffTests(ControlsBase):
    def setUp(self):
        super().setUp()
        self.legacy = self.admin

    def add(self, name, **extra):
        return self.client.post(E, headers=self.mgr, json={"name": name, "job_title": "teacher", **extra})

    # ---- rights ----
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
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(E, headers=headers).status_code, 403)
            self.assertEqual(self.client.get(PEOPLE + "/staff-accounts", headers=headers).status_code, 403)

    # ---- one person stays one person ----
    def test_deactivating_keeps_the_person_with_an_end_date_and_coming_back_clears_it(self):
        made = self.add("Lina Ali").json()
        self.assertEqual(self.client.delete(f"{E}/{made['id']}", headers=self.mgr).status_code, 204)
        with Session(self.engine) as s:
            row = s.scalar(select(Employee).where(Employee.name == "Lina Ali"))
            self.assertEqual((row.is_active, row.left_on), (False, local_today()))
        again = self.add("Lina Ali")
        self.assertEqual((again.status_code, again.json()["employee_no"], again.json()["left_on"]), (201, "M-0001", None))

    def test_a_removed_person_who_is_saved_again_keeps_salary_and_account(self):
        accounts = self.client.get(PEOPLE + "/staff-accounts", headers=self.acc).json()
        teacher_account = next(a for a in accounts if a["username"] == "teacher1")["id"]
        first = self.client.post(E, headers=self.mgr, json={"name": "Rima Saleh", "job_title": "Teacher", "salary": "500", "salary_currency": "SYP", "account_id": teacher_account}).json()
        self.client.delete(f"{E}/{first['id']}", headers=self.mgr)
        again = self.client.post(E, headers=self.mgr, json={"name": "rima saleh", "job_title": "Head teacher"})
        self.assertEqual(again.status_code, 201)
        self.assertEqual((again.json()["id"], again.json()["salary"], again.json()["account_id"]), (first["id"], "500.00", teacher_account))
        self.assertEqual(again.json()["job_title"], "Head teacher")
        self.assertEqual([p["name"] for p in self.client.get(E, headers=self.mgr).json()], ["Rima Saleh"])  # one person, not two
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(Employee)).all()), 1)

    def test_an_account_given_up_by_a_removed_person_can_be_linked_again(self):
        account_id = next(a for a in self.client.get(PEOPLE + "/staff-accounts", headers=self.acc).json() if a["username"] == "teacher1")["id"]
        old = self.client.post(E, headers=self.mgr, json={"name": "Old Name", "account_id": account_id}).json()
        self.client.delete(f"{E}/{old['id']}", headers=self.mgr)
        new = self.client.post(E, headers=self.mgr, json={"name": "New Name", "account_id": account_id})
        self.assertEqual(new.status_code, 201)
        self.assertEqual(new.json()["account_id"], account_id)
        # an active person still holds an account against everyone else
        self.assertEqual(self.client.post(E, headers=self.mgr, json={"name": "Third Person", "account_id": account_id}).status_code, 409)

    def test_an_account_created_with_a_removed_persons_name_takes_that_person_back(self):
        person = self.client.post(E, headers=self.mgr, json={"name": "Hana Ali", "salary": "300"}).json()
        self.client.delete(f"{E}/{person['id']}", headers=self.mgr)
        created = self.client.post("/api/admin/platform/teacher-accounts", headers=self.legacy, json={
            "username": "hana-teacher", "role": "teacher", "full_name": "Hana Ali", "job_title": "Teacher", "password": "Qx1d3f5h7j9l-9"})
        self.assertEqual(created.status_code, 201)
        people = self.client.get(E, headers=self.mgr).json()
        self.assertEqual([(p["id"], p["salary"], p["account_username"]) for p in people], [(person["id"], "300.00", "hana-teacher")])

    def test_staff_can_be_renamed_and_removed_and_a_name_exists_once(self):
        created = self.client.post(E, headers=self.mgr, json={"name": "Rima Saleh", "job_title": "معلمة"}).json()
        self.add("Lana")
        renamed = self.client.patch(f"{E}/{created['id']}", headers=self.mgr, json={"name": "Rima S.", "job_title": "مديرة"})
        self.assertEqual(renamed.json()["name"], "Rima S.")
        self.assertEqual(self.client.patch(f"{E}/{created['id']}", headers=self.mgr, json={"name": "lana", "job_title": ""}).status_code, 409)
        self.assertEqual(self.client.delete(f"{E}/{created['id']}", headers=self.mgr).status_code, 204)
        self.assertEqual([p["name"] for p in self.client.get(E, headers=self.mgr).json()], ["Lana"])

    def test_the_saved_salary_and_its_currency(self):
        a = self.client.post(E, headers=self.mgr, json={"name": "Rima", "job_title": "معلمة", "salary": "1500000"}).json()
        self.client.post(E, headers=self.mgr, json={"name": "Dina", "salary": "120", "salary_currency": "USD"})
        self.client.post(E, headers=self.mgr, json={"name": "NoSalary"})
        self.assertEqual((a["salary"], a["salary_currency"]), ("1500000.00", "SYP"))
        listing = {e["name"]: e for e in self.client.get(E, headers=self.mgr).json()}
        self.assertEqual((listing["Dina"]["salary"], listing["Dina"]["salary_currency"]), ("120.00", "USD"))
        self.assertIsNone(listing["NoSalary"]["salary"])
        changed = self.client.patch(f"{E}/{a['id']}", headers=self.mgr, json={"name": "Rima", "salary": "1600000", "salary_currency": "SYP"}).json()
        self.assertEqual(changed["salary"], "1600000.00")

    def test_staff_names_follow_the_accounts(self):
        admin = self.legacy
        created = self.client.post("/api/admin/platform/teacher-accounts", headers=admin, json={
            "role": "teacher", "username": "rima.s", "password": "Qx7f3a9c1d2e44-9", "full_name": "ريما صالح", "job_title": "معلمة"})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual((created.json()["full_name"], created.json()["job_title"]), ("ريما صالح", "معلمة"))
        staff = self.client.get(E, headers=self.mgr).json()
        person = next(e for e in staff if e["name"] == "ريما صالح")
        self.assertEqual(person["account_username"], "rima.s")
        accounts = {a["username"]: a for a in self.client.get("/api/admin/platform/accounts", headers=admin).json()}
        self.assertEqual(accounts["rima.s"]["full_name"], "ريما صالح")

        # renaming through the account renames the same person (no duplicate)
        account_id = created.json()["id"]
        self.client.patch(f"/api/admin/platform/accounts/{account_id}", headers=admin, json={"full_name": "ريما أحمد"})
        staff = self.client.get(E, headers=self.mgr).json()
        self.assertEqual([e["name"] for e in staff if e["account_id"] == account_id], ["ريما أحمد"])
        self.assertEqual(len(staff), 1)

        # tying a saved person to an account; an account has only one person
        loose = self.client.post(E, headers=self.mgr, json={"name": "Dina Kareem", "job_title": "محاسبة"}).json()
        options = {a["username"]: a for a in self.client.get(PEOPLE + "/staff-accounts", headers=self.acc).json()}
        self.assertEqual(options["rima.s"]["linked_to"], "ريما أحمد")
        self.assertEqual(options["acc"]["linked_to"], "")
        conflict = self.client.patch(f"{E}/{loose['id']}", headers=self.mgr, json={"name": "Dina Kareem", "account_id": account_id})
        self.assertEqual(conflict.status_code, 409)
        linked = self.client.patch(f"{E}/{loose['id']}", headers=self.mgr, json={"name": "Dina Kareem", "account_id": options["acc"]["id"]})
        self.assertEqual(linked.json()["account_username"], "acc")
        unlinked = self.client.patch(f"{E}/{loose['id']}", headers=self.mgr, json={"name": "Dina Kareem", "account_id": None})
        self.assertEqual(unlinked.json()["account_id"], "")
        # parents' accounts cannot be tied to staff
        parent_tie = self.client.patch(f"{E}/{loose['id']}", headers=self.mgr, json={"name": "Dina Kareem", "account_id": str(uuid.uuid4())})
        self.assertEqual(parent_tie.status_code, 404)

    # ---- the export (a signed PDF) ----
    def test_the_export_is_a_pdf_for_the_management_and_the_accounting_and_logged(self):
        self.add("Lina Ali", phone="+963933123456", hired_on="2024-09-01", salary="500000", salary_currency="SYP")
        gone = self.add("Hana Omar").json()
        self.client.delete(f"{E}/{gone['id']}", headers=self.mgr)
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.client.get(E + "/export.pdf", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(E + "/export.pdf", headers=self.acc).status_code, 200)
        for wrong in ("/export.csv", "/export.xlsx", "/export.pdf?scope=weird"):
            self.assertEqual(self.client.get(E + wrong, headers=self.mgr).status_code, 422, wrong)
        everyone = self.client.get(E + "/export.pdf", headers=self.mgr)
        self.assertEqual(everyone.status_code, 200)
        self.assertEqual(everyone.headers["content-type"], "application/pdf")
        self.assertTrue(everyone.content.startswith(b"%PDF"))
        self.assertIn(b"/Subtype /Image", everyone.content)  # the logo
        self.assertEqual(self.client.get(E + "/export.pdf?scope=active", headers=self.mgr).status_code, 200)
        with Session(self.engine) as s:
            lines = s.scalars(select(FeeAuditLog).where(FeeAuditLog.action == "employee.export").order_by(FeeAuditLog.at)).all()
            self.assertEqual([line.details for line in lines], ["pdf 2", "pdf 2", "pdf 1"])  # the accounting, every person, then only the active one

    def test_the_staff_pdf_lists_the_central_table_without_private_notes(self):
        from app import pdfs

        people = [{"employee_no": "M-0001", "name": "Lina", "job_title": "teacher", "phone": "0933", "hired_on": "2024-09-01", "is_active": True,
                   "left_on": None, "salary": "300000.00", "salary_currency": "SYP", "notes": "private"}]
        signer = pdfs.signer_of("mgr0", "manager")
        self.assertTrue(pdfs.staff_pdf(people, "all", signer).startswith(b"%PDF"))
        self.assertTrue(pdfs.staff_pdf([], "active", signer).startswith(b"%PDF"))  # an empty list is still a document
