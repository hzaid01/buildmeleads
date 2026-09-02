import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lead_engine.app import app
from lead_engine.config import settings
from lead_engine.database import connect, init_db


class LeadEngineApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="lead-saas-api-"))
        object.__setattr__(settings, "database_path", self.temp_dir / "api.db")
        object.__setattr__(settings, "engine_token", "engine-test")
        object.__setattr__(settings, "manage_pid_file", False)
        object.__setattr__(settings, "gmail_testing_mode", True)
        object.__setattr__(settings, "gmail_test_user_limit", 100)
        init_db()
        self.context = TestClient(app); self.client = self.context.__enter__()
        self.engine = {"X-Lead-Engine-Token": "engine-test"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        object.__setattr__(settings, "manage_pid_file", True)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def register(self, email: str) -> dict[str, str]:
        response = self.client.post("/api/auth/register", headers=self.engine, json={"email":email,"password":"correct-horse-battery","display_name":"Test"})
        self.assertEqual(response.status_code, 200)
        token = response.json()["sessionToken"]
        with connect() as connection:
            stored = connection.execute("SELECT token_hash FROM sessions ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertNotEqual(stored, token)
        return {**self.engine, "X-Lead-Session-Token": token}

    def test_session_authentication_and_logout(self):
        self.assertEqual(self.client.get("/api/leads", headers=self.engine).status_code, 401)
        headers = self.register("admin@example.com")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/leads", headers=headers).status_code, 401)

    def test_cross_tenant_lead_access_is_blocked(self):
        admin = self.register("admin@example.com")
        member = self.register("member@example.com")
        payload={"source":"test","leads":[{"placeId":"private","name":"Private Lead","website":"","email":"owner@example.org","rating":3.5,"reviewCount":2,"photoCount":0,"category":"Plumber"}]}
        self.assertEqual(self.client.post("/api/leads/ingest",headers=admin,json=payload).status_code,200)
        admin_rows=self.client.get("/api/leads",headers=admin).json(); member_rows=self.client.get("/api/leads",headers=member).json()
        self.assertEqual(admin_rows["total"],1); self.assertEqual(member_rows["total"],0)
        lead_id=admin_rows["leads"][0]["id"]
        self.assertEqual(self.client.post(f"/api/leads/{lead_id}/reply",headers=member,json={}).status_code,404)

    def test_campaign_defaults_and_gmail_minimum_scope(self):
        headers=self.register("admin@example.com")
        campaign=self.client.get("/api/settings/campaign",headers=headers)
        self.assertEqual(campaign.status_code,200); self.assertEqual(campaign.json()["workflow_mode"],"manual")
        self.assertEqual(campaign.json()["groq_model"],"openai/gpt-oss-120b")
        gmail=self.client.get("/api/gmail/status",headers=headers).json()
        self.assertEqual(gmail["scope"],"https://www.googleapis.com/auth/gmail.send")
        self.assertEqual(gmail["maxConnectedUsers"],100)
        self.assertIn("setupRequired",gmail)
        self.assertEqual(gmail["redirectUri"],settings.google_oauth_redirect_uri)
        self.assertNotIn(settings.google_oauth_client_secret,gmail.values())


if __name__ == "__main__": unittest.main()
