"""
CSE Annual Report Analyzer — Streamlit UI

Run locally with:
    streamlit run app.py

This is intentionally a thin UI layer. All the real work (finding
statement pages, extracting metrics, merging years, computing ratios)
happens in the existing modules (find_statements.py, metrics.py,
pipeline.py, merge_reports.py, ratios.py, report_builder.py) - this
file just wires them together and renders the result, and is careful
never to hide uncertainty: every number shown links back to its page
and source line, and anything summed/derived is visibly flagged.
"""

import os
import io
import json
import tempfile

import pandas as pd
import streamlit as st

from pipeline import process_report, to_yearly_records
from merge_reports import merge_yearly_records
from ratios import compute_ratios_for_series
from report_builder import (
    build_markdown_report,
    METRIC_LABELS, RATIO_LABELS,
)
from education import GLOSSARY, BEGINNER_GUIDE, get_explanation
from valuation import compute_valuation, compute_position_size
from red_flags import compute_red_flags

st.set_page_config(page_title="CSE Annual Report Analyzer", layout="wide")

st.title("📊 CSE Annual Report Analyzer")
st.caption(
    "Upload multiple years of a company's annual report PDFs. Numbers are extracted "
    "deterministically (no AI guessing at figures) and every value is traceable to its "
    "exact source page and line."
)

with st.sidebar:
    st.header("1. Upload Annual Reports")
    company_name = st.text_input("Company name (for the report title)", value="")
    uploaded_files = st.file_uploader(
        "Upload one or more annual report PDFs (any years, any order)",
        type=["pdf"],
        accept_multiple_files=True,
    )
    analyze_clicked = st.button("🔍 ANALYZE REPORTS", type="primary", use_container_width=True,
                                 disabled=not uploaded_files)
    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) ready:")
        for f in uploaded_files:
            st.caption(f"• {f.name}")

if analyze_clicked:
    all_records = []
    per_file_status = []

    with st.spinner("Reading PDFs and extracting financials — large reports can take a minute..."):
        for f in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(f.getvalue())
                tmp_path = tmp.name
            try:
                result = process_report(tmp_path)
                records = to_yearly_records(result)
                for r in records:
                    r["source_pdf"] = f.name
                all_records.extend(records)
                found_years = sorted({r["year"] for r in records if r["year"]})
                pages = result["pages_used"]
                per_file_status.append({
                    "file": f.name, "years_found": found_years,
                    "pages_used": pages, "ok": bool(found_years),
                })
            except Exception as e:
                per_file_status.append({"file": f.name, "years_found": [], "pages_used": {},
                                         "ok": False, "error": str(e)})
            finally:
                os.unlink(tmp_path)

    merged, dropped = merge_yearly_records(all_records)
    with_ratios = compute_ratios_for_series(merged)

    st.session_state["with_ratios"] = with_ratios
    st.session_state["per_file_status"] = per_file_status
    st.session_state["company_name"] = company_name or "Company"

if "with_ratios" in st.session_state:
    with_ratios = st.session_state["with_ratios"]
    per_file_status = st.session_state["per_file_status"]
    company_name = st.session_state["company_name"]

    with st.expander("📄 Per-file processing status", expanded=False):
        for s in per_file_status:
            if s["ok"]:
                st.success(f"**{s['file']}** — found year(s) {s['years_found']}, "
                           f"used pages {s['pages_used']}")
            else:
                st.error(f"**{s['file']}** — could not extract data. "
                         f"{s.get('error', 'No statement pages found — check this PDF manually.')}")

    if not with_ratios:
        st.warning("No data could be extracted from any uploaded file. See status above.")
        st.stop()

    years = [r["year"] for r in with_ratios]
    st.header(f"{company_name} — {years[0]}–{years[-1]}")

    with st.expander("📚 New to reading annual reports? Click here to learn the basics", expanded=False):
        st.markdown(BEGINNER_GUIDE)

    tab_table, tab_charts, tab_flags, tab_value, tab_verify, tab_download = st.tabs(
        ["📋 5-Year Table", "📈 Charts", "🚩 Red Flags", "💰 Valuation & Sizing",
         "⚠️ Verification", "⬇️ Download"]
    )

    with tab_table:
        explain_mode = st.toggle("🎓 Explain these terms in plain language", value=False)

        st.subheader("Core Financials")
        table_rows = []
        for key, label in METRIC_LABELS.items():
            row = {"Metric": label}
            any_present = False
            for r in with_ratios:
                v = r.get(key)
                if v is not None:
                    any_present = True
                    row[str(r["year"])] = f"{v:,.2f}" if key == "eps" else f"{v:,.0f}"
                else:
                    row[str(r["year"])] = "—"
            if any_present:
                table_rows.append(row)
                if explain_mode:
                    exp = get_explanation(key)
                    with st.expander(f"📖 {label}"):
                        st.markdown(f"**What it means:** {exp['plain']}")
                        if exp.get("watch_for"):
                            st.markdown(f"**Watch for:** {exp['watch_for']}")
        st.dataframe(pd.DataFrame(table_rows).set_index("Metric"), use_container_width=True)

        st.subheader("Ratios")
        ratio_rows = []
        for key, label in RATIO_LABELS.items():
            row = {"Ratio": label}
            any_present = False
            for r in with_ratios:
                v = r.get("_ratios", {}).get(key)
                if v is not None:
                    any_present = True
                    row[str(r["year"])] = f"{v:,.2f}"
                else:
                    row[str(r["year"])] = "—"
            if any_present:
                ratio_rows.append(row)
                if explain_mode:
                    exp = get_explanation(key)
                    with st.expander(f"📖 {label}"):
                        st.markdown(f"**What it means:** {exp['plain']}")
                        if exp.get("watch_for"):
                            st.markdown(f"**Watch for:** {exp['watch_for']}")
        st.dataframe(pd.DataFrame(ratio_rows).set_index("Ratio"), use_container_width=True)

        st.subheader("🔍 Look up a value's source")
        col1, col2 = st.columns(2)
        with col1:
            metric_choice = st.selectbox("Metric", list(METRIC_LABELS.keys()),
                                          format_func=lambda k: METRIC_LABELS[k])
        with col2:
            year_choice = st.selectbox("Year", years)
        rec = next((r for r in with_ratios if r["year"] == year_choice), None)
        ext = rec.get("_extractions", {}).get(metric_choice) if rec else None
        if ext:
            badge = "✅ direct" if ext["method"] == "direct" else f"⚠️ {ext['method']}"
            st.markdown(f"**{METRIC_LABELS[metric_choice]} — {year_choice}**: "
                        f"{ext['value']:,.2f}  \n"
                        f"Method: {badge} · Page: {ext['page']} · Unit: {ext['unit']}")
            if ext["notes"]:
                st.info(ext["notes"])
            st.code(ext["source_line"], language=None)
        else:
            st.caption("No value extracted for this metric/year.")

    with tab_charts:
        df = pd.DataFrame(with_ratios)
        df["year"] = df["year"].astype(str)

        chart_pairs = [
            ("revenue", "Revenue"), ("net_profit", "Net Profit"),
            ("total_assets", "Total Assets"), ("eps", "EPS"),
        ]
        c1, c2 = st.columns(2)
        for i, (key, label) in enumerate(chart_pairs):
            if key in df.columns:
                target = c1 if i % 2 == 0 else c2
                with target:
                    st.caption(label)
                    st.bar_chart(df.set_index("year")[[key]])

        st.caption("ROE / ROA / Net Margin (%)")
        ratio_df = pd.DataFrame([
            {"year": str(r["year"]), **{k: r["_ratios"].get(k) for k in
             ["roe_pct", "roa_pct", "net_profit_margin_pct"]}}
            for r in with_ratios
        ]).set_index("year")
        st.line_chart(ratio_df)

    with tab_flags:
        st.caption(
            "Automatic checks for a handful of common warning patterns, based only on the "
            "numbers extracted above. This is NOT complete due diligence — always read the "
            "actual report too, especially the auditor's opinion and management discussion, "
            "which this tool doesn't check yet. None of this is a 'sell' signal — it's a "
            "prompt to look closer."
        )
        flags = compute_red_flags(with_ratios)
        severity_icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "none": "✅"}
        for f in flags:
            icon = severity_icon.get(f["severity"], "•")
            with st.container(border=True):
                st.markdown(f"{icon} **{f['title']}**")
                st.caption(f["detail"])

    with tab_value:
        st.subheader("💰 Valuation (needs today's share price)")
        st.caption(
            "The annual report doesn't contain the current market price — the CSE trading "
            "price changes daily. Enter it yourself below. These ratios are INPUTS to your "
            "own thinking, not a recommendation."
        )
        latest = with_ratios[-1]
        price = st.number_input("Current share price (Rs.)", min_value=0.0, step=1.0, value=0.0)

        if price > 0:
            val = compute_valuation(
                share_price=price,
                eps=latest.get("eps"),
                total_equity=latest.get("total_equity"),
                net_profit=latest.get("net_profit"),
                dividend_paid=latest.get("dividend_paid"),
            )
            explain_val = st.toggle("🎓 Explain these terms", value=False, key="explain_val")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("P/E Ratio", f"{val['pe_ratio']:.2f}" if val["pe_ratio"] else "—")
                if explain_val:
                    st.caption(get_explanation("pe_ratio")["plain"])
            with c2:
                st.metric("P/B Ratio (approx.)", f"{val['pb_ratio']:.2f}" if val["pb_ratio"] else "—")
                if explain_val:
                    st.caption(get_explanation("pb_ratio")["plain"])
            with c3:
                st.metric("Dividend Yield (approx.)",
                          f"{val['dividend_yield_pct']:.2f}%" if val["dividend_yield_pct"] else "—")
                if explain_val:
                    st.caption(get_explanation("dividend_yield_pct")["plain"])

            if val["approximate_shares_outstanding"]:
                unit_note = latest.get("_extractions", {}).get("net_profit", {}).get("unit", "")
                st.caption(
                    f"⚠️ Shares outstanding is APPROXIMATED as Net Profit ÷ EPS, and isn't "
                    f"one of the extracted line items — the P/E, P/B and Dividend Yield "
                    f"ratios above are unit-consistent and reliable, but we're not showing "
                    f"the raw share count here since Net Profit's unit ({unit_note or 'unknown'}) "
                    f"means it wouldn't be the literal number of shares — treat it as an "
                    f"internal calculation step, not a fact to quote elsewhere."
                )
        else:
            st.info("Enter a share price above to see valuation ratios.")

        st.divider()
        st.subheader("🧮 Position Size Calculator")
        st.caption(
            "Pure arithmetic based on numbers YOU choose — your budget and how much of it "
            "you've decided to risk on this one stock. This does not suggest an allocation."
        )
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            budget = st.number_input("Your total investing budget (Rs.)", min_value=0.0, step=1000.0, value=0.0)
        with pc2:
            allocation = st.slider("% of budget for THIS stock (your choice)", 0, 100, 10)
        with pc3:
            portfolio_value = st.number_input("Total portfolio value, if you have other holdings (optional, Rs.)",
                                               min_value=0.0, step=1000.0, value=0.0)

        if budget > 0 and price > 0:
            pos = compute_position_size(budget, allocation, price, portfolio_value or None)
            st.markdown(
                f"- Amount allocated: **Rs. {pos['amount_to_invest']:,.2f}**\n"
                f"- Shares you can buy: **{pos['shares_you_can_buy']:,}**\n"
                f"- Actual amount spent: **Rs. {pos['actual_amount_spent']:,.2f}**\n"
                f"- Leftover cash: Rs. {pos['leftover_cash']:,.2f}"
            )
            if pos["pct_of_total_portfolio"] is not None:
                st.markdown(f"- This position would be **{pos['pct_of_total_portfolio']:.1f}%** "
                           f"of your total portfolio.")
                if pos["pct_of_total_portfolio"] > 25:
                    st.warning("That's a large concentration in a single stock — many investors "
                              "diversify across multiple companies/sectors to reduce risk. "
                              "That's your call to make, not this app's.")
        else:
            st.info("Enter your budget and a share price above to calculate position size.")

    with tab_verify:
        st.markdown(
            "Figures below were **not** matched directly to a single labeled line, or "
            "required summing several lines together. Please spot-check these against "
            "the source PDF before relying on them."
        )
        any_flagged = False
        for r in with_ratios:
            for key, ext in r.get("_extractions", {}).items():
                if ext["method"] in ("summed", "derived"):
                    any_flagged = True
                    st.warning(
                        f"**{r['year']} — {METRIC_LABELS.get(key, key)}** "
                        f"({ext['method']}, page {ext['page']})  \n{ext['notes']}"
                    )
                    st.code(ext["source_line"], language=None)
        if not any_flagged:
            st.success("Every figure was matched directly from a labeled statement line.")

        missing = []
        for r in with_ratios:
            for key, label in METRIC_LABELS.items():
                if r.get(key) is None:
                    missing.append(f"{r['year']} — {label}")
        if missing:
            with st.expander(f"Metrics not found at all ({len(missing)})"):
                for m in missing:
                    st.caption(f"• {m}")

    with tab_download:
        md = build_markdown_report(company_name, with_ratios)
        st.download_button("⬇️ Download Markdown Report (.md)", md,
                            file_name=f"{company_name.replace(' ', '_')}_5_Year_Analysis.md",
                            mime="text/markdown", use_container_width=True)

        csv_buf = io.StringIO()
        pd.DataFrame(with_ratios).drop(columns=["_extractions", "_ratios"], errors="ignore").to_csv(csv_buf, index=False)
        st.download_button("⬇️ Download Data (.csv)", csv_buf.getvalue(),
                            file_name=f"{company_name.replace(' ', '_')}_data.csv",
                            mime="text/csv", use_container_width=True)

        json_str = json.dumps(with_ratios, indent=2, default=str)
        st.download_button("⬇️ Download Full Data incl. sources (.json)", json_str,
                            file_name=f"{company_name.replace(' ', '_')}_data.json",
                            mime="application/json", use_container_width=True)

        st.markdown("---")
        st.markdown("**Preview:**")
        st.markdown(md)
else:
    st.info("👈 Upload one or more annual report PDFs in the sidebar, then click **ANALYZE REPORTS**.")
