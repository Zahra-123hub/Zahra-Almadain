"""Everyday life of a child: notes, things to bring, the week plan, attendance, messages and the parents' fees."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Child, Notification, parent_child_links
from app.timeutil import local_today
from tests.base import MONEY, ControlsBase

P = "/api/platform/parent/children"
S = "/api/platform/staff"


class EverydayBase(ControlsBase):
    def setUp(self):
        super().setUp()
        with Session(self.engine) as s:
            amal = s.scalar(select(Child).where(Child.display_name == "Amal"))
            other = Child(display_name="Basel", class_name="KG2")
            s.add(other)
            s.flush()
            parent_id = s.scalar(select(Account.id).where(Account.username == "parent1"))
            s.execute(parent_child_links.insert().values(account_id=parent_id, child_id=amal.id, confirmed_at=datetime.now(timezone.utc)))
            s.commit()
            self.amal, self.basel, self.parent_id = str(amal.id), str(other.id), str(parent_id)

    def notes_of(self, kind):
        with Session(self.engine) as s:
            return s.scalars(select(Notification.kind).where(Notification.kind == kind)).all()


class ChildPageTests(EverydayBase):
    def test_a_parent_sees_only_their_own_child(self):
        page = self.client.get(f"{P}/{self.amal}/overview", headers=self.parent)
        self.assertEqual((page.status_code, page.json()["name"], page.json()["class_name"]), (200, "Amal", "KG1"))
        self.assertEqual(self.client.get(f"{P}/{self.basel}/overview", headers=self.parent).status_code, 404)
        self.assertEqual(self.client.get(f"{P}/{self.amal}/overview", headers=self.teacher).status_code, 403)

    def test_notes_are_written_by_the_kindergarten_and_read_by_the_parents(self):
        made = self.client.post(f"{S}/children/{self.amal}/notes", headers=self.teacher, json={"kind": "praise", "text": "Full marks in drawing"})
        self.assertEqual(made.status_code, 201)
        self.assertEqual(self.client.post(f"{S}/children/{self.amal}/notes", headers=self.parent, json={"text": "x"}).status_code, 403)
        notes = self.client.get(f"{P}/{self.amal}/notes", headers=self.parent).json()
        self.assertEqual([(n["kind"], n["text"]) for n in notes], [("praise", "Full marks in drawing")])
        self.assertEqual(len(self.notes_of("note_praise")), 1)
        self.assertEqual(self.client.get(f"{P}/{self.amal}/overview", headers=self.parent).json()["counts"]["notes_new"], 1)
        self.assertEqual(self.client.delete(f"{S}/notes/{made.json()['id']}", headers=self.teacher).status_code, 204)
        self.assertEqual(self.client.get(f"{P}/{self.amal}/notes", headers=self.parent).json(), [])

    def test_things_to_bring_for_a_group_every_group_or_one_child(self):
        due = (local_today() + timedelta(days=2)).isoformat()
        self.client.post(f"{S}/bring", headers=self.teacher, json={"title": "Apron for painting", "class_name": "KG1", "due_on": due})
        self.client.post(f"{S}/bring", headers=self.teacher, json={"title": "Warm jacket"})
        self.client.post(f"{S}/bring", headers=self.teacher, json={"title": "Other group only", "class_name": "KG2"})
        self.client.post(f"{S}/bring", headers=self.teacher, json={"title": "Signed form", "child_id": self.amal})
        titles = sorted(b["title"] for b in self.client.get(f"{P}/{self.amal}/bring", headers=self.parent).json())
        self.assertEqual(titles, ["Apron for painting", "Signed form", "Warm jacket"])
        self.assertTrue(self.notes_of("bring_new"))

    def test_the_week_plan_of_the_group(self):
        saved = self.client.put(f"{S}/plan", headers=self.teacher, json={"class_name": "KG1", "entries": [
            {"weekday": 0, "position": 2, "title": "Music"}, {"weekday": 0, "position": 1, "title": "Letters", "detail": "A to E"}, {"weekday": 3, "title": "Garden"}]})
        self.assertEqual(saved.status_code, 200)
        plan = self.client.get(f"{P}/{self.amal}/plan", headers=self.parent).json()
        self.assertEqual([(e["weekday"], e["position"], e["title"]) for e in plan["entries"]], [(0, 1, "Letters"), (0, 2, "Music"), (3, 1, "Garden")])
        self.client.put(f"{S}/plan", headers=self.teacher, json={"class_name": "KG1", "entries": [{"weekday": 1, "title": "Sport"}]})
        self.assertEqual([e["title"] for e in self.client.get(f"{P}/{self.amal}/plan", headers=self.parent).json()["entries"]], ["Sport"])
        self.assertEqual(self.client.put(f"{S}/plan", headers=self.teacher, json={"class_name": "KG1", "entries": [{"weekday": 6, "title": "x"}]}).status_code, 422)

    def test_attendance_marked_by_the_kindergarten_and_absence_reported_by_the_parents(self):
        today = local_today()
        tomorrow = (today + timedelta(days=1)).isoformat()
        reported = self.client.post(f"{P}/{self.amal}/absence", headers=self.parent, json={"day": tomorrow, "status": "sick", "note": "fever"})
        self.assertEqual(reported.status_code, 201)
        self.assertTrue(self.notes_of("absence_reported"))
        self.assertEqual(self.client.post(f"{P}/{self.amal}/absence", headers=self.parent, json={"day": (today - timedelta(days=1)).isoformat()}).status_code, 422)
        saved = self.client.put(f"{S}/attendance", headers=self.teacher, json={"day": today.isoformat(), "entries": [{"child_id": self.amal, "status": "present"}, {"child_id": self.basel, "status": "absent"}]})
        self.assertEqual(saved.json()["changed"], 2)
        day = self.client.get(f"{S}/attendance?day={today.isoformat()}", headers=self.teacher).json()
        self.assertEqual({r["name"]: r["status"] for r in day["rows"]}, {"Amal": "present", "Basel": "absent"})
        self.assertEqual(self.client.put(f"{S}/attendance", headers=self.teacher, json={"day": tomorrow, "entries": []}).status_code, 422)
        month = self.client.get(f"{P}/{self.amal}/attendance?month={today.year}-{today.month:02d}", headers=self.parent).json()
        self.assertEqual(month["counts"]["present"], 1)
        self.assertEqual(self.client.get(f"{P}/{self.amal}/overview", headers=self.parent).json()["today"]["attendance"], "present")

    def test_messages_between_parents_and_the_kindergarten(self):
        sent = self.client.post(f"{P}/{self.amal}/messages", headers=self.parent, json={"body": "Amal will be picked up at 12"})
        self.assertEqual(sent.status_code, 201)
        conversations = self.client.get(f"{S}/conversations", headers=self.teacher).json()
        self.assertEqual([(c["child"], c["parent"], c["unread"]) for c in conversations], [("Amal", "parent1", 1)])
        thread = self.client.get(f"{S}/conversations/{self.amal}/{self.parent_id}", headers=self.teacher).json()
        self.assertEqual([m["body"] for m in thread], ["Amal will be picked up at 12"])
        self.assertEqual(self.client.get(f"{S}/conversations", headers=self.teacher).json()[0]["unread"], 0)
        answer = self.client.post(f"{S}/messages", headers=self.teacher, json={"child_id": self.amal, "parent_id": self.parent_id, "body": "Thank you, noted."})
        self.assertEqual(answer.status_code, 201)
        self.assertEqual(self.client.get(f"{P}/{self.amal}/overview", headers=self.parent).json()["counts"]["messages_unread"], 1)
        mine = self.client.get(f"{P}/{self.amal}/messages", headers=self.parent).json()
        self.assertEqual([(m["from_parent"], m["body"]) for m in mine], [(True, "Amal will be picked up at 12"), (False, "Thank you, noted.")])
        self.assertEqual(self.client.get(f"{P}/{self.amal}/overview", headers=self.parent).json()["counts"]["messages_unread"], 0)
        self.assertEqual(self.client.post(f"{S}/messages", headers=self.teacher, json={"child_id": self.basel, "parent_id": self.parent_id, "body": "x"}).status_code, 422)

    def test_the_parents_see_the_fees_of_their_child(self):
        self.set_rate("12000")
        invoice = self.client.post(MONEY + "/invoices", headers=self.acc, json={"issued_on": local_today().isoformat(), "child_id": self.amal, "currency": "USD", "items": [{"description": "November", "amount": "50"}]}).json()
        self.client.post(f"{MONEY}/invoices/{invoice['id']}/payments", headers=self.acc, json={"booked_on": local_today().isoformat(), "amount": "20", "currency": "USD"})
        fees = self.client.get(f"{P}/{self.amal}/fees", headers=self.parent).json()
        self.assertEqual((fees["open"], fees["invoices"][0]["status"], fees["invoices"][0]["open"]["usd"]), (1, "partial", "30.00"))
        self.assertEqual(len(fees["invoices"][0]["payments"]), 1)
        self.assertEqual(self.client.get(f"{P}/{self.basel}/fees", headers=self.parent).status_code, 404)
