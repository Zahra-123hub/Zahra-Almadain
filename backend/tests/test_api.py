import copy
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class FakeStore:
    def __init__(self):
        self.data = {"settings": {}, "gallery": [], "news": []}
        self.files = {}
        self.sha = "test-sha"

    async def get_content(self):
        return copy.deepcopy(self.data), self.sha

    async def put_content(self, data, sha, message):
        self.data = copy.deepcopy(data)
        self.sha = f"{self.sha}-next"

    async def put_file(self, name, contents, message):
        self.files[name] = contents

    async def get_file(self, name):
        class FakeResponse:
            content = self.files[name]

        return FakeResponse()

    async def delete_file(self, name):
        self.files.pop(name, None)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "test-password",
                "SESSION_SECRET": "test-session-secret-long-enough",
            },
        )
        self.env.start()
        self.original_store = main.store
        self.fake_store = FakeStore()
        main.store = self.fake_store
        self.client = TestClient(main.app)
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def tearDown(self):
        self.client.close()
        main.store = self.original_store
        self.env.stop()

    def test_admin_routes_require_login(self):
        response = self.client.get("/api/admin/content")
        self.assertEqual(response.status_code, 401)

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_upload_gallery_asset_and_delete(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        response = self.client.post(
            "/api/admin/gallery",
            headers=self.headers,
            data={"kind": "image", "caption": "Test"},
            files={"file": ("test.png", png, "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()
        self.assertEqual(item["caption"], "Test")
        self.assertIn(item["asset"], self.fake_store.files)

        asset = self.client.get("/api/assets/" + item["asset"])
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.content, png)

        deleted = self.client.delete(
            "/api/admin/gallery/" + item["id"], headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertNotIn(item["asset"], self.fake_store.files)

    def test_news_can_be_created_and_removed(self):
        response = self.client.post(
            "/api/admin/news",
            headers=self.headers,
            data={"tag": "خبر", "title": "عنوان", "text": "نص الخبر"},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()
        self.assertEqual(self.fake_store.data["news"][0]["id"], item["id"])

        deleted = self.client.delete(
            "/api/admin/news/" + item["id"], headers=self.headers
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.fake_store.data["news"], [])

    def test_settings_are_validated_and_stored(self):
        response = self.client.put(
            "/api/admin/settings",
            headers=self.headers,
            json={
                "whatsapp": "963985122704",
                "facebook": "https://facebook.com/example",
                "hideDefaultGallery": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.fake_store.data["settings"]["hideDefaultGallery"])

        invalid = self.client.put(
            "/api/admin/settings",
            headers=self.headers,
            json={"whatsapp": "123"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_health_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.json(), {"status": "ok"})

    def test_session_tokens_expire_and_reject_tampering(self):
        token = main.create_session_token("admin", "secret", now=1000)
        self.assertEqual(main.verify_session_token(token, "secret", now=1001), "admin")
        self.assertIsNone(
            main.verify_session_token(
                token, "secret", now=1000 + main.SESSION_TTL_SECONDS
            )
        )
        self.assertIsNone(main.verify_session_token(token + "x", "secret", now=1001))


if __name__ == "__main__":
    unittest.main()
