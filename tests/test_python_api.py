import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lead_engine.app import app
from lead_engine.config import settings
from lead_engine.database import init_db


class LeadEngineApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="lead-engine-api-tests-"))
        object.__setattr__(settings, "database_path", self.temp_dir / "api.db")
        object.__setattr__(settings, "engine_token", "test-engine-token")
        object.__setattr__(settings, "manage_pid_file", False)
        object.__setattr__(settings, "dry_run", True)
        object.__setattr__(settings, "live_sending_enabled", False)
        init_db()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.headers = {"X-Lead-Engine-Token": "test-engine-token"}

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        object.__setattr__(settings, "manage_pid_file", True)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_health_and_authentication(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["dryRun"])
        unauthorized = self.client.get("/api/leads")
        self.assertEqual(unauthorized.status_code, 401)

    def test_ingest_list_analytics_and_reply(self):
        payload = {
            "source": "test",
            "query": "plumbers in Tampa",
            "leads": [{
                "placeId": "api-place-1",
                "name": "API Plumbing",
                "niche": "Plumber",
                "category": "Plumber",
                "city": "Tampa, Florida, US",
                "timezone": "America/New_York",
                "website": "",
                "rating": 4.6,
                "reviewCount": 30,
                "photoCount": 2,
            }],
        }
        ingested = self.client.post("/api/leads/ingest", headers=self.headers, json=payload)
        self.assertEqual(ingested.status_code, 200)
        self.assertEqual(ingested.json()["inserted"], 1)
        listed = self.client.get("/api/leads", headers=self.headers).json()
        self.assertEqual(listed["total"], 1)
        self.assertIn("no website", listed["leads"][0]["issue_detected"].lower())
        lead_id = listed["leads"][0]["id"]
        reply = self.client.post(f"/api/leads/{lead_id}/reply", headers=self.headers, json={})
        self.assertEqual(reply.status_code, 200)
        contacted = self.client.post(f"/api/leads/{lead_id}/contacted", headers=self.headers, json={})
        self.assertEqual(contacted.status_code, 200)
        analytics = self.client.get("/api/analytics", headers=self.headers).json()
        self.assertEqual(analytics["qualified"], 1)
        self.assertEqual(analytics["replied"], 1)
        self.assertEqual(analytics["sent"], 1)


if __name__ == "__main__":
    unittest.main()
