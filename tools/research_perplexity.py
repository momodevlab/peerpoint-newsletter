"""
research_perplexity.py
Uses the Perplexity API (OpenAI-compatible) to web-research this week's news
across mortgage rates, hard money lending, real estate investing, and macro.

Each query returns a live-web-searched summary with citations.
Output: .tmp/research_results.json

Usage:
    python tools/research_perplexity.py [--output .tmp/research_results.json]
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
MODEL = "sonar-pro"

# Queries ordered by importance — most critical first
QUERIES = [
    {
        "topic": "mortgage_rates",
        "query": (
            "What happened with US mortgage rates this week? Give specific rate numbers, "
            "which direction they moved and by how many basis points, and quote any named "
            "lenders, economists, or analysts who commented. Include the current 30-year fixed, "
            "15-year fixed, and jumbo rates."
        ),
    },
    {
        "topic": "hard_money_private_lending",
        "query": (
            "What is the latest news in US hard money lending and private real estate lending this week? "
            "Include current fix-and-flip loan rates, bridge loan rates, DSCR loan availability, "
            "and any named lenders who changed their programs or pricing. Focus on news relevant "
            "to real estate investors."
        ),
    },
    {
        "topic": "real_estate_investor_news",
        "query": (
            "What are the most important US real estate market developments this week for "
            "flippers, BRRRR investors, and landlords? Include home price trends, inventory changes, "
            "days on market, rental market data, and any specific metro markets making news. "
            "Name specific sources and cite data."
        ),
    },
    {
        "topic": "fed_and_macro",
        "query": (
            "What is the Federal Reserve's current stance on interest rates as of this week, "
            "and what are leading economists predicting for the next 2-3 FOMC meetings? "
            "Include any Fed officials who spoke, CPI or PCE data released, and what the "
            "bond market is pricing in for rate cuts or hikes."
        ),
    },
    {
        "topic": "dscr_bridge_loans",
        "query": (
            "What are current DSCR loan rates, bridge loan rates, and fix-and-flip loan terms "
            "from major US private lenders as of this week? Include LTV limits, credit requirements, "
            "and any notable shifts in underwriting criteria. Name specific lenders where possible."
        ),
    },
    {
        "topic": "regulatory_and_macro_risk",
        "query": (
            "Are there any significant regulatory changes, legislative developments, or "
            "macroeconomic risks announced this week that could affect US real estate investors, "
            "mortgage availability, or lending standards? Include any CFPB, HUD, or GSE news."
        ),
    },
]


def build_client():
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=PERPLEXITY_BASE_URL)
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)


def query_perplexity(client, query: str, topic: str) -> dict:
    """Fire a single Perplexity query and return structured result."""
    print(f"  Researching: {topic}...")
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial research analyst covering US real estate and mortgage markets. "
                        "Provide factual, specific, data-backed answers. Always include specific numbers, "
                        "named sources, and dates when available. Do not hedge or generalize. "
                        "If information is not available for this week, say so explicitly."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.1,  # low temperature — we want facts, not creativity
        )

        message = response.choices[0].message
        summary = message.content

        # Extract citations if present (Perplexity returns them in message.citations on some models)
        citations = []
        if hasattr(message, "citations"):
            citations = message.citations or []

        return {
            "topic": topic,
            "query": query,
            "summary": summary,
            "citations": citations,
            "model": MODEL,
            "fetched_at": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"  ERROR on topic '{topic}': {e}", file=sys.stderr)
        return {
            "topic": topic,
            "query": query,
            "summary": None,
            "citations": [],
            "error": str(e),
            "fetched_at": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(description="Research newsletter topics via Perplexity.")
    parser.add_argument("--output", default=".tmp/research_results.json")
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    client = build_client()

    results = []
    for item in QUERIES:
        result = query_perplexity(client, item["query"], item["topic"])
        results.append(result)

    # Validate — require at least 4 successful results
    successful = [r for r in results if r.get("summary")]
    failed     = [r for r in results if not r.get("summary")]

    if failed:
        print(f"\nWARNING: {len(failed)} query(s) failed: {[r['topic'] for r in failed]}", file=sys.stderr)

    if len(successful) < 4:
        print(f"ERROR: Only {len(successful)} queries succeeded (minimum 4 required).", file=sys.stderr)
        sys.exit(1)

    output = {
        "fetched_at": datetime.now().isoformat(),
        "query_count": len(results),
        "success_count": len(successful),
        "results": results,
    }

    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nResearch complete: {len(successful)}/{len(results)} queries succeeded.")
    print(f"Output written to {out_path}")

    # Preview summaries
    for r in successful:
        preview = (r["summary"] or "")[:120].replace("\n", " ")
        print(f"\n  [{r['topic']}]\n  {preview}...")


if __name__ == "__main__":
    main()
