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
    # Exact label text as printed on the statement line (useful when
    # several aliases map to one normalized metric, e.g. credit_impairment).
    original_label: str = ""


# metric_key -> list of regex patterns tested against the (lowercased,
# prefix-stripped) start of a line. First match wins, patterns listed
# in priority order (more specific first) to avoid mismatches e.g.
# "gross profit" should not swallow "operating profit" lines.
METRIC_PATTERNS = {
    "revenue": [
        r"^revenue from contracts with customers\b",
        r"^revenue\b",
        # NOTE: "Turnover" is NOT an alias here. For companies like CTC,
        # Turnover includes government levies and is much larger than Revenue.
        # Turnover is only used as a last-resort fallback after the full pass.
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
        r"^gross profit\s*/\s*\(loss\)",
        r"^gross profit/\(loss\)",
        r"^gross profit",
    ],
    "operating_profit": [
        r"^operating profit\s*/\s*\(loss\)",
        r"^operating profit/\(loss\)",
        r"^operating profit",
        r"^net operating income",
        r"^results from operating activities",
        r"^profit from operations",
        r"^operating profit before tax on financial services",
    ],
    "profit_before_tax": [
        r"^profit\s*/\s*\(loss\)\s*before (income )?tax",
        r"^profit/\(loss\) before (income )?tax",
        r"^profit before income tax expense",
        r"^profit.*before (income )?tax",
        r"^\(?profit/\(loss\)\)? before tax",
        r"^profit before taxation",
        r"^profit/\(loss\) before taxation",
    ],
    "net_profit": [
        r"^profit\s*/\s*\(loss\)\s*for the year",
        r"^profit/\(loss\) for the year",
        r"^profit\s*/\s*\(loss\)\s*for the period",
        r"^profit/\(loss\) for the period",
        r"^profit for the year",
        r"^profit for the period",
        r"^net profit for the year",
        r"^net profit for the period",
        r"^profit attributable to (equity holders|owners of the parent|shareholders|the bank)",
        r"^profit/\(loss\) attributable to (equity holders|owners)",
        r"^profit attributable to ordinary shareholders",
        r"^profit attributable to equity holders of the bank",
        r"^profit attributable to equity holders of the parent",
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
        r"^total shareholders['\u2019]? equity\b",
        r"^total equity\b(?! attributable)",
        r"^total equity attributable",
    ],
    "cash_and_equivalents": [
        r"^cash and cash equivalents\b",
        r"^cash and bank balances\b",
        r"^cash in hand and at banks\b",
    ],
    "operating_cash_flow": [
        r"^net cash.*operating activities",
    ],
    "dividend_paid": [
        r"^dividend paid to shareholders",
        r"^dividends? paid\b",
        r"^dividend$|^dividends$",  # equity statement "Dividend" line
    ],
}

# Which statement type each metric is allowed to match on. Metrics not
# listed here are unrestricted (checked on every page type). This
# exists because of a real bug we hit: "net_profit" matched a stray
# "Profit for the year" line inside the Statement of Changes in Equity,
# which gets pulled in as a continuation page of the Balance Sheet -
# and because it was recorded as a "direct" match, a CORRECT net_profit
# found later on the real income statement couldn't overwrite it (our
# merge rule keeps the first direct match). Restricting P&L concepts to
# income-statement-type pages stops them from ever being eligible to
# match there in the first place.
RESTRICT_TO_STMT_TYPE = {
    "revenue": "income_statement",
    "gross_income": "income_statement",
    "net_interest_income": "income_statement",
    "gross_profit": "income_statement",
    "operating_profit": "income_statement",
    "profit_before_tax": "income_statement",
    "net_profit": "income_statement",
    "total_assets": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "total_equity_and_liabilities": "balance_sheet",
    "total_equity": "balance_sheet",
    "cash_and_equivalents": "balance_sheet",
    "operating_cash_flow": "cash_flow",
    # dividend_paid is deliberately NOT restricted - it legitimately
    # appears on the Cash Flow statement (financing activities) OR the
    # Statement of Changes in Equity, and we want to catch either.
}

# Credit Impairment / ECL — ONE normalized metric for banks (and any
# company that reports loan/asset impairment). Patterns are ordered
# most-specific / total-line FIRST so we prefer a reported "Net
# impairment charge" over a component line such as "Impairment on
# loans and advances". We never sum multiple impairment lines
# (would double-count when the total already includes the components).
# Matching is restricted to the income statement (see extract path).
CREDIT_IMPAIRMENT_PATTERNS = [
    r"^impairment\s+charge\s*/\s*\(reversal\)\s+for\s+loans",
    r"^impairment\s+charge\s*/\s*\(reversal\)",
    r"^impairment\s+charges?\s*/\s*\(reversals?\)",
    r"^less[:\s]+impairment\s+charge",
    # Prefer explicit net / total lines (CSE bank P&Ls vary a lot)
    r"^net\s+impairment\s+(charge|charges|loss|losses)\b",
    r"^net\s+impairment\s*\(charge\)/?\(?(reversal|write[- ]?back)\)?",
    r"^net\s+impairment\s+(charge|charges)\s*/\s*(reversal|write[- ]?back)",
    r"^net\s+credit\s+impairment\b",
    r"^total\s+impairment\s+(charge|charges|loss|losses)\b",
    # Common Sri Lankan bank wording
    r"^impairment\s+charges?\s+for\s+loans?\s+and\s+other\s+losses\b",
    r"^impairment\s+charges?\s+for\s+loans?\b",
    r"^impairment\s+(charge|charges|loss|losses)\s+on\s+loans?\s+and\s+advances?\b",
    r"^impairment\s+(charge|charges|loss|losses)\s+on\s+loans?\b",
    r"^impairment\s+of\s+loans?\s+and\s+advances?\b",
    r"^impairment\s+of\s+financial\s+assets?\b",
    r"^impairment\s+(charge|charges|loss|losses)\s+on\s+financial\s+assets?\b",
    r"^impairment\s+(charge|charges)\s*/\s*(reversal|write[- ]?back)",
    r"^impairment\s*\(charge\)/?\(?(reversal|write[- ]?back)\)?",
    r"^expected\s+credit\s+loss(es)?\b",
    r"^net\s+expected\s+credit\s+loss(es)?\b",
    r"^expected\s+credit\s+loss(es)?\s+(charge|charges|allowance)\b",
    r"^credit\s+impairment\s+(charge|charges|loss|losses)?\b",
    r"^provision\s+for\s+(loan\s+)?impairment\b",
    r"^provision\s+for\s+(credit\s+)?losses\b",
    r"^loan\s+loss\s+provision\b",
    r"^allowance\s+for\s+(expected\s+)?credit\s+loss(es)?\b",
    r"^impairment\s+(charge|charges|loss|losses)\b",
    r"^impairment\s+on\s+loans?\s+and\s+advances?\b",
    # Compact / OCR-tolerant
    r"^ecl\b",
    r"^impairm[ae]nt\s+(charge|charges|loss|losses)\b",
]

# EPS/DPS use the decimal token pass instead.
EPS_PATTERNS = [
    r"^basic/diluted earnings/\(loss\) per share",
    r"^basic\s*/\s*diluted earnings/\(loss\) per share",
    r"^basic earnings/\(loss\) per share",
    r"^basic earnings per (ordinary )?share",
    r"^earnings/\(loss\) per share",
    r"^earnings per share",
    r"^basic\s*\(rs\.?\)",
    r"^-\s*basic\s*\(rs\.?\)",
    r"^basic\s*eps\b",
    r"^diluted earnings per (ordinary )?share",
]

# Lines to SUM (not just take one) for a best-effort Debt figure.
# Flagged as needing manual verification - "debt" is defined
# inconsistently across industries (esp. banks vs non-financial firms).
# Prefer specific lines. Bare "borrowings" is last and only used if nothing
# more specific matched — and we de-dupe by skipping lines that look like
# sub-totals already covered (see extract path).
DEBT_PATTERNS = [
    r"interest[- ]bearing loans? and borrowings",
    r"^loans and borrowings\b",
    r"interest[- ]bearing borrowings",
    r"debt securities issued",
    r"subordinated (liabilities|debt)",
    r"bank (overdrafts?|loans?|borrowings)",
    r"long[- ]term borrowings",
    r"short[- ]term borrowings",
    r"lease liabilities",
    r"^total\s+borrowings\b",
    r"^borrowings\b",
]


def _clean_line_start(line: str) -> str:
    s = line.strip()
    s = STRIP_PREFIXES.sub("", s)
    # Drop leading note/ref numbers: "12 Impairment..." / "12. Impairment..." / "(12) Impairment..."
    s = re.sub(r"^\(?\d{1,3}\)?\.?\s+", "", s)
    return s


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
    # Common CSE wordings for thousands
    if any(x in low for x in (
        "rs. \u2019000", "rs.\u2019000", "rs. '000", "rs.’000", "rs.'000",
        "rupees thousands", "rupee thousands", "lkr '000", "lkr thousands",
        "amounts in sri lanka rupees thousands",
        "(all amounts in sri lanka rupees thousands)",
    )):
        return "LKR_thousand"
    if re.search(r"rs\.?\s*['\u2019`]?000", page_text, re.IGNORECASE):
        return "LKR_thousand"
    if re.search(r"in\s+thousands", low) and ("rupee" in low or "rs" in low or "lkr" in low):
        return "LKR_thousand"
    if re.search(r"rs\.?\s*mn\b|rs\.?\s*million|rupees? million", low):
        return "LKR_million"
    if "rs." in low or "lkr" in low:
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
        restrict = RESTRICT_TO_STMT_TYPE.get(metric)
        if restrict and stmt_type and restrict != stmt_type:
            continue
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

    # Turnover fallback: only if Revenue was not found (industrial companies
    # that report a single "Turnover" top line without a separate Revenue line).
    if "revenue" not in results and stmt_type in ("", "income_statement"):
        raw_line, values = _search([r"^turnover\b"], lines, _parse_money_tokens)
        if values is None:
            raw_line, values = _search([r"^turnover\b"], joined_lines, _parse_money_tokens)
        if values:
            results["revenue"] = Extraction(
                metric="revenue",
                current=values[0],
                previous=values[1] if len(values) > 1 else None,
                unit=unit,
                page=page_number,
                source_line=raw_line.strip(),
                method="direct",
                notes="No separate 'Revenue' line — used Turnover as top-line proxy.",
                original_label="Turnover",
            )

    # EPS (decimal pass) - restricted to income-statement-type pages for
    # the same reason as the P&L metrics above: "per share" figures also
    # appear on the Statement of Changes in Equity and in notes, and we
    # don't want a stray match there to block the real one.
    if stmt_type in ("", "income_statement"):
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

    # Credit Impairment / ECL — income statement preferred (profit impact).
    # Search by PATTERN priority first (not line order) so a "Net impairment
    # charge" wins over a later component line on the same page. Never sum.
    if stmt_type in ("", "income_statement"):
        impairment_hit = None  # (pat_index, raw_line, values, matched_label)
        for raw_line in lines:
            line = _clean_line_start(raw_line)
            low = line.lower()
            for pat_idx, pat in enumerate(CREDIT_IMPAIRMENT_PATTERNS):
                m = re.search(pat, low)
                if m:
                    values = _parse_money_tokens(line)
                    if values:
                        if impairment_hit is None or pat_idx < impairment_hit[0]:
                            # Capture the matched phrase as original_label
                            label = m.group(0).strip()
                            # Prefer the human-readable start of the line
                            # up to the first number-ish token
                            label_full = re.split(
                                r"\s+\(?-?\d{1,3}(?:,\d{3})+", line, maxsplit=1
                            )[0].strip(" .:-")
                            impairment_hit = (pat_idx, raw_line, values, label_full or label)
                    break  # one pattern per line is enough
        if impairment_hit is None:
            # Fallback: wrapped label across two physical lines
            for raw_line in joined_lines:
                line = _clean_line_start(raw_line)
                low = line.lower()
                for pat_idx, pat in enumerate(CREDIT_IMPAIRMENT_PATTERNS):
                    m = re.search(pat, low)
                    if m:
                        values = _parse_money_tokens(line)
                        if values:
                            if impairment_hit is None or pat_idx < impairment_hit[0]:
                                label_full = re.split(
                                    r"\s+\(?-?\d{1,3}(?:,\d{3})+", line, maxsplit=1
                                )[0].strip(" .:-")
                                impairment_hit = (
                                    pat_idx, raw_line, values, label_full or m.group(0).strip()
                                )
                        break
        if impairment_hit is not None:
            _, raw_line, values, orig_label = impairment_hit
            results["credit_impairment"] = Extraction(
                metric="credit_impairment",
                current=values[0],
                previous=values[1] if len(values) > 1 else None,
                unit=unit,
                page=page_number,
                source_line=raw_line.strip(),
                method="direct",
                original_label=orig_label,
                notes=(
                    f"Normalized as Credit Impairment / ECL. "
                    f"Original statement label: «{orig_label}». "
                    f"Single line preferred — components are not summed to avoid double-counting."
                ),
            )

    # Debt (summed, flagged) - balance sheet only, see docstring above.
    # Strategy: collect candidate lines, then if any line looks like a TOTAL
    # ("total borrowings", line-start "Borrowings" alone), prefer that single
    # line over summing components — avoids double-counting parent + children.
    debt_matches = []  # list of (values, raw_line, is_total_like)
    for raw_line in (lines if stmt_type == "balance_sheet" else []):
        line = _clean_line_start(raw_line)
        low = line.lower()
        if any(re.search(pat, low) for pat in DEBT_PATTERNS):
            values = _parse_money_tokens(line)
            if values:
                is_total = bool(re.search(
                    r"^(total\s+)?borrowings\b|^total\s+interest[- ]bearing|^total\s+debt\b",
                    low,
                ))
                debt_matches.append((values, raw_line.strip(), is_total))
    if debt_matches:
        totals = [m for m in debt_matches if m[2]]
        if totals:
            # Prefer the largest total-like line (most complete)
            best = max(totals, key=lambda m: abs(m[0][0]) if m[0] else 0)
            chosen = [best]
            method_note = "total-line preferred (components not summed)"
        else:
            chosen = debt_matches
            method_note = f"sum of {len(chosen)} component line(s)"
        cur_sum = sum(m[0][0] for m in chosen)
        # Previous: only include lines that actually have a prior-year column
        prev_vals = [m[0][1] for m in chosen if len(m[0]) > 1]
        prev_sum = sum(prev_vals) if prev_vals and len(prev_vals) == len(chosen) else (
            sum(prev_vals) if prev_vals else None
        )
        debt_lines = [m[1] for m in chosen]
        if industry == "bank":
            debt_note = (f"{method_note.capitalize()} — deliberately EXCLUDES customer "
                         f"deposits (a bank's main funding source, not conventional debt). "
                         f"Verify against the source lines before using in leverage ratios.")
        else:
            debt_note = (f"{method_note.capitalize()} — verify manually; "
                         f"'debt' definitions vary by company/industry.")
        results["total_debt"] = Extraction(
            metric="total_debt",
            current=cur_sum,
            previous=prev_sum,
            unit=unit,
            page=page_number,
            source_line=" | ".join(debt_lines),
            method="summed" if len(chosen) > 1 else "direct",
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


def unit_to_scale(unit: str) -> float:
    """How many rupees one reported unit represents. Used to normalise
    mixed units across years and to scale share-count approximations."""
    if unit == "LKR_thousand":
        return 1_000.0
    if unit == "LKR_million":
        return 1_000_000.0
    return 1.0  # LKR or unknown — treat as face value
