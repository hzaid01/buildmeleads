import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from lead_engine.auth import register
from lead_engine.config import settings
from lead_engine.database import TenantScopeError, analytics, connect, init_db, list_leads, set_consent, update_campaign_settings, upsert_leads
from lead_engine.outreach import approve_batch, dispatch_due, generate_batch, process_sendgrid_events


class LeadEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="lead-saas-tests-"))
        object.__setattr__(settings, "database_path", self.temp_dir / "leads.db")
        object.__setattr__(settings, "groq_api_key", "test-key")
        init_db()
        _, self.admin = register("admin@example.com", "correct-horse-battery", "Admin")
        _, self.member = register("member@example.com", "correct-horse-battery", "Member")
        self.copy_patch = patch("lead_engine.outreach.generate_email_text", side_effect=lambda lead, campaign: f"I noticed {lead['name']} has room to strengthen its profile. Would it help if I shared {campaign['offer']}?")
        self.copy_patch.start()

    def tearDown(self):
        self.copy_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def lead(self, key: str, email: str):
        return {"placeId": key, "name": f"Business {key}", "city": "Austin", "website": "", "email": email,
                "rating": 3.8, "reviewCount": 5, "photoCount": 1, "category": "Plumber"}

    def make_sendable(self, user_id: str):
        with connect() as connection:
            connection.execute("UPDATE leads SET email_valid=1,mx_valid=1,consent_status='confirmed' WHERE user_id=?", (user_id,))
            connection.commit()

    def test_tenant_decorator_and_query_isolation(self):
        with self.assertRaises(TenantScopeError):
            list_leads("")
        upsert_leads(self.admin["id"], [self.lead("same", "admin@example.org")])
        upsert_leads(self.member["id"], [self.lead("same", "member@example.org")])
        self.assertEqual(list_leads(self.admin["id"])["total"], 1)
        self.assertEqual(list_leads(self.member["id"])["total"], 1)
        self.assertEqual(list_leads(self.admin["id"])["leads"][0]["email"], "admin@example.org")
        with connect() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            indexes = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn("idx_leads_user_pipeline", indexes)
        self.assertIn("idx_send_logs_user_time", indexes)

    def test_manual_and_automatic_are_first_class(self):
        upsert_leads(self.admin["id"], [self.lead("manual", "manual@example.org")])
        self.make_sendable(self.admin["id"])
        manual = generate_batch(self.admin["id"], 10, datetime(2026, 8, 29, tzinfo=timezone.utc))
        self.assertEqual(manual["status"], "draft")
        self.assertEqual(manual["items"][0]["status"], "draft")
        approved = approve_batch(self.admin["id"], manual["batchId"])
        self.assertEqual(approved["queued"], 1)

        upsert_leads(self.member["id"], [self.lead("auto", "auto@example.org")])
        self.make_sendable(self.member["id"])
        update_campaign_settings(self.member["id"], {"workflow_mode": "automatic", "automatic_enabled": 1})
        automatic = generate_batch(self.member["id"], 10, datetime(2026, 8, 29, tzinfo=timezone.utc))
        self.assertEqual(automatic["status"], "queued")
        self.assertEqual(automatic["items"][0]["status"], "queued")

    def test_gmail_testing_limit_blocks_new_unique_user(self):
        from lead_engine.gmail import GMAIL_SEND_SCOPE, create_authorization_url
        object.__setattr__(settings, "google_oauth_client_id", "client")
        object.__setattr__(settings, "google_oauth_client_secret", "secret")
        object.__setattr__(settings, "gmail_token_encryption_key", Fernet.generate_key().decode())
        object.__setattr__(settings, "gmail_testing_mode", True)
        object.__setattr__(settings, "gmail_test_user_limit", 1)
        now = datetime.now(timezone.utc).isoformat()
        encrypted = Fernet(settings.gmail_token_encryption_key.encode()).encrypt(b"refresh")
        with connect() as connection:
            connection.execute("INSERT INTO gmail_oauth_accounts(user_id,refresh_token_encrypted,scope,connected_at,updated_at) VALUES(?,?,?,?,?)",
                               (self.admin["id"], encrypted, GMAIL_SEND_SCOPE, now, now))
            connection.commit()
        with self.assertRaisesRegex(RuntimeError, "capacity reached"):
            create_authorization_url(self.member["id"])
        self.assertIn("gmail.send", create_authorization_url(self.admin["id"]))

    def test_suppression_and_events_are_tenant_scoped(self):
        upsert_leads(self.admin["id"], [self.lead("event", "event@example.org")])
        lead_id = list_leads(self.admin["id"])["leads"][0]["id"]
        set_consent(self.admin["id"], lead_id, False)
        with connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM suppressions WHERE user_id=?", (self.admin["id"],)).fetchone()[0]
        self.assertEqual(count, 1)
        result = process_sendgrid_events([{"sg_event_id":"open-1","event":"open","lead_id":lead_id,"user_id":self.admin["id"],"timestamp":1787846400}])
        self.assertEqual(result["stored"], 1)
        self.assertEqual(analytics(self.admin["id"])["opened"], 1)
        self.assertEqual(analytics(self.member["id"])["opened"], 0)

    def test_worker_revalidates_suppression_before_provider_attempt(self):
        for name, value in {
            "sendgrid_api_key":"key", "sender_name":"Sender", "business_name":"Agency",
            "sender_email":"sender@acme.test", "reply_to_email":"reply@acme.test",
            "physical_address":"1 Main Street, Austin, TX", "public_base_url":"https://leadscout.test",
        }.items():
            object.__setattr__(settings, name, value)
        upsert_leads(self.member["id"], [self.lead("worker", "worker@example.org")])
        self.make_sendable(self.member["id"])
        update_campaign_settings(self.member["id"], {"workflow_mode":"automatic", "automatic_enabled":1})
        generated = generate_batch(self.member["id"], 1, datetime(2026, 8, 31, 14, 0, tzinfo=timezone.utc))
        self.assertTrue(generated["success"])
        with connect() as connection:
            connection.execute("UPDATE outreach_queue SET scheduled_for='2026-08-31T14:00:00+00:00' WHERE user_id=?", (self.member["id"],))
            connection.execute("INSERT INTO suppressions(user_id,email,reason,created_at) VALUES(?,?,?,?)", (self.member["id"],"worker@example.org","test suppression",datetime.now(timezone.utc).isoformat()))
            connection.commit()
        result = dispatch_due(datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc), self.member["id"])
        self.assertEqual(result["sent"], 0)
        self.assertIn("suppression", result["reason"])
        with connect() as connection:
            log = connection.execute("SELECT status FROM send_logs WHERE user_id=? ORDER BY id DESC", (self.member["id"],)).fetchone()
        self.assertEqual(log["status"], "blocked-by-suppression")


if __name__ == "__main__":
    unittest.main()
