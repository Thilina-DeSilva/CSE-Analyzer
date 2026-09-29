# CSE Annual Report Analyzer

Turns one or more CSE-listed company annual report PDFs into a structured, source-traceable
financial dataset — deterministic extraction (regex/rule-based, no AI guessing at numbers),
industry-aware (bank vs. industrial), with every figure linked back to its exact page and line.

## Setup (one-time)
```
pip install -r requirements.txt
```

## Run
```
streamlit run app.py
```
Then open the local URL it prints (usually http://localhost:8501).

## How to use
1. In the sidebar, type the company name and upload 1+ annual report PDFs (any years, any order).
2. Click "ANALYZE REPORTS".
3. Browse tabs:
   - **5-Year Table**: core financials + ratios, with a "🔍 Look up a value's source" tool to see
     the exact source page/line for any number. Toggle "🎓 Explain these terms" for a plain-language
     glossary entry + further-reading link under each row.
   - **Charts**: revenue, profit, assets, EPS bars, plus ROE/ROA/margin trend lines.
   - **🚩 Red Flags**: automatic checks for common warning patterns — negative operating cash
     flow, net losses, declining margins, rising debt/equity, declining revenue, cash flow
     weaker than reported profit, inconsistent earnings. Never a "sell" verdict, just a prompt
     to look closer.
   - **🎯 Pre-Buy Checklist**: the consolidated "look at this before buying" view — Growth
     (CAGR), Profitability (ROE/ROA/margin), Financial Strength (Debt/Equity, cash flow),
     Shareholder Value (NAVPS, dividend history), Valuation (P/E, P/B, yield — needs a share
     price you enter), and the Red Flags summary, all in one place. Includes a deep-dive
     "how to actually use this before buying" guide (collapsed by default) and its own
     standalone downloadable PDF report.
   - **💰 Valuation & Sizing**: enter today's CSE share price to get P/E, P/B, Dividend Yield,
     plus a position-size calculator (your budget × your chosen allocation % ÷ price = shares).
     Pure arithmetic — never suggests an allocation, just does the math on numbers you choose.
   - **⚠️ Verification**: everything that was summed or derived rather than matched directly
     (e.g. Total Debt, Total Liabilities when no single line exists), flagged for manual
     spot-checking, plus a list of any metric not found at all.
   - **⬇️ Download**: get the full 5-year report as Markdown, CSV, or JSON (with sources).
     Separately, the Pre-Buy Checklist tab has its own PDF export.

## Files
- `app.py` — Streamlit UI (thin layer; all logic lives in the modules below)
- `find_statements.py` — locates statement pages inside large PDFs (cheap pypdf scan for
  candidates → pdfplumber to confirm the real heading and extract clean, ordered text)
- `industry.py` — detects bank vs. industrial company, so "Revenue" is never conflated with
  a bank's "Gross Income", and Debt is annotated correctly (a bank's deposits aren't debt)
- `metrics.py` — synonym-based line matching + number parsing engine; also restricts which
  statement type each metric is allowed to match on (a P&L concept can't accidentally match
  a stray line on the balance sheet or equity statement)
- `years.py` — detects which fiscal years the current/previous columns represent, and whether
  the document is a full-year or interim (Q1/H1/...) report
- `pipeline.py` — runs the full extraction for one PDF, including a fallback for companies
  that publish a single combined "Statement of Comprehensive Income" instead of a separate
  Income Statement
- `merge_reports.py` — merges/dedupes years across multiple PDFs of the same company
- `ratios.py` — ROE, ROA, margins, growth rates, CAGR
- `red_flags.py` — the automated warning-pattern checks
- `valuation.py` — P/E, P/B, Dividend Yield, NAVPS/DPS approximation, position sizing
- `pre_buy.py` — assembles the Pre-Buy Checklist tab's data
- `pre_buy_pdf.py` — renders the Pre-Buy Checklist as a standalone PDF (reportlab)
- `education.py` — the plain-language glossary, further-reading links, and beginner/pre-buy guides
- `report_builder.py` — Markdown/CSV/JSON report generation for the full 5-year report

## Accuracy notes — read before trusting a number
This is pattern-matching against real, inconsistently-formatted PDFs, not a guarantee.
Tested so far against a bank, and several industrial companies across different sectors
(petroleum, construction, plantations, gas) — each new company type has surfaced new
label wording or layout quirks, and more will. Expect this to continue.

- **Missing values show as `—`, never `0`.** A `0` would be indistinguishable from a company
  genuinely reporting a zero, and would silently corrupt every ratio built on it. `—` means
  "not found" — check the Verification tab or source PDF, don't assume it's zero.
- **Total Debt** is a best-effort sum of borrowing-related balance sheet lines — always
  flagged as `summed`, since "debt" is defined differently across industries and companies.
- **Total Liabilities**, when no single line exists, is `derived` (Total Equity & Liabilities
  minus Total Equity) — always flagged.
- **NAVPS, DPS, and shares outstanding are approximations**, back-calculated as
  Net Profit ÷ EPS (since shares outstanding isn't a line item we extract directly) — treat
  as indicative, not exact; preferred shares or special dividends can distort them.
- **Company name, business description, and risk-factor text are not extracted** — only the
  ~14 core financial line items + ratios built from them.
- **Scanned (image-only) PDF pages won't extract** — needs OCR, not yet added.
- **A metric coming up missing can mean one of two different things**: the company genuinely
  didn't report it that year (a real "—"), or this report phrases it in a way the patterns in
  `metrics.py` don't recognize yet. When in doubt, check the source PDF page directly.

## Improving accuracy over time
The single highest-value thing you can do: when a report produces unexpected gaps or a wrong
number, don't just work around it — find the actual line in the PDF and add/fix the matching
pattern in `metrics.py` (or the relevant module). Every fix is permanent and applies to every
future report of that type, not just the one you're looking at.
