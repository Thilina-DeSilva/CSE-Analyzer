"""
Streamlit rendering for the extra tabs: Advanced, Banking, Construction,
Things to Investigate. app.py only calls these; all numbers come from
advanced.py.
"""

import io

import pandas as pd
import streamlit as st

from advanced import (
    SECTIONS, BANK_SECTIONS, CONSTRUCTION_SECTIONS, NOT_AVAILABLE,
    compute_cagr_table, compute_investigate_flags, format_value,
    metric_history, all_history_keys, cagr_for, _series_value,
)

SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🔵", "none": "✅"}


def _period_labels(records):
    return [str(r.get("period_label") or r.get("year")) for r in records]


def _section_table(records, rows, show_why: bool):
    labels = _period_labels(records)
    table, hidden = [], 0
    for key, label, fmt, why in rows:
        vals = [_series_value(r, key) for r in records]
        if all(v is None for v in vals):
            hidden += 1
            continue
        row = {"Metric": label}
        for lab, v in zip(labels, vals):
            row[lab] = format_value(v, fmt)
        if show_why:
            row["Why it matters"] = why
        table.append(row)
    return table, hidden


def _render_sections(records, sections, show_why):
    for title, rows in sections.items():
        table, hidden = _section_table(records, rows, show_why)
        st.subheader(title)
        if table:
            st.dataframe(pd.DataFrame(table).set_index("Metric"), use_container_width=True)
        else:
            st.caption("Nothing in this group could be calculated from the extracted data.")
        if hidden and table:
            st.caption(f"{hidden} more metric(s) in this group need inputs that were not found in these reports.")


def render_advanced(records):
    st.caption(
        "Why is this happening? These are calculated from the extracted statements. "
        "A '—' means an input line was not found (never zero). Growth is only computed "
        "against the same period one year earlier."
    )
    show_why = st.toggle("🎓 Show why each metric matters", value=False, key="adv_why")

    st.subheader("Growth over time (full-year figures)")
    cagr_rows = compute_cagr_table(records)
    if any(r["3Y CAGR %"] is not None or r["5Y CAGR %"] is not None for r in cagr_rows):
        df = pd.DataFrame([
            {"Metric": r["Metric"],
             "3Y CAGR": format_value(r["3Y CAGR %"], "pct"),
             "5Y CAGR": format_value(r["5Y CAGR %"], "pct")} for r in cagr_rows
        ]).set_index("Metric")
        st.dataframe(df, use_container_width=True)
        st.caption("Needs full-year data for both endpoint years and positive values at both ends. "
                   "NAVPS uses the approximate share count.")
    else:
        st.caption("Not enough full-year history yet: a 3Y CAGR needs 4 consecutive annual data points "
                   "(year N and year N−3); 5Y needs 6.")

    _render_sections(records, SECTIONS, show_why)

    st.markdown("---")
    st.subheader("📊 Metric history")
    keys = all_history_keys(records)
    if keys:
        choice = st.selectbox("Pick any metric", list(keys.keys()), format_func=lambda k: keys[k], key=f"hist_metric_{abs(hash(tuple(keys.keys()))) % 10**8}")
        hist = metric_history(records, choice)
        df = pd.DataFrame(hist, columns=["Period", "Value"])
        st.dataframe(df.assign(Value=df["Value"].map(lambda v: "—" if v is None else f"{v:,.2f}")).set_index("Period").T,
                     use_container_width=True)
        c3, c5 = cagr_for(records, choice, 3), cagr_for(records, choice, 5)
        st.caption(f"3Y CAGR: {format_value(c3, 'pct')} · 5Y CAGR: {format_value(c5, 'pct')}")
        if df["Value"].notna().sum() >= 2:
            st.line_chart(df.set_index("Period")["Value"])

    st.markdown("---")
    csv_buf = io.StringIO()
    rows = []
    for r in records:
        row = {"period": r.get("period_label") or r.get("year")}
        row.update({k: v for k, v in (r.get("_extra") or {}).items() if not k.startswith("_")})
        rows.append(row)
    pd.DataFrame(rows).to_csv(csv_buf, index=False)
    st.download_button("⬇️ Download advanced metrics (.csv)", csv_buf.getvalue(),
                       file_name="advanced_metrics.csv", mime="text/csv")


def render_bank(records):
    st.caption("Banking mode appears automatically because this looks like a bank.")
    _render_sections(records, BANK_SECTIONS, st.toggle("🎓 Show why each metric matters", value=False, key="bank_why"))
    st.info("Not extracted (they live in the notes / regulatory disclosures, not the four statements): "
            + NOT_AVAILABLE["Bank"] + ".")


def render_construction(records):
    st.caption("Construction mode appears because contract assets / liabilities were found.")
    _render_sections(records, CONSTRUCTION_SECTIONS, st.toggle("🎓 Show why each metric matters", value=False, key="con_why"))
    st.info("Not extracted: " + NOT_AVAILABLE["Construction"] + ".")


def render_investigate(records):
    st.caption(
        "Relationships between numbers that are worth a closer look. This is NOT a buy or sell "
        "signal, and it complements the automatic checks on the Red Flags tab."
    )
    flags = compute_investigate_flags(records)
    if not flags:
        st.success("None of these cross-checks triggered for the latest period "
                   "(some need inputs that may not have been found; see the Advanced tab).")
        return
    for f in flags:
        with st.container(border=True):
            st.markdown(f"{SEVERITY_ICON.get(f['severity'], '•')} **{f['category']}** — {f['title']}")
            st.caption(f["detail"])
