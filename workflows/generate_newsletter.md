# Workflow: Generate Weekly Newsletter

## Objective
Produce a complete, publication-ready HTML newsletter for PeerPoint Capital covering mortgage rates, real estate finance, private/hard money lending, and macro news — tailored for real estate investors.

## Trigger
Run manually each week. Recommended: Monday morning so the issue covers last week's data (FRED updates weekly mortgage rates on Thursdays).

## Required Inputs
- Week to cover (defaults to current date)
- Issue number (for the issue footer — increment each week)
- No other inputs required; all data is fetched live

## Required API Keys (in .env)
| Key | Where to get it | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | ~$0.20–0.50/run |
| `PERPLEXITY_API_KEY` | perplexity.ai/settings/api | ~$0.05–0.15/run |
| `FRED_API_KEY` | fred.stlouisfed.org/docs/api/api_key.html | Free |
| `GEMINI_API_KEY` | aistudio.google.com/app/apikey | Free tier available |

---

## Steps

### Step 1 — Fetch Rate Data
```
python tools/research_rates.py --weeks-back 52
```
**Expected output:** `.tmp/rate_data.json`

**Verify:**
- `as_of_date` is within the last 7 days
- `current_rates.30yr_fixed` and `current_rates.15yr_fixed` are populated
- `rate_history.30yr_fixed` has ≥50 data points (needed for 52-week chart)

**If FRED fails:** Check `FRED_API_KEY` in `.env`. The key is free and instant at fred.stlouisfed.org. Rate data will fall back to yfinance for current yield but historical chart data will be missing.

**Note:** FRED publishes weekly mortgage rate data every Thursday at 10am ET. Running on Monday uses last Thursday's data, which is correct — that is the most recent official figure.

---

### Step 2 — Generate Charts and Infographics
```
python tools/create_infographics.py
```
**Expected output:** 4 PNG files in `.tmp/charts/`:
- `rate_trend_12mo.png` — Plotly line chart
- `fed_vs_mortgage.png` — Plotly overlay chart
- `rate_snapshot_card.png` — Gemini-generated branded card
- `deal_math_card.png` — Gemini-generated investor card

**Verify:** Open each PNG file and confirm:
- Plotly charts show actual rate data on navy background with green lines
- Gemini cards are legible and contain the correct rate numbers
- No broken/blank images

**If Gemini image gen fails:** The newsletter assembler will skip missing charts gracefully. The plotly charts are the priority — Gemini cards are a bonus. Check `GEMINI_API_KEY` and that `google-genai` is installed.

**If kaleido (Plotly export) fails:** Run `pip install kaleido`. On some systems this requires a Chromium install. As a fallback, the Plotly charts can be exported via `fig.write_html()` and screenshots taken manually.

---

### Step 3 — Research This Week's News
```
python tools/research_perplexity.py
```
**Expected output:** `.tmp/research_results.json`

**Verify:**
- `success_count` is ≥ 4
- Preview the summaries printed to console — they should contain specific rate numbers and named sources
- If a summary looks thin or generic, the query may have returned poor results; re-run once

**Minimum viable:** 4 of 6 queries must succeed for the newsletter to proceed. If fewer than 4, check `PERPLEXITY_API_KEY` and internet connectivity.

---

### Step 4 — Generate Newsletter Content (uses paid Claude API)
```
python tools/generate_newsletter.py --issue-number 1
```
Replace `1` with the correct issue number.

**Expected output:** `.tmp/newsletter_content.json`

**Cost:** ~$0.20–0.40 in Anthropic credits per run. Do not re-run unnecessarily — if the output looks mostly right, edit the JSON directly rather than calling Claude again.

**Verify the JSON:**
- `subject_line` is specific and punchy (should include a rate number or news hook)
- `sections.top_stories` has 3–4 items
- `sections.rate_snapshot.body_html` references actual numbers
- `sections.deal_math.body_html` contains a concrete deal scenario

**If Claude returns malformed JSON:** Check `.tmp/claude_raw_output.txt` for the raw response. Usually the issue is an unclosed code fence or trailing commentary. Fix the JSON manually and save to `newsletter_content.json` before proceeding.

**Writing quality check:**
- No "certainly", "great question", "it's worth noting"
- No overuse of bullets where prose belongs
- Rate numbers are specific (e.g., "7.18%", not "around 7%")
- Named sources appear (e.g., "per Mortgage News Daily", "according to FRED")

---

### Step 5 — Assemble HTML
```
python tools/assemble_html.py --issue-number 1
```
**Expected output:** `.tmp/newsletter_YYYY-MM-DD.html`

**Verify:** Open the HTML file in Chrome and check:
- [ ] PeerPoint logo appears in header and footer
- [ ] Rate table populates correctly with green/red directional arrows
- [ ] All 4 chart images render (not broken)
- [ ] Fonts load: DM Serif Display for headlines, Space Mono for labels/numbers
- [ ] Colors match PeerPoint brand: navy header, green accents
- [ ] Hard Money Pulse section has the green-pale background callout box
- [ ] Deal Math section has the dark navy background
- [ ] Footer shows "Your Capital Partner" tagline and issue number
- [ ] No "Issue #None" or placeholder text visible

**Mobile check:** Resize Chrome to ~375px wide and confirm the layout stacks correctly.

---

### Step 6 — Review and QA

Before publishing, verify:
1. **Rate accuracy** — Compare the 30yr fixed rate shown in the newsletter against mortgagenewsdaily.com. Should be within ~5 bps of the current figure.
2. **Link check** — Click 3–5 article links to confirm they resolve.
3. **Subject line** — Is it specific? Does it have a news hook a real investor would click on?
4. **Tone check** — Read the Rate Snapshot and Hard Money Pulse sections. Does it sound like a sharp advisor, or does it sound like a language model? Rewrite any section that hedges without cause or avoids taking a clear position.

---

### Step 7 — Publish to Substack
```
python tools/publish_substack.py
```
Creates a **draft** in Substack for review. Visit https://peerpointcapital.substack.com/publish/posts to review and send manually.

To publish immediately:
```
python tools/publish_substack.py --send
```

To schedule for a specific time (e.g. Monday 8am):
```
python tools/publish_substack.py --schedule "2026-03-17 08:00"
```

**Weekly automation:** Double-click `run_weekly.bat` to run the full pipeline, or schedule it via Windows Task Scheduler (see below).

#### Windows Task Scheduler Setup
1. Open Task Scheduler (`taskschd.msc`)
2. Action → Create Basic Task
3. Name: "PeerPoint Market Wire"
4. Trigger: Weekly → Monday → 7:00 AM
5. Action: Start a program → `C:\Users\aprud\OneDrive\Desktop\Newsletter\run_weekly.bat`
6. Finish

---

## Edge Cases

**Rate data is stale (>10 days):** `assemble_html.py` will print a warning. Re-run `research_rates.py` or manually update the key numbers in `newsletter_content.json` before assembly.

**A Perplexity query returns thin results:** Re-run `research_perplexity.py` once. If the topic area genuinely had no news, the writing prompt will tell Claude to acknowledge the quiet week rather than fabricate activity.

**Claude output is too AI-sounding:** Edit `newsletter_content.json` directly. The JSON is human-readable. Fix the offending sections, then re-run `assemble_html.py` — assembly is free and fast.

**Charts are blank or missing:** The newsletter will assemble without them (graceful degradation). Address the chart issue and re-run `create_infographics.py`, then `assemble_html.py`.

---

## Output Files
| File | Description |
|---|---|
| `.tmp/rate_data.json` | Current and historical rate data from FRED + yfinance |
| `.tmp/research_results.json` | 6 Perplexity research summaries with citations |
| `.tmp/charts/*.png` | 4 infographic images (2 Plotly + 2 Gemini) |
| `.tmp/newsletter_content.json` | Structured newsletter content from Claude |
| `.tmp/newsletter_YYYY-MM-DD.html` | Final self-contained HTML newsletter |

All `.tmp/` files are regenerable. They are gitignored and treated as disposable.

## Estimated Run Time and Cost
| Step | Time | Cost |
|---|---|---|
| research_rates.py | ~10–20s | Free |
| create_infographics.py | ~30–60s | Free (Gemini free tier) |
| research_perplexity.py | ~30–60s | ~$0.05–0.15 |
| generate_newsletter.py | ~20–40s | ~$0.20–0.40 |
| assemble_html.py | ~5s | Free |
| **Total** | **~2 min** | **~$0.25–0.55** |
