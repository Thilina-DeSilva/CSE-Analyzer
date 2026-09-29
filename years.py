"""
Detect the reporting period from statement headers.

Supports:
  - Annual: "Year ended 31 December 2024"
  - Interim half-year: "For the six months ended 30th June 2026"
  - Interim quarter: "For the three months ended 31st March 2026"
  - Quarter ended / period ended variants

Returns a structured period so annual and interim rows can coexist
in the multi-period table without overwriting each other.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

YEAR = re.compile(r"20\d{2}")

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _dedup_preserve_order(items):
    return list(dict.fromkeys(items))


def _month_from_text(text: str) -> Optional[int]:
    low = text.lower()
    for name, num in MONTH_MAP.items():
        if re.search(rf"\b{name}\b", low):
            return num
    return None


def _period_type_from_text(text: str, end_month: Optional[int]) -> str:
    """Return FY | H1 | H2 | Q1 | Q2 | Q3 | Q4 | interim.

    Prefer YTD half-year over single-quarter when both appear in the same
    header (common on CSE bank interims: 6 months + quarter columns).
    """
    low = text.lower()
    has_six = bool(re.search(
        r"\b(six|6)\s+months?\b|\bhalf[\s-]?year\b|\bfirst half\b|\b1h\b|\bh1\b", low
    ))
    has_three = bool(re.search(
        r"\b(three|3)\s+months?\b|\bquarter ended\b|\b1st quarter\b", low
    ))
    if has_six and not (has_three and "six months" not in low and "6 months" not in low):
        # If six months is present, prefer H1/H2 (YTD is the primary bank column)
        if has_six:
            return "H1" if (end_month is None or end_month <= 6) else "H2"
    if has_three or re.search(r"\bq1\b|\bq2\b|\bq3\b|\bq4\b", low):
        if end_month in (1, 2, 3):
            return "Q1"
        if end_month in (4, 5, 6):
            return "Q2"
        if end_month in (7, 8, 9):
            return "Q3"
        if end_month in (10, 11, 12):
            return "Q4"
        return "Q"
    if has_six:
        return "H1" if (end_month is None or end_month <= 6) else "H2"
    if re.search(r"\b(nine|9)\s+months?\b", low):
        return "9M"
    if re.search(r"\byear ended\b|\bfor the year\b|\bannual\b", low):
        return "FY"
    if re.search(r"\bas at\b|\bas of\b", low) and end_month:
        if end_month == 12:
            return "FY"
        if end_month == 3:
            return "Q1"
        if end_month == 6:
            return "H1"
        if end_month == 9:
            return "Q3"
    return "FY"


def detect_period(page_text: str) -> dict:
    """
    Returns {
      current_year, previous_year,
      period_type, period_key, previous_period_key,
      label, previous_label, doc_kind, end_month
    }
    """
    head = page_text[:800]
    years = _dedup_preserve_order(YEAR.findall(head))
    end_month = _month_from_text(head)
    ptype = _period_type_from_text(head, end_month)

    cur_year = prev_year = None
    for line in page_text.split("\n")[:12]:
        low = line.lower()
        if any(k in low for k in (
            "year ended", "months ended", "quarter ended", "period ended",
            "for the year", "for the six", "for the three", "for the nine",
            "as at", "as of",
        )):
            ys = _dedup_preserve_order(YEAR.findall(line))
            if len(ys) >= 2:
                a, b = int(ys[0]), int(ys[1])
                if a < b:
                    a, b = b, a
                cur_year, prev_year = a, b
                end_month = _month_from_text(line) or end_month
                ptype = _period_type_from_text(line, end_month)
                break
            if len(ys) == 1:
                cur_year = int(ys[0])
                end_month = _month_from_text(line) or end_month
                ptype = _period_type_from_text(line, end_month)
                break

    if cur_year is None and years:
        cur_year = int(years[0])
        if len(years) >= 2:
            prev_year = int(years[1])
            if cur_year < prev_year:
                cur_year, prev_year = prev_year, cur_year

    if prev_year is None and cur_year is not None:
        prev_year = cur_year - 1

    def _key(y, pt):
        if y is None:
            return None
        if pt == "FY":
            return str(y)
        return f"{y}-{pt}"

    def _label(y, pt):
        if y is None:
            return "—"
        if pt == "FY":
            return str(y)
        return f"{pt} {y}"

    doc_kind = "annual" if ptype == "FY" else "interim"
    low_full = page_text[:2000].lower()
    if ("performance commentary" in low_full or "financial commentary" in low_full) and \
       "statement of financial position" not in low_full and \
       "income statement" not in low_full:
        doc_kind = "commentary"

    return {
        "current_year": cur_year,
        "previous_year": prev_year,
        "period_type": ptype,
        "period_key": _key(cur_year, ptype),
        "previous_period_key": _key(prev_year, ptype),
        "label": _label(cur_year, ptype),
        "previous_label": _label(prev_year, ptype),
        "doc_kind": doc_kind,
        "end_month": end_month,
    }


def detect_years(page_text: str) -> Tuple[Optional[int], Optional[int]]:
    """Backward-compatible: (current_year, previous_year)."""
    p = detect_period(page_text)
    return p["current_year"], p["previous_year"]
