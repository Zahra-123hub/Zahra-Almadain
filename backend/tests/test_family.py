"""Parents and children connected without friction: one connection in the portal and in the child's record."""

import unittest

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import family
from app.models import Account, Child, ChildGuardian, parent_child_links
from tests.base import PEOPLE, ControlsBase

PASSWORD = "Qxdaa9b450839c-9"


class FamilyTests(ControlsBase):
    def request(self, child_name, relation="mother", email="mona@example.com", phone="+963 11 1234567"):
        body = {"guardian_name": "Mona Parent", "email": email, "phone": phone, "child_name": child_name,
                "child_birth_date": "2021-05-04", "relationship_to_child": relation, "notes": "", "preferred_language": "ar"}
        self.assertEqual(self.client.post("/api/platform/registration-requests", json=body).status_code, 202)
        items = self.client.get("/api/admin/platform/registration-requests", headers=self.admin).json()
        return next(i for i in items if i["child_name"] == child_name.strip() and i["status"] == "pending")

    def redeem(self, code, username):
        made = self.client.post("/api/platform/auth/redeem-invitation", json={"invitation_code": code, "username": username, "password": PASSWORD})
        self.assertEqual(made.status_code, 202, made.text)
        with Session(self.engine) as s:
            return s.scalar(select(Account.id).where(Account.username == username))

    def record(self, name):
        return next(c for c in self.client.get(PEOPLE + "/children", headers=self.mgr).json() if c["name"] == name)

    def test_an_approved_request_uses_the_child_on_the_list_and_fills_the_record(self):
        self.enroll("Sam")
        item = self.request("sam ")
        approved = self.client.post(f"/api/admin/platform/registration-requests/{item['id']}/decision", headers=self.admin, json={"decision": "approve"})
        self.assertEqual(approved.status_code, 200)
        with Session(self.engine) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Child).where(func.lower(Child.display_name) == "sam")), 1)
        mother = next(g for g in self.record("Sam")["guardians"] if g["relation"] == "mother")
        self.assertEqual((mother["name"], mother["email"], mother["account_id"]), ("Mona Parent", "mona@example.com", ""))

        account = self.redeem(approved.json()["registration_code"], "mona")
        record = self.record("Sam")
        mother = next(g for g in record["guardians"] if g["relation"] == "mother")
        self.assertEqual((mother["account_id"], mother["account_username"]), (str(account), "mona"))
        self.assertEqual(record["other_accounts"], [])
        # deleting the request now is refused (it has an account); the child stays in every case
        self.assertEqual(self.client.delete(f"/api/admin/platform/registration-requests/{item['id']}", headers=self.admin).status_code, 409)

    def test_deleting_a_request_never_removes_a_child_that_was_on_the_list(self):
        self.enroll("Rami")
        item = self.request("Rami", email="rami@example.com")
        self.client.post(f"/api/admin/platform/registration-requests/{item['id']}/decision", headers=self.admin, json={"decision": "approve"})
        self.assertEqual(self.client.delete(f"/api/admin/platform/registration-requests/{item['id']}", headers=self.admin).status_code, 204)
        self.assertEqual(self.record("Rami")["name"], "Rami")

    def test_an_invitation_for_the_father_of_the_record(self):
        child = self.enroll("Lina")
        invite = self.client.post(f"{PEOPLE}/children/{child['id']}/invite", headers=self.mgr, json={"relation": "father"})
        self.assertEqual(invite.status_code, 201, invite.text)
        self.assertIn("/login/?code=", invite.json()["link"])
        self.assertEqual(self.client.post(f"{PEOPLE}/children/{child['id']}/invite", headers=self.acc, json={"relation": "father"}).status_code, 403)
        account = self.redeem(invite.json()["code"].lower(), "lina-dad")
        father = next(g for g in self.record("Lina")["guardians"] if g["relation"] == "father")
        self.assertEqual(father["account_id"], str(account))
        with Session(self.engine) as s:
            self.assertIsNotNone(s.execute(select(parent_child_links).where(parent_child_links.c.account_id == account)).first())
        self.assertEqual(self.client.post(f"{PEOPLE}/children/{child['id']}/invite", headers=self.mgr, json={"relation": "father"}).status_code, 409)
        # the father's account is found for the record's account field with what is known about him
        accounts = {a["username"]: a for a in self.client.get(PEOPLE + "/parent-accounts", headers=self.mgr).json()}
        self.assertEqual((accounts["lina-dad"]["name"], accounts["lina-dad"]["children"]), ("Father of Lina", ["Lina"]))

    def test_a_link_made_elsewhere_shows_in_the_record_and_is_taken_off_everywhere(self):
        child = self.enroll("Omar")
        with Session(self.engine) as s:
            parent = s.scalar(select(Account.id).where(Account.username == "parent1"))
        made = self.client.post(f"/api/admin/platform/children/{child['id']}/parents", headers=self.admin, json={"parent_id": str(parent)})
        self.assertEqual(made.status_code, 201)
        self.assertEqual(self.record("Omar")["other_accounts"], [{"id": str(parent), "username": "parent1"}])
        # put on the father in the record, then taken off by the admin: gone from the record too
        record = self.record("Omar")
        father = record["guardians"][0]
        self.client.patch(f"{PEOPLE}/children/{child['id']}", headers=self.mgr, json={"name": "Omar", "class_name": "KG1", "guardians": [{**{k: father[k] for k in ("id", "relation", "name", "phone", "email")}, "account_id": str(parent)}]})
        self.assertEqual(self.record("Omar")["guardians"][0]["account_id"], str(parent))
        self.assertEqual(self.client.delete(f"/api/admin/platform/children/{child['id']}/parents/{parent}", headers=self.admin).status_code, 204)
        self.assertEqual(self.record("Omar")["guardians"][0]["account_id"], "")
        with Session(self.engine) as s:
            self.assertIsNone(s.scalar(select(ChildGuardian.account_id).where(ChildGuardian.account_id == parent)))


class WordsTests(unittest.TestCase):
    def test_relation_of_what_the_parents_wrote(self):
        self.assertEqual([family.relation_of(t) for t in ("الأم", "Vater", "ولي الأمر", "mother", "", "الأب / father")],
                         ["mother", "father", "guardian", "mother", "guardian", "father"])
        self.assertTrue(family.same_phone("+963 11 1234567", "011-1234567"))
        self.assertFalse(family.same_phone("123", "123"))
