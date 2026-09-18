"""
Small helper: figure out which two years the "current" / "previous"
columns actually refer to, by reading the statement header line itself
("For the year ended December 31, 2024 2023 ..." or
"Year ended 31 March 2025 2025 2024 ...") rather than assuming.
"""

import re

YEAR = re.compile(r"20\d{2}")


def _dedup_preserve_order(items):
    return list(dict.fromkeys(items))


def detect_years(page_text: str) -> tuple:
    """
    Returns (current_year, previous_year) as ints, or (None, None).

    Header lines often restate the report's own end-date year before
    the actual column headers, e.g.
      "Year ended 31 March 2025 2025 2024 2025 2024"
                              ^^^^ date phrase   ^^^^ ^^^^ real columns
    so a plain "take the first two years found" would grab the date
    phrase's year twice. Deduping while preserving order fixes this:
    ['2025','2025','2024','2025','2024'] -> ['2025','2024'].
    """
    for line in page_text.split("\n")[:6]:
        low = line.lower()
        if "year ended" in low or "as at" in low:
            years = _dedup_preserve_order(YEAR.findall(line))
            if len(years) >= 2:
                return int(years[0]), int(years[1])
    # fallback: just look at the first few lines for any two years
    years = _dedup_preserve_order(YEAR.findall(page_text[:200]))
    if len(years) >= 2:
        return int(years[0]), int(years[1])
    return None, None
