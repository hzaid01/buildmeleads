import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lead_engine.config import settings, validate_live_configuration
from lead_engine.database import analytics, connect, init_db, unsubscribe, upsert_leads
from lead_engine.enrichment import email_format_valid
from lead_engine.outreach import plan_outreach, process_sendgrid_events
from lead_engine.qualification import detect_weaknesses, is_qualified


class LeadEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="lead-engine-tests-"))
        object.__setattr__(settings, "database_path", self.temp_dir / "leads.db")
        object.__setattr__(settings, "dry_run", True)
        object.__setattr__(settings, "live_sending_enabled", False)
        object.__setattr__(settings, "campaign_start_date", "")
        object.__setattr__(settings, "minimum_delay_minutes", 15)
        object.__setattr__(settings, "maximum_delay_minutes", 45)
        init_db()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_weakness_qualification(self):
        strong = {
            "website": "https://example.com",
            "rating": 4.8,
            "reviewCount": 40,
            "photoCount": 3,
            "category": "Plumber",
            "lastReviewAt": datetime.now(timezone.utc).isoformat(),
        }
        self.assertEqual(detect_weaknesses(strong), [])
        self.assertFalse(is_qualified(strong))
        weak = {**strong, "website": "", "reviewCount": 4}
        self.assertIn("no_website", detect_weaknesses(weak))
        self.assertIn("few_reviews", detect_weaknesses(weak))
        self.assertTrue(is_qualified(weak))

    def test_upsert_deduplicates_and_persists(self):
        lead = {
            "placeId": "place-123",
            "name": "Tampa Test Plumbing",
            "city": "Tampa, Florida, US",
            "timezone": "America/New_York",
            "website": "",
            "rating": 4.7,
            "reviewCount": 15,
            "photoCount": 2,
            "category": "Plumber",
        }
        first = upsert_leads([lead])
        second = upsert_leads([{**lead, "phone": "+18135550199"}])
        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second["updated"], 1)
        self.assertEqual(analytics()["total"], 1)
        with connect() as connection:
            stored = connection.execute("SELECT phone,qualified FROM leads").fetchone()
        self.assertEqual(stored["phone"], "+18135550199")
        self.assertEqual(stored["qualified"], 1)

    def test_email_format_validation(self):
        self.assertTrue(email_format_valid("owner@example.org"))
        self.assertFalse(email_format_valid("not-an-email"))
        self.assertFalse(email_format_valid("image@example.png"))

    def test_dry_run_preview_and_unsubscribe(self):
        upsert_leads([{
            "placeId": "preview-1",
            "name": "Austin Roof Test",
            "city": "Austin, Texas, US",
            "timezone": "America/Chicago",
            "website": "https://example.org",
            "email": "owner@example.org",
            "rating": 3.8,
            "reviewCount": 20,
            "photoCount": 4,
            "category": "Roofing contractor",
        }])
        with connect() as connection:
            connection.execute("UPDATE leads SET email_valid=1,mx_valid=1")
            connection.commit()
            token = connection.execute("SELECT unsubscribe_token FROM leads").fetchone()[0]
        preview = plan_outreach(datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc))
        self.assertTrue(preview["success"])
        self.assertTrue(preview["dryRun"])
        self.assertEqual(preview["planned"], 1)
        self.assertIn("Austin Roof Test", preview["items"][0]["body"])
        self.assertIn("Unsubscribe:", preview["items"][0]["body"])
        self.assertTrue(unsubscribe(token))
        with connect() as connection:
            lead = connection.execute("SELECT consent_status FROM leads").fetchone()
            queue = connection.execute("SELECT status FROM outreach_queue").fetchone()
        self.assertEqual(lead["consent_status"], "revoked")
        self.assertEqual(queue["status"], "cancelled")

    def test_live_sending_is_hard_blocked_by_placeholders(self):
        errors = validate_live_configuration(settings)
        self.assertTrue(any("OUTREACH_DRY_RUN" in error for error in errors))
        self.assertTrue(any("LIVE_SENDING_ENABLED" in error for error in errors))
        self.assertTrue(any("SENDER_NAME" in error for error in errors))

    def test_day_one_cap_and_randomized_business_hour_spacing(self):
        leads = []
        for index in range(12):
            leads.append({
                "placeId": f"cap-{index}",
                "name": f"Austin Business {index}",
                "city": "Austin, Texas, US",
                "timezone": "America/Chicago",
                "website": "",
                "email": f"owner{index}@example.org",
                "rating": 4.7,
                "reviewCount": 20,
                "photoCount": 2,
                "category": "Plumber",
            })
        upsert_leads(leads)
        with connect() as connection:
            connection.execute("UPDATE leads SET email_valid=1,mx_valid=1")
            connection.commit()
        preview = plan_outreach(datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(preview["warmup"]["cap"], 10)
        self.assertEqual(preview["planned"], 10)
        scheduled = [datetime.fromisoformat(item["scheduledFor"]) for item in preview["items"]]
        for previous, current in zip(scheduled, scheduled[1:]):
            gap_minutes = (current - previous).total_seconds() / 60
            self.assertGreaterEqual(gap_minutes, 15)
            self.assertLessEqual(gap_minutes, 45)
        for item in scheduled:
            local_hour = item.astimezone(__import__("zoneinfo").ZoneInfo("America/Chicago")).hour
            self.assertGreaterEqual(local_hour, 9)
            self.assertLess(local_hour, 17)

    def test_sendgrid_open_and_suppression_events_are_idempotent(self):
        upsert_leads([{
            "placeId": "event-1",
            "name": "Event Business",
            "website": "",
            "email": "events@example.org",
            "rating": 4.5,
            "reviewCount": 20,
            "photoCount": 2,
            "category": "Cleaner",
        }])
        with connect() as connection:
            lead_id = connection.execute("SELECT id FROM leads").fetchone()[0]
        open_event = {"sg_event_id": "open-1", "event": "open", "lead_id": str(lead_id), "timestamp": 1787846400}
        first = process_sendgrid_events([open_event, open_event])
        self.assertEqual(first["stored"], 1)
        self.assertEqual(analytics()["opened"], 1)
        suppression = process_sendgrid_events([{
            "sg_event_id": "spam-1", "event": "spamreport", "lead_id": str(lead_id), "timestamp": 1787846460
        }])
        self.assertEqual(suppression["suppressions"], 1)
        with connect() as connection:
            row = connection.execute("SELECT consent_status FROM leads WHERE id=?", (lead_id,)).fetchone()
            suppressed = connection.execute("SELECT reason FROM suppressions WHERE email='events@example.org'").fetchone()
        self.assertEqual(row["consent_status"], "revoked")
        self.assertIn("spamreport", suppressed["reason"])


if __name__ == "__main__":
    unittest.main()
