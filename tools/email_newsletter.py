"""
email_newsletter.py
Emails the assembled newsletter HTML to a recipient using Gmail SMTP.

Requires:
    GMAIL_SENDER    — your Gmail address (e.g. you@gmail.com)
    GMAIL_APP_PASSWORD — 16-character Gmail App Password
    GMAIL_RECIPIENT — address to send to (can be same as sender)

Usage:
    python tools/email_newsletter.py
    python tools/email_newsletter.py --html .tmp/newsletter_2026-03-17.html
"""

import argparse
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def find_latest_html() -> Path | None:
    candidates = sorted(Path(".tmp").glob("newsletter_*.html"), reverse=True)
    return candidates[0] if candidates else None


def load_subject() -> str:
    p = Path(".tmp/newsletter_content.json")
    if p.exists():
        data = json.loads(p.read_text())
        return data.get("subject_line", "PeerPoint Market Wire")
    return "PeerPoint Market Wire"


def send_email(sender: str, app_password: str, recipient: str, subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[DRAFT] {subject}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())


def main():
    parser = argparse.ArgumentParser(description="Email newsletter HTML via Gmail.")
    parser.add_argument("--html", default=None, help="Path to HTML file (default: latest in .tmp/)")
    args = parser.parse_args()

    sender       = os.getenv("GMAIL_SENDER", "").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    recipient    = os.getenv("GMAIL_RECIPIENT", "").strip()

    for name, val in [("GMAIL_SENDER", sender), ("GMAIL_APP_PASSWORD", app_password),
                      ("GMAIL_RECIPIENT", recipient)]:
        if not val:
            print(f"ERROR: {name} not set.", file=sys.stderr)
            sys.exit(1)

    html_path = Path(args.html) if args.html else find_latest_html()
    if not html_path or not html_path.exists():
        print("ERROR: No newsletter HTML found. Run assemble_html.py first.", file=sys.stderr)
        sys.exit(1)

    subject = load_subject()
    html    = html_path.read_text(encoding="utf-8")

    print(f"Sending '{subject}' to {recipient}...")
    send_email(sender, app_password, recipient, subject, html)
    print("  Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
