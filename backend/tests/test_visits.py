"""Counting the visitors of the public site (anonymous) and showing who signed in to the portals."""

import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import visits
from app.models import SiteVisit
from tests.test_accounting_controls import ControlsBase

PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
TABLET = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
STATS = "/api/admin/platform/visits"


class VisitTests(ControlsBase):
    def visit(self, path="/", agent=DESKTOP, address="203.0.113.7", referrer="", lang="ar", body=None):
        payload = body if body is not None else json.dumps({"path": path, "referrer": referrer, "lang": lang})
        headers = {"X-Forwarded-For": address, "Content-Type": "text/plain"}
        headers["User-Agent"] = agent if agent is not None else ""  # no browser string at all
        return self.client.post("/api/track", content=payload, headers=headers)

    def rows(self):
        with Session(self.engine) as session:
            return session.scalars(select(SiteVisit)).all()

    def stats(self, days=30, headers=None):
        return self.client.get(f"{STATS}?days={days}", headers=headers or self.admin)

    # ---- counting ----
    def test_a_visit_is_counted_and_the_answer_is_always_empty(self):
        done = self.visit(referrer="https://www.google.com/search?q=secret+words")
        self.assertEqual((done.status_code, done.content), (204, b""))
        row = self.rows()[0]
        self.assertEqual((row.path, row.referrer, row.device, row.language, row.day), ("/", "www.google.com", "desktop", "ar", date.today()))

    def test_one_person_counts_once_a_day_but_every_page_view_is_counted(self):
        for _ in range(3):
            self.visit()
        self.visit(address="198.51.100.9")  # another person
        today = self.stats().json()["today"]
        self.assertEqual((today["views"], today["visitors"]), (4, 2))

    def test_devices_and_sources_and_languages_are_summed_up(self):
        self.visit(agent=PHONE, address="192.0.2.1", referrer="https://www.facebook.com/", lang="ar")
        self.visit(agent=DESKTOP, address="192.0.2.2", lang="en")
        self.visit(agent=TABLET, address="192.0.2.3", referrer="https://zahratalmadain.com/other")  # our own site is direct
        data = self.stats().json()
        self.assertEqual(data["devices"], {"mobile": 1, "desktop": 1, "tablet": 1})
        self.assertEqual({item["host"]: item["views"] for item in data["sources"]}, {"": 2, "www.facebook.com": 1})
        self.assertEqual({item["lang"]: item["views"] for item in data["languages"]}, {"ar": 2, "en": 1})
        self.assertEqual(data["pages"], [{"path": "/", "views": 3}])
        self.assertEqual(len(data["series"]), 30)
        self.assertEqual(data["series"][-1]["views"], 3)
        self.assertEqual((data["period"]["views"], data["week"]["views"], data["today"]["views"]), (3, 3, 3))

    def test_robots_private_areas_and_bad_requests_are_not_counted(self):
        self.visit(agent="Googlebot/2.1 (+http://www.google.com/bot.html)")
        self.visit(agent="curl/8.0")
        self.visit(agent="python-requests/2.31")
        self.visit(agent=None)
        for private in ("/admin/", "/login/", "/parents/", "/teachers/", "/management/", "/api/content", "/backend/x"):
            self.visit(path=private)
        self.visit(path="/has space")
        self.visit(path="//evil.example/x")
        self.assertEqual(self.visit(body="not json").status_code, 204)
        self.assertEqual(self.visit(body="[1,2]").status_code, 204)
        self.assertEqual(self.visit(body="").status_code, 204)
        self.assertEqual(self.rows(), [])
        self.visit(path="/?utm=1#top")  # the query and the part after # never reach the table
        self.assertEqual([row.path for row in self.rows()], ["/"])

    def test_a_visitor_cannot_flood_the_numbers(self):
        for _ in range(visits.MAX_VIEWS_PER_VISITOR_PER_DAY + 15):
            self.visit()
        self.assertEqual(len(self.rows()), visits.MAX_VIEWS_PER_VISITOR_PER_DAY)

    # ---- privacy ----
    def test_no_address_and_no_browser_string_are_kept(self):
        self.visit(address="203.0.113.77", agent=DESKTOP)
        row = self.rows()[0]
        stored = " ".join(str(getattr(row, column.name)) for column in SiteVisit.__table__.columns)
        for secret in ("203.0.113.77", "Windows", "Chrome", "Mozilla"):
            self.assertNotIn(secret, stored)
        self.assertEqual(len(row.visitor), 24)

    def test_the_fingerprint_changes_every_day_and_per_person(self):
        today, tomorrow = date.today(), date.today() + timedelta(days=1)
        first = visits.fingerprint(today, "203.0.113.7", DESKTOP)
        self.assertEqual(first, visits.fingerprint(today, "203.0.113.7", DESKTOP))
        self.assertNotEqual(first, visits.fingerprint(tomorrow, "203.0.113.7", DESKTOP))  # nobody can be followed over days
        self.assertNotEqual(first, visits.fingerprint(today, "203.0.113.8", DESKTOP))
        self.assertNotEqual(first, visits.fingerprint(today, "203.0.113.7", PHONE))

    def test_helpers(self):
        self.assertEqual(visits.referrer_host("https://t.me/zahra?x=1"), "t.me")
        self.assertEqual(visits.referrer_host("https://www.zahratalmadain.com/"), "")
        self.assertEqual(visits.referrer_host(""), "")
        self.assertEqual(visits.referrer_host("not a url"), "")
        self.assertEqual((visits.device_of(PHONE), visits.device_of(TABLET), visits.device_of(DESKTOP)), ("mobile", "tablet", "desktop"))

    # ---- what the admin sees ----
    def test_only_the_administrator_sees_the_numbers(self):
        self.visit()
        for headers in (self.acc, self.teacher, self.parent, self.mgr):
            self.assertIn(self.stats(headers=headers).status_code, (401, 403))
        self.assertEqual(self.client.get(STATS).status_code, 401)
        self.assertEqual(self.stats().status_code, 200)
        self.assertEqual(len(self.stats(days=7).json()["series"]), 7)
        self.assertEqual(len(self.stats(days=9999).json()["series"]), 365)  # a sensible limit

    def test_the_admin_sees_who_signed_in_to_the_portals(self):
        data = self.stats().json()
        names = {item["username"]: item for item in data["sign_ins"]}
        self.assertTrue({"acc", "acc2", "teacher1", "parent1", "mgr0"} <= set(names))
        self.assertEqual(names["teacher1"]["roles"], ["teacher"])
        self.assertEqual(names["acc"]["times"], 1)
        self.assertTrue(names["acc"]["last_at"])
        self.assertGreaterEqual(data["signed_in_recently"], 5)
