"""
assemble_html.py
Combines newsletter_content.json + chart PNGs + brand logos into
a single self-contained HTML file using the Jinja2 template.
Runs premailer to inline all CSS for email client compatibility.

Usage:
    python tools/assemble_html.py [--content .tmp/newsletter_content.json]
                                  [--charts-dir .tmp/charts]
                                  [--output .tmp/newsletter_YYYY-MM-DD.html]
                                  [--template tools/templates/newsletter.html]
                                  [--issue-number 1]
"""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path


# ── HELPERS ───────────────────────────────────────────────────────────────────

def encode_image(path: Path) -> str | None:
    """Base64-encode an image file. Returns None if file doesn't exist."""
    if path and path.exists():
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    return None


def load_charts(charts_dir: Path) -> dict:
    """Load all chart PNGs as base64 strings."""
    chart_names = [
        "rate_trend_12mo",
        "fed_vs_mortgage",
        "rate_snapshot_card",
        "deal_math_card",
    ]
    charts = {}
    for name in chart_names:
        p = charts_dir / f"{name}.png"
        enc = encode_image(p)
        charts[name] = enc
        if enc:
            print(f"  Chart loaded: {name}.png ({len(enc) // 1024}KB b64)")
        else:
            print(f"  Chart missing (will be skipped): {name}.png")
    return charts


def build_rate_rows(rate_data: dict) -> list[dict]:
    """Build the rate table rows for the template."""
    current = rate_data.get("current_rates", {})
    wow     = rate_data.get("wow_changes", {})

    def change_info(key: str) -> tuple[str, str]:
        v = wow.get(key)
        if v is None:
            return "flat", "—"
        if v > 0:
            return "up", f"▲ {abs(v):.2f}%"
        if v < 0:
            return "down", f"▼ {abs(v):.2f}%"
        return "flat", "—"

    rows = []
    rate_fields = [
        ("30yr_fixed",    "30-Yr Fixed"),
        ("15yr_fixed",    "15-Yr Fixed"),
        ("fed_funds",     "Fed Funds"),
        ("10yr_treasury", "10-Yr Treasury"),
        ("prime_rate",    "Prime Rate"),
    ]
    for key, label in rate_fields:
        val = current.get(key)
        if val is None:
            continue
        direction, change_label = change_info(key)
        rows.append({
            "label":        label,
            "value":        f"{val:.2f}%",
            "direction":    direction,
            "change_label": change_label,
        })
    return rows


def format_edition_date(date_str: str) -> str:
    """Format YYYY-MM-DD → 'March 16, 2026'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %-d, %Y")
    except Exception:
        try:
            # Windows doesn't support %-d — fall back
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%B %d, %Y").replace(" 0", " ")
        except Exception:
            return date_str


def check_data_staleness(rate_data: dict) -> bool:
    """Return True if rate data is more than 10 days old."""
    as_of = rate_data.get("as_of_date")
    if not as_of:
        return True
    try:
        age = (datetime.now() - datetime.strptime(as_of, "%Y-%m-%d")).days
        return age > 10
    except Exception:
        return False


def render_template(template_path: Path, context: dict) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        print("ERROR: jinja2 not installed. Run: pip install jinja2", file=sys.stderr)
        sys.exit(1)

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html"]),
    )
    # Mark body_html fields as safe (they contain HTML from Claude)
    template = env.get_template(template_path.name)
    return template.render(**context)


def inline_css(html: str) -> str:
    try:
        import premailer
        return premailer.transform(html)
    except ImportError:
        print("  WARNING: premailer not installed — CSS will not be inlined. Run: pip install premailer")
        return html
    except Exception as e:
        print(f"  WARNING: premailer failed ({e}) — using un-inlined HTML.")
        return html


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Assemble final newsletter HTML.")
    parser.add_argument("--content",      default=".tmp/newsletter_content.json")
    parser.add_argument("--charts-dir",   default=".tmp/charts")
    parser.add_argument("--output",       default=None)  # auto-named by date if omitted
    parser.add_argument("--template",     default="tools/templates/newsletter.html")
    parser.add_argument("--issue-number", type=int, default=1)
    args = parser.parse_args()

    content_path  = Path(args.content)
    charts_dir    = Path(args.charts_dir)
    template_path = Path(args.template)

    # Validate inputs
    for p, label in [(content_path, "newsletter content"), (template_path, "HTML template")]:
        if not p.exists():
            print(f"ERROR: {label} not found at {p}", file=sys.stderr)
            sys.exit(1)

    print("Loading newsletter content...")
    newsletter = json.loads(content_path.read_text())
    edition_date = newsletter.get("edition_date", datetime.now().strftime("%Y-%m-%d"))

    # Auto-name output file
    out_path = Path(args.output) if args.output else Path(f".tmp/newsletter_{edition_date}.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Loading charts...")
    charts = load_charts(charts_dir)

    print("Loading brand logos...")
    # Try both possible logo filenames
    logo_white_path = Path("brand_assets/logo-white (1).png")
    logo_path       = Path("brand_assets/logo (1).png")
    logo_white_b64  = encode_image(logo_white_path)
    logo_b64        = encode_image(logo_path)
    if logo_white_b64:
        print("  White logo loaded.")
    else:
        print("  WARNING: White logo not found at brand_assets/logo-white (1).png")

    print("Building rate rows...")
    # Load rate data for the rate table (separate from newsletter content)
    rate_data_path = Path(".tmp/rate_data.json")
    rate_data = json.loads(rate_data_path.read_text()) if rate_data_path.exists() else {}
    rate_rows = build_rate_rows(rate_data)

    stale = check_data_staleness(rate_data)
    if stale:
        print("  WARNING: Rate data may be stale (>10 days old). Consider re-running research_rates.py")

    # Build Jinja2 context
    sections = newsletter.get("sections", {})
    context = {
        "subject_line":        newsletter.get("subject_line", "The PeerPoint Market Wire"),
        "edition_date":        edition_date,
        "edition_date_formatted": format_edition_date(edition_date),
        "issue_number":        args.issue_number,
        "sections":            sections,
        "rate_rows":           rate_rows,
        "charts":              charts,
        "logo_white_b64":      logo_white_b64,
        "logo_b64":            logo_b64,
        "stale_data_warning":  stale,
    }

    print("Rendering template...")
    html = render_template(template_path, context)

    print("Inlining CSS (premailer)...")
    html = inline_css(html)

    out_path.write_text(html, encoding="utf-8")

    size_kb = out_path.stat().st_size // 1024
    print(f"\nNewsletter written to {out_path}  ({size_kb}KB)")
    print(f"  Subject: {newsletter.get('subject_line')}")
    print(f"  Edition: {edition_date}")
    print(f"  Charts embedded: {sum(1 for v in charts.values() if v)}/{len(charts)}")
    print(f"\nOpen in browser to QA:\n  {out_path.resolve()}")


if __name__ == "__main__":
    main()
