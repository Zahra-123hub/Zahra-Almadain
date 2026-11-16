"""A small kindergarten for the tests: one child, accounts of every role, an in-memory database."""

import os
import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_session
from app.models import Account, Child, FeeAuditLog, IncomeCategory, Role
from app.timeutil import local_today

PEOPLE = "/api/admin/people"
MONEY = "/api/admin/money"
PASSWORD = "Qx5a6ba62b7e4b-9"


class ControlsBase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "SESSION_SECRET": "test-controls-secret-long-enough",
                "ADMIN_USERNAME": "legacy-admin",
                "ADMIN_PASSWORD": "Qx9edbcb5679ea-9",
            },
        )
        self.env.start()
        self.feed = patch("app.money.fetch_online_rate", return_value=None)  # the tests never touch the internet
        self.feed.start()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)

        def override():
            with Session(self.engine) as session:
                yield session

        main.app.dependency_overrides[get_session] = override
        main.app.dependency_overrides[main.optional_session] = override
        self.client = TestClient(main.app)
        with Session(self.engine) as session:
            roles = {n: Role(name=n) for n in ("admin", "teacher", "parent", "accountant", "manager")}
            session.add_all(roles.values())
            for username, role in (("acc", "accountant"), ("acc2", "accountant"), ("teacher1", "teacher"), ("parent1", "parent"), ("mgr0", "manager")):
                session.add(Account(username=username, password_hash=main.PASSWORD_HASHER.hash(PASSWORD), roles=[roles[role]]))
            session.add(Child(display_name="Amal", class_name="KG1"))
            # the built-in income categories (in a real database the migration adds them)
            for position, (key, name) in enumerate((("tuition", "رسوم الروضة"), ("registration", "رسوم التسجيل"), ("extra_fees", "رسوم إضافية"), ("other_income", "إيرادات أخرى")), start=1):
                session.add(IncomeCategory(key=key, name=name, position=position))
            session.commit()

        def token(name):
            return {"Authorization": "Bearer " + self.client.post(
                "/api/platform/auth/login", json={"username": name, "password": PASSWORD}
            ).json()["access_token"]}

        self.acc, self.teacher, self.parent, self.mgr = token("acc"), token("teacher1"), token("parent1"), token("mgr0")
        self.acc2 = token("acc2")  # a second accountant
        self.admin = {"Authorization": "Bearer " + self.client.post(
            "/api/auth/login", json={"username": "legacy-admin", "password": "Qx9edbcb5679ea-9"}
        ).json()["access_token"]}

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.pop(get_session, None)
        main.app.dependency_overrides.pop(main.optional_session, None)
        self.engine.dispose()
        self.feed.stop()
        self.env.stop()

    # ---- people are the work of the management ----
    def hire(self, name, job="teacher", **extra):
        made = self.client.post(PEOPLE + "/employees", headers=self.mgr, json={"name": name, "job_title": job, **extra})
        self.assertIn(made.status_code, (201, 409), made.text)
        return made

    def enroll(self, name, class_name="KG1"):
        """Adds a child with a father, the way the management does."""
        made = self.client.post(PEOPLE + "/children", headers=self.mgr, json={
            "name": name, "class_name": class_name, "guardians": [{"relation": "father", "name": "Father of " + name}]})
        self.assertEqual(made.status_code, 201, made.text)
        return made.json()

    def child_id(self):
        with Session(self.engine) as session:
            return session.scalar(select(Child.id).order_by(Child.created_at))

    def actions(self):
        with Session(self.engine) as session:
            return [row.action for row in session.scalars(select(FeeAuditLog).order_by(FeeAuditLog.at)).all()]

    # ---- money ----
    def set_rate(self, value="12000", day=None, headers=None):
        return self.client.post(MONEY + "/rates", headers=headers or self.mgr, json={"valid_from": (day or date(2000, 1, 1)).isoformat(), "syp_per_usd": value})

    def category(self, key="tuition"):
        with Session(self.engine) as session:
            return str(session.scalar(select(IncomeCategory.id).where(IncomeCategory.key == key)))

    def income(self, amount="20", currency="USD", day=None, headers=None, **extra):
        body = {"booked_on": (day or local_today()).isoformat(), "description": "fee", "category_id": self.category(extra.pop("key", "tuition")),
                "amount": amount, "currency": currency, **extra}
        return self.client.post(MONEY + "/income", headers=headers or self.acc, json=body)

    def expense(self, amount="5", currency="USD", category="food", day=None, headers=None, **extra):
        body = {"booked_on": (day or local_today()).isoformat(), "description": "bread", "category": category, "amount": amount, "currency": currency, **extra}
        return self.client.post(MONEY + "/expenses", headers=headers or self.acc, json=body)
