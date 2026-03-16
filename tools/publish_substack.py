"""
publish_substack.py
Logs into Substack and creates a newsletter post from the assembled HTML file.

By default creates a DRAFT so you can review before sending.
Use --send to publish immediately, or --schedule "2026-03-17 08:00" to schedule.

Usage:
    python tools/publish_substack.py
    python tools/publish_substack.py --send
    python tools/publish_substack.py --schedule "2026-03-17 08:00"
    python tools/publish_substack.py --html .tmp/newsletter_2026-03-16.html
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://substack.com"


def login(email: str, password: str, publication: str) -> dict:
    """Authenticate and return session cookies."""
    print("Logging into Substack...")
    with httpx.Client(follow_redirects=True) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/login",
            json={
                "email": email,
                "password": password,
                "for_pub": publication,
                "captcha_response": None,
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ERROR: Login failed ({resp.status_code}): {resp.text[:300]}", file=sys.stderr)
            sys.exit(1)

        cookies = dict(resp.cookies)
        if not cookies.get("substack.sid"):
            print("  ERROR: No session cookie returned — check credentials.", file=sys.stderr)
            sys.exit(1)

        print(f"  Logged in as {email}")
        return cookies


def extract_body_html(full_html: str) -> str:
    """
    Extract the inner content div from the full HTML file.
    Substack doesn't want the full <html><head>... wrapper.
    """
    # Try to get everything inside <body>
    body_match = re.search(r"<body[^>]*>(.*?)</body>", full_html, re.DOTALL | re.IGNORECASE)
    if body_match:
        return body_match.group(1).strip()
    return full_html


def get_publication_id(cookies: dict, publication: str) -> int | None:
    """Fetch the numeric publication ID (needed for post creation)."""
    with httpx.Client(follow_redirects=True, cookies=cookies) as client:
        resp = client.get(
            f"https://{publication}.substack.com/api/v1/publication",
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            pub_id = data.get("id")
            print(f"  Publication ID: {pub_id}")
            return pub_id
    return None


def create_draft(
    cookies: dict,
    publication: str,
    subject: str,
    preview_text: str,
    body_html: str,
    audience: str = "everyone",
) -> dict:
    """Create a draft post on Substack. Returns the post object."""
    pub_url = f"https://{publication}.substack.com"

    payload = {
        "draft_title": subject,
        "draft_subtitle": preview_text,
        "draft_body": body_html,
        "draft_section_id": None,
        "section_chosen": True,
        "type": "newsletter",
        "audience": audience,
    }

    with httpx.Client(follow_redirects=True, cookies=cookies) as client:
        resp = client.post(
            f"{pub_url}/api/v1/posts",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

    if resp.status_code not in (200, 201):
        print(f"  ERROR: Draft creation failed ({resp.status_code}): {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def send_post(cookies: dict, publication: str, post_id: int, schedule_utc: str | None = None):
    """Publish or schedule a draft post."""
    pub_url = f"https://{publication}.substack.com"

    if schedule_utc:
        payload = {"post_date": schedule_utc, "send": True}
        action = f"scheduled for {schedule_utc}"
    else:
        payload = {"send": True}
        action = "sent immediately"

    with httpx.Client(follow_redirects=True, cookies=cookies) as client:
        resp = client.post(
            f"{pub_url}/api/v1/posts/{post_id}/publish",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    if resp.status_code not in (200, 201):
        print(f"  ERROR: Publish failed ({resp.status_code}): {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)

    print(f"  Post {action}.")


def find_latest_html() -> Path | None:
    """Find the most recently generated newsletter HTML in .tmp/."""
    candidates = sorted(Path(".tmp").glob("newsletter_*.html"), reverse=True)
    return candidates[0] if candidates else None


def load_content_json() -> dict:
    p = Path(".tmp/newsletter_content.json")
    if p.exists():
        return json.loads(p.read_text())
    return {}


def parse_schedule(schedule_str: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM' local time to ISO 8601 UTC string for Substack."""
    try:
        local_dt = datetime.strptime(schedule_str, "%Y-%m-%d %H:%M")
        # Treat as local time, convert to UTC (simplified — assumes system timezone)
        utc_dt = local_dt.astimezone(timezone.utc)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except ValueError:
        print(f"  ERROR: Invalid schedule format '{schedule_str}'. Use 'YYYY-MM-DD HH:MM'.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Publish newsletter to Substack.")
    parser.add_argument("--html", default=None, help="Path to newsletter HTML file (default: latest in .tmp/)")
    parser.add_argument("--send", action="store_true", help="Publish immediately (default: draft only)")
    parser.add_argument("--schedule", default=None, metavar="YYYY-MM-DD HH:MM",
                        help="Schedule send time in local time (e.g. '2026-03-17 08:00')")
    parser.add_argument("--audience", default="everyone", choices=["everyone", "paid"],
                        help="Audience: everyone (free+paid) or paid only")
    args = parser.parse_args()

    email       = os.getenv("SUBSTACK_EMAIL", "").strip()
    password    = os.getenv("SUBSTACK_PASSWORD", "").strip()
    publication = os.getenv("SUBSTACK_PUBLICATION", "").strip()

    for name, val in [("SUBSTACK_EMAIL", email), ("SUBSTACK_PASSWORD", password),
                      ("SUBSTACK_PUBLICATION", publication)]:
        if not val:
            print(f"ERROR: {name} not set in .env", file=sys.stderr)
            sys.exit(1)

    # Find HTML file
    html_path = Path(args.html) if args.html else find_latest_html()
    if not html_path or not html_path.exists():
        print("ERROR: No newsletter HTML found. Run assemble_html.py first.", file=sys.stderr)
        sys.exit(1)
    print(f"HTML file: {html_path}")

    # Load subject/preview from content JSON
    content = load_content_json()
    subject      = content.get("subject_line", html_path.stem)
    preview_text = content.get("preview_text", "")
    print(f"Subject: {subject}")

    # Extract body HTML
    full_html = html_path.read_text(encoding="utf-8")
    body_html = extract_body_html(full_html)

    # Authenticate
    cookies = login(email, password, publication)

    # Create draft
    print("Creating Substack draft...")
    post = create_draft(cookies, publication, subject, preview_text, body_html, args.audience)
    post_id  = post.get("id")
    post_url = post.get("canonical_url") or f"https://{publication}.substack.com/p/{post.get('slug', '')}"
    print(f"  Draft created: {post_url}")

    # Send or schedule if requested
    if args.send:
        print("Publishing now...")
        send_post(cookies, publication, post_id)
    elif args.schedule:
        schedule_utc = parse_schedule(args.schedule)
        print(f"Scheduling post for {args.schedule} local time...")
        send_post(cookies, publication, post_id, schedule_utc=schedule_utc)
    else:
        print("\nDraft saved. Review at:")
        print(f"  https://{publication}.substack.com/publish/posts")

    # Save result
    result = {
        "post_id": post_id,
        "post_url": post_url,
        "subject": subject,
        "published_at": datetime.now().isoformat(),
        "status": "scheduled" if args.schedule else ("sent" if args.send else "draft"),
    }
    Path(".tmp/publish_result.json").write_text(json.dumps(result, indent=2))
    print(f"\nDone. Result saved to .tmp/publish_result.json")


if __name__ == "__main__":
    main()
