import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright


class DashboardE2ETests(unittest.TestCase):
    def test_signup_dashboard_logout_and_mobile(self):
        console_errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto("http://127.0.0.1:3000/", wait_until="networkidle")
            self.assertEqual(page.url, "http://127.0.0.1:3000/login")
            page.get_by_role("link", name="Create an account").click()
            page.get_by_label("Name").fill("Browser Admin")
            page.get_by_label("Email").fill("browser-admin@example.com")
            page.get_by_label("Password").fill("correct-horse-battery")
            page.get_by_role("button", name="Create account").click()
            page.locator("#pipelineStatus.success").wait_for(timeout=15000)
            self.assertEqual(page.locator("#currentUserEmail").inner_text(), "browser-admin@example.com")
            self.assertEqual(page.locator("#systemStatus .status-text").inner_text(), "Discovery: Ready")
            self.assertNotIn("Docker", page.locator("body").inner_text())
            self.assertIn("Gmail connection is in Google Testing mode", page.locator(".gmail-testing-notice").inner_text())
            self.assertEqual(page.locator("#connectGmailBtn").inner_text(), "Connect Gmail")
            self.assertNotIn("GOOGLE_OAUTH_CLIENT_SECRET is not configured", page.locator("body").inner_text())
            self.assertEqual(page.locator("#workflowModeSelect").input_value(), "manual")
            self.assertEqual(page.locator("#sendingMethodSelect").input_value(), "sendgrid")

            desktop_path = Path(tempfile.gettempdir()) / "lead-scout-saas-desktop.png"
            page.screenshot(path=str(desktop_path), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(250)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth") + 1)
            mobile_path = Path(tempfile.gettempdir()) / "lead-scout-saas-mobile.png"
            page.screenshot(path=str(mobile_path), full_page=True)
            page.get_by_role("button", name="Log out").click()
            page.wait_for_url("**/login")
            print(f"Desktop screenshot: {desktop_path}\nMobile screenshot: {mobile_path}")
            browser.close()
        self.assertEqual([e for e in console_errors if "favicon" not in e.lower()], [])


if __name__ == "__main__": unittest.main()
