"""Adding children with one or both parents (accountant / admin area)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Child, ChildGuardian, FeeAuditLog, Role, parent_child_links
from tests.test_accounting_controls import A, ControlsBase


def father(**extra):
    return {"relation": "father", "name": "أحمد", "phone": "0933111222", "email": "ahmad@example.com", **extra}


def mother(**extra):
    return {"relation": "mother", "name": "ريم", "phone": "0944222333", **extra}


class ChildrenTests(ControlsBase):
    def make(self, name="سلمى", guardians=None, headers=None, **extra):
        return self.client.post(A + "/children", headers=headers or self.acc, json={
            "name": name, "class_name": "KG1", "birth_date": "2021-05-04",
            "guardians": [father(), mother()] if guardians is None else guardians, **extra})

    def parent_account(self, username="baba1"):
        with Session(self.engine) as session:
            role = session.scalar(select(Role).where(Role.name == "parent"))
            account = Account(username=username, password_hash="x", roles=[role])
            session.add(account)
            session.commit()
            return str(account.id)

    def links(self):
        with Session(self.engine) as session:
            return {(str(a), str(c)) for a, c in session.execute(select(parent_child_links.c.account_id, parent_child_links.c.child_id)).all()}

    # ---- adding ----
    def test_a_child_with_both_parents(self):
        made = self.make()
        self.assertEqual(made.status_code, 201, made.text)
        child = made.json()
        self.assertEqual((child["name"], child["class_name"], child["birth_date"]), ("سلمى", "KG1", "2021-05-04"))
        self.assertEqual([(g["relation"], g["name"]) for g in child["guardians"]], [("mother", "ريم"), ("father", "أحمد")])
        listed = self.client.get(A + "/children", headers=self.acc).json()
        self.assertIn("سلمى", [c["name"] for c in listed])
        self.assertIn("child.create", [row.action for row in self._audit()])

    def test_a_child_with_one_parent_only(self):
        for who in (father(), mother()):
            made = self.make(name="طفل " + who["relation"], guardians=[who])
            self.assertEqual(made.status_code, 201, made.text)
            self.assertEqual(len(made.json()["guardians"]), 1)

    def test_a_child_needs_one_or_two_parents_never_more_or_the_same_role_twice(self):
        self.assertEqual(self.make(guardians=[]).status_code, 422)
        self.assertEqual(self.make(guardians=[father(), mother(), {"relation": "guardian", "name": "جدة"}]).status_code, 422)
        self.assertEqual(self.make(guardians=[father(), father(name="آخر", email="x@example.com")]).status_code, 422)
        self.assertEqual(self.make(guardians=[father(), mother(email="ahmad@example.com")]).status_code, 422)  # same e-mail twice
        self.assertEqual(self.make(guardians=[{"relation": "uncle", "name": "عم"}]).status_code, 422)
        self.assertEqual(self.make(guardians=[{"relation": "father", "name": "أ"}]).status_code, 422)  # name too short
        self.assertEqual(self.make(guardians=[{"relation": "guardian", "name": "الجدة"}]).status_code, 201)  # another guardian is fine alone
        self.assertEqual(self.make(name="س").status_code, 422)

    def test_the_same_name_cannot_be_added_twice(self):
        self.make()
        self.assertEqual(self.make(name="  سلمى ").status_code, 409)
        self.assertEqual(self.make(name="Amal").status_code, 409)  # the child that already exists in the fees list

    def test_only_accountant_and_admin_add_children(self):
        for headers in (self.teacher, self.parent):
            self.assertEqual(self.make(headers=headers).status_code, 403)
            self.assertEqual(self.client.get(A + "/children", headers=headers).status_code, 403)
            self.assertEqual(self.client.get(A + "/parent-accounts", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(A + "/children").status_code, 401)
        self.assertEqual(self.make(headers=self.admin).status_code, 201)

    # ---- the portal account of a parent ----
    def test_a_parent_account_is_tied_to_the_child(self):
        account = self.parent_account()
        child = self.make(guardians=[father(account_id=account), mother()]).json()
        self.assertEqual(child["guardians"][1]["account_username"], "baba1")
        self.assertEqual(self.links(), {(account, child["id"])})  # the parent sees the child in the portal
        listing = self.client.get(A + "/parent-accounts", headers=self.acc).json()
        self.assertIn("baba1", [a["username"] for a in listing])

    def test_only_active_parent_accounts_can_be_tied(self):
        with Session(self.engine) as session:
            teacher = str(session.scalar(select(Account.id).where(Account.username == "teacher1")))
        self.assertEqual(self.make(guardians=[father(account_id=teacher)]).status_code, 404)
        self.assertEqual(self.make(guardians=[father(account_id=str(uuid.uuid4()))]).status_code, 404)
        self.assertEqual(self.make(guardians=[father(account_id=self.parent_account("a")), mother(account_id=self.parent_account("a2"))]).status_code, 201)
        same = self.parent_account("shared")
        self.assertEqual(self.make(name="ثانٍ", guardians=[father(account_id=same), mother(account_id=same)]).status_code, 422)
        self.assertEqual(Child_count(self.engine), 2)  # Amal + the one accepted; the refused ones left nothing behind

    def test_siblings_share_one_parent_account(self):
        account = self.parent_account()
        self.make(name="الأخ الأكبر", guardians=[father(account_id=account)])
        self.make(name="الأخت الصغرى", guardians=[father(account_id=account)])
        self.assertEqual(len(self.links()), 2)

    # ---- changing ----
    def test_the_second_parent_can_be_added_later_and_removed_again(self):
        account = self.parent_account("mama")
        child = self.make(guardians=[father()]).json()
        body = {"name": "سلمى", "class_name": "KG2", "birth_date": "2021-05-04",
                "guardians": [{"id": child["guardians"][0]["id"], **father()}, mother(account_id=account)]}
        two = self.client.patch(f"{A}/children/{child['id']}", headers=self.acc, json=body)
        self.assertEqual(two.status_code, 200, two.text)
        self.assertEqual((two.json()["class_name"], len(two.json()["guardians"])), ("KG2", 2))
        self.assertEqual(self.links(), {(account, child["id"])})
        body["guardians"] = [{"id": child["guardians"][0]["id"], **father(phone="0999")}]
        one = self.client.patch(f"{A}/children/{child['id']}", headers=self.acc, json=body).json()
        self.assertEqual([(g["relation"], g["phone"]) for g in one["guardians"]], [("father", "0999")])
        self.assertEqual(self.links(), set())  # the mother is gone, so is her access
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(ChildGuardian).where(ChildGuardian.child_id == uuid.UUID(child["id"]))).all()), 1)

    def test_changing_the_account_of_a_parent_moves_the_access(self):
        first, second = self.parent_account("one"), self.parent_account("two")
        child = self.make(guardians=[father(account_id=first)]).json()
        body = {"name": "سلمى", "class_name": "", "guardians": [{"id": child["guardians"][0]["id"], **father(account_id=second)}]}
        self.assertEqual(self.client.patch(f"{A}/children/{child['id']}", headers=self.acc, json=body).status_code, 200)
        self.assertEqual(self.links(), {(second, child["id"])})
        body["guardians"] = [father()]  # no account any more
        self.client.patch(f"{A}/children/{child['id']}", headers=self.acc, json=body)
        self.assertEqual(self.links(), set())

    def test_an_update_cannot_leave_a_child_without_parents_or_clash_with_another_child(self):
        child = self.make().json()
        base = {"name": "سلمى", "class_name": "", "guardians": []}
        self.assertEqual(self.client.patch(f"{A}/children/{child['id']}", headers=self.acc, json=base).status_code, 422)
        base["guardians"] = [father()]
        base["name"] = "Amal"
        self.assertEqual(self.client.patch(f"{A}/children/{child['id']}", headers=self.acc, json=base).status_code, 409)
        base["name"] = "سلمى"
        self.assertEqual(self.client.patch(f"{A}/children/{uuid.uuid4()}", headers=self.acc, json=base).status_code, 404)
        self.assertEqual(self.client.patch(f"{A}/children/{child['id']}", headers=self.teacher, json=base).status_code, 403)

    def test_removing_a_child_keeps_the_fees(self):
        child = self.make(name="Amal2").json()
        charge = self.charge(month=2)  # the fee list of the existing child Amal
        self.assertEqual(self.client.delete(f"{A}/children/{child['id']}", headers=self.acc).status_code, 204)
        self.assertNotIn("Amal2", [c["name"] for c in self.client.get(A + "/children", headers=self.acc).json()])
        self.assertEqual(self.client.delete(f"{A}/children/{child['id']}", headers=self.acc).status_code, 404)
        self.assertEqual(self.client.get("/api/admin/fees?year=2026&month=2", headers=self.acc).json()["rows"][0]["id"], charge["id"])
        self.assertEqual(self.make(name="Amal2").status_code, 201)  # the name is free again

    def _audit(self):
        with Session(self.engine) as session:
            return session.scalars(select(FeeAuditLog)).all()


def Child_count(engine):
    with Session(engine) as session:
        return len(session.scalars(select(Child).where(Child.is_active.is_(True))).all())
