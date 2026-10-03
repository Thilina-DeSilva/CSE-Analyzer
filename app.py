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
import re
import json
import pickle
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from pipeline import process_report, to_yearly_records
from merge_reports import merge_yearly_records
from ratios import compute_ratios_for_series
from report_builder import (
    build_markdown_report,
    METRIC_LABELS, RATIO_LABELS,
)
from education import GLOSSARY, BEGINNER_GUIDE, PRE_BUY_GUIDE, get_explanation
from valuation import compute_valuation, compute_position_size
from red_flags import compute_red_flags
from pre_buy import compute_pre_buy
from advanced import (
    compute_extra_series, sections_have_data, CONSTRUCTION_SECTIONS,
)
import advanced_ui

APP_VERSION = "2026.10.04-bank-credit"  # bump when shipping fixes

st.set_page_config(
    page_title="CSE Annual Report Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Visual design ----
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"]  {
        font-family: 'DM Sans', system-ui, sans-serif;
    }
    .block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1200px; }

    h1 { font-weight: 700 !important; letter-spacing: -0.02em; }
    h2, h3 { font-weight: 600 !important; }

    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 12px 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 0.8rem !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f8fafc !important; font-family: 'JetBrains Mono', monospace; font-size: 1.35rem !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

    .cse-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f766e 100%);
        border-radius: 16px; padding: 1.5rem 1.75rem; margin-bottom: 1.25rem;
        color: #f1f5f9; border: 1px solid #334155;
    }
    .cse-hero h1 { color: #fff !important; margin: 0 0 0.35rem 0; font-size: 1.75rem; }
    .cse-hero p { color: #cbd5e1; margin: 0; font-size: 0.95rem; }
    .cse-badge {
        display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px;
        font-size: 0.75rem; font-weight: 600; margin-right: 0.4rem; margin-top: 0.5rem;
    }
    .badge-bank { background: #0ea5e9; color: #0c4a6e; }
    .badge-ind { background: #a78bfa; color: #2e1065; }
    .badge-unit { background: #34d399; color: #064e3b; }
    .badge-warn { background: #fbbf24; color: #78350f; }

    .cse-card {
        border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem 1.15rem;
        background: #fff; margin-bottom: 0.75rem;
    }
    [data-theme="dark"] .cse-card, .stApp[data-theme="dark"] .cse-card {
        background: #1e293b; border-color: #334155;
    }

    div[data-testid="stTabs"] button {
        font-weight: 500; font-size: 0.9rem;
    }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    section[data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(90deg, #0d9488, #0891b2) !important;
        color: white !important; border: none !important; font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="cse-hero">
  <h1>📊 CSE Annual Report Analyzer</h1>
  <p>Upload multi-year annual report PDFs. Figures are extracted deterministically
  (no AI guessing) and every value stays traceable to its source page and line.</p>
  <p style="margin-top:0.6rem;font-size:0.8rem;opacity:0.85">Build <code>{APP_VERSION}</code> · multi-company tabs · Dialog EPS/NAVPS</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Multi-company workspace (browser-tab style)
# Each analyzed company is stored under session_state["companies"][id]
# so loading a new company does NOT overwrite previous ones.
# ---------------------------------------------------------------------------
WORKSPACE_FILE = Path.home() / ".cse_analyzer" / "workspace.pkl"


def _load_workspace() -> dict:
    """Reload open company tabs saved by a previous run/refresh."""
    try:
        if WORKSPACE_FILE.exists():
            with open(WORKSPACE_FILE, "rb") as fh:
                data = pickle.load(fh)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_workspace():
    """Persist open tabs so a browser refresh / restart does not wipe them."""
    try:
        WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(WORKSPACE_FILE, "wb") as fh:
            pickle.dump(st.session_state["companies"], fh)
    except Exception:
        pass


if "companies" not in st.session_state:
    st.session_state["companies"] = _load_workspace()  # id -> {name, with_ratios, per_file_status, share_price}
if "active_company_id" not in st.session_state:
    _ids = list(st.session_state["companies"].keys())
    st.session_state["active_company_id"] = _ids[-1] if _ids else None


def _activate(cid):
    """Make a company the active tab (keeps sidebar + top tab bar in sync)."""
    st.session_state["active_company_id"] = cid
    if cid is None:
        st.session_state.pop("company_tab_bar", None)
    else:
        st.session_state["company_tab_bar"] = cid


def _guess_company_name(files) -> str:
    """Best-effort name from the first PDF's first pages ('... PLC' / '... Limited')."""
    try:
        import pypdf
        for f in files:
            reader = pypdf.PdfReader(io.BytesIO(f.getvalue()))
            for pg in reader.pages[:3]:
                txt = pg.extract_text() or ""
                m = re.search(r"([A-Z][A-Za-z0-9&.\-]*(?:\s+(?:of|and|&|the|[A-Z][A-Za-z0-9&.\-]*)){0,5}\s+(?:PLC|Plc|Limited|LIMITED|Ltd))", txt)
                if m:
                    return " ".join(m.group(1).split())
    except Exception:
        pass
    return ""


def _company_id_for(name: str) -> str:
    """Reuse the id of an existing tab with the same name (case-insensitive) so
    re-analyzing UPDATES it; any different name gets its own new tab."""
    base = (name or "Company").strip() or "Company"
    for existing_id, cdata in st.session_state["companies"].items():
        if cdata["name"].strip().lower() == base.lower():
            return existing_id
    return base


with st.sidebar:
    st.markdown("### 1 · Upload reports")
    company_name = st.text_input("Company name", value="", placeholder="e.g. Dialog Axiata (blank = auto-detect)")
    uploaded_files = st.file_uploader(
        "PDFs: annual · interim/quarterly financials · (commentary PDFs rarely have tables)",
        type=["pdf"],
        accept_multiple_files=True,
        key="uploader_main",
    )
    analyze_clicked = st.button(
        "🔍  Analyze reports",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_files,
    )
    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) queued")
        for f in uploaded_files:
            st.caption(f"• {f.name}")

    st.markdown("---")
    st.markdown("### 2 · Open companies (tabs)")
    st.caption("Each Analyze keeps a separate tab — switch without overwriting.")
    companies = st.session_state["companies"]
    if not companies:
        st.info("No company tabs yet. Enter a name, upload PDFs, click Analyze.")
    else:
        for cid, cdata in list(companies.items()):
            cols = st.columns([4, 1])
            is_active = st.session_state["active_company_id"] == cid
            label = f"{'● ' if is_active else ''}{cdata['name']}"
            if cols[0].button(label, key=f"sel_{cid}", use_container_width=True,
                              type="primary" if is_active else "secondary"):
                _activate(cid)
                st.rerun()
            if cols[1].button("✕", key=f"close_{cid}", help=f"Close {cdata['name']}"):
                del st.session_state["companies"][cid]
                if st.session_state["active_company_id"] == cid:
                    remaining = list(st.session_state["companies"].keys())
                    _activate(remaining[-1] if remaining else None)
                _save_workspace()
                st.rerun()
        st.caption(f"{len(companies)} company tab(s) open — switch without losing data.")

    st.markdown("---")
    st.caption("Tip: mix annual reports + quarterly/interim financials. Each Analyze adds/updates a company tab; others stay open.")

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

    name = (company_name or "").strip()
    if not name:
        name = _guess_company_name(uploaded_files)
    if not name:
        name = f"Company {len(st.session_state['companies']) + 1}"
    # Same name -> update that tab; different/blank name -> NEW tab (never overwrites).
    cid = _company_id_for(name)

    prev_price = 0.0
    if cid in st.session_state["companies"]:
        prev_price = float(st.session_state["companies"][cid].get("share_price") or 0.0)

    st.session_state["companies"][cid] = {
        "name": name,
        "with_ratios": with_ratios,
        "per_file_status": per_file_status,
        "share_price": prev_price,
    }
    _activate(cid)
    _save_workspace()
    # Back-compat keys used by older code paths
    st.session_state["with_ratios"] = with_ratios
    st.session_state["per_file_status"] = per_file_status
    st.session_state["company_name"] = name
    st.session_state["share_price"] = prev_price

# Browser-style tab bar across the top: one tab per analyzed company.
_open_ids = list(st.session_state["companies"].keys())
if _open_ids:
    if st.session_state.get("active_company_id") not in _open_ids:
        _activate(_open_ids[-1])
    if st.session_state.get("company_tab_bar") not in _open_ids:
        st.session_state["company_tab_bar"] = st.session_state["active_company_id"]
    _picked = st.radio(
        "Open companies", _open_ids,
        format_func=lambda i: "📈 " + st.session_state["companies"][i]["name"],
        horizontal=True, key="company_tab_bar", label_visibility="collapsed",
    )
    st.session_state["active_company_id"] = _picked

# Resolve active company workspace
_active_id = st.session_state.get("active_company_id")
_active = st.session_state["companies"].get(_active_id) if _active_id else None

if _active is not None:
    with_ratios = _active["with_ratios"]
    per_file_status = _active["per_file_status"]
    company_name = _active["name"]
    # Keep legacy keys in sync for any code still reading them
    st.session_state["with_ratios"] = with_ratios
    st.session_state["per_file_status"] = per_file_status
    st.session_state["company_name"] = company_name
    st.session_state["share_price"] = _active.get("share_price") or 0.0

if _active is not None:

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

    years = [r.get("period_label") or r["year"] for r in with_ratios]
    year_keys = [r.get("period_key") or r["year"] for r in with_ratios]
    latest = with_ratios[-1]
    industry = latest.get("industry") or "industrial"

    # Unit consistency check across years
    units_seen = set()
    for r in with_ratios:
        for ext in (r.get("_extractions") or {}).values():
            u = (ext or {}).get("unit")
            if u and u not in ("unknown", "LKR_per_share"):
                units_seen.add(u)
    mixed_units = len(units_seen) > 1
    primary_unit = sorted(units_seen)[0] if units_seen else "unknown"

    badge_ind = (
        '<span class="cse-badge badge-bank">Bank / FI</span>'
        if industry == "bank"
        else '<span class="cse-badge badge-ind">Industrial</span>'
    )
    unit_label = {
        "LKR_thousand": "Rs. '000",
        "LKR_million": "Rs. million",
        "LKR": "Rs. (full)",
    }.get(primary_unit, primary_unit)
    badge_unit = f'<span class="cse-badge badge-unit">Unit: {unit_label}</span>'
    badge_warn = (
        '<span class="cse-badge badge-warn">Mixed units across years — compare carefully</span>'
        if mixed_units else ""
    )

    st.markdown(
        f"## {company_name}  "
        f"<span style='color:#64748b;font-weight:500;font-size:1.1rem'>{years[0]} → {years[-1]}</span><br>"
        f"{badge_ind}{badge_unit}{badge_warn}",
        unsafe_allow_html=True,
    )

    # ---- KPI strip (latest year) ----
    lr = latest.get("_ratios") or {}
    top_line = latest.get("revenue") if latest.get("revenue") is not None else latest.get("gross_income")
    top_label = "Revenue" if latest.get("revenue") is not None else "Gross Income"
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric(f"{top_label} ({latest['year']})", f"{top_line:,.0f}" if top_line is not None else "—")
    with k2:
        np_ = latest.get("net_profit")
        st.metric("Net Profit", f"{np_:,.0f}" if np_ is not None else "—")
    with k3:
        v = lr.get("roe_pct")
        st.metric("ROE", f"{v:.1f}%" if v is not None else "—")
    with k4:
        v = lr.get("net_profit_margin_pct")
        st.metric("Net Margin", f"{v:.1f}%" if v is not None else "—")
    with k5:
        v = latest.get("eps")
        st.metric("EPS", f"{v:.2f}" if v is not None else "—")

    if mixed_units:
        st.warning(
            "Reports appear to use **different unit scales** (e.g. Rs.'000 vs full Rs.). "
            "YoY growth and CAGRs can be distorted. Check the Verification tab and source lines."
        )

    with st.expander("📚 New to annual reports? Learn the basics", expanded=False):
        st.markdown(BEGINNER_GUIDE)

    # Extra metrics (Advanced / Banking / Construction / Investigate) are
    # calculated on top of the existing data; nothing above is modified.
    with_extra = compute_extra_series(with_ratios)
    extra_labels = ["🔵 Advanced"]
    if industry == "bank":
        extra_labels.append("🏦 Banking")
    if any(r.get(k) is not None for r in with_extra for k in ("contract_assets", "contract_liabilities")):
        extra_labels.append("🏗️ Construction")
    extra_labels.append("🧭 Things to Investigate")

    tab_table, tab_charts, tab_flags, tab_prebuy, tab_value, tab_verify, tab_download, *extra_tabs = st.tabs(
        ["📋 5-Year Table", "📈 Charts", "🚩 Red Flags", "🔍 Before You Buy",
         "💰 Valuation & Sizing", "⚠️ Verification", "⬇️ Download"] + extra_labels
    )
    extra_tab_by_label = dict(zip(extra_labels, extra_tabs))

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
                    row[str(r.get("period_label") or r["year"])] = f"{v:,.2f}" if key == "eps" else f"{v:,.0f}"
                else:
                    row[str(r.get("period_label") or r["year"])] = "—"
            if any_present:
                table_rows.append(row)
                if explain_mode:
                    exp = get_explanation(key)
                    with st.expander(f"📖 {label}"):
                        st.markdown(f"**What it means:** {exp['plain']}")
                        if exp.get("watch_for"):
                            st.markdown(f"**Watch for:** {exp['watch_for']}")
                        if exp.get("learn_more"):
                            links_md = " · ".join(
                                f"[{l['title']}]({l['url']})" for l in exp["learn_more"]
                            )
                            st.markdown(f"**Learn more:** {links_md}")
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
                    row[str(r.get("period_label") or r["year"])] = f"{v:,.2f}"
                else:
                    row[str(r.get("period_label") or r["year"])] = "—"
            if any_present:
                ratio_rows.append(row)
                if explain_mode:
                    exp = get_explanation(key)
                    with st.expander(f"📖 {label}"):
                        st.markdown(f"**What it means:** {exp['plain']}")
                        if exp.get("watch_for"):
                            st.markdown(f"**Watch for:** {exp['watch_for']}")
                        if exp.get("learn_more"):
                            links_md = " · ".join(
                                f"[{l['title']}]({l['url']})" for l in exp["learn_more"]
                            )
                            st.markdown(f"**Learn more:** {links_md}")
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
            orig = ext.get("original_label") or ""
            orig_bit = f" · Original label: «{orig}»" if orig else ""
            st.markdown(f"**{METRIC_LABELS[metric_choice]} — {year_choice}**: "
                        f"{ext['value']:,.2f}  \n"
                        f"Method: {badge} · Page: {ext['page']} · Unit: {ext['unit']}{orig_bit}")
            if ext["notes"]:
                st.info(ext["notes"])
            st.code(ext["source_line"], language=None)
        else:
            st.caption("No value extracted for this metric/year.")

    with tab_charts:
        df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in with_ratios])
        df["year"] = df["year"].astype(str)
        df = df.set_index("year")

        # Adaptive chart set: banks get NII + impairment; industrials get revenue
        if industry == "bank":
            chart_pairs = [
                ("gross_income", "Gross Income"),
                ("net_interest_income", "Net Interest Income"),
                ("net_profit", "Net Profit"),
                ("credit_impairment", "Credit Impairment / ECL"),
                ("total_assets", "Total Assets"),
                ("eps", "EPS"),
            ]
        else:
            chart_pairs = [
                ("revenue", "Revenue"),
                ("net_profit", "Net Profit"),
                ("operating_profit", "Operating Profit"),
                ("total_assets", "Total Assets"),
                ("operating_cash_flow", "Operating Cash Flow"),
                ("eps", "EPS"),
            ]

        try:
            import plotly.express as px
            use_plotly = True
        except ImportError:
            use_plotly = False

        c1, c2 = st.columns(2)
        for i, (key, label) in enumerate(chart_pairs):
            if key not in df.columns or df[key].isna().all():
                continue
            target = c1 if i % 2 == 0 else c2
            with target:
                st.caption(label)
                series = df[[key]].dropna()
                if use_plotly and not series.empty:
                    fig = px.bar(series, y=key, labels={key: label, "year": "Year"})
                    fig.update_layout(
                        margin=dict(l=10, r=10, t=10, b=10), height=260,
                        showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.bar_chart(series)

        st.caption("Profitability ratios (%)")
        ratio_df = pd.DataFrame([
            {"year": str(r["year"]), **{k: r["_ratios"].get(k) for k in
             ["roe_pct", "roa_pct", "net_profit_margin_pct"]}}
            for r in with_ratios
        ]).set_index("year")
        # Force every column to a uniform float dtype. Without this, a
        # ratio that's None for every year in the series (e.g. ROA when
        # prior-year Total Assets was never found) keeps pandas' inferred
        # "object" dtype instead of float64, while the other columns are
        # float64 - Plotly Express's wide-form melt then fails with
        # "columns of different type" because it can't concatenate them.
        ratio_df = ratio_df.apply(pd.to_numeric, errors="coerce")
        ratio_df = ratio_df.dropna(axis=1, how="all")  # drop ratios with zero data at all

        if ratio_df.empty:
            st.caption("Not enough data to chart profitability ratios yet.")
        elif use_plotly:
            fig = px.line(ratio_df, markers=True, labels={"value": "%", "variable": "Ratio"})
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
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

    with tab_prebuy:
        st.caption(
            "A structured pre-purchase review of the numbers we extracted. "
            "This consolidates growth, profitability, strength, shareholder value, "
            "valuation inputs, and risk patterns in one place. It is **not** a buy/sell signal."
        )
        with st.expander("📚 How to use this checklist (read this first)", expanded=False):
            st.markdown(PRE_BUY_GUIDE)

        # Reuse price from valuation if already entered in session, else local input
        default_pb = float(st.session_state.get("share_price", 0.0) or 0.0)
        pb_price = st.number_input(
            "Current share price (Rs.) — used for valuation block below",
            min_value=0.0, step=0.5, value=default_pb, key=f"prebuy_price_{st.session_state.get('active_company_id')}",
        )
        if pb_price:
            st.session_state["share_price"] = pb_price
            if st.session_state.get("active_company_id") and st.session_state["active_company_id"] in st.session_state.get("companies", {}):
                _c = st.session_state["companies"][st.session_state["active_company_id"]]
            if _c.get("share_price") != pb_price:
                _c["share_price"] = pb_price
                _save_workspace()
        pb = compute_pre_buy(with_ratios, share_price=pb_price)
        explain_pb = st.toggle("🎓 Explain terms in this checklist", value=False, key="explain_prebuy")

        status_icon = {"ok": "✅", "warn": "⚠️", "unknown": "❔"}

        # ----- 1. Growth -----
        st.subheader("1. Growth — multi-year CAGR")
        g = pb["growth"]
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            v = g.get("revenue_cagr_pct")
            span = g.get("revenue_span_years") or 0
            st.metric(
                "Revenue CAGR",
                f"{v:.1f}%" if v is not None else "—",
                help=f"Over {span} year(s) of available data" if span else None,
            )
            if explain_pb:
                exp = get_explanation("revenue_cagr")
                st.caption(exp["plain"])
                if exp.get("watch_for"):
                    st.caption(f"**Watch for:** {exp['watch_for']}")
        with gc2:
            v = g.get("net_profit_cagr_pct")
            span = g.get("net_profit_span_years") or 0
            st.metric(
                "Net Profit CAGR",
                f"{v:.1f}%" if v is not None else "—",
                help=f"Over {span} year(s)" if span else None,
            )
            if explain_pb:
                exp = get_explanation("net_profit_cagr")
                st.caption(exp["plain"])
                if exp.get("watch_for"):
                    st.caption(f"**Watch for:** {exp['watch_for']}")
        with gc3:
            v = g.get("eps_cagr_pct")
            span = g.get("eps_span_years") or 0
            st.metric(
                "EPS CAGR",
                f"{v:.1f}%" if v is not None else "—",
                help=f"Over {span} year(s)" if span else None,
            )
            if explain_pb:
                exp = get_explanation("eps_cagr")
                st.caption(exp["plain"])
                if exp.get("watch_for"):
                    st.caption(f"**Watch for:** {exp['watch_for']}")
        st.caption(
            f"Based on {g.get('n_years_available', 0)} year(s) extracted. "
            "CAGR needs a positive starting value and ≥2 years; otherwise shows —."
        )

        # ----- 2. Profitability -----
        st.subheader("2. Profitability")
        p = pb["profitability"]
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            v = p.get("roe_pct")
            st.metric("ROE", f"{v:.1f}%" if v is not None else "—",
                      help=p.get("roe_basis") or None)
            if explain_pb:
                exp = get_explanation("roe_pct")
                st.caption(exp["plain"])
        with pc2:
            v = p.get("roa_pct")
            st.metric("ROA", f"{v:.1f}%" if v is not None else "—",
                      help=p.get("roa_basis") or None)
            if explain_pb:
                exp = get_explanation("roa_pct")
                st.caption(exp["plain"])
        with pc3:
            v = p.get("net_profit_margin_pct")
            trend = p.get("margin_trend")
            delta = {"up": "improving", "down": "declining", "flat": "stable"}.get(trend)
            st.metric("Net Profit Margin", f"{v:.1f}%" if v is not None else "—",
                      delta=delta if delta else None)
            if explain_pb:
                exp = get_explanation("net_profit_margin_pct")
                st.caption(exp["plain"])

        # ----- 3. Financial strength -----
        st.subheader("3. Financial strength")
        s = pb["strength"]
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            v = s.get("debt_to_equity")
            st.metric("Debt / Equity", f"{v:.2f}" if v is not None else "—")
            if explain_pb:
                exp = get_explanation("debt_to_equity")
                st.caption(exp["plain"])
        with sc2:
            ocf = s.get("operating_cash_flow_latest")
            st.metric("Operating Cash Flow (latest)", f"{ocf:,.0f}" if ocf is not None else "—")
            if explain_pb:
                exp = get_explanation("operating_cash_flow")
                st.caption(exp["plain"])
        with sc3:
            st.metric("Interest Coverage", "Manual check")
            st.caption(s.get("interest_coverage_note", ""))
            if explain_pb:
                exp = get_explanation("interest_coverage")
                st.caption(exp["plain"])
                if exp.get("watch_for"):
                    st.caption(f"**Watch for:** {exp['watch_for']}")

        # ----- 4. Shareholder value -----
        st.subheader("4. Shareholder value")
        sh = pb["shareholder"]
        shc1, shc2, shc3 = st.columns(3)
        with shc1:
            v = sh.get("navps_latest")
            st.metric("NAVPS (approx.)", f"{v:,.2f}" if v is not None else "—")
            if explain_pb:
                exp = get_explanation("navps")
                st.caption(exp["plain"])
                if exp.get("watch_for"):
                    st.caption(f"**Watch for:** {exp['watch_for']}")
        with shc2:
            v = sh.get("navps_cagr_pct")
            st.metric("NAVPS Growth (CAGR)", f"{v:.1f}%" if v is not None else "—")
        with shc3:
            v = sh.get("dps_latest")
            st.metric("Dividend / Share (approx.)", f"{v:,.2f}" if v is not None else "—")
            if explain_pb:
                exp = get_explanation("dividend_per_share")
                st.caption(exp["plain"])

        # Dividend / NAVPS history table
        hist_rows = []
        for nav, dps in zip(sh.get("navps_by_year", []), sh.get("dps_by_year", [])):
            hist_rows.append({
                "Year": nav["year"],
                "NAVPS (approx.)": f"{nav['navps']:,.2f}" if nav.get("navps") is not None else "—",
                "DPS (approx.)": f"{dps['dps']:,.2f}" if dps.get("dps") is not None else "—",
                "Dividend Paid (total)": (
                    f"{dps['dividend_paid']:,.0f}" if dps.get("dividend_paid") is not None else "—"
                ),
            })
        if hist_rows:
            st.dataframe(pd.DataFrame(hist_rows).set_index("Year"), use_container_width=True)
            st.caption(sh.get("dividend_history_note", ""))

        # ----- 5. Valuation -----
        st.subheader("5. Valuation")
        val = pb["valuation"]
        if val.get("share_price"):
            vc1, vc2, vc3, vc4 = st.columns(4)
            with vc1:
                v = val.get("pe_ratio")
                st.metric("P/E", f"{v:.2f}" if v is not None else "—")
                if explain_pb:
                    exp = get_explanation("pe_ratio")
                    st.caption(exp["plain"])
            with vc2:
                v = val.get("pb_ratio")
                st.metric("P/B", f"{v:.2f}" if v is not None else "—")
                if explain_pb:
                    exp = get_explanation("pb_ratio")
                    st.caption(exp["plain"])
            with vc3:
                v = val.get("dividend_yield_pct")
                st.metric("Dividend Yield", f"{v:.2f}%" if v is not None else "—")
                if explain_pb:
                    exp = get_explanation("dividend_yield_pct")
                    st.caption(exp["plain"])
            with vc4:
                v = val.get("price_vs_navps")
                st.metric("Price / NAVPS", f"{v:.2f}×" if v is not None else "—")
                st.caption("Same idea as P/B when NAVPS ≈ book value per share.")
        else:
            st.info(val.get("note", "Enter a share price above to see valuation ratios."))

        # ----- 6. Risk flags -----
        st.subheader("6. Risk pattern flags")
        for item in pb.get("risk_items", []):
            icon = status_icon.get(item["status"], "•")
            with st.container(border=True):
                st.markdown(f"{icon} **{item['title']}**")
                st.caption(item["detail"])

        st.markdown("---")
        st.caption(
            "All figures above are derived from the same extracted annual-report numbers "
            "shown in the other tabs. Always verify critical values against the source PDF "
            "(use the Table → source lookup and the Verification tab)."
        )

        # ----- PDF export of this tab -----
        st.markdown("### 📄 Download this checklist as a PDF")
        st.caption(
            "A standalone, printable PDF containing everything on this tab — separate from "
            "the full 5-year financials report in the Download tab."
        )
        if st.button("Generate Pre-Buy PDF", key="gen_prebuy_pdf"):
            import tempfile
            from pre_buy_pdf import build_pre_buy_pdf
            pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            build_pre_buy_pdf(company_name, pb, pdf_path,
                               industry=with_ratios[-1].get("industry", "industrial"))
            with open(pdf_path, "rb") as f:
                st.session_state["prebuy_pdf_bytes"] = f.read()
            os.unlink(pdf_path)

        if "prebuy_pdf_bytes" in st.session_state:
            st.download_button(
                "⬇️ Download Pre-Buy Checklist (.pdf)",
                st.session_state["prebuy_pdf_bytes"],
                file_name=f"{company_name.replace(' ', '_')}_Pre_Buy_Checklist.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with tab_value:
        st.subheader("💰 Valuation (needs today's share price)")
        st.caption(
            "The annual report doesn't contain the current market price — the CSE trading "
            "price changes daily. Enter it yourself below. These ratios are INPUTS to your "
            "own thinking, not a recommendation."
        )
        latest = with_ratios[-1]
        default_price = float(st.session_state.get("share_price", 0.0) or 0.0)
        price = st.number_input("Current share price (Rs.)", min_value=0.0, step=0.5, value=default_price,
                                key=f"val_price_{st.session_state.get('active_company_id')}")
        st.session_state["share_price"] = price
        if st.session_state.get("active_company_id") and st.session_state["active_company_id"] in st.session_state.get("companies", {}):
            _c = st.session_state["companies"][st.session_state["active_company_id"]]
            if _c.get("share_price") != price:
                _c["share_price"] = price
                _save_workspace()

        if price > 0:
            # Prefer profit attributable to equity holders (excludes NCI) —
            # that is the base published EPS uses, so share-count approx is tighter.
            np_for_val = latest.get("profit_attributable")
            if np_for_val is None:
                np_for_val = latest.get("net_profit")
            val = compute_valuation(
                share_price=price,
                eps=latest.get("eps"),
                total_equity=latest.get("total_equity"),
                net_profit=np_for_val,
                dividend_paid=latest.get("dividend_paid"),
                dividend_per_share_direct=latest.get("dividend_per_share"),
            )
            explain_val = st.toggle("🎓 Explain these terms", value=False, key="explain_val")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("P/E Ratio", f"{val['pe_ratio']:.2f}" if val["pe_ratio"] else "—")
                if explain_val:
                    exp = get_explanation("pe_ratio")
                    st.caption(exp["plain"])
                    if exp.get("learn_more"):
                        st.caption(" · ".join(f"[{l['title']}]({l['url']})" for l in exp["learn_more"]))
            with c2:
                st.metric("P/B Ratio (approx.)", f"{val['pb_ratio']:.2f}" if val["pb_ratio"] else "—")
                if explain_val:
                    exp = get_explanation("pb_ratio")
                    st.caption(exp["plain"])
                    if exp.get("learn_more"):
                        st.caption(" · ".join(f"[{l['title']}]({l['url']})" for l in exp["learn_more"]))
            with c3:
                st.metric("Dividend Yield (approx.)",
                          f"{val['dividend_yield_pct']:.2f}%" if val["dividend_yield_pct"] else "—")
                if explain_val:
                    exp = get_explanation("dividend_yield_pct")
                    st.caption(exp["plain"])
                    if exp.get("learn_more"):
                        st.caption(" · ".join(f"[{l['title']}]({l['url']})" for l in exp["learn_more"]))

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
        pd.DataFrame(with_ratios).drop(columns=["_extractions", "_ratios", "_extra"], errors="ignore").to_csv(csv_buf, index=False)
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
    with extra_tab_by_label["🔵 Advanced"]:
        advanced_ui.render_advanced(with_extra)
    if "🏦 Banking" in extra_tab_by_label:
        with extra_tab_by_label["🏦 Banking"]:
            advanced_ui.render_bank(with_extra)
    if "🏗️ Construction" in extra_tab_by_label:
        with extra_tab_by_label["🏗️ Construction"]:
            advanced_ui.render_construction(with_extra)
    with extra_tab_by_label["🧭 Things to Investigate"]:
        advanced_ui.render_investigate(with_extra)
else:
    st.info("👈 Upload one or more annual report PDFs in the sidebar, then click **ANALYZE REPORTS**.")
