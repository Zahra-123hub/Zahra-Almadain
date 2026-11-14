"""The control centre: who may see it, and that every number is counted from the real tables."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import control
from app.fees import FeesActor
from app.models import Account, AccountGrant, Child, FeeAuditLog, RegistrationRequest, SystemCheck
from tests.test_accounting_controls import ControlsBase
from tests.test_ledger import ADMIN, LedgerBase
from app import legacy_migration as migration
from app.timeutil import local_today

C = "/api/admin/control"
P = "/api/platform"


class ControlTests(LedgerBase):
    def grant(self, username, name):
        return self.client.post(C + "/grants", headers=self.admin, json={"username": username, "grant": name})

    def report(self, child_id, title="Day", submit=True):
        return self.client.post(P + "/teacher/reports", headers=self.teacher, json={"child_id": child_id, "title": title, "body": "text", "submit_for_review": submit})

    # ---- rights ----
    def test_only_the_administrator_and_a_manager_with_the_grant_may_look(self):
        for headers in (self.teacher, self.parent, self.acc):
            self.assertEqual(self.client.get(C + "/overview", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(C + "/overview", headers=self.mgr).status_code, 403)  # a manager without the grant
        self.assertEqual(self.client.get(C + "/overview", headers=self.admin).status_code, 200)
        self.assertEqual(self.grant("mgr0", "control.view").status_code, 201)
        self.assertEqual(self.client.get(C + "/overview", headers=self.mgr).status_code, 200)

    def test_money_is_only_shown_to_those_who_were_given_the_finance_view(self):
        self.grant("mgr0", "control.view")
        self.assertIsNone(self.client.get(C + "/overview", headers=self.mgr).json()["finance"])
        self.assertIsNotNone(self.client.get(C + "/overview", headers=self.admin).json()["finance"])
        self.grant("mgr0", "finance.view")
        self.assertIsNotNone(self.client.get(C + "/overview", headers=self.mgr).json()["finance"])

    def test_grants_are_for_the_administrator_only_and_are_logged(self):
        self.assertEqual(self.client.post(C + "/grants", headers=self.mgr, json={"username": "mgr0", "grant": "control.view"}).status_code, 403)
        self.assertEqual(self.grant("mgr0", "everything").status_code, 422)
        self.assertEqual(self.grant("nobody", "control.view").status_code, 404)
        made = self.grant("mgr0", "control.view")
        self.assertEqual(made.status_code, 201)
        self.assertEqual(self.grant("mgr0", "control.view").status_code, 409)
        listed = self.client.get(C + "/grants", headers=self.admin).json()
        self.assertEqual([(g["username"], g["grant"]) for g in listed], [("mgr0", "control.view")])
        self.assertEqual(self.client.delete(f"{C}/grants/{made.json()['id']}", headers=self.admin).status_code, 204)
        self.assertEqual(self.client.get(C + "/overview", headers=self.mgr).status_code, 403)
        with Session(self.engine) as s:
            rows = s.scalars(select(FeeAuditLog).where(FeeAuditLog.domain == "account").order_by(FeeAuditLog.at)).all()
        self.assertEqual([r.action for r in rows], ["grant.add", "grant.remove"])
        self.assertIn("control.view", rows[0].after_json)
        self.assertIn("control.view", rows[1].before_json)

    # ---- people and tasks ----
    def test_the_numbers_are_counted_from_the_tables(self):
        self.enroll("Noor")
        with Session(self.engine) as s:
            s.add(RegistrationRequest(guardian_name="Mona", email="m@example.com", phone="0933", child_name="Omar", status="pending"))
            s.commit()
        child_id = self.client.get(P + "/teacher/children", headers=self.teacher).json()[0]["id"]
        self.assertEqual(self.report(child_id).status_code, 201)
        people = self.client.get(C + "/overview", headers=self.admin).json()["people"]
        self.assertEqual(people["children_active"], 2)
        self.assertEqual(people["children_new_30d"], 2)
        self.assertEqual((people["teachers"], people["parents"], people["requests_pending"], people["reports_in_review"]), (1, 1, 1, 1))

    def test_tasks_show_what_waits_for_somebody_with_a_priority(self):
        with Session(self.engine) as s:
            s.add(RegistrationRequest(guardian_name="Mona", email="m@example.com", phone="0933", child_name="Omar", status="pending"))
            s.commit()
        child_id = self.client.get(P + "/teacher/children", headers=self.teacher).json()[0]["id"]
        self.report(child_id, title="Garden day")
        kinds = {t["kind"]: t for t in self.client.get(C + "/tasks", headers=self.admin).json()["summary"]}
        self.assertEqual(kinds["requests_pending"]["priority"], "medium")
        self.assertEqual((kinds["reports_in_review"]["count"], kinds["reports_in_review"]["oldest_days"]), (1, 0))
        self.assertEqual(kinds["children_missing_info"]["priority"], "low")
        detail = self.client.get(C + "/tasks", headers=self.admin).json()
        self.assertEqual([(r["title"], r["child"], r["author"]) for r in detail["reports_in_review"]], [("Garden day", "Amal", "teacher1")])
        self.assertEqual(detail["registration_requests"][0]["guardian"], "Mona")

    def test_many_failed_sign_ins_are_a_high_priority_task(self):
        for _ in range(4):
            self.client.post(P + "/auth/login", json={"username": "teacher1", "password": "definitely-wrong-1"})
        tasks = {t["kind"]: t for t in self.client.get(C + "/tasks", headers=self.admin).json()["summary"]}
        self.assertEqual((tasks["failed_sign_ins"]["priority"], tasks["failed_sign_ins"]["count"]), ("high", 4))

    # ---- teachers ----
    def test_a_teacher_who_made_a_report_today_is_active_and_one_who_did_nothing_is_not(self):
        self.client.post(A_EMP, headers=self.mgr, json={"name": "Lina", "job_title": "teacher"})
        child_id = self.client.get(P + "/teacher/children", headers=self.teacher).json()[0]["id"]
        self.report(child_id, submit=False)
        data = self.client.get(C + "/teachers/activity", headers=self.admin).json()
        mine = next(t for t in data["teachers"] if t["username"] == "teacher1")
        self.assertEqual((mine["reports_created"], mine["drafts_open"], mine["active_that_day"]), (1, 1, True))
        self.assertEqual(data["active"], 1)
        yesterday = (local_today() - timedelta(days=1)).isoformat()
        past = self.client.get(f"{C}/teachers/activity?day={yesterday}", headers=self.admin).json()
        self.assertEqual(next(t for t in past["teachers"] if t["username"] == "teacher1")["reports_created"], 0)

    # ---- children ----
    def test_children_new_missing_information_and_those_who_left(self):
        made = self.enroll("Noor")
        children = self.client.get(C + "/children", headers=self.admin).json()
        self.assertEqual(children["active"], 2)
        self.assertEqual({g["name"]: g["children"] for g in children["groups"]}, {"KG1": 2})
        self.assertEqual({c["name"] for c in children["new_last_30_days"]}, {"Amal", "Noor"})
        missing = {c["name"]: c["missing"] for c in children["missing_information"]}
        self.assertIn("birth_date", missing["Noor"])
        self.assertEqual(children["teacher_assignment"], "not_used")
        self.assertEqual(self.client.delete(f"/api/admin/accounting/children/{made['id']}", headers=self.mgr).status_code, 204)
        after = self.client.get(C + "/children", headers=self.admin).json()
        self.assertEqual(after["active"], 1)
        self.assertEqual([(c["name"], c["left_on"]) for c in after["left_last_30_days"]], [("Noor", local_today().isoformat())])
        with Session(self.engine) as s:
            self.assertEqual(s.scalar(select(Child.left_on).where(Child.display_name == "Noor")), local_today())

    # ---- finance ----
    def test_the_finance_block_shows_each_currency_apart_and_follows_the_switch(self):
        self.opening("SYP", "1000", local_today().year, 1)
        self.opening("USD", "50", local_today().year, 1)
        self.payment("300", local_today(), month=local_today().month, year=local_today().year)
        block = self.client.get(C + "/overview", headers=self.admin).json()["finance"]
        self.assertEqual((block["mode"], block["source"]), ("legacy", "legacy_sheets"))
        self.assertEqual(set(block["currencies"]), {"SYP", "USD"})
        self.assertEqual(block["currencies"]["SYP"]["balance"], "1300.00")
        self.assertEqual(block["currencies"]["USD"]["balance"], "50.00")
        self.assertEqual(block["currencies"]["SYP"]["open_fees"]["amount"], "99700.00")  # 100000 due, 300 paid
        self.assertNotIn("total", block)
        with Session(self.engine) as s:
            migration.apply(s, ADMIN, local_today(), go_live=True)
        live = self.client.get(C + "/overview", headers=self.admin).json()["finance"]
        self.assertEqual((live["mode"], live["source"]), ("live", "cash_book"))
        self.assertEqual(live["currencies"]["SYP"]["balance"], "1300.00")
        self.assertEqual(live["currencies"]["SYP"]["payments_this_month"], "300.00")

    # ---- system ----
    def test_the_system_check_says_what_it_really_found_and_stores_it(self):
        first = self.client.get(C + "/system", headers=self.admin).json()
        self.assertTrue(first["database"]["ok"])
        self.assertFalse(first["migrations"]["known"])  # a test database has no migration table: "not known", not "fine"
        self.assertIsNotNone(first["last_success_at"])
        self.assertFalse(first["backup"]["available"])  # there is no backup source: it must never look green
        with Session(self.engine) as s:
            self.assertEqual(s.scalars(select(SystemCheck)).all()[0].database_ok, True)
        self.assertEqual(self.client.get(C + "/overview", headers=self.admin).json()["system"]["last_success_at"], first["last_success_at"])

    def test_an_unreachable_database_is_reported_as_down(self):
        class Dead:
            added: list = []

            def execute(self, *_a, **_k):
                raise RuntimeError("connection refused")

            def rollback(self): pass
            def commit(self): pass
            def add(self, item): self.added.append(item)
            def scalar(self, *_a, **_k): return None

            def scalars(self, *_a, **_k):
                class Rows:
                    def all(self_inner): return []
                return Rows()

        result = control.system_check(Dead())
        self.assertFalse(result["database"]["ok"])
        self.assertIsNone(result["last_success_at"])
        self.assertEqual((Dead.added[0].ok, Dead.added[0].database_ok), (False, False))
        self.assertIn("database", Dead.added[0].details)

    # ---- the log of every area ----
    def test_the_activity_feed_covers_every_area_and_hides_money_from_those_without_the_finance_view(self):
        self.client.post(P + "/auth/login", json={"username": "teacher1", "password": "Qx5a6ba62b7e4b-9"})
        self.make_live()
        self.new_booking()
        self.grant("mgr0", "control.view")
        full = self.client.get(C + "/activity", headers=self.admin).json()
        self.assertTrue({"security", "finance"} <= {row["domain"] for row in full})
        self.assertTrue(all(row["at_local"] for row in full))
        seen = self.client.get(C + "/activity", headers=self.mgr).json()
        self.assertNotIn("finance", {row["domain"] for row in seen})
        self.assertIn("security", {row["domain"] for row in seen})
        only = self.client.get(C + "/activity?domain=security", headers=self.admin).json()
        self.assertEqual({row["domain"] for row in only}, {"security"})


A_EMP = "/api/admin/accounting/employees"
