"""
Email the markdown report as a styled HTML email via Gmail SMTP.

Requires a Gmail App Password (not your regular Gmail password):
  myaccount.google.com/apppasswords → create one for "Mail"

.env vars needed:
  GMAIL_SENDER        your Gmail address (e.g. you@gmail.com)
  GMAIL_APP_PASSWORD  16-char app password from Google Account
  GMAIL_RECIPIENT     where to send (defaults to GMAIL_SENDER)
"""

import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown as md_lib

_EMAIL_CSS = """
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 680px; margin: 0 auto; padding: 24px; color: #111827;
    background: #ffffff;
  }
  h1 {
    color: #0f172a; border-bottom: 3px solid #2563eb;
    padding-bottom: 10px; font-size: 1.5em;
  }
  h2 { color: #1d4ed8; margin-top: 28px; font-size: 1.15em; }
  h3 { color: #374151; margin-top: 20px; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 0.88em; }
  th { background: #1d4ed8; color: #fff; padding: 10px 14px; text-align: left; }
  td { padding: 8px 14px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
  tr:nth-child(even) td { background: #f8fafc; }
  ul, ol { padding-left: 20px; }
  li { margin-bottom: 4px; line-height: 1.5; }
  strong { color: #111827; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .footer {
    margin-top: 36px; padding-top: 16px; border-top: 1px solid #e5e7eb;
    color: #9ca3af; font-size: 0.78em;
  }
</style>
"""


def send_report(report_md: str) -> None:
    """
    Convert the markdown report to HTML and send it via Gmail SMTP.
    Skips silently if email credentials are not configured.
    """
    sender = os.getenv("GMAIL_SENDER")
    password = os.getenv("GMAIL_APP_PASSWORD")

    if not sender or not password:
        print("Email skipped — set GMAIL_SENDER and GMAIL_APP_PASSWORD in .env to enable.")
        return

    recipient = os.getenv("GMAIL_RECIPIENT", sender)
    subject = f"Meta Smart Glasses — India Content Ideas | {date.today()}"

    html_content = md_lib.markdown(report_md, extensions=["tables"])
    html_body = (
        f"<!DOCTYPE html><html><head>{_EMAIL_CSS}</head>"
        f"<body>{html_content}"
        f"<div class='footer'>Social Trends Agent · {date.today()}</div>"
        f"</body></html>"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(report_md, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"Report emailed to {recipient}")
    except Exception as e:
        print(f"Email failed: {e}")
