# Static Marketing & Waitlist Site

This directory contains the standalone static marketing and legal documentation site for the project. It can be hosted on any static web server, GitHub Pages, or cPanel `/public_html`.

## Preview locally

From the repository root:

```bash
python -m http.server 4173 --directory marketing
```

Open `http://localhost:4173`.

## Waitlist Integration Options

### Option 1: Native PHP Endpoint (`waitlist.php`)
If hosting on Apache / LiteSpeed / Nginx with PHP:
- Submissions are logged to `waitlist.csv`.
- Configure optional SMTP variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_EMAIL`) to receive instant email notifications.

### Option 2: Google Forms
1. Create a blank Google Form named **Launch Waitlist**.
2. Add one required **Short answer** question named **Work email**. Enable email response validation.
3. In the form menu, choose **Get pre-filled link**, enter `email-marker@example.com`, and generate the link.
4. From the pre-filled URL, copy the `entry.123456789` parameter name.
5. Copy the URL through `/viewform`, change `/viewform` to `/formResponse`.
6. In `marketing/index.html`, set:
   - `data-google-form-action="https://docs.google.com/forms/d/e/.../formResponse"`
   - `data-email-entry-id="entry.123456789"`
