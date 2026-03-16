"""
create_infographics.py
Generates chart images for the newsletter.

Two-part approach:
  1. Plotly + Kaleido  — data-accurate line/overlay charts (rate trend, Fed vs mortgage)
  2. Google Gemini     — styled branded infographic cards (rate snapshot, deal math)

Usage:
    python tools/create_infographics.py [--data .tmp/rate_data.json] [--output-dir .tmp/charts]
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# PeerPoint brand palette
NAVY_DEEP  = "#0D2240"
NAVY       = "#1B3A6B"
GREEN      = "#4BAE4F"
GREEN_LT   = "#7DC67F"
GREEN_PALE = "#E8F5E9"
WHITE      = "#FFFFFF"
OFF_WHITE  = "#F7F9FC"
G600       = "#5A6A7E"
G800       = "#2C3A4A"
RED        = "#C0392B"


# ── 1. PLOTLY CHARTS ──────────────────────────────────────────────────────────

def chart_rate_trend(rate_data: dict, out_path: Path):
    """52-week dual line: 30yr fixed + 15yr fixed."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("  ERROR: plotly not installed.", file=sys.stderr)
        return

    history = rate_data.get("rate_history", {})
    series_30 = history.get("30yr_fixed", [])
    series_15 = history.get("15yr_fixed", [])

    if not series_30:
        print("  WARNING: No 30yr history — skipping rate trend chart.", file=sys.stderr)
        return

    dates_30 = [e["date"] for e in series_30]
    vals_30   = [e["value"] for e in series_30]
    dates_15 = [e["date"] for e in series_15]
    vals_15   = [e["value"] for e in series_15]

    current_30 = vals_30[-1] if vals_30 else None
    wow_30 = rate_data.get("wow_changes", {}).get("30yr_fixed")
    wow_label = f"{'▲' if wow_30 and wow_30 > 0 else '▼'} {abs(wow_30):.2f}%" if wow_30 else ""

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates_30, y=vals_30,
        mode="lines",
        name="30yr Fixed",
        line=dict(color=GREEN, width=2.5),
        hovertemplate="%{x}: %{y:.2f}%<extra>30yr Fixed</extra>",
    ))

    if vals_15:
        fig.add_trace(go.Scatter(
            x=dates_15, y=vals_15,
            mode="lines",
            name="15yr Fixed",
            line=dict(color=GREEN_LT, width=2, dash="dot"),
            hovertemplate="%{x}: %{y:.2f}%<extra>15yr Fixed</extra>",
        ))

    if current_30:
        fig.add_annotation(
            x=dates_30[-1], y=current_30,
            text=f"<b>{current_30:.2f}%</b> {wow_label}",
            showarrow=True, arrowhead=2,
            arrowcolor=WHITE, font=dict(color=WHITE, size=12, family="DM Sans"),
            bgcolor=NAVY, bordercolor=GREEN, borderwidth=1,
            ax=40, ay=-30,
        )

    fig.update_layout(
        paper_bgcolor=NAVY_DEEP,
        plot_bgcolor=NAVY_DEEP,
        font=dict(family="DM Sans", color=WHITE),
        title=dict(
            text="Mortgage Rate Trend — 52 Weeks",
            font=dict(size=16, family="DM Sans", color=WHITE),
            x=0.04,
        ),
        legend=dict(
            orientation="h", x=0.04, y=1.08,
            font=dict(size=11, color=WHITE),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            showgrid=False, color=G600,
            tickfont=dict(size=10, family="Space Mono"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            color=G600,
            ticksuffix="%",
            tickfont=dict(size=10, family="Space Mono"),
        ),
        margin=dict(l=50, r=30, t=60, b=50),
        width=800, height=380,
    )

    _save_plotly(fig, out_path)


def chart_fed_vs_mortgage(rate_data: dict, out_path: Path):
    """2-year overlay: Fed Funds Rate vs 30yr fixed, with shaded spread."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    history = rate_data.get("rate_history", {})
    series_30  = history.get("30yr_fixed", [])
    series_fed = history.get("fed_funds", [])

    # Use last 104 weeks (~2 years) if available
    series_30  = series_30[-104:]
    series_fed = series_fed[-104:]

    if not series_30 or not series_fed:
        print("  WARNING: Insufficient data for Fed vs Mortgage chart.", file=sys.stderr)
        return

    dates_30  = [e["date"] for e in series_30]
    vals_30   = [e["value"] for e in series_30]
    dates_fed = [e["date"] for e in series_fed]
    vals_fed  = [e["value"] for e in series_fed]

    fig = go.Figure()

    # Shaded spread area (fill between — approximate with fill to zero then subtract)
    fig.add_trace(go.Scatter(
        x=dates_30, y=vals_30,
        mode="lines",
        name="30yr Fixed",
        line=dict(color=GREEN, width=2.5),
        fill="tonexty",
        fillcolor="rgba(75,174,79,0.12)",
    ))

    fig.add_trace(go.Scatter(
        x=dates_fed, y=vals_fed,
        mode="lines",
        name="Fed Funds Rate",
        line=dict(color="#D4AF37", width=2, dash="dash"),
    ))

    fig.update_layout(
        paper_bgcolor=NAVY_DEEP,
        plot_bgcolor=NAVY_DEEP,
        font=dict(family="DM Sans", color=WHITE),
        title=dict(
            text="Fed Funds Rate vs. 30yr Fixed Mortgage",
            font=dict(size=16, family="DM Sans", color=WHITE),
            x=0.04,
        ),
        legend=dict(
            orientation="h", x=0.04, y=1.08,
            font=dict(size=11, color=WHITE),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(showgrid=False, color=G600, tickfont=dict(size=10, family="Space Mono")),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            color=G600,
            ticksuffix="%",
            tickfont=dict(size=10, family="Space Mono"),
        ),
        margin=dict(l=50, r=30, t=60, b=50),
        width=800, height=380,
    )

    _save_plotly(fig, out_path)


def _save_plotly(fig, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.write_image(str(out_path), format="png", scale=2)
        print(f"  Saved: {out_path}")
    except Exception as e:
        print(f"  ERROR saving {out_path}: {e}", file=sys.stderr)
        print("  Hint: ensure kaleido is installed — pip install kaleido", file=sys.stderr)


# ── 2. MATPLOTLIB STAT CARDS ──────────────────────────────────────────────────
# Branded stat cards built with matplotlib — no external API required.
# Gemini image gen can replace these later once billing is enabled.

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def card_rate_snapshot(rate_data: dict, out_path: Path, client=None):
    """Branded rate snapshot card built with matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        print("  ERROR: matplotlib not installed.", file=sys.stderr)
        return

    rates = rate_data.get("current_rates", {})
    wow   = rate_data.get("wow_changes", {})
    as_of = rate_data.get("as_of_date", "")

    fields = [
        ("30-YR FIXED",    "30yr_fixed"),
        ("15-YR FIXED",    "15yr_fixed"),
        ("FED FUNDS",      "fed_funds"),
        ("PRIME RATE",     "prime_rate"),
        ("10-YR TREASURY", "10yr_treasury"),
    ]

    fig = plt.figure(figsize=(8, 5.5), facecolor=NAVY_DEEP)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=NAVY_DEEP)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    # Green accent bar top
    ax.add_patch(mpatches.Rectangle((0, 5.3), 8, 0.2, color=GREEN, zorder=3))

    # Header
    ax.text(0.3, 4.95, "PEERPOINT CAPITAL", color=GREEN, fontsize=8,
            fontfamily="monospace", fontweight="bold", va="center")
    ax.text(0.3, 4.65, "RATE SNAPSHOT", color=WHITE, fontsize=14,
            fontfamily="monospace", fontweight="bold", va="center")
    ax.text(7.7, 4.8, as_of, color=G600, fontsize=8,
            fontfamily="monospace", va="center", ha="right")

    # Divider
    ax.axhline(y=4.45, xmin=0.04, xmax=0.96, color=GREEN, linewidth=0.8, alpha=0.5)

    # Rate rows
    row_h = 0.72
    for i, (label, key) in enumerate(fields):
        y = 3.85 - i * row_h
        val = rates.get(key)
        chg = wow.get(key)

        val_str = f"{val:.2f}%" if val else "N/A"

        # Change color & arrow
        if chg is not None and chg < -0.001:
            chg_color = GREEN
            chg_str   = f"▼ {abs(chg):.2f}%"
        elif chg is not None and chg > 0.001:
            chg_color = RED
            chg_str   = f"▲ {abs(chg):.2f}%"
        else:
            chg_color = G600
            chg_str   = "—"

        # Label
        ax.text(0.35, y, label, color=G600, fontsize=8,
                fontfamily="monospace", va="center")
        # Value
        ax.text(5.2, y, val_str, color=WHITE, fontsize=18,
                fontfamily="monospace", fontweight="bold", va="center", ha="right")
        # Change
        ax.text(5.5, y, chg_str, color=chg_color, fontsize=9,
                fontfamily="monospace", va="center")

        # Row separator
        if i < len(fields) - 1:
            ax.axhline(y=y - row_h / 2, xmin=0.04, xmax=0.96,
                       color=NAVY, linewidth=0.5, alpha=0.8)

    # Footer
    ax.text(4.0, 0.18, "PeerPoint Capital  ·  The Market Wire",
            color=G600, fontsize=7, fontfamily="monospace",
            va="center", ha="center", alpha=0.6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight",
                facecolor=NAVY_DEEP, edgecolor="none")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def card_deal_math(rate_data: dict, out_path: Path, client=None):
    """Deal math card — P&I at various rates — built with matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("  ERROR: matplotlib not installed.", file=sys.stderr)
        return

    current_30 = rate_data.get("current_rates", {}).get("30yr_fixed")
    loan = 350_000
    rate_steps = [5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    payments = []
    for r in rate_steps:
        mr = r / 100 / 12
        pmt = loan * (mr * (1 + mr)**360) / ((1 + mr)**360 - 1)
        payments.append((r, round(pmt)))

    fig = plt.figure(figsize=(8, 5.5), facecolor=NAVY_DEEP)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=NAVY_DEEP)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    # Green accent bar
    ax.add_patch(mpatches.Rectangle((0, 5.3), 8, 0.2, color=GREEN, zorder=3))

    # Header
    ax.text(0.3, 4.95, "PEERPOINT CAPITAL", color=GREEN, fontsize=8,
            fontfamily="monospace", fontweight="bold", va="center")
    ax.text(0.3, 4.65, "DEAL MATH", color=WHITE, fontsize=14,
            fontfamily="monospace", fontweight="bold", va="center")
    subtitle = f"$350,000 LOAN  ·  30-YEAR TERM"
    if current_30:
        subtitle += f"  ·  CURRENT: {current_30:.2f}%"
    ax.text(0.3, 4.35, subtitle, color=G600, fontsize=8,
            fontfamily="monospace", va="center")

    ax.axhline(y=4.15, xmin=0.04, xmax=0.96, color=GREEN, linewidth=0.8, alpha=0.5)

    # Payment rows
    row_h = 0.58
    for i, (r, pmt) in enumerate(payments):
        y = 3.65 - i * row_h
        is_current = current_30 and abs(r - current_30) < 0.26

        row_color = GREEN_PALE if is_current else "none"
        txt_color = NAVY if is_current else WHITE
        lbl_color = NAVY if is_current else G600

        if is_current:
            ax.add_patch(mpatches.FancyBboxPatch(
                (0.25, y - 0.22), 7.5, 0.44,
                boxstyle="round,pad=0.05",
                facecolor=GREEN, alpha=0.15, edgecolor=GREEN, linewidth=0.8,
            ))

        ax.text(0.5, y, f"{r:.1f}%", color=GREEN if is_current else G600,
                fontsize=10, fontfamily="monospace", va="center", fontweight="bold" if is_current else "normal")
        ax.text(3.8, y, f"${pmt:,} / mo", color=WHITE, fontsize=16,
                fontfamily="monospace", fontweight="bold", va="center", ha="center")

        if not is_current and i < len(payments) - 1:
            ax.axhline(y=y - row_h / 2, xmin=0.04, xmax=0.96,
                       color=NAVY, linewidth=0.5, alpha=0.6)

    # Footer
    ax.text(4.0, 0.18, "Principal & interest only. Excludes taxes, insurance, HOA.",
            color=G600, fontsize=7, fontfamily="monospace",
            va="center", ha="center", alpha=0.6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight",
                facecolor=NAVY_DEEP, edgecolor="none")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate newsletter infographics.")
    parser.add_argument("--data", default=".tmp/rate_data.json")
    parser.add_argument("--output-dir", default=".tmp/charts")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: Rate data not found at {data_path}. Run research_rates.py first.", file=sys.stderr)
        sys.exit(1)

    rate_data = json.loads(data_path.read_text())
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Generating Plotly data charts...")
    chart_rate_trend(rate_data, out_dir / "rate_trend_12mo.png")
    chart_fed_vs_mortgage(rate_data, out_dir / "fed_vs_mortgage.png")

    print("\nGenerating branded stat cards (matplotlib)...")
    card_rate_snapshot(rate_data, out_dir / "rate_snapshot_card.png")
    card_deal_math(rate_data, out_dir / "deal_math_card.png")

    # Report what was produced
    charts = list(out_dir.glob("*.png"))
    print(f"\nProduced {len(charts)} chart(s) in {out_dir}/:")
    for c in sorted(charts):
        print(f"  {c.name}  ({c.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
