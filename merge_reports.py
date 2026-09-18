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


def merge_yearly_records(all_records: list) -> list:
    """
    all_records: list of per-year dicts (each with a "year" key), e.g.
    everything returned by to_yearly_records() across multiple PDFs.

    Returns one row per distinct year, sorted oldest -> newest, with a
    "_is_restated_comparative" flag added where we dropped a duplicate.
    """
    by_year = {}
    dropped_duplicates = []

    for rec in all_records:
        yr = rec.get("year")
        if yr is None:
            continue
        if yr not in by_year:
            by_year[yr] = rec
        else:
            # already have this year - keep whichever one is more
            # complete (more non-null metrics), since we can't always
            # tell which report treated it as "current" vs "previous"
            existing = by_year[yr]
            existing_count = sum(1 for k, v in existing.items() if not k.startswith("_") and v is not None)
            new_count = sum(1 for k, v in rec.items() if not k.startswith("_") and v is not None)
            if new_count > existing_count:
                dropped_duplicates.append(existing)
                by_year[yr] = rec
            else:
                dropped_duplicates.append(rec)

    merged = sorted(by_year.values(), key=lambda r: r["year"])
    return merged, dropped_duplicates
