"""
Find financial-statement pages inside annual / interim report PDFs.

Two stages:
  1) Fast pypdf scan for money-dense pages with statement keywords
  2) pdfplumber confirmation that the keyword is a page heading

Ranking prefers the PRIMARY face statements (Group LKR, full scale)
over decade summaries, segment notes, US$ annexes, and highlights.
"""

from __future__ import annotations

import re
import pypdf
import pdfplumber

MONEY_PATTERN = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
# Numbers that look like full LKR amounts (at least 1,000,000)
LARGE_MONEY = re.compile(r"\b\d{1,3}(?:,\d{3}){2,}\b")

KEYWORDS = {
    "income_statement": [
        "income statement",
        "statement of profit or loss",
        "statement of profit and loss",
        "statement of profit or loss and other comprehensive income",
        "consolidated statement of profit or loss",
    ],
    "balance_sheet": [
        "statement of financial position",
        "balance sheet",
        "consolidated statement of financial position",
        "statement of financial position (continued)",
    ],
    "cash_flow": [
        "statement of cash flows",
        "cash flow statement",
        "statement of cash flow",
        "consolidated statement of cash flows",
    ],
    "comprehensive_income": [
        "statement of comprehensive income",
        "other comprehensive income",
    ],
}

# Hard deprioritise — these are almost never the primary face statement
DEPRIORITISE = [
    "annex",
    "us dollar",
    "u.s. dollar",
    "decade at a glance",
    "ten year",
    "10 year",
    "ten-year",
    "5 year summary",
    "five year summary",
    "five-year summary",
    "summarised",
    "summarized",
    "interim financial",
    "financial highlights",
    "at a glance",
    "highlights of the year",
    "value added statement",
    "statement of value added",
    "quarterly analysis",
    "segment information",
    "notes to the financial statements",
]

# Soft signals that a page is the REAL face statement
PRIMARY_SIGNALS = [
    r"year ended",
    r"for the year ended",
    r"as at \d",
    r"as at 3[01]",
    r"group\s+company",
    r"company\s+group",
    r"rs\.?\s*['\u2019`]?000",
    r"all amounts in",
]

MIN_MONEY_NUMBERS = 8


def _stage1_candidates(pdf_path: str) -> dict:
    reader = pypdf.PdfReader(pdf_path)
    n_pages = len(reader.pages)
    candidates = {key: [] for key in KEYWORDS}

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        low = " ".join(text.lower().split())  # collapse newlines for keyword match
        money_count = len(MONEY_PATTERN.findall(text))
        if money_count < MIN_MONEY_NUMBERS:
            continue

        large_count = len(LARGE_MONEY.findall(text))
        deprioritised = any(flag in low for flag in DEPRIORITISE)

        # Prefer middle-of-report zone (after covers/TOC, before deep notes)
        # Typical primary statements sit ~30–70% through the PDF.
        position = i / max(n_pages, 1)
        position_penalty = 0
        if position < 0.05:
            position_penalty = 2  # covers / early TOC
        elif position > 0.85:
            position_penalty = 1  # deep notes / annexes

        primary_hits = sum(1 for p in PRIMARY_SIGNALS if re.search(p, low))

        for key, kws in KEYWORDS.items():
            if any(kw in low for kw in kws):
                candidates[key].append({
                    "page": i,
                    "money_count": money_count,
                    "large_count": large_count,
                    "deprioritised": deprioritised,
                    "position_penalty": position_penalty,
                    "primary_hits": primary_hits,
                })
    return candidates


def _stage2_confirm(pdf_path: str, candidates: dict) -> dict:
    all_pages_needed = sorted({c["page"] for lst in candidates.values() for c in lst})
    if not all_pages_needed:
        return {key: [] for key in KEYWORDS}

    confirmed = {key: [] for key in KEYWORDS}

    with pdfplumber.open(pdf_path) as pdf:
        page_text_cache = {}
        for p in all_pages_needed:
            text = pdf.pages[p].extract_text() or ""
            page_text_cache[p] = text
            pdf.pages[p].flush_cache()

        for key, lst in candidates.items():
            for c in lst:
                text = page_text_cache[c["page"]]
                # Collapse newlines so "Statement of\nFinancial Position" matches
                head = " ".join(text[:900].lower().split())
                is_heading = any(kw in head for kw in KEYWORDS[key])
                if not is_heading:
                    continue

                # Extra reject: note pages that only mention the statement name
                # deep in text but have "note" dense headers
                note_density = head.count("note ")
                if note_density >= 4 and c.get("primary_hits", 0) < 2:
                    continue

                # Balance sheet: require total assets or equity somewhere
                has_assets = False
                if key == "balance_sheet":
                    low_full = text.lower()
                    has_assets = "total assets" in low_full
                    if not has_assets and "total equity" not in low_full:
                        continue
                c = {**c, "has_total_assets": has_assets}

                # Income: require revenue/turnover or profit line
                if key == "income_statement":
                    low_full = text.lower()
                    if not any(x in low_full for x in (
                        "revenue", "turnover", "profit for the", "gross profit",
                        "net interest income", "gross income",
                    )):
                        continue

                confirmed[key].append({**c, "text": text})

    return confirmed


def find_statement_pages(pdf_path: str, verbose: bool = False) -> dict:
    """
    Ranked confirmed pages per statement type.
    Sort key (best first):
      1. not deprioritised
      2. more primary header signals
      3. lower position penalty
      4. more large (full-scale) money tokens
      5. more money tokens overall
      6. earlier page as mild tie-break
    """
    candidates = _stage1_candidates(pdf_path)
    if verbose:
        for key, lst in candidates.items():
            print(f"[stage1] {key}: {len(lst)} candidate page(s)")

    confirmed = _stage2_confirm(pdf_path, candidates)

    for key, lst in confirmed.items():
        lst.sort(key=lambda c: (
            c["deprioritised"],
            -c.get("primary_hits", 0),
            c.get("position_penalty", 0),
            -int(c.get("has_total_assets", False)),  # BS pages with Total Assets first
            -c.get("large_count", 0),
            -c["money_count"],
            c["page"],
        ))
        if verbose:
            print(f"[stage2] {key}: {len(lst)} confirmed -> "
                  f"{[c['page'] for c in lst[:8]]}")

    return confirmed


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    result = find_statement_pages(path, verbose=True)
    print()
    for key, lst in result.items():
        best = lst[0]["page"] if lst else None
        print(f"{key}: best page = {best}")
