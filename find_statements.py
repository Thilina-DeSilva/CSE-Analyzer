"""
V1: Find the financial statement pages inside a huge annual report PDF,
and return CLEAN, correctly-ordered text for just those pages.

Design (two stages), based on what we learned testing on real reports:

  STAGE 1 - cheap full-document scan (pypdf)
    pypdf is fast and uses flat memory (~90MB even on 558 pages), but its
    text often comes out of reading order on complex multi-column layouts
    (headers can land in the wrong place in the string). We only use it
    here to find CANDIDATE pages, by:
      a) counting how many "money-shaped" numbers (e.g. 45,200,123) are
         on the page - real statement pages are dense with these, a
         mention in a table of contents or audit report is not.
      b) checking for statement-specific keywords anywhere on the page.

  STAGE 2 - confirm with pdfplumber, but ONLY on the small shortlist
    pdfplumber preserves reading order properly, which is what we need to
    confirm the heading is really at the TOP of the page (a true
    statement page) rather than mentioned mid-paragraph. Critically, we
    only open pdfplumber on ~10-30 candidate pages, not the whole
    document - this avoids the memory blow-up we hit on the first try
    (pdfplumber leaked to 2.8GB and got OOM-killed iterating all 558
    pages of a bank report).
"""

import re
import pypdf
import pdfplumber

MONEY_PATTERN = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")

# keyword groups used to guess a page's statement type in stage 1.
# matching is "any of these substrings appear on the page" - loose on
# purpose, stage 2 does the precise check.
KEYWORDS = {
    "income_statement": ["income statement", "statement of profit or loss", "statement of profit and loss"],
    "balance_sheet": ["statement of financial position", "balance sheet"],
    "cash_flow": ["statement of cash flows", "cash flow statement"],
    "comprehensive_income": ["statement of comprehensive income"],
}

# pages containing these are deprioritised - they're real statements but
# NOT the primary group LKR ones we want (US$ annexes, decade summaries,
# interim/quarterly summaries duplicate the same heading text).
DEPRIORITISE = ["annex", "us dollar", "decade at a glance", "summarised", "summarized", "interim financial"]

MIN_MONEY_NUMBERS = 15  # a real statement page is dense with these


def _stage1_candidates(pdf_path: str) -> dict:
    """pypdf pass: return candidate page indices per statement type,
    each tagged with a score and whether it looks deprioritised."""
    reader = pypdf.PdfReader(pdf_path)
    candidates = {key: [] for key in KEYWORDS}

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        low = text.lower()
        money_count = len(MONEY_PATTERN.findall(text))
        if money_count < MIN_MONEY_NUMBERS:
            continue

        deprioritised = any(flag in low for flag in DEPRIORITISE)

        for key, kws in KEYWORDS.items():
            if any(kw in low for kw in kws):
                candidates[key].append({
                    "page": i,
                    "money_count": money_count,
                    "deprioritised": deprioritised,
                })
    return candidates


def _stage2_confirm(pdf_path: str, candidates: dict) -> dict:
    """pdfplumber pass: open only the candidate pages, check the anchor
    phrase is near the top (a real heading), return clean text for
    confirmed pages."""
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
                head = text[:120].lower()
                is_heading = any(kw in head for kw in KEYWORDS[key])
                if is_heading:
                    confirmed[key].append({**c, "text": text})

    return confirmed


def find_statement_pages(pdf_path: str, verbose: bool = False) -> dict:
    """
    Main entry point. Returns, for each statement type, a ranked list of
    confirmed pages (best first: not deprioritised, then by money density),
    each with its clean extracted text ready for the next parsing step.
    """
    candidates = _stage1_candidates(pdf_path)
    if verbose:
        for key, lst in candidates.items():
            print(f"[stage1] {key}: {len(lst)} candidate page(s)")

    confirmed = _stage2_confirm(pdf_path, candidates)

    for key, lst in confirmed.items():
        lst.sort(key=lambda c: (c["deprioritised"], -c["money_count"]))
        if verbose:
            print(f"[stage2] {key}: {len(lst)} confirmed -> "
                  f"{[c['page'] for c in lst]}")

    return confirmed


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    result = find_statement_pages(path, verbose=True)
    print()
    for key, lst in result.items():
        best = lst[0]["page"] if lst else None
        print(f"{key}: best page = {best}")
