"""Notifications, management notices, groups, the management role and the new report fields."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import main
from app.models import Account, Child, ChildGuardian, Role, parent_child_links, teacher_child_links
from tests.test_accounting_controls import PASSWORD, ControlsBase

M = "/api/admin/platform"
P = "/api/platform"


class CommunityTests(ControlsBase):
    def setUp(self):
        super().setUp()
        with Session(self.engine) as session:
            manager = Role(name="manager")
            session.add(manager)
            session.add(Account(username="manager1", password_hash=main.PASSWORD_HASHER.hash(PASSWORD), roles=[manager]))
            parent_role = session.scalar(select(Role).where(Role.name == "parent"))
            session.add(Account(username="parent2", password_hash=main.PASSWORD_HASHER.hash(PASSWORD), roles=[parent_role]))
            session.commit()
            amal = session.scalar(select(Child).where(Child.display_name == "Amal"))
            other = Child(display_name="Omar", class_name="KG2")
            session.add(other)
            session.flush()
            now = datetime.now(timezone.utc)
            ids = {a.username: a.id for a in session.scalars(select(Account)).all()}
            session.execute(parent_child_links.insert().values(account_id=ids["parent1"], child_id=amal.id, confirmed_at=now))
            session.execute(parent_child_links.insert().values(account_id=ids["parent2"], child_id=other.id, confirmed_at=now))
            session.execute(teacher_child_links.insert().values(account_id=ids["teacher1"], child_id=amal.id, assigned_at=now))
            session.add(ChildGuardian(child_id=amal.id, relation="father", name="أحمد", phone="0933", email="a@example.com", account_id=ids["parent1"]))
            session.add(ChildGuardian(child_id=amal.id, relation="mother", name="ريم", phone="0944"))
            session.commit()
            self.amal, self.omar = str(amal.id), str(other.id)
        self.manager = {"Authorization": "Bearer " + self.client.post(
            P + "/auth/login", json={"username": "manager1", "password": PASSWORD}).json()["access_token"]}
        self.parent2 = {"Authorization": "Bearer " + self.client.post(
            P + "/auth/login", json={"username": "parent2", "password": PASSWORD}).json()["access_token"]}

    def inbox(self, headers):
        return self.client.get(P + "/notifications", headers=headers).json()

    def kinds(self, headers):
        return [item["kind"] for item in self.inbox(headers)["items"]]

    # ---- the daily report: activities, meals, notifications along the way ----
    def test_report_travels_from_teacher_to_manager_to_parent(self):
        made = self.client.post(P + "/teacher/reports", headers=self.teacher, json={
            "child_id": self.amal, "title": "يوم ممتع", "body": "لعب", "activities": "رسم وقصة", "meals": "فطور وغداء", "submit_for_review": True})
        self.assertEqual(made.status_code, 201, made.text)
        self.assertEqual((made.json()["activities"], made.json()["meals"]), ("رسم وقصة", "فطور وغداء"))
        self.assertEqual(self.kinds(self.manager), ["report_submitted"])
        self.assertEqual(self.inbox(self.manager)["items"][0]["subject"], "Amal")
        self.assertEqual(self.kinds(self.parent), [])  # not visible to the family yet
        done = self.client.patch(P + "/review/reports/" + made.json()["id"], headers=self.manager, json={"status": "published"})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(self.kinds(self.parent), ["report_published"])
        self.assertEqual(self.kinds(self.parent2), [])  # another child's parent hears nothing
        seen = self.client.get(f"{P}/children/{self.amal}/reports", headers=self.parent).json()
        self.assertEqual((seen[0]["meals"], seen[0]["activities"]), ("فطور وغداء", "رسم وقصة"))

    def test_a_returned_report_tells_the_teacher(self):
        made = self.client.post(P + "/teacher/reports", headers=self.teacher, json={
            "child_id": self.amal, "title": "t", "body": "b", "submit_for_review": True}).json()
        self.client.patch(P + "/review/reports/" + made["id"], headers=self.manager, json={"status": "rejected"})
        self.assertEqual(self.kinds(self.teacher), ["report_returned"])

    def test_a_draft_notifies_nobody(self):
        self.client.post(P + "/teacher/reports", headers=self.teacher, json={"child_id": self.amal, "title": "t", "body": "b"})
        self.assertEqual(self.kinds(self.manager), [])

    def test_posts_notify_the_right_parents(self):
        general = self.client.post(P + "/teacher/posts", headers=self.teacher, data={"scope": "general", "title": "رحلة", "body": "x"})
        self.assertEqual(general.status_code, 201, general.text)
        private = self.client.post(P + "/teacher/posts", headers=self.teacher, data={"scope": "child", "title": "ملاحظة", "body": "x", "child_id": self.amal})
        self.assertEqual(private.status_code, 201, private.text)
        self.assertEqual(self.kinds(self.parent), ["post_new", "post_new"])
        self.assertEqual(self.kinds(self.parent2), ["post_new"])  # only the general one

    # ---- reading notifications ----
    def test_reading_notifications(self):
        for _ in range(2):
            self.client.post(P + "/teacher/posts", headers=self.teacher, data={"scope": "general", "title": "x", "body": "y"})
        box = self.inbox(self.parent)
        self.assertEqual(box["unread"], 2)
        first = box["items"][0]["id"]
        self.assertEqual(self.client.post(f"{P}/notifications/{first}/read", headers=self.parent).status_code, 204)
        self.assertEqual(self.inbox(self.parent)["unread"], 1)
        self.assertEqual(self.client.post(f"{P}/notifications/{first}/read", headers=self.parent2).status_code, 404)  # not theirs
        self.assertEqual(self.client.post(P + "/notifications/read-all", headers=self.parent).status_code, 204)
        self.assertEqual(self.inbox(self.parent)["unread"], 0)
        self.assertEqual(self.client.get(P + "/notifications").status_code, 401)

    # ---- notices of the management ----
    def test_notice_reaches_parents_and_teachers_only_the_management_writes_it(self):
        made = self.client.post(M + "/announcements", headers=self.manager, json={"title": "إجازة", "body": "الروضة مغلقة غداً"})
        self.assertEqual(made.status_code, 201, made.text)
        for headers in (self.parent, self.parent2, self.teacher):
            self.assertEqual(self.kinds(headers), ["announcement"])
            self.assertEqual(self.client.get(P + "/announcements", headers=headers).json()[0]["title"], "إجازة")
        for headers in (self.parent, self.teacher, self.acc):
            self.assertIn(self.client.post(M + "/announcements", headers=headers, json={"title": "x"}).status_code, (401, 403))
        self.assertEqual(self.client.post(M + "/announcements", headers=self.admin, json={"title": "من المدير"}).status_code, 201)
        self.assertEqual(self.client.delete(f"{M}/announcements/{made.json()['id']}", headers=self.manager).status_code, 204)
        self.assertEqual(len(self.client.get(P + "/announcements", headers=self.parent).json()), 1)
        self.assertEqual(self.client.post(M + "/announcements", headers=self.manager, json={"title": "  "}).status_code, 422)

    # ---- the management role ----
    def test_manager_works_with_children_groups_and_numbers(self):
        children = self.client.get(M + "/children", headers=self.manager)
        self.assertEqual(children.status_code, 200, children.text)
        amal = [c for c in children.json() if c["display_name"] == "Amal"][0]
        self.assertEqual(amal["class_name"], "KG1")
        self.assertEqual(sorted(g["relation"] for g in amal["guardians"]), ["father", "mother"])
        stats = self.client.get(M + "/stats", headers=self.manager).json()
        self.assertEqual((stats["children"], stats["parents"], stats["teachers"], stats["groups"]), (2, 2, 1, 2))
        self.assertEqual(self.client.patch(f"{M}/children/{self.omar}/group", headers=self.manager, json={"class_name": "KG1"}).status_code, 200)
        self.assertEqual(self.client.get(M + "/groups", headers=self.manager).json(), [{"name": "KG1", "children": 2}])
        renamed = self.client.post(M + "/groups/rename", headers=self.manager, json={"old_name": "KG1", "new_name": "الروضة الأولى"})
        self.assertEqual(renamed.json(), {"children": 2})
        self.assertEqual(self.client.post(M + "/groups/rename", headers=self.manager, json={"old_name": "none", "new_name": "x"}).status_code, 404)
        with Session(self.engine) as session:
            teacher = str(session.scalar(select(Account.id).where(Account.username == "teacher1")))
        assign = self.client.post(f"{M}/children/{self.omar}/teachers", headers=self.manager, json={"teacher_id": teacher})
        self.assertEqual(assign.status_code, 201, assign.text)

    def test_nobody_else_gets_management_rights(self):
        for headers in (self.teacher, self.parent, self.acc):
            for path in ("/children", "/stats", "/groups", "/registration-requests"):
                self.assertIn(self.client.get(M + path, headers=headers).status_code, (401, 403), path)
            self.assertIn(self.client.patch(f"{M}/children/{self.omar}/group", headers=headers, json={"class_name": "x"}).status_code, (401, 403))
        self.assertEqual(self.client.get(M + "/stats").status_code, 401)
        # a manager still cannot open the accounts or the fees
        self.assertIn(self.client.get(M + "/accounts", headers=self.manager).status_code, (401, 403))
        self.assertEqual(self.client.get("/api/admin/fees/children", headers=self.manager).status_code, 403)

    # ---- the parent's view of the other guardians ----
    def test_parent_sees_guardians_of_their_own_child_without_contact_data(self):
        listing = self.client.get(f"{P}/parent/children/{self.amal}/guardians", headers=self.parent)
        self.assertEqual(listing.status_code, 200, listing.text)
        body = listing.json()
        self.assertEqual([(g["relation"], g["name"], g["has_account"], g["is_me"]) for g in body],
                         [("father", "أحمد", True, True), ("mother", "ريم", False, False)])
        self.assertTrue(all(set(g) == {"relation", "name", "has_account", "is_me"} for g in body))
        self.assertEqual(self.client.get(f"{P}/parent/children/{self.amal}/guardians", headers=self.parent2).status_code, 404)
        self.assertEqual(self.client.get(f"{P}/parent/children/{self.amal}/guardians", headers=self.teacher).status_code, 403)

    # ---- teacher storage ----
    def test_teacher_storage_use(self):
        base = self.client.get(P + "/teacher/storage", headers=self.teacher).json()
        self.assertEqual((base["used_bytes"], base["limit_bytes"]), (0, 250 * 1024 * 1024))
        self.assertEqual(self.client.get(P + "/teacher/storage", headers=self.parent).status_code, 403)
