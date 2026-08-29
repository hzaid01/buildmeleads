import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright


class DashboardE2ETests(unittest.TestCase):
    def test_persisted_pipeline_and_dry_run_preview(self):
        console_errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto("http://127.0.0.1:3000/", wait_until="networkidle")
            page.locator("#pipelineStatus.success").wait_for(timeout=15000)

            self.assertEqual(page.locator("#metricTotal").inner_text(), "79")
            self.assertEqual(page.locator("#metricQualified").inner_text(), "5")
            self.assertEqual(page.locator("#metricSendable").inner_text(), "2")
            self.assertEqual(page.locator("#metricSent").inner_text(), "0")
            self.assertEqual(page.locator("#pipelineTableBody tr").count(), 79)
            self.assertEqual(page.locator("#outreachModeBadge").inner_text(), "Dry-run locked")

            page.get_by_role("button", name="Build Dry-Run Preview").click()
            page.locator("#previewModal:not(.hidden)").wait_for(timeout=10000)
            self.assertEqual(page.locator(".preview-email").count(), 2)
            self.assertIn("No email has been sent", page.locator("#previewModal").inner_text())
            page.get_by_role("button", name="Close", exact=True).click()
            self.assertTrue(page.locator("#previewModal").evaluate("el => el.classList.contains('hidden')"))

            desktop_path = Path(tempfile.gettempdir()) / "local-lead-scout-dashboard-desktop.png"
            page.screenshot(path=str(desktop_path), full_page=True)

            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(250)
            document_width = page.evaluate("document.documentElement.scrollWidth")
            viewport_width = page.evaluate("document.documentElement.clientWidth")
            self.assertLessEqual(document_width, viewport_width + 1)

            mobile_path = Path(tempfile.gettempdir()) / "local-lead-scout-dashboard-mobile.png"
            page.screenshot(path=str(mobile_path), full_page=True)
            print(f"Desktop screenshot: {desktop_path}")
            print(f"Mobile screenshot: {mobile_path}")
            browser.close()

        relevant_errors = [error for error in console_errors if "favicon" not in error.lower()]
        self.assertEqual(relevant_errors, [])


if __name__ == "__main__":
    unittest.main()
