"""Working in one role at a time: the server knows the active role of a session and checks it on every request."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import activity, main
from app.models import Account, FeeAuditLog, PortalSession, Role
from tests.test_accounting_controls import PASSWORD, ControlsBase

P = "/api/platform"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


class RoleTests(ControlsBase):
    def setUp(self):
        super().setUp()
        with Session(self.engine) as s:
            roles = {r.name: r for r in s.scalars(select(Role))}
            for name, names in (("multi", ["parent", "teacher", "manager"]), ("money-teacher", ["accountant", "teacher"])):
                s.add(Account(username=name, password_hash=main.PASSWORD_HASHER.hash(PASSWORD), roles=[roles[n] for n in names]))
            s.commit()

    def login(self, name, headers=None):
        return self.client.post(P + "/auth/login", json={"username": name, "password": PASSWORD}, headers=headers or {})

    def bearer(self, result):
        return {"Authorization": "Bearer " + result["access_token"]}

    def switch(self, headers, role):
        return self.client.post(P + "/auth/switch-role", headers=headers, json={"role": role})

    def sessions(self):
        with Session(self.engine) as s:
            return {row.id: row for row in s.scalars(select(PortalSession))}

    def new_session(self, known):
        """The one session that was opened after `known` (the ones from the test set-up are not it)."""
        fresh = [row for key, row in self.sessions().items() if key not in known]
        self.assertEqual(len(fresh), 1)
        return fresh[0]

    def log(self, action=None):
        with Session(self.engine) as s:
            query = select(FeeAuditLog).order_by(FeeAuditLog.at)
            if action:
                query = query.where(FeeAuditLog.action == action)
            return list(s.scalars(query))

    # ---- login ----
    def test_one_role_works_in_that_role_at_once(self):
        result = self.login("teacher1").json()
        self.assertEqual((result["roles"], result["active_role"], result["needs_role_choice"]), (["teacher"], "teacher", False))
        me = self.client.get(P + "/auth/me", headers=self.bearer(result)).json()
        self.assertEqual((me["active_role"], me["needs_role_choice"]), ("teacher", False))

    def test_several_roles_must_be_chosen_but_an_older_client_that_never_chooses_keeps_working(self):
        result = self.login("multi").json()
        self.assertEqual((result["roles"], result["active_role"], result["needs_role_choice"]), (["manager", "parent", "teacher"], None, True))
        headers = self.bearer(result)
        self.assertEqual(self.client.get(P + "/teacher/children", headers=headers).status_code, 200)  # as before: all roles count
        self.assertEqual(self.client.get(P + "/parent/posts", headers=headers).status_code, 200)

    def test_when_the_server_insists_an_account_with_several_roles_must_choose_first(self):
        headers = self.bearer(self.login("multi").json())
        with patch.dict(os.environ, {"ENFORCE_ACTIVE_ROLE": "1"}):
            self.assertEqual(self.client.get(P + "/teacher/children", headers=headers).status_code, 403)
            self.assertEqual(self.client.get(P + "/parent/posts", headers=headers).status_code, 403)
            self.assertEqual(self.client.get(P + "/auth/me", headers=headers).status_code, 200)  # asking who I am and choosing still work
            chosen = self.switch(headers, "teacher")
            self.assertEqual(chosen.status_code, 200)
            self.assertEqual(self.client.get(P + "/teacher/children", headers=self.bearer(chosen.json())).status_code, 200)
            # a single-role account is not asked to choose
            single = self.bearer(self.login("teacher1").json())
            self.assertEqual(self.client.get(P + "/teacher/children", headers=single).status_code, 200)

    # ---- switching ----
    def test_switching_gives_a_new_session_and_the_old_one_ends(self):
        old = self.bearer(self.login("multi").json())
        chosen = self.switch(old, "teacher")
        self.assertEqual(chosen.status_code, 200, chosen.text)
        self.assertEqual((chosen.json()["active_role"], chosen.json()["needs_role_choice"]), ("teacher", False))
        self.assertEqual(self.client.get(P + "/auth/me", headers=old).status_code, 401)  # the old token is dead
        self.assertEqual(self.client.get(P + "/auth/me", headers=self.bearer(chosen.json())).json()["active_role"], "teacher")

    def test_a_website_tab_can_keep_its_old_session_while_it_opens_another_portal(self):
        old = self.bearer(self.login("multi").json())
        teacher = self.client.post(P + "/auth/switch-role", headers=old, json={"role": "teacher", "keep_previous": True})
        parent = self.client.post(P + "/auth/switch-role", headers=old, json={"role": "parent", "keep_previous": True})
        self.assertEqual((teacher.status_code, parent.status_code), (200, 200))
        self.assertEqual(self.client.get(P + "/auth/me", headers=old).status_code, 200)  # the first tab still works
        self.assertEqual(self.client.get(P + "/teacher/children", headers=self.bearer(teacher.json())).status_code, 200)
        self.assertEqual(self.client.get(P + "/teacher/children", headers=self.bearer(parent.json())).status_code, 403)  # but each session has its own role

    def test_in_the_chosen_role_nothing_of_the_other_roles_is_open(self):
        old = self.bearer(self.login("multi").json())
        teacher = self.bearer(self.switch(old, "teacher").json())
        self.assertEqual(self.client.get(P + "/teacher/children", headers=teacher).status_code, 200)
        self.assertEqual(self.client.get(P + "/parent/posts", headers=teacher).status_code, 403)
        self.assertEqual(self.client.get(P + "/review/reports", headers=teacher).status_code, 403)
        manager = self.bearer(self.switch(teacher, "manager").json())
        self.assertEqual(self.client.get(P + "/review/reports", headers=manager).status_code, 200)
        self.assertEqual(self.client.get(P + "/teacher/children", headers=manager).status_code, 403)
        parent = self.bearer(self.switch(manager, "parent").json())
        self.assertEqual(self.client.get(P + "/parent/posts", headers=parent).status_code, 200)
        self.assertEqual(self.client.get(P + "/review/reports", headers=parent).status_code, 403)

    def test_a_role_the_account_does_not_hold_is_refused_and_logged_and_the_session_stays(self):
        headers = self.bearer(self.login("teacher1").json())
        for role in ("admin", "accountant", "manager", "nonsense"):
            self.assertEqual(self.switch(headers, role).status_code, 403, role)
        self.assertEqual(self.client.get(P + "/auth/me", headers=headers).status_code, 200)  # not thrown out, nothing changed
        denied = self.log("auth.switch_role.denied")
        self.assertEqual([row.reason for row in denied], ["admin", "accountant", "manager", "nonsense"])
        self.assertTrue(all(row.actor_name == "teacher1" and row.domain == "security" for row in denied))

    def test_switching_is_written_to_the_log_with_before_and_after(self):
        old = self.bearer(self.login("multi").json())
        self.switch(old, "teacher")
        row = self.log("auth.switch_role")[0]
        self.assertEqual((row.actor_name, row.domain, row.before_json, row.after_json), ("multi", "security", '{"active_role": null}', '{"active_role": "teacher"}'))

    def test_a_role_taken_away_stops_working_at_once(self):
        teacher = self.bearer(self.switch(self.bearer(self.login("multi").json()), "teacher").json())
        self.assertEqual(self.client.get(P + "/teacher/children", headers=teacher).status_code, 200)
        with Session(self.engine) as s:
            account = s.scalar(select(Account).where(Account.username == "multi"))
            account.roles = [r for r in account.roles if r.name != "teacher"]
            s.commit()
        self.assertEqual(self.client.get(P + "/teacher/children", headers=teacher).status_code, 403)

    def test_the_accounting_follows_the_active_role_too(self):
        old = self.bearer(self.login("money-teacher").json())
        money = self.bearer(self.switch(old, "accountant").json())
        self.assertEqual(self.client.get("/api/admin/fees/me", headers=money).status_code, 200)
        teacher = self.bearer(self.switch(money, "teacher").json())
        self.assertEqual(self.client.get("/api/admin/fees/me", headers=teacher).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/accounting/cash", headers=teacher).status_code, 403)

    def test_the_server_admin_login_is_not_affected(self):
        self.assertEqual(self.client.get("/api/admin/fees/me", headers=self.admin).status_code, 200)

    # ---- sessions and the log ----
    def test_a_session_remembers_the_kind_of_device_but_never_the_address_or_the_browser_text(self):
        known = set(self.sessions())
        self.login("teacher1", headers={"user-agent": CHROME, "x-forwarded-for": "203.0.113.9"})
        row = self.new_session(known)
        self.assertEqual(row.device_label, "Windows · Chrome")
        self.assertEqual((len(row.ip_hash), len(row.user_agent_hash)), (64, 64))
        self.assertNotIn("203.0.113.9", row.ip_hash + row.user_agent_hash + row.device_label)
        self.assertIsNotNone(row.last_seen_at)
        known = set(self.sessions())
        self.login("teacher1", headers={"user-agent": CHROME, "x-forwarded-for": "198.51.100.4"})
        self.assertNotEqual(self.new_session(known).ip_hash, row.ip_hash)  # another address is another fingerprint
        self.assertEqual(self.new_session(known).user_agent_hash, row.user_agent_hash)

    def test_the_last_use_of_a_session_is_kept_up_to_date(self):
        known = set(self.sessions())
        headers = self.bearer(self.login("teacher1").json())
        key = self.new_session(known).id
        long_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        with Session(self.engine) as s:
            s.get(PortalSession, key).last_seen_at = long_ago
            s.commit()
        self.client.get(P + "/auth/me", headers=headers)
        with Session(self.engine) as s:
            self.assertGreater(s.get(PortalSession, key).last_seen_at, long_ago)

    def test_sign_ins_are_logged_and_a_wrong_password_only_for_a_real_account(self):
        self.login("teacher1", headers={"user-agent": CHROME})
        self.client.post(P + "/auth/login", json={"username": "teacher1", "password": "wrong-password-123"}, headers={"user-agent": CHROME})
        self.client.post(P + "/auth/login", json={"username": "nobody-there", "password": "wrong-password-123"})
        good, bad = [r for r in self.log("auth.login") if "Chrome" in r.details], self.log("auth.login.failed")
        self.assertEqual([(r.actor_name, r.domain, r.details) for r in good], [("teacher1", "security", "Windows · Chrome")])
        self.assertEqual([r.actor_name for r in bad], ["teacher1"])  # the typed name of an unknown account is never stored
        self.assertNotIn("nobody-there", " ".join(r.actor_name + r.details for r in self.log()))

    def test_the_money_log_stays_a_money_log_and_the_administrator_can_ask_for_the_rest(self):
        self.login("teacher1")
        self.client.post("/api/admin/accounting/cash/counts", headers=self.acc, json={})  # (a refused call; the log only shows real changes)
        money_log = self.client.get("/api/admin/fees/audit", headers=self.admin).json()
        self.assertNotIn("auth.login", {row["action"] for row in money_log})
        everything = self.client.get("/api/admin/fees/audit?domain=all", headers=self.admin).json()
        self.assertIn("auth.login", {row["action"] for row in everything})
        security = self.client.get("/api/admin/fees/audit?domain=security", headers=self.admin).json()
        self.assertTrue(security and all(row["entity_type"] == "session" for row in security))
        # an accountant never gets past the money area, whatever they ask for
        mine = self.client.get("/api/admin/fees/audit?domain=all", headers=self.acc).json()
        self.assertNotIn("auth.login", {row["action"] for row in mine})

    def test_helpers(self):
        self.assertEqual(activity.hash_value("s", "ip", "1.2.3.4"), activity.hash_value("s", "ip", "1.2.3.4"))
        self.assertNotEqual(activity.hash_value("s", "ip", "1.2.3.4"), activity.hash_value("s", "ua", "1.2.3.4"))
        self.assertEqual(activity.describe_device("Dart/3.5 (dart:io)"), "Zahra+ App")
        self.assertEqual(activity.describe_device("Mozilla/5.0 (Linux; Android 14) Chrome/120"), "Android · Chrome")
        self.assertEqual(activity.describe_device(""), "")
