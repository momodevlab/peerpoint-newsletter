"""
generate_social_posts.py
Uses Claude to generate a LinkedIn post and 3 tweets from newsletter_content.json.

Output: .tmp/social_posts.json

Usage:
    python tools/generate_social_posts.py
    python tools/generate_social_posts.py --content .tmp/newsletter_content.json
                                          --output .tmp/social_posts.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from json_repair import repair_json
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You write social media content for PeerPoint Capital, a private lender serving real estate investors.
Readers are active investors: flippers, BRRRR practitioners, and landlords.

Voice: Direct, warm, expert. PeerPoint is the advisor in the room, not a salesperson.

Writing rules:
- Every claim gets a specific number. Not "rates are rising" — "30yr fixed climbed 12 bps to 7.21%."
- Name sources when relevant.
- Take a clear stance when the data points one direction.
- Do not open with "Certainly!", "Great question!", or any affirmation.
- Never use: delve, tapestry, nuanced, multifaceted, robust (generic), synergistic, leverage (verb),
  empower, journey, holistic, ecosystem (non-tech).
- No hedging with "may," "might," "could" unless genuine uncertainty exists.
- No em dashes (—). Use commas, periods, or new sentences instead.
- Do not summarize at the end. End on the most useful sentence.
"""


def call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def build_prompt(content: dict) -> str:
    subject      = content.get("subject_line", "")
    edition_date = content.get("edition_date", "")
    sections     = content.get("sections", {})

    rate_snapshot = sections.get("rate_snapshot", {})
    rate_takeaway = rate_snapshot.get("key_takeaway", "")

    top_stories = sections.get("top_stories", [])
    story_headlines = [s.get("headline", "") for s in top_stories[:3]]

    hard_money    = sections.get("hard_money_pulse", {})
    hm_takeaway   = hard_money.get("key_takeaway", "")

    deal_math     = sections.get("deal_math", {})
    deal_label    = deal_math.get("scenario_label", "")

    quick_hits    = sections.get("quick_hits", [])
    hit_texts     = [q.get("text", "") for q in quick_hits[:3]]

    story_list  = "\n".join(f"  - {h}" for h in story_headlines)
    hits_list   = "\n".join(f"  - {t}" for t in hit_texts)

    return f"""Write social media content for PeerPoint Capital based on this week's newsletter.

Edition date: {edition_date}
Newsletter subject: {subject}

Key data points:
- Rate takeaway: {rate_takeaway}
- Hard money takeaway: {hm_takeaway}
- Deal math scenario: {deal_label}
- Top story headlines:
{story_list}
- Quick hits:
{hits_list}

Return JSON only, no other text:
{{
  "linkedin_post": "200-350 words. Lead with the most important market development. Include 2-3 specific numbers with sources. End with one clear implication for investors. At most 3 hashtags at the very end, or none. Do NOT reference 'our newsletter' or 'this week's edition'.",
  "tweets": [
    "Tweet 1 (under 280 chars): Rate-focused — the most important number this week and what it means.",
    "Tweet 2 (under 280 chars): Market conditions angle — prices, inventory, or policy shift.",
    "Tweet 3 (under 280 chars): Actionable investor take — what to do or watch right now."
  ]
}}"""


def generate_posts(client: anthropic.Anthropic, content: dict) -> dict:
    prompt = build_prompt(content)
    text   = call_claude(client, prompt)

    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$",          "", text.strip(), flags=re.MULTILINE)

    return json.loads(repair_json(text))


def main():
    parser = argparse.ArgumentParser(description="Generate LinkedIn and Twitter posts from newsletter content.")
    parser.add_argument("--content", default=".tmp/newsletter_content.json")
    parser.add_argument("--output",  default=".tmp/social_posts.json")
    args = parser.parse_args()

    content_path = Path(args.content)
    out_path     = Path(args.output)

    if not content_path.exists():
        print(f"ERROR: {content_path} not found. Run generate_newsletter.py first.", file=sys.stderr)
        sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    content = json.loads(content_path.read_text())
    client  = anthropic.Anthropic(api_key=api_key)

    print(f"Generating social posts for: {content.get('subject_line', '')}")
    posts = generate_posts(client, content)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(posts, indent=2))
    print(f"Social posts written to {out_path}")

    linkedin = posts.get("linkedin_post", "")
    tweets   = posts.get("tweets", [])
    print(f"  LinkedIn: {len(linkedin)} chars")
    for i, tweet in enumerate(tweets, 1):
        status = "OK" if len(tweet) <= 280 else f"OVER LIMIT ({len(tweet)} chars)"
        print(f"  Tweet {i}: {len(tweet)} chars — {status}")


if __name__ == "__main__":
    main()
