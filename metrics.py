"""
V2/V3: Extract core financial metrics from statement page text.

Design principles (deliberately simple/deterministic, no LLM):

1. Every metric has a list of REGEX synonyms, because different
   companies word the same line differently:
     bank:  "Net cash from/(used in) operating activities"
     gas:   "Net Cash Flows Generated from/(Used in) Operating Activities"
   We match with a loose regex (".*" between key phrases) instead of
   exact strings, and check the start of the line (after stripping
   "Less:" / "Add:" prefixes) so we don't grab the wrong line.

2. Numbers are pulled using two different token patterns, based on the
   real reports we tested:
     - MONEY numbers always have thousands-commas (Rs.'000 or full Rs,
       either way any real Revenue/Assets/Profit figure is >= 4 digits).
       This is what lets us skip over "Note" and "Page No." reference
       columns (small plain integers, no comma) and "Change %" columns
       (decimals with NO comma, e.g. "17.04") without needing to know
       the exact table layout of each company.
     - EPS/DPS numbers are small decimals WITHOUT commas (e.g. 38.44),
       so they get their own extraction pass.

3. Every extracted value carries its page number and the exact source
   line, so a human can verify it against the PDF later. Nothing is
   silently trusted.

4. When a metric can't be found directly (e.g. many companies don't
   print a single "Total Liabilities" line, only subtotals), we fall
   back to a derivation (Total Liabilities = Total Equity & Liabilities
   − Total Equity) and mark it clearly as derived, not extracted.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


MONEY_TOKEN = re.compile(r"\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?")
# Exactly 2 decimal digits, on purpose: real per-share/EPS figures are
# always printed to 2 decimals (e.g. 38.44). A 1-decimal-digit number
# like "24.1" appearing on the same line is a sub-note reference
# (Note 24, point 1), not a value - excluding it avoids the extractor
# picking up "24.1" instead of the real "38.44" that follows it.
DECIMAL_TOKEN = re.compile(r"\(?-?\d+\.\d{2}\)?")
NIL_TOKEN = re.compile(r"^[–—-]$")

STRIP_PREFIXES = re.compile(r"^(less|add)\s*:\s*", re.IGNORECASE)


@dataclass
class Extraction:
    metric: str
    current: Optional[float] = None
    previous: Optional[float] = None
    unit: str = "unknown"
    page: Optional[int] = None
    source_line: str = ""
    method: str = "not_found"  # direct | derived | summed | not_found
    notes: str = ""


# metric_key -> list of regex patterns tested against the (lowercased,
# prefix-stripped) start of a line. First match wins, patterns listed
# in priority order (more specific first) to avoid mismatches e.g.
# "gross profit" should not swallow "operating profit" lines.
METRIC_PATTERNS = {
    "revenue": [
        r"^revenue\b",
        r"^turnover\b",
        r"^revenue from contracts with customers\b",
    ],
    # Bank-specific top line — kept SEPARATE from "revenue" on purpose.
    # "Gross income" for a bank includes interest income, fee income
    # etc. and is not comparable to an industrial company's Revenue/
    # Turnover line - conflating them would misstate margins.
    "gross_income": [
        r"^gross income\b",
    ],
    "net_interest_income": [
        r"^net interest income\b",
    ],
    "gross_profit": [
        r"^gross profit",
    ],
    "operating_profit": [
        r"^operating profit",
        r"^results from operating activities",
        r"^profit from operations",
    ],
    "profit_before_tax": [
        r"^profit.*before (income )?tax",
        r"^\(?profit/\(loss\)\)? before tax",
    ],
    "net_profit": [
        r"^profit for the year",
        r"^profit/\(loss\) for the year",
        r"^net profit for the year",
    ],
    "total_assets": [
        r"^total assets\b",
    ],
    "total_liabilities": [
        r"^total liabilities\b(?!.{0,3}and equity)",
    ],
    "total_equity_and_liabilities": [
        r"^total liabilities and equity",
        r"^total equity and liabilities",
    ],
    "total_equity": [
        r"^total equity\b(?! attributable)",
    ],
    "cash_and_equivalents": [
        r"^cash and cash equivalents\b",
    ],
    "operating_cash_flow": [
        r"^net cash.*operating activities",
    ],
    "dividend_paid": [
        r"^dividend paid to shareholders",
        r"^dividends? paid\b",
    ],
}

# EPS/DPS use the decimal token pass instead.
EPS_PATTERNS = [
    r"^basic earnings per (ordinary )?share",
    r"^basic/diluted earnings/\(loss\) per share",
    r"^earnings per share",
]

# Lines to SUM (not just take one) for a best-effort Debt figure.
# Flagged as needing manual verification - "debt" is defined
# inconsistently across industries (esp. banks vs non-financial firms).
DEBT_PATTERNS = [
    r"interest bearing loans and borrowings",
    r"interest-bearing borrowings",
    r"borrowings",  # unanchored - safe now that this only runs on balance_sheet text
    r"debt securities issued",
    r"subordinated liabilities",
]


def _clean_line_start(line: str) -> str:
    return STRIP_PREFIXES.sub("", line.strip())


# A token counts as "numeric-ish" (part of the trailing values region of
# the line) if it's a money number, a plain decimal/integer (percent
# change, note ref, page ref), or a lone dash used for a nil/blank cell.
_NUMERIC_ISH = re.compile(r"^\(?-?[\d,]+\.?\d*\)?$")


def _trailing_numeric_tokens(line: str) -> list:
    """
    Walk the line's tokens from the RIGHT and collect the trailing run
    of numeric-ish tokens, stopping at the first real word. This is the
    key fix for a bug we hit: labels sometimes contain a lone en-dash
    as a typographic separator (e.g. "...amortised cost – other
    borrowings"), which looks identical to a "–" used for a nil/blank
    value cell. Scanning outside-in from the right means we stop at
    "borrowings" (a real word) before ever reaching that label dash, so
    it never gets mistaken for a value. A dash IS accepted once we're
    already inside the trailing numeric run (i.e. a genuine blank cell
    between real numbers).
    """
    tokens = line.split()
    trailing = []
    for tok in reversed(tokens):
        if _NUMERIC_ISH.match(tok) or NIL_TOKEN.match(tok):
            trailing.append(tok)
        else:
            break
    trailing.reverse()
    return trailing


def _parse_money_tokens(line: str) -> list:
    """Parse comma-formatted numbers from the trailing values region of
    a line, respecting () as negative and a lone – as 0 (nil cell)."""
    out = []
    for tok in _trailing_numeric_tokens(line):
        if NIL_TOKEN.match(tok):
            out.append(0.0)
            continue
        m = MONEY_TOKEN.fullmatch(tok)
        if m:
            raw = tok.replace(",", "")
            neg = raw.startswith("(") and raw.endswith(")")
            raw = raw.strip("()")
            try:
                val = float(raw)
            except ValueError:
                continue
            out.append(-val if neg else val)
    return out


def _parse_decimal_tokens(line: str) -> list:
    """Parse plain (non-comma) 2-decimal values, e.g. EPS, from the
    trailing values region of a line."""
    out = []
    for tok in _trailing_numeric_tokens(line):
        if MONEY_TOKEN.fullmatch(tok):
            continue  # has a comma, not a plain decimal
        m = DECIMAL_TOKEN.fullmatch(tok)
        if m:
            raw = tok
            neg = raw.startswith("(") and raw.endswith(")")
            raw = raw.strip("()")
            try:
                val = float(raw)
            except ValueError:
                continue
            out.append(-val if neg else val)
    return out


def detect_unit(page_text: str) -> str:
    low = page_text.lower()
    if "rs. \u2019000" in low or "rs.\u2019000" in low or "rs. '000" in low or "rs.’000" in page_text.lower():
        return "LKR_thousand"
    if re.search(r"rs\.?\s*['\u2019]000", page_text, re.IGNORECASE):
        return "LKR_thousand"
    if re.search(r"rs\.?\s*mn\b|rs\.?\s*million", low):
        return "LKR_million"
    if "rs." in low:
        return "LKR"
    return "unknown"


def extract_metrics_from_page(page_text: str, page_number: int, stmt_type: str = "",
                                industry: str = "industrial") -> dict:
    """Run the direct-match extraction for every metric against one
    statement page's text. Returns metric_key -> Extraction.

    stmt_type restricts which page types certain metrics are allowed to
    match on. This matters for Debt in particular: the substring
    patterns we use for it (e.g. "subordinated liabilities") also
    appear on the Cash Flow statement as MOVEMENTS during the year
    ("Interest expense on subordinated liabilities", "Proceeds from
    issue of subordinated liabilities") which are NOT balance figures
    and would corrupt the sum if included.
    """
    unit = detect_unit(page_text)
    lines = page_text.split("\n")
    # Fallback candidates only: some line items wrap across two physical
    # text lines in the PDF (label ends on one line, numbers start the
    # next - we hit this for real with LAUGFS Gas's operating cash flow
    # line). Joining every consecutive pair lets us catch those too, but
    # we only ever consult this AFTER single-line matching has failed
    # for a given metric, so it can't override a clean single-line match
    # (which is what would happen if we blindly merged section headers
    # into the row below them).
    joined_lines = [f"{lines[i]} {lines[i+1]}" for i in range(len(lines) - 1)]

    def _search(metric_patterns, line_pool, parser):
        for raw_line in line_pool:
            line = _clean_line_start(raw_line)
            low = line.lower()
            for pat in metric_patterns:
                if re.search(pat, low):
                    values = parser(line)
                    if values:
                        return raw_line, values
        return None, None

    results = {}
    for metric, patterns in METRIC_PATTERNS.items():
        raw_line, values = _search(patterns, lines, _parse_money_tokens)
        if values is None:
            raw_line, values = _search(patterns, joined_lines, _parse_money_tokens)
        if values:
            results[metric] = Extraction(
                metric=metric,
                current=values[0],
                previous=values[1] if len(values) > 1 else None,
                unit=unit,
                page=page_number,
                source_line=raw_line.strip(),
                method="direct",
            )

    # EPS (decimal pass)
    for raw_line in lines:
        line = _clean_line_start(raw_line)
        low = line.lower()
        for pat in EPS_PATTERNS:
            if re.search(pat, low):
                values = _parse_decimal_tokens(line)
                if values:
                    results["eps"] = Extraction(
                        metric="eps",
                        current=values[0],
                        previous=values[1] if len(values) > 1 else None,
                        unit="LKR_per_share",
                        page=page_number,
                        source_line=raw_line.strip(),
                        method="direct",
                    )
                break
        if "eps" in results:
            break

    # Debt (summed, flagged) - balance sheet only, see docstring above.
    debt_matches = []
    debt_lines = []
    for raw_line in (lines if stmt_type == "balance_sheet" else []):
        line = _clean_line_start(raw_line)
        low = line.lower()
        if any(re.search(pat, low) for pat in DEBT_PATTERNS):
            values = _parse_money_tokens(line)
            if values:
                debt_matches.append(values)
                debt_lines.append(raw_line.strip())
    if debt_matches:
        cur_sum = sum(v[0] for v in debt_matches)
        prev_sum = sum(v[1] for v in debt_matches if len(v) > 1)
        if industry == "bank":
            debt_note = (f"Sum of {len(debt_matches)} borrowings/subordinated-debt line(s) — "
                         f"deliberately EXCLUDES customer deposits (a bank's main funding "
                         f"source, not conventional debt). Verify against the source lines "
                         f"before using in leverage ratios.")
        else:
            debt_note = (f"Sum of {len(debt_matches)} borrowings-related line(s) — verify "
                         f"manually, 'debt' definitions vary by company/industry.")
        results["total_debt"] = Extraction(
            metric="total_debt",
            current=cur_sum,
            previous=prev_sum if any(len(v) > 1 for v in debt_matches) else None,
            unit=unit,
            page=page_number,
            source_line=" | ".join(debt_lines),
            method="summed",
            notes=debt_note,
        )

    return results


def derive_missing_metrics(all_results: dict) -> dict:
    """Fill in metrics we can compute from others when not found directly."""
    if "total_liabilities" not in all_results and \
       "total_equity_and_liabilities" in all_results and \
       "total_equity" in all_results:
        tel = all_results["total_equity_and_liabilities"]
        te = all_results["total_equity"]
        if tel.current is not None and te.current is not None:
            all_results["total_liabilities"] = Extraction(
                metric="total_liabilities",
                current=tel.current - te.current,
                previous=(tel.previous - te.previous)
                    if tel.previous is not None and te.previous is not None else None,
                unit=tel.unit,
                page=tel.page,
                source_line=f"Derived: Total Equity & Liabilities − Total Equity",
                method="derived",
                notes="No single 'Total Liabilities' line found on the page — "
                      "computed from Total Equity & Liabilities minus Total Equity.",
            )
    return all_results
