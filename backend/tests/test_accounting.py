import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import accounting, fees, main
from app.database import Base, get_session
from app import import_vorlagen
from app.import_vorlagen import parse_date, run_import
from app.models import Account, Child, Employee, FeeCharge, FeePayment, Role, SalaryLine
from app.numbers_ar import parse_amount


class NumberWordTests(unittest.TestCase):
    def amount(self, text):
        parsed = parse_amount(text)
        return parsed.value, parsed.ok

    def test_words_and_digits_become_numbers(self):
        cases = {
            "مليون ونصف": 1_500_000,
            "مليونين": 2_000_000,
            "٣ مليون": 3_000_000,
            "نصف مليون": 500_000,
            "مئتين وخمسين ألف": 250_000,
            "ثلاث مئة ألف": 300_000,
            "1,500,000": 1_500_000,
            "١٥٠٠٠٠٠ ل.س": 1_500_000,
            "٢٫٥ مليون": 2_500_000,
            "500000 + 250 ألف": 750_000,
            "مليون و٢٠٠ ألف": 1_200_000,
        }
        for text, expected in cases.items():
            value, ok = self.amount(text)
            self.assertTrue(ok, text)
            self.assertEqual(value, Decimal(expected), text)

    def test_currency_marks(self):
        self.assertEqual(parse_amount("100$").currency, "USD")
        self.assertEqual(parse_amount("75000 ل.س").currency, "SYP")
        self.assertIsNone(parse_amount("75000").currency)

    def test_unsure_amounts_are_rejected_not_guessed(self):
        for text in ("مليون و٢٠٠", "شيء غير مقروء", "100$ + 5000 ل.س"):
            self.assertFalse(parse_amount(text).ok, text)
        self.assertEqual(parse_amount("").value, None)

    def test_dates(self):
        self.assertEqual(parse_date("٠٣/٠٩", 2026)[0].isoformat(), "2026-09-03")
        self.assertEqual(parse_date("2026-09-03", 2026)[0].isoformat(), "2026-09-03")
        self.assertFalse(parse_date("31/02/2026", 2026)[1])
        self.assertEqual(parse_date("", 2026), (None, True))


class CalculationTests(unittest.TestCase):
    def test_net_pay(self):
        self.assertEqual(
            accounting.net_pay(Decimal("1000"), Decimal("200"), Decimal("150"), Decimal("50")),
            Decimal("1000.00"),
        )

    def test_salary_totals_keep_currencies_apart(self):
        rows = [
            {"currency": "SYP", "base": "100", "bonus": "10", "advance": "5", "deduction": "5", "net": "100"},
            {"currency": "SYP", "base": "200", "bonus": "0", "advance": "0", "deduction": "0", "net": "200"},
            {"currency": "USD", "base": "50", "bonus": "0", "advance": "0", "deduction": "0", "net": "50"},
        ]
        totals = accounting.salary_totals(rows)
        self.assertEqual(totals["SYP"]["net"], "300.00")
        self.assertEqual(totals["USD"]["net"], "50.00")


class AccountingApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "test-accounting-secret-long-enough",
                "ADMIN_USERNAME": "legacy-admin",
                "ADMIN_PASSWORD": "legacy-admin-password",
            },
        )
        self.env.start()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
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
                session.add(Account(username=username, password_hash=main.PASSWORD_HASHER.hash("password-123456"), roles=[roles[role]]))
            session.add(Child(display_name="Amal", class_name="KG1"))
            session.commit()

        def token(name):
            return {"Authorization": "Bearer " + self.client.post(
                "/api/platform/auth/login", json={"username": name, "password": "password-123456"}
            ).json()["access_token"]}

        self.acc = token("acc")
        self.teacher = token("teacher1")
        self.parent = token("parent1")
        self.legacy = {"Authorization": "Bearer " + self.client.post(
            "/api/auth/login", json={"username": "legacy-admin", "password": "legacy-admin-password"}
        ).json()["access_token"]}

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.optional_session, None)
        self.engine.dispose()
        self.env.stop()

    def salary(self, name="Rima", base="1000", currency="SYP", month=10, **extra):
        return self.client.post(
            "/api/admin/accounting/salaries", headers=self.acc,
            json={"employee_name": name, "job_title": "teacher", "year": 2026, "month": month,
                  "currency": currency, "base": base, **extra},
        )

    # ---- access ----
    def test_only_accountant_and_admin_reach_accounting(self):
        paths = ["/api/admin/accounting/employees", "/api/admin/accounting/salaries",
                 "/api/admin/accounting/sheet?period_type=month&year=2026&month=10&currency=SYP",
                 "/api/admin/accounting/overview?year=2026"]
        for path in paths:
            for headers, expected in ((self.acc, 200), (self.legacy, 200), (self.teacher, 403),
                                      (self.parent, 403), ({}, 401)):
                self.assertEqual(self.client.get(path, headers=headers).status_code, expected, (path, expected))
        for method, path in (("post", "/api/admin/accounting/salaries"), ("put", "/api/admin/accounting/entries"),
                             ("post", "/api/admin/accounting/employees")):
            for headers in (self.teacher, self.parent):
                self.assertEqual(getattr(self.client, method)(path, headers=headers, json={}).status_code, 403, path)

    # ---- payroll ----
    def test_salary_net_totals_and_validation(self):
        self.assertEqual(self.salary("Rima", "1000", bonus="200", advance="150", deduction="50").json()["net"], "1000.00")
        self.salary("Dina", "500")
        self.salary("Rima", "40", currency="USD")
        listing = self.client.get("/api/admin/accounting/salaries?year=2026&month=10", headers=self.acc).json()
        self.assertEqual(listing["totals"]["SYP"]["net"], "1500.00")
        self.assertEqual(listing["totals"]["USD"]["net"], "40.00")
        self.assertEqual(self.salary("Rima", "1000").status_code, 409)  # same employee/month/currency
        self.assertEqual(self.salary("Neg", "100", advance="200").status_code, 422)  # negative net
        self.assertEqual(self.salary("Bad", "-5").status_code, 422)
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(Employee)).all()), 2)  # Rima reused; rejected rows create nobody

    # ---- sheets ----
    def test_monthly_sheet_fills_registration_and_salaries_automatically(self):
        child_id = self.client.get("/api/admin/fees/children", headers=self.acc).json()[0]["id"]
        charge = self.client.post("/api/admin/fees/charges", headers=self.acc, json={
            "child_id": child_id, "year": 2026, "month": 10, "amount": "1500000", "currency": "SYP"}).json()
        self.client.post(f"/api/admin/fees/charges/{charge['id']}/payments", headers=self.acc,
                         json={"amount": "600000", "paid_on": "2026-10-04", "receipt_no": "S-1"})
        self.salary("Rima", "1000000", bonus="100000", advance="50000")
        url = "/api/admin/accounting/sheet?period_type=month&year=2026&month=10&currency=SYP"
        rows = {r["key"]: r for r in self.client.get(url, headers=self.acc).json()["rows"]}
        self.assertEqual(rows["registration"]["income"], "600000.00")
        self.assertEqual(rows["salaries"]["expense"], "1050000.00")
        self.assertEqual(len(rows) , 6)
        sheet = self.client.get(url, headers=self.acc).json()
        self.assertEqual(sheet["totals"], {"income": "600000.00", "expense": "1050000.00", "net": "-450000.00"})
        # the other currency is untouched
        usd = self.client.get(url.replace("SYP", "USD"), headers=self.acc).json()
        self.assertEqual(usd["totals"]["income"], "0.00")

        # manual override beats the automatic value; deleting the row restores it
        saved = self.client.put("/api/admin/accounting/entries", headers=self.acc, json={
            "period_type": "month", "year": 2026, "month": 10, "currency": "SYP", "item_key": "registration",
            "details": "تعديل يدوي", "income": "700000", "manual": True})
        reg = next(r for r in saved.json()["rows"] if r["key"] == "registration")
        self.assertEqual((reg["income"], reg["manual"], reg["auto_income"]), ("700000.00", True, "600000.00"))
        reset = self.client.delete(f"/api/admin/accounting/entries/{reg['id']}", headers=self.acc).json()
        self.assertEqual(next(r for r in reset["rows"] if r["key"] == "registration")["income"], "600000.00")

        # other items and custom rows
        self.client.put("/api/admin/accounting/entries", headers=self.acc, json={
            "period_type": "month", "year": 2026, "month": 10, "currency": "SYP", "item_key": "operating",
            "expense": "250000"})
        custom = self.client.put("/api/admin/accounting/entries", headers=self.acc, json={
            "period_type": "month", "year": 2026, "month": 10, "currency": "SYP", "item_key": "custom",
            "item_label": "بند إضافي", "expense": "10000"}).json()
        self.assertEqual(custom["totals"]["expense"], "1310000.00")

    def test_weekly_sheet_uses_payment_dates(self):
        child_id = self.client.get("/api/admin/fees/children", headers=self.acc).json()[0]["id"]
        charge = self.client.post("/api/admin/fees/charges", headers=self.acc, json={
            "child_id": child_id, "year": 2026, "month": 10, "amount": "100", "currency": "USD"}).json()
        for day, amount in (("2026-10-05", "30"), ("2026-10-14", "20")):  # Monday week of the 5th vs next week
            self.client.post(f"/api/admin/fees/charges/{charge['id']}/payments", headers=self.acc,
                             json={"amount": amount, "paid_on": day})
        url = "/api/admin/accounting/sheet?period_type=week&year=2026&currency=USD&week_start="
        first = self.client.get(url + "2026-10-07", headers=self.acc).json()  # a Wednesday -> week of Mon 5th
        self.assertEqual(first["start"], "2026-10-05")
        self.assertEqual(next(r for r in first["rows"] if r["key"] == "registration")["income"], "30.00")
        second = self.client.get(url + "2026-10-12", headers=self.acc).json()
        self.assertEqual(next(r for r in second["rows"] if r["key"] == "registration")["income"], "20.00")

    def test_daily_sheet_uses_that_days_payments_and_salaries(self):
        child_id = self.client.get("/api/admin/fees/children", headers=self.acc).json()[0]["id"]
        charge = self.client.post("/api/admin/fees/charges", headers=self.acc, json={
            "child_id": child_id, "year": 2026, "month": 10, "amount": "1000", "currency": "SYP"}).json()
        for day, amount in (("2026-10-05", "300"), ("2026-10-06", "200")):
            self.client.post(f"/api/admin/fees/charges/{charge['id']}/payments", headers=self.acc,
                             json={"amount": amount, "paid_on": day})
        self.salary("Rima", "5000", paid_on="2026-10-06")
        url = "/api/admin/accounting/sheet?period_type=day&year=2026&currency=SYP&week_start="
        first = self.client.get(url + "2026-10-05", headers=self.acc).json()
        self.assertEqual((first["start"], first["end"]), ("2026-10-05", "2026-10-05"))
        rows = {r["key"]: r for r in first["rows"]}
        self.assertEqual((rows["registration"]["income"], rows["salaries"]["expense"]), ("300.00", "0.00"))
        second = {r["key"]: r for r in self.client.get(url + "2026-10-06", headers=self.acc).json()["rows"]}
        self.assertEqual((second["registration"]["income"], second["salaries"]["expense"]), ("200.00", "5000.00"))
        # rows saved for one day do not leak into another day or into the week sheet
        saved = self.client.put("/api/admin/accounting/entries", headers=self.acc, json={
            "period_type": "day", "year": 2026, "week_start": "2026-10-05", "currency": "SYP",
            "item_key": "operating", "expense": "75", "details": "x"}).json()
        self.assertEqual(saved["totals"]["expense"], "75.00")
        other = self.client.get(url + "2026-10-06", headers=self.acc).json()
        self.assertEqual(other["totals"]["expense"], "5000.00")
        week = self.client.get("/api/admin/accounting/sheet?period_type=week&year=2026&currency=SYP&week_start=2026-10-05", headers=self.acc).json()
        self.assertEqual(next(r for r in week["rows"] if r["key"] == "operating")["expense"], "0.00")

    def test_syrian_pound_is_the_main_currency(self):
        self.assertEqual(fees.CURRENCIES[0], "SYP")
        overview = self.client.get("/api/admin/accounting/overview?year=2026", headers=self.acc).json()
        self.assertEqual([k for k in overview if k in ("SYP", "USD")], ["SYP", "USD"])

    def test_overview_per_class_and_chart_series(self):
        children = {c["display_name"]: c["id"] for c in self.client.get("/api/admin/fees/children", headers=self.acc).json()}
        new = self.client.post("/api/admin/fees/charges", headers=self.acc, json={
            "child_name": "Bashar", "class_name": "KG1", "year": 2026, "month": 10, "amount": "100", "currency": "USD"}).json()
        self.client.post("/api/admin/fees/charges", headers=self.acc, json={
            "child_id": children["Amal"], "year": 2026, "month": 10, "amount": "100", "currency": "USD",
            "payment": {"amount": "100", "paid_on": "2026-10-02"}})
        data = self.client.get("/api/admin/accounting/overview?year=2026", headers=self.acc).json()
        cell = data["USD"]["classes"]["KG1"][0]
        self.assertEqual((cell["required"], cell["paid"], cell["remaining"], cell["children_open"]),
                         ("200.00", "100.00", "100.00", 1))
        self.assertEqual(data["USD"]["children_open"], 1)
        self.assertEqual(len(data["USD"]["series"]), 12)
        self.assertEqual(data["USD"]["series"][9]["income"], "100.00")
        self.assertEqual(data["SYP"]["classes"], {})
        self.assertTrue(new["id"])

    def test_zero_amount_row_is_review_not_paid(self):
        child_id = self.client.get("/api/admin/fees/children", headers=self.acc).json()[0]["id"]
        row = self.client.post("/api/admin/fees/charges", headers=self.acc, json={
            "child_id": child_id, "year": 2026, "month": 10, "amount": "0", "currency": "SYP"}).json()
        self.assertEqual((row["amount"], row["paid"], row["remaining"], row["status"]), ("0.00", "0.00", "0.00", "review"))
        listing = self.client.get("/api/admin/fees?status=review", headers=self.acc).json()["rows"]
        self.assertEqual(len(listing), 1)
        self.assertEqual(self.client.get("/api/admin/fees?status=paid", headers=self.acc).json()["rows"], [])

    def test_correcting_an_imported_salary_row_keeps_empty_fields_empty(self):
        with Session(self.engine) as session:
            employee = Employee(name="")
            session.add(employee)
            session.flush()
            line = SalaryLine(employee_id=employee.id, year=2026, month=9, currency="SYP", needs_review=True,
                              raw_text="x", source="g.csv#1")
            session.add(line)
            session.commit()
            line_id = str(line.id)
        rows = self.client.get("/api/admin/accounting/salaries?needs_review=true", headers=self.acc).json()["rows"]
        self.assertEqual((rows[0]["base"], rows[0]["net"]), (None, None))
        fixed = self.client.patch(f"/api/admin/accounting/salaries/{line_id}", headers=self.acc,
                                  json={"employee_name": "Rima", "base": "1000", "bonus": None, "advance": None, "deduction": None})
        self.assertEqual(fixed.status_code, 200, fixed.text)
        self.assertEqual((fixed.json()["employee_name"], fixed.json()["base"], fixed.json()["bonus"], fixed.json()["net"]),
                         ("Rima", "1000.00", None, "1000.00"))
        self.assertTrue(fixed.json()["needs_review"])  # stays flagged until a human confirms
        confirmed = self.client.post(f"/api/admin/accounting/salaries/{line_id}/reviewed", headers=self.acc).json()
        self.assertFalse(confirmed["needs_review"])

    def test_needs_review_can_be_cleared(self):
        with Session(self.engine) as session:
            child = session.scalar(select(Child))
            charge = FeeCharge(child_id=child.id, year=2026, month=9, currency="SYP", amount=Decimal("5"),
                               needs_review=True, raw_text="x", source="a.jpg#1")
            session.add(charge)
            session.commit()
            charge_id = str(charge.id)
        flagged = self.client.get("/api/admin/fees?needs_review=true", headers=self.acc).json()["rows"]
        self.assertEqual([r["needs_review"] for r in flagged], [True])
        cleared = self.client.post(f"/api/admin/fees/charges/{charge_id}/reviewed", headers=self.acc).json()
        self.assertFalse(cleared["needs_review"])


FEES_HEADER = "م,اسم الطفل,الصف/الشعبة,الرسم/القسط المطلوب,المبلغ المدفوع,المتبقي,تاريخ الدفع,رقم الإيصال,ملاحظات,الشهر,السنة"
SALARY_HEADER = "م,اسم الموظف/المدرسة,المسمى الوظيفي,الراتب الأساسي,المكافآت/الإضافي,السلف,الخصومات,الصافي المستحق,تاريخ الاستلام,الشهر,السنة"


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.dir = tempfile.TemporaryDirectory()
        self.fees_csv = Path(self.dir.name) / "beitraege.csv"
        self.salaries_csv = Path(self.dir.name) / "gehaelter.csv"

    def tearDown(self):
        self.dir.cleanup()
        self.engine.dispose()

    def write(self, path, header, *rows):
        path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8-sig")

    def run_fees(self, session):
        return run_import(session, self.fees_csv, None)

    def test_values_are_stored_as_read_and_empty_stays_empty(self):
        self.write(
            self.fees_csv, FEES_HEADER,
            "1,Amal,KG1,مليون ونصف,500000 + 250 ألف,750000,٠٣/٠٩,R1,,9,2026",      # adds up
            "2,Bashar,KG2,مليونين,٣ مليون,,05/09,R2,,9,2026",                        # paid > required
            "3,,KG1,,,,,,,9,2026",                                                   # nothing readable
            "4,Carla,KG3,0,0,0,,,,9,2026",                                           # 0 / 0 / 0
            "5,Dana,KG1,مليون,,,,,ملاحظة,9,2026",                                    # nothing paid yet
            "6,Eli,KG2,100$,,,,,,9,2026",                                            # dollar mark on a SYP sheet
            "7,Fadi,KG1,مليون,مليون,800000,١٠/٠٩,R7,,9,2026",                        # open column does not add up
        )
        with Session(self.engine) as session:
            report, text = self.run_fees(session)
            session.commit()
            charges = {c.source: c for c in session.scalars(select(FeeCharge))}
            children = {c.id: c for c in session.scalars(select(Child))}
            by = lambda n: charges[f"beitraege.csv#{n}"]

            first = by(1)
            self.assertEqual((first.amount, first.currency, first.needs_review), (Decimal("1500000.00"), "SYP", False))
            self.assertEqual(sum(p.amount for p in first.payments), Decimal("750000.00"))
            self.assertEqual(first.payments[0].paid_on.isoformat(), "2026-09-03")
            self.assertEqual(fees.status_of(first.amount, fees.paid_amount(first), first.needs_review), "partial")

            over = by(2)  # stored exactly as read, but flagged
            self.assertEqual(sum(p.amount for p in over.payments), Decimal("3000000.00"))
            self.assertTrue(over.needs_review)

            blank = by(3)  # unreadable: EMPTY values, raw text kept, never 0 or an invented name
            self.assertIsNone(blank.amount)
            self.assertEqual(children[blank.child_id].display_name, "")
            self.assertTrue(blank.needs_review)
            self.assertIn("KG1", blank.raw_text)

            zero = by(4)
            self.assertTrue(zero.needs_review)
            self.assertEqual(fees.status_of(zero.amount, fees.paid_amount(zero), zero.needs_review), "review")

            unpaid = by(5)
            self.assertFalse(unpaid.needs_review)
            self.assertEqual(unpaid.note, "ملاحظة")
            self.assertEqual(len(unpaid.payments), 0)

            self.assertEqual((by(6).currency, by(6).needs_review), ("USD", True))
            self.assertTrue(by(7).needs_review)  # 1,000,000 - 1,000,000 != 800,000

            fees_stats = report.stats["fees"]
            self.assertEqual((fees_stats["rows"], fees_stats["imported"]), (7, 7))
            self.assertIn("needs_review", text)

    def test_no_placeholders_after_import(self):
        self.write(self.fees_csv, FEES_HEADER, "1,,,,,,,,,9,2026", "2,,,غير واضح,,,,,,9,2026", "3,Amal,KG1,مليون,,,,,,9,2026")
        self.write(self.salaries_csv, SALARY_HEADER, "1,,,,,,,,,9,2026", "2,Rima,معلمة,,,,,,,9,2026")
        with Session(self.engine) as session:
            run_import(session, self.fees_csv, self.salaries_csv)
            session.commit()
            names = [c.display_name for c in session.scalars(select(Child))]
            self.assertEqual(sorted(names), ["", "", "Amal"])  # unreadable names stay empty, nothing invented
            for text in names + [e.name for e in session.scalars(select(Employee))]:
                for marker in ("تجريبي", "غير مقروء", "demo", "DEMO", "placeholder"):
                    self.assertNotIn(marker, text)
            charges = session.scalars(select(FeeCharge)).all()
            self.assertEqual(sorted(str(c.amount) for c in charges if c.amount is not None), ["1000000.00"])
            self.assertEqual(len([c for c in charges if c.amount is None]), 2)  # empty, not 0
            lines = session.scalars(select(SalaryLine)).unique().all()
            for line in lines:
                self.assertIsNone(line.base)
                self.assertIsNone(line.bonus)
                self.assertTrue(line.needs_review)

    def test_import_is_idempotent(self):
        self.write(self.fees_csv, FEES_HEADER, "1,Amal,KG1,مليون,500000,500000,01/09,R1,,9,2026", "2,,,,,,,,,9,2026")
        self.write(self.salaries_csv, SALARY_HEADER, "1,Rima,معلمة,مليون,٢٠٠ ألف,,,1200000,28/09,9,2026")
        with Session(self.engine) as session:
            first, _ = run_import(session, self.fees_csv, self.salaries_csv)
            session.commit()
            counts = (session.scalar(select(func.count()).select_from(Child)), session.scalar(select(func.count()).select_from(FeeCharge)),
                      session.scalar(select(func.count()).select_from(FeePayment)), session.scalar(select(func.count()).select_from(Employee)),
                      session.scalar(select(func.count()).select_from(SalaryLine)))
            again, text = run_import(session, self.fees_csv, self.salaries_csv)
            session.commit()
            self.assertEqual(again.stats["fees"]["imported"], 0)
            self.assertEqual(again.stats["fees"]["skipped"], 2)
            self.assertEqual(again.stats["salaries"]["skipped"], 1)
            after = (session.scalar(select(func.count()).select_from(Child)), session.scalar(select(func.count()).select_from(FeeCharge)),
                     session.scalar(select(func.count()).select_from(FeePayment)), session.scalar(select(func.count()).select_from(Employee)),
                     session.scalar(select(func.count()).select_from(SalaryLine)))
            self.assertEqual(counts, after)
            self.assertEqual(counts, (2, 2, 1, 1, 1))
            self.assertIn("الإجمالي SYP", text)  # the report is the same after a repeat

    def test_salary_rules(self):
        self.write(
            self.salaries_csv, SALARY_HEADER,
            "1,Rima,معلمة,مليون,٢٠٠ ألف,100000,,1100000,28/09,9,2026",   # adds up (empty deduction stays empty)
            "2,Dina,مساعدة,مليون,,,50000,900000,,9,2026",                # written net is wrong
            "3,Lana,معلمة,مليون و٢٠٠,,,,,,9,2026",                        # ambiguous words: not guessed
            "4,Maya,معلمة,,,,,,,9,2026",                                  # no base salary
        )
        with Session(self.engine) as session:
            report, text = run_import(session, None, self.salaries_csv)
            session.commit()
            lines = {l.source: l for l in session.scalars(select(SalaryLine)).unique()}
            first = lines["gehaelter.csv#1"]
            self.assertEqual((first.base, first.bonus, first.advance, first.deduction), (Decimal("1000000.00"), Decimal("200000.00"), Decimal("100000.00"), None))
            self.assertFalse(first.needs_review)
            self.assertEqual(accounting.net_pay(first.base, first.bonus, first.advance, first.deduction), Decimal("1100000.00"))
            self.assertTrue(lines["gehaelter.csv#2"].needs_review)
            self.assertIsNone(lines["gehaelter.csv#3"].base)
            self.assertTrue(lines["gehaelter.csv#3"].needs_review)
            self.assertIsNone(accounting.net_pay(None, None, None, None))
            self.assertTrue(lines["gehaelter.csv#4"].needs_review)

    def test_rows_without_a_period_are_rejected_not_guessed(self):
        self.write(self.fees_csv, "م,اسم الطفل,الرسم/القسط المطلوب", "1,Amal,مليون")
        with Session(self.engine) as session:
            report, text = run_import(session, self.fees_csv, None)
            self.assertEqual(report.stats["fees"]["rejected"], 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(FeeCharge)), 0)
            report, _ = run_import(session, self.fees_csv, None, year=2026, month=9)  # period given explicitly
            self.assertEqual(report.stats["fees"]["imported"], 1)

    def test_import_aborts_when_csv_files_are_missing(self):
        argv = ["import_vorlagen", "--fees", str(Path(self.dir.name) / "fehlt.csv"), "--salaries", str(self.salaries_csv)]
        with unittest.mock.patch.object(sys, "argv", argv), unittest.mock.patch("builtins.print") as shown:
            self.assertEqual(import_vorlagen.main(), 2)
        self.assertIn("fehlt.csv", shown.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()
