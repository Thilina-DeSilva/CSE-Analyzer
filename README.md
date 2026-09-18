# CSE Annual Report Analyzer

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
1. In the sidebar, type the company name and upload 1+ annual report PDFs (any years).
2. Click "ANALYZE REPORTS".
3. Browse tabs:
   - **5-Year Table**: core financials + ratios, with a lookup tool to see the exact
     source page/line for any number.
   - **Charts**: revenue, profit, assets, EPS, and ROE/ROA/margin trends.
   - **Verification**: everything that was summed or derived rather than matched
     directly (e.g. Total Debt), flagged for manual spot-checking.
   - **Download**: get the report as Markdown, CSV, or full JSON (with sources).

## Files
- `app.py` — Streamlit UI (thin layer, no extraction logic itself)
- `find_statements.py` — locates statement pages inside large PDFs (pypdf scan + pdfplumber confirm)
- `metrics.py` — synonym-based line matching + number parsing engine
- `years.py` — detects which fiscal years the current/previous columns represent
- `pipeline.py` — runs the full extraction for one PDF
- `merge_reports.py` — merges/dedupes years across multiple PDFs of the same company
- `ratios.py` — ROE, ROA, margins, growth rates
- `report_builder.py` — Markdown/CSV/JSON report generation

## Known limitations (tested against 2 companies so far - a bank and an
industrial company). Test against a 3rd, differently-structured company
next and expect to need new synonyms in metrics.py's METRIC_PATTERNS.
- Total Debt is a best-effort sum of borrowing-related balance sheet lines —
  always flagged, "debt" is defined differently across industries.
- Company name/business description/risk factors are not extracted yet
  (only the 13 core financial metrics + ratios).
- Scanned (image-only) PDF pages won't extract — needs OCR, not yet added.
