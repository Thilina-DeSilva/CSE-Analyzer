"""
V5: Merge yearly records from multiple annual reports (of the SAME
company) into one sorted, deduplicated multi-year dataset.

Each annual report gives us 2 years of data (current + prior
comparative column). With 5 reports you get up to 10 data points but
only 5-6 distinct years - years overlap between consecutive reports
(e.g. the 2023 report's "current year" is the same fiscal year as the
2024 report's "previous year" comparative column).

When a year appears in more than one source report, we prefer the
value from the report where that year was the CURRENT column, not the
comparative column - the year's own report is the authoritative,
final-audited source; a prior-year comparative in a later report can
occasionally be restated for accounting policy changes, which is
useful to know about but shouldn't silently overwrite the primary
figure.
"""


def _sort_key(rec):
    """Sort annual years and interim periods chronologically."""
    y = rec.get("year") or 0
    pt = rec.get("period_type") or "FY"
    order = {"Q1": 1, "H1": 2, "Q2": 2, "9M": 3, "Q3": 3, "H2": 4, "Q4": 4, "FY": 5, "Q": 2, "interim": 2}
    return (y, order.get(pt, 3))


def merge_yearly_records(all_records: list) -> list:
    """
    Merge records across PDFs. Key is period_key when present
    ("2026-H1", "2024") so annual and interim do not overwrite each other.
    Prefer current-column records over comparative restatements.
    """
    by_key = {}
    dropped_duplicates = []

    for rec in all_records:
        key = rec.get("period_key") or rec.get("year")
        if key is None:
            continue
        if key not in by_key:
            by_key[key] = rec
        else:
            existing = by_key[key]
            existing_current = bool(existing.get("_is_current"))
            new_current = bool(rec.get("_is_current"))
            existing_count = sum(
                1 for k, v in existing.items() if not k.startswith("_") and v is not None
            )
            new_count = sum(
                1 for k, v in rec.items() if not k.startswith("_") and v is not None
            )
            take_new = False
            if new_current and not existing_current:
                take_new = True
            elif new_current == existing_current and new_count > existing_count:
                take_new = True
            if take_new:
                dropped_duplicates.append(existing)
                by_key[key] = rec
            else:
                dropped_duplicates.append(rec)

    merged = sorted(by_key.values(), key=_sort_key)
    return merged, dropped_duplicates
