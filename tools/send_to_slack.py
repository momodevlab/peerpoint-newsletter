"""
send_to_slack.py
Posts the newsletter HTML, LinkedIn post, and tweets to a Slack channel for weekly review.

Required env vars:
  SLACK_BOT_TOKEN  — Bot OAuth token (xoxb-...)
  SLACK_CHANNEL_ID — Channel ID (e.g. C0123456789) or name (e.g. #newsletter-review)

Usage:
    python tools/send_to_slack.py
    python tools/send_to_slack.py --content .tmp/newsletter_content.json
                                  --social .tmp/social_posts.json
                                  --html .tmp/newsletter_2026-03-17.html
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()


def find_latest_html() -> Path | None:
    candidates = sorted(Path(".tmp").glob("newsletter_*.html"), reverse=True)
    return candidates[0] if candidates else None


def post_message(client: WebClient, channel: str, blocks: list, text: str = "") -> str:
    """Post a block kit message. Returns ts for threading."""
    resp = client.chat_postMessage(channel=channel, blocks=blocks, text=text)
    return resp["ts"]


def post_to_slack(
    client: WebClient,
    channel: str,
    content: dict,
    posts: dict,
    html_path: Path | None,
) -> None:
    edition_date  = content.get("edition_date", datetime.now().strftime("%Y-%m-%d"))
    subject       = content.get("subject_line", "PeerPoint Market Wire")
    linkedin_post = posts.get("linkedin_post", "")
    tweets        = posts.get("tweets", [])

    # ── 1. Header ─────────────────────────────────────────────────────────────
    post_message(
        client, channel,
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f":newspaper: PeerPoint Market Wire — {edition_date}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Subject line:* {subject}\n\nReview below and post when ready."},
            },
            {"type": "divider"},
        ],
        text=f"PeerPoint Market Wire — {edition_date}",
    )
    print("  Header posted")

    # ── 2. LinkedIn post ───────────────────────────────────────────────────────
    post_message(
        client, channel,
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*:linkedin: LinkedIn Post*"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": linkedin_post},
            },
            {"type": "divider"},
        ],
        text="LinkedIn Post",
    )
    print("  LinkedIn post sent")

    # ── 3. Tweets ──────────────────────────────────────────────────────────────
    tweet_blocks: list = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:bird: Tweets (3)*"},
        },
    ]
    for i, tweet in enumerate(tweets, 1):
        char_count = len(tweet)
        over = f"  :warning: *{char_count}/280*" if char_count > 280 else f"  _{char_count}/280_"
        tweet_blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{i}.* {tweet}\n{over}"},
        })
        tweet_blocks.append({"type": "divider"})

    post_message(client, channel, tweet_blocks, text="Tweets")
    print("  Tweets sent")

    # ── 4. Newsletter HTML file upload ─────────────────────────────────────────
    if html_path and html_path.exists():
        client.files_upload_v2(
            channel=channel,
            file=str(html_path),
            filename=html_path.name,
            title=f"Newsletter HTML — {edition_date}",
            initial_comment=":page_facing_up: *Newsletter HTML* — open in browser to review the full email",
        )
        print(f"  HTML uploaded: {html_path.name}")
    else:
        print("  WARNING: No newsletter HTML found to upload", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Post newsletter and social posts to Slack for review.")
    parser.add_argument("--content", default=".tmp/newsletter_content.json")
    parser.add_argument("--social",  default=".tmp/social_posts.json")
    parser.add_argument("--html",    default=None, help="Newsletter HTML path (default: latest in .tmp/)")
    args = parser.parse_args()

    token   = os.getenv("SLACK_BOT_TOKEN",  "").strip()
    channel = os.getenv("SLACK_CHANNEL_ID", "").strip()

    for name, val in [("SLACK_BOT_TOKEN", token), ("SLACK_CHANNEL_ID", channel)]:
        if not val:
            print(f"ERROR: {name} not set in .env", file=sys.stderr)
            sys.exit(1)

    content_path = Path(args.content)
    social_path  = Path(args.social)
    html_path    = Path(args.html) if args.html else find_latest_html()

    for p in [content_path, social_path]:
        if not p.exists():
            print(f"ERROR: {p} not found.", file=sys.stderr)
            sys.exit(1)

    content = json.loads(content_path.read_text())
    posts   = json.loads(social_path.read_text())
    client  = WebClient(token=token)

    print(f"Posting to Slack channel: {channel}")
    try:
        post_to_slack(client, channel, content, posts, html_path)
        print("\nDone. Check Slack for your review.")
    except SlackApiError as e:
        print(f"ERROR: Slack API — {e.response['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
