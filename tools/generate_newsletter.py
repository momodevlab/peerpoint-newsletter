"""
generate_newsletter.py
Uses Claude to synthesize Perplexity research + rate data into structured
newsletter content. Two API calls: curation → writing.

Output: .tmp/newsletter_content.json

Usage:
    python tools/generate_newsletter.py [--articles .tmp/research_results.json]
                                        [--rates .tmp/rate_data.json]
                                        [--output .tmp/newsletter_content.json]
                                        [--edition-date YYYY-MM-DD]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from json_repair import repair_json

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You write for PeerPoint Capital's weekly newsletter, "The PeerPoint Market Wire." \
Readers are active real estate investors — flippers, BRRRR practitioners, and landlords \
who know the basics cold. They open this newsletter to learn what changed this week and \
exactly how it affects their next deal. Give them that.

Voice: Direct, warm, expert. PeerPoint is the advisor in the room who tells you the truth, \
not the one selling you something. We say what we think when the data supports it.

Non-negotiable writing rules:
- Every claim gets a specific number. Not "rates are rising" — "30yr fixed climbed 12 bps to 7.21%."
- Name your sources: "according to Mortgage News Daily," "per FRED data," "reported by HousingWire."
- Take a clear stance when the data points one direction. Do not present both sides when one is right.
- Write in prose paragraphs. Use bullets only when the content is genuinely a list.
- Do not open with "Certainly!", "Great question!", or any affirmation. Start with the news.
- Never use these words: delve, tapestry, nuanced, multifaceted, robust (in generic usage), \
  synergistic, leverage (as a verb), empower, journey, holistic, ecosystem (in non-tech context).
- Do not summarize at the end. End on the most useful sentence.
- No "it's worth noting that" or "in the ever-evolving landscape of" — ever.
- No hedging with "may," "might," "could" unless genuine uncertainty exists. State what is true.
- Specific names, specific lenders, specific dollar amounts. No generic examples.
- Do NOT use em dashes (—) as a stylistic crutch. One em dash per section maximum. \
  Rewrite with a comma, period, or new sentence instead. \
  Wrong: "The rate climbed — driven by inflation fears." Right: "The rate climbed, driven by inflation fears." \
  Wrong: "It clears coverage — but not with room to spare." Right: "It clears coverage, but barely."
- Never open a section by disclosing what data is unavailable. If data is thin, write what you know. \
  Do not write "there is no fresh data," "we cannot confirm," or "data is not available for this week."
"""


def load_research(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    results = data.get("results", [])
    return [r for r in results if r.get("summary")]


def load_rates(path: Path) -> dict:
    return json.loads(path.read_text())


def call_claude(client: anthropic.Anthropic, messages: list, max_tokens: int = 4096) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def curation_call(client: anthropic.Anthropic, research: list[dict], rates: dict) -> dict:
    """
    Call 1: Ask Claude to curate the research into a structured content plan.
    Returns a dict mapping section names to selected topic keys.
    """
    summaries = "\n\n".join([
        f"[{r['topic']}]\n{r['summary'][:600]}"
        for r in research
    ])

    rates_brief = {
        "30yr_fixed": rates.get("current_rates", {}).get("30yr_fixed"),
        "15yr_fixed": rates.get("current_rates", {}).get("15yr_fixed"),
        "fed_funds":  rates.get("current_rates", {}).get("fed_funds"),
        "prime_rate": rates.get("current_rates", {}).get("prime_rate"),
        "wow_30yr":   rates.get("wow_changes", {}).get("30yr_fixed"),
        "as_of":      rates.get("as_of_date"),
    }

    prompt = f"""Here is this week's research for the PeerPoint Market Wire newsletter, \
plus current rate data. Plan the newsletter content.

RATE DATA:
{json.dumps(rates_brief, indent=2)}

RESEARCH SUMMARIES:
{summaries}

Return a JSON object with this exact structure. No other text — JSON only:
{{
  "subject_line": "compelling email subject line, max 60 chars, specific rate or news hook",
  "preview_text": "one-line preview, max 90 chars, different angle from subject",
  "rate_snapshot_focus": "1-2 sentences on what's most notable about rates this week",
  "top_story_topics": ["topic_key_1", "topic_key_2", "topic_key_3"],
  "hard_money_pulse_notes": "key points to hit in the hard money section",
  "deal_math_scenario": "describe the specific deal scenario to use (e.g., $350k SFR flip in Phoenix)",
  "market_intel_focus": "what macro/Fed angle is most useful for investors this week",
  "quick_hits": [
    "one-liner 1 (include a source name)",
    "one-liner 2 (include a source name)",
    "one-liner 3 (include a source name)",
    "one-liner 4 (include a source name)"
  ]
}}
"""

    text = call_claude(client, [{"role": "user", "content": prompt}], max_tokens=1024)

    # Strip any markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)

    return json.loads(repair_json(text))


def writing_call(
    client: anthropic.Anthropic,
    research: list[dict],
    rates: dict,
    content_plan: dict,
    edition_date: str,
) -> dict:
    """
    Call 2: Write all newsletter sections based on the content plan.
    Returns the full newsletter_content dict.
    """
    # Build the full research context for selected topics
    selected_topics = set(content_plan.get("top_story_topics", []))
    research_by_topic = {r["topic"]: r for r in research}

    full_research = ""
    for topic, r in research_by_topic.items():
        full_research += f"\n\n=== {topic.upper()} ===\n{r['summary']}"
        if r.get("citations"):
            full_research += "\nCitations: " + ", ".join(str(c) for c in r["citations"][:5])

    prompt = f"""Write the full PeerPoint Market Wire newsletter for the week of {edition_date}.

CONTENT PLAN (use this as your guide):
{json.dumps(content_plan, indent=2)}

RATE DATA:
{json.dumps(rates.get("current_rates"), indent=2)}
Week-over-week changes: {json.dumps(rates.get("wow_changes"), indent=2)}
Year-over-year changes: {json.dumps(rates.get("yoy_changes"), indent=2)}
52-week ranges: {json.dumps(rates.get("ranges_52wk"), indent=2)}

FULL RESEARCH:
{full_research}

Write each section as HTML fragments (p, strong, a tags only — no divs, no classes). \
Return a JSON object with this exact structure. JSON only, no other text:

{{
  "edition_date": "{edition_date}",
  "subject_line": "...",
  "preview_text": "...",
  "sections": {{
    "rate_snapshot": {{
      "headline": "Rate Snapshot: Week of {edition_date}",
      "body_html": "<p>...</p>",
      "key_takeaway": "one sentence — the single most actionable rate insight this week"
    }},
    "top_stories": [
      {{
        "headline": "...",
        "body_html": "<p>...</p><p>...</p>",
        "source_name": "...",
        "source_url": "...",
        "category_tag": "Mortgage Rates | Private Lending | Market Conditions | Fed & Macro"
      }}
    ],
    "hard_money_pulse": {{
      "headline": "Hard Money Pulse",
      "body_html": "<p>...</p>",
      "key_takeaway": "one sentence on the hard money market right now"
    }},
    "deal_math": {{
      "headline": "Deal Math",
      "body_html": "<p>...</p>",
      "scenario_label": "e.g., $350k SFR Flip, Phoenix AZ"
    }},
    "market_intel": {{
      "headline": "Market Intel",
      "body_html": "<p>...</p><p>...</p>"
    }},
    "quick_hits": [
      {{"text": "...", "source_name": "...", "source_url": "..."}}
    ]
  }}
}}
"""

    text = call_claude(client, [{"role": "user", "content": prompt}], max_tokens=8096)

    # Strip fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)

    try:
        return json.loads(repair_json(text))
    except Exception:
        Path(".tmp/claude_raw_output.txt").write_text(text)
        print("  ERROR: Could not parse Claude writing output. Raw saved to .tmp/claude_raw_output.txt", file=sys.stderr)
        raise


def clean_em_dashes(obj):
    """
    Recursively replace em dashes in all string values.
    ' — ' (surrounded by spaces) → ', '   (parenthetical separator)
    '— '  (leading)               → ''     (remove opener dash)
    ' —'  (trailing)              → '.'    (close the sentence)
    '—'   (no spaces, rare)       → '-'    (treat as hyphen)
    """
    if isinstance(obj, dict):
        return {k: clean_em_dashes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_em_dashes(v) for v in obj]
    if isinstance(obj, str):
        s = obj
        s = re.sub(r'\s+\u2014\s+', ', ', s)   # word — word  →  word, word
        s = re.sub(r'^\u2014\s*', '', s)         # leading —
        s = re.sub(r'\s*\u2014$', '.', s)        # trailing —
        s = s.replace('\u2014', '-')              # any remaining
        return s
    return obj


def main():
    parser = argparse.ArgumentParser(description="Generate newsletter content via Claude.")
    parser.add_argument("--articles", default=".tmp/research_results.json")
    parser.add_argument("--rates", default=".tmp/rate_data.json")
    parser.add_argument("--output", default=".tmp/newsletter_content.json")
    parser.add_argument("--edition-date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    articles_path = Path(args.articles)
    rates_path    = Path(args.rates)
    out_path      = Path(args.output)

    for p in [articles_path, rates_path]:
        if not p.exists():
            print(f"ERROR: Required input not found: {p}", file=sys.stderr)
            sys.exit(1)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client   = anthropic.Anthropic(api_key=api_key)
    research = load_research(articles_path)
    rates    = load_rates(rates_path)

    print(f"Loaded {len(research)} research summaries.")
    print(f"Edition date: {args.edition_date}")

    print("\nCall 1 — Curating content plan...")
    content_plan = curation_call(client, research, rates)
    print(f"  Subject: {content_plan.get('subject_line')}")

    print("\nCall 2 — Writing newsletter sections...")
    newsletter = writing_call(client, research, rates, content_plan, args.edition_date)

    newsletter = clean_em_dashes(newsletter)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(newsletter, indent=2))

    print(f"\nNewsletter content written to {out_path}")
    sections = newsletter.get("sections", {})
    print(f"  Sections: {', '.join(sections.keys())}")
    stories = sections.get("top_stories", [])
    print(f"  Top stories: {len(stories)}")
    quick_hits = sections.get("quick_hits", [])
    print(f"  Quick hits: {len(quick_hits)}")


if __name__ == "__main__":
    main()
