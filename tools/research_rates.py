"""
research_rates.py
Fetches current mortgage rate data from FRED API and yfinance.
Outputs .tmp/rate_data.json for use by create_infographics.py and generate_newsletter.py.

Usage:
    python tools/research_rates.py [--weeks-back 52] [--output .tmp/rate_data.json]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# ── FRED series ───────────────────────────────────────────────────────────────
FRED_SERIES = {
    "30yr_fixed":  "MORTGAGE30US",
    "15yr_fixed":  "MORTGAGE15US",
    "fed_funds":   "DFF",
    "inflation_10yr": "T10YIE",
}

YFINANCE_TICKERS = {
    "10yr_treasury": "^TNX",
    "mbs_etf":       "MBB",
}

CACHE_FILE = Path(".tmp/fred_cache.json")
CACHE_MAX_AGE_HOURS = 6


def load_cache() -> dict:
    if CACHE_FILE.exists():
        data = json.loads(CACHE_FILE.read_text())
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at < timedelta(hours=CACHE_MAX_AGE_HOURS):
            return data
    return {}


def save_cache(data: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["cached_at"] = datetime.now().isoformat()
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def fetch_fred(weeks_back: int) -> dict:
    """Fetch FRED series. Returns dict of {series_key: list of {date, value}}."""
    cache = load_cache()
    if cache.get("fred_series"):
        print("  Using cached FRED data.")
        return cache["fred_series"]

    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        print("  WARNING: FRED_API_KEY not set. Rate history will be empty.", file=sys.stderr)
        return {}

    try:
        from fredapi import Fred
        fred = Fred(api_key=api_key)
    except ImportError:
        print("  ERROR: fredapi not installed. Run: pip install fredapi", file=sys.stderr)
        return {}

    start_date = (datetime.now() - timedelta(weeks=weeks_back)).strftime("%Y-%m-%d")
    result = {}

    for key, series_id in FRED_SERIES.items():
        try:
            s = fred.get_series(series_id, observation_start=start_date)
            s = s.dropna().resample("W-THU").last().dropna()
            result[key] = [
                {"date": str(d.date()), "value": round(float(v), 4)}
                for d, v in s.items()
            ]
            print(f"  FRED {series_id}: {len(result[key])} weekly observations")
        except Exception as e:
            print(f"  WARNING: Could not fetch FRED {series_id}: {e}", file=sys.stderr)
            result[key] = []

    cache_data = load_cache()
    cache_data["fred_series"] = result
    save_cache(cache_data)
    return result


def fetch_yfinance() -> dict:
    """Fetch current market data from yfinance."""
    result = {}
    for key, ticker in YFINANCE_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist.empty:
                result[key] = None
                continue
            last_close = round(float(hist["Close"].iloc[-1]), 4)
            prev_close = round(float(hist["Close"].iloc[-2]), 4) if len(hist) >= 2 else last_close
            result[key] = {
                "current": last_close,
                "prev": prev_close,
                "change": round(last_close - prev_close, 4),
            }
            print(f"  yfinance {ticker}: {last_close}")
        except Exception as e:
            print(f"  WARNING: Could not fetch yfinance {ticker}: {e}", file=sys.stderr)
            result[key] = None
    return result


def compute_stats(series: list[dict]) -> dict:
    """Compute current, WoW change, YoY change, 52wk high/low from a list of {date, value}."""
    if not series:
        return {"current": None, "wow_change": None, "yoy_change": None,
                "high_52wk": None, "low_52wk": None}

    values = [entry["value"] for entry in series]
    current = values[-1]
    wow = round(current - values[-2], 4) if len(values) >= 2 else None
    yoy = round(current - values[-52], 4) if len(values) >= 52 else None

    recent = values[-52:] if len(values) >= 52 else values
    return {
        "current": current,
        "wow_change": wow,
        "yoy_change": yoy,
        "high_52wk": round(max(recent), 4),
        "low_52wk": round(min(recent), 4),
    }


def derive_prime_rate(fed_funds_current: float | None) -> float | None:
    """Prime rate = Fed Funds + 3.0 (standard spread)."""
    if fed_funds_current is None:
        return None
    return round(fed_funds_current + 3.0, 4)


def build_output(fred_series: dict, yf_data: dict) -> dict:
    stats = {key: compute_stats(series) for key, series in fred_series.items()}

    current_rates = {
        "30yr_fixed":  stats.get("30yr_fixed", {}).get("current"),
        "15yr_fixed":  stats.get("15yr_fixed", {}).get("current"),
        "fed_funds":   stats.get("fed_funds", {}).get("current"),
        "10yr_treasury": yf_data.get("10yr_treasury", {}).get("current") if yf_data.get("10yr_treasury") else None,
        "prime_rate":  derive_prime_rate(stats.get("fed_funds", {}).get("current")),
    }

    wow_changes = {key: stats[key].get("wow_change") for key in stats}
    yoy_changes = {key: stats[key].get("yoy_change") for key in stats}
    ranges_52wk = {
        key: {"high": stats[key].get("high_52wk"), "low": stats[key].get("low_52wk")}
        for key in stats
    }

    # Keep last 52 weekly data points for charting
    history = {}
    for key, series in fred_series.items():
        history[key] = series[-52:] if len(series) >= 52 else series

    return {
        "as_of_date": datetime.now().strftime("%Y-%m-%d"),
        "current_rates": current_rates,
        "wow_changes": wow_changes,
        "yoy_changes": yoy_changes,
        "ranges_52wk": ranges_52wk,
        "market": {
            "10yr_treasury": yf_data.get("10yr_treasury"),
            "mbs_etf":       yf_data.get("mbs_etf"),
        },
        "rate_history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch mortgage rate data.")
    parser.add_argument("--weeks-back", type=int, default=52)
    parser.add_argument("--output", default=".tmp/rate_data.json")
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Fetching FRED rate data...")
    fred_series = fetch_fred(args.weeks_back)

    print("Fetching yfinance market data...")
    yf_data = fetch_yfinance()

    output = build_output(fred_series, yf_data)

    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nRate data written to {out_path}")

    # Summary
    rates = output["current_rates"]
    print(f"  30yr fixed:    {rates.get('30yr_fixed')}%  (WoW: {output['wow_changes'].get('30yr_fixed'):+.2f})" if rates.get('30yr_fixed') else "  30yr fixed: N/A")
    print(f"  15yr fixed:    {rates.get('15yr_fixed')}%")
    print(f"  Fed Funds:     {rates.get('fed_funds')}%")
    print(f"  10yr Treasury: {rates.get('10yr_treasury')}%")
    print(f"  Prime Rate:    {rates.get('prime_rate')}%")


if __name__ == "__main__":
    main()
