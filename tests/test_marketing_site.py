from __future__ import annotations

import contextlib
import functools
import http.server
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "marketing"


@contextlib.contextmanager
def serve_site():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class MarketingSiteTests(unittest.TestCase):
    def test_public_pages_are_reachable_and_have_required_navigation(self) -> None:
        with serve_site() as base_url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for path in ["/", "/pricing/", "/terms/", "/privacy/", "/refunds/"]:
                with self.subTest(path=path):
                    page = browser.new_page(viewport={"width": 1280, "height": 800})
                    console_errors: list[str] = []
                    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                    response = page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=10_000)
                    self.assertIsNotNone(response)
                    self.assertTrue(response.ok)
                    self.assertIn("BuildMeLeads", page.title())
                    self.assertGreaterEqual(page.locator("a[href='/pricing/']").count(), 1)
                    self.assertGreaterEqual(page.locator("a[href='/terms/']").count(), 1)
                    self.assertGreaterEqual(page.locator("a[href='/privacy/']").count(), 1)
                    self.assertGreaterEqual(page.locator("a[href='/refunds/']").count(), 1)
                    self.assertTrue(page.locator("body").evaluate("el => el.scrollWidth <= document.documentElement.clientWidth"))
                    self.assertFalse(console_errors)
                    page.close()
            browser.close()

    def test_homepage_is_responsive_and_honest_about_prelaunch(self) -> None:
        with serve_site() as base_url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height in [(390, 844), (768, 1024), (1440, 1000)]:
                with self.subTest(width=width):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.goto(base_url, wait_until="domcontentloaded", timeout=10_000)
                    self.assertTrue(page.get_by_role("heading", name="Find local service businesses with weak Google Business Profiles and automate personalized outreach to them.").is_visible())
                    self.assertTrue(page.get_by_text("Pre-launch waitlist. No payment is collected today.", exact=True).is_visible())
                    self.assertTrue(page.locator("body").evaluate("el => el.scrollWidth <= document.documentElement.clientWidth"))
                    page.close()
            browser.close()

    def test_private_street_address_is_not_published(self) -> None:
        public_text = "\n".join(path.read_text(encoding="utf-8") for path in SITE.rglob("*.html"))
        self.assertNotIn("376 R1", public_text)
        self.assertNotIn("54782", public_text)
        self.assertNotIn("68.65.120", public_text)


if __name__ == "__main__":
    unittest.main()
