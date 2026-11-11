"""The mobile app: version check and device tokens."""

import os
from unittest import mock

from tests.test_accounting_controls import ControlsBase

TOKEN_A = "a" * 40
TOKEN_B = "b" * 40


class MobileTests(ControlsBase):
    def sign_in(self, username):
        from tests.test_accounting_controls import PASSWORD

        token = self.client.post("/api/platform/auth/login", json={"username": username, "password": PASSWORD}).json()["access_token"]
        return {"Authorization": "Bearer " + token}

    def test_version_check_is_public_and_compares_versions(self):
        env = {"APP_LATEST_VERSION": "1.2.0", "APP_MIN_VERSION": "1.0.5"}
        with mock.patch.dict(os.environ, env):
            old = self.client.get("/api/app/version", params={"version": "1.0.4"}).json()
            self.assertEqual((old["update_required"], old["update_available"]), (True, True))
            mid = self.client.get("/api/app/version", params={"version": "1.0.10"}).json()
            self.assertEqual((mid["update_required"], mid["update_available"]), (False, True))
            cur = self.client.get("/api/app/version", params={"version": "1.2.0"}).json()
            self.assertEqual((cur["update_required"], cur["update_available"]), (False, False))
            self.assertEqual(self.client.get("/api/app/version").json()["update_required"], False)

    def test_a_device_is_bound_to_the_signed_in_account_and_can_be_removed(self):
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from app.models import DeviceToken

        body = {"token": TOKEN_A, "platform": "android", "app_version": "1.0.0", "language": "de"}
        self.assertEqual(self.client.post("/api/platform/devices", json=body).status_code, 401)
        parent = self.sign_in("parent1")
        self.assertEqual(self.client.post("/api/platform/devices", headers=parent, json=body).status_code, 204)
        self.assertEqual(self.client.post("/api/platform/devices", headers=parent, json={**body, "platform": "web"}).status_code, 422)
        teacher = self.sign_in("teacher1")
        # the same phone, signed in by someone else, now belongs to that person
        self.assertEqual(self.client.post("/api/platform/devices", headers=teacher, json=body).status_code, 204)
        with Session(self.engine) as session:
            rows = session.scalars(select(DeviceToken)).all()
            self.assertEqual(len(rows), 1)
        # somebody else cannot remove it
        self.client.post("/api/platform/devices/remove", headers=parent, json={"token": TOKEN_A})
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(DeviceToken)).all()), 1)
        self.client.post("/api/platform/devices/remove", headers=teacher, json={"token": TOKEN_A})
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(DeviceToken)).all()), 0)
