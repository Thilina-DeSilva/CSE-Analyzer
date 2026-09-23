"""
Standalone PDF report for the Pre-Buy Checklist tab.

Separate from report_builder.py (which handles the main 5-year
financials/ratios Markdown+CSV+JSON report) - this focuses ONLY on the
pre-buy analysis: growth CAGR, profitability, financial strength,
shareholder value, valuation inputs, and risk pattern flags, laid out
as a printable one-stop document a beginner could read before deciding
whether to look closer at a stock.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)


STATUS_COLORS = {"ok": colors.HexColor("#1a7f37"), "warn": colors.HexColor("#b45309"),
                  "unknown": colors.HexColor("#6b7280")}
STATUS_LABEL = {"ok": "OK", "warn": "WATCH", "unknown": "UNKNOWN"}


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontSize=20, spaceAfter=4))
    styles.add(ParagraphStyle(name="SubTitle", parent=styles["Normal"], fontSize=11,
                               textColor=colors.HexColor("#555555"), spaceAfter=14))
    styles.add(ParagraphStyle(name="SectionHead", parent=styles["Heading2"], fontSize=13,
                               spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1f2937")))
    styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=9.5, leading=13))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=11,
                               textColor=colors.HexColor("#6b7280")))
    styles.add(ParagraphStyle(name="Disclaimer", parent=styles["Normal"], fontSize=8.5, leading=12,
                               textColor=colors.HexColor("#7a1f1f"), borderColor=colors.HexColor("#f3c9c9"),
                               borderWidth=1, borderPadding=8, backColor=colors.HexColor("#fdf2f2")))
    return styles


def _fmt(v, decimals=2, suffix=""):
    if v is None:
        return "—"
    return f"{v:,.{decimals}f}{suffix}"


def _metric_table(rows, styles, col_widths=None):
    """rows: list of (label, value) tuples -> a simple 2-col table."""
    data = [[Paragraph(f"<b>{label}</b>", styles["Body"]), Paragraph(str(value), styles["Body"])]
            for label, value in rows]
    t = Table(data, colWidths=col_widths or [70 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f9fafb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build_pre_buy_pdf(company_name: str, pb: dict, output_path: str, industry: str = "industrial"):
    """
    company_name: str
    pb: the dict returned by pre_buy.compute_pre_buy()
    output_path: where to write the .pdf
    """
    styles = _styles()
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=16 * mm, bottomMargin=16 * mm)
    story = []

    years = pb.get("years", [])
    year_range = f"{years[0]}–{years[-1]}" if len(years) >= 2 else (str(years[0]) if years else "N/A")

    story.append(Paragraph(f"{company_name} — Pre-Buy Checklist", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Structured review of {year_range} extracted from the company's own annual report(s). "
        f"Industry classification: {'Bank / Financial Institution' if industry == 'bank' else 'Industrial / Non-bank'}.",
        styles["SubTitle"]))

    story.append(Paragraph(
        "<b>This is not a buy/sell recommendation.</b> It is a structured summary of numbers "
        "extracted deterministically from the annual report PDF(s), meant to be read alongside "
        "the original report — not instead of it. No tool reading one company's financial "
        "statements can know your budget, risk tolerance, or overall portfolio. Verify anything "
        "important against the source PDF before acting on it.",
        styles["Disclaimer"]))

    # ---------------- 1. Growth ----------------
    story.append(Paragraph("1. Growth (CAGR)", styles["SectionHead"]))
    g = pb.get("growth", {})
    rows = [
        ("Revenue / Gross Income CAGR",
         f"{_fmt(g.get('revenue_cagr_pct'), 1, '%')}  (over {g.get('revenue_span_years', 0)} yr span)"),
        ("Net Profit CAGR",
         f"{_fmt(g.get('net_profit_cagr_pct'), 1, '%')}  (over {g.get('net_profit_span_years', 0)} yr span)"),
        ("EPS CAGR",
         f"{_fmt(g.get('eps_cagr_pct'), 1, '%')}  (over {g.get('eps_span_years', 0)} yr span)"),
        ("Years of data used", str(g.get("n_years_available", 0))),
    ]
    story.append(_metric_table(rows, styles))
    story.append(Paragraph(
        "CAGR needs a positive starting value and at least 2 years of data — shows '—' otherwise "
        "(e.g. a loss-making starting year makes CAGR mathematically undefined).", styles["Small"]))

    # ---------------- 2. Profitability ----------------
    story.append(Paragraph("2. Profitability (latest year)", styles["SectionHead"]))
    p = pb.get("profitability", {})
    trend_word = {"up": "improving", "down": "declining", "flat": "stable"}.get(p.get("margin_trend"), "—")
    rows = [
        ("Return on Equity (ROE)", f"{_fmt(p.get('roe_pct'), 1, '%')}  ({p.get('roe_basis', '')})"),
        ("Return on Assets (ROA)", f"{_fmt(p.get('roa_pct'), 1, '%')}  ({p.get('roa_basis', '')})"),
        ("Net Profit Margin", f"{_fmt(p.get('net_profit_margin_pct'), 1, '%')}  (trend: {trend_word})"),
    ]
    story.append(_metric_table(rows, styles))

    # ---------------- 3. Financial strength ----------------
    story.append(Paragraph("3. Financial Strength", styles["SectionHead"]))
    s = pb.get("strength", {})
    rows = [
        ("Debt / Equity (latest)", _fmt(s.get("debt_to_equity"))),
        ("Debt / Equity (prior year)", _fmt(s.get("debt_to_equity_prior"))),
        ("Operating Cash Flow (latest)", _fmt(s.get("operating_cash_flow_latest"), 0)),
        ("Interest Coverage", "Manual check — " + s.get("interest_coverage_note", "")),
    ]
    story.append(_metric_table(rows, styles))

    # ---------------- 4. Shareholder value ----------------
    story.append(Paragraph("4. Shareholder Value", styles["SectionHead"]))
    sh = pb.get("shareholder", {})
    rows = [
        ("NAVPS (approx., latest)", _fmt(sh.get("navps_latest"))),
        ("NAVPS Growth (CAGR)", _fmt(sh.get("navps_cagr_pct"), 1, "%")),
        ("Dividend / Share (approx., latest)", _fmt(sh.get("dps_latest"))),
    ]
    story.append(_metric_table(rows, styles))

    hist = sh.get("navps_by_year", [])
    dps_hist = {d["year"]: d for d in sh.get("dps_by_year", [])}
    if hist:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Dividend & NAVPS history:", styles["Body"]))
        head = ["Year", "NAVPS (approx.)", "DPS (approx.)", "Dividend Paid (total)"]
        data = [head]
        for row in hist:
            d = dps_hist.get(row["year"], {})
            data.append([
                str(row["year"]),
                _fmt(row.get("navps")),
                _fmt(d.get("dps")),
                _fmt(d.get("dividend_paid"), 0),
            ])
        t = Table(data, colWidths=[25 * mm, 45 * mm, 40 * mm, 50 * mm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Paragraph(sh.get("dividend_history_note", ""), styles["Small"]))

    # ---------------- 5. Valuation ----------------
    story.append(Paragraph("5. Valuation", styles["SectionHead"]))
    val = pb.get("valuation", {})
    if val.get("share_price"):
        rows = [
            ("Share price used", _fmt(val.get("share_price"))),
            ("P/E Ratio", _fmt(val.get("pe_ratio"))),
            ("P/B Ratio", _fmt(val.get("pb_ratio"))),
            ("Dividend Yield", _fmt(val.get("dividend_yield_pct"), 2, "%")),
            ("Price / NAVPS", f"{_fmt(val.get('price_vs_navps'))}×"),
        ]
        story.append(_metric_table(rows, styles))
    else:
        story.append(Paragraph(
            "No share price was entered when this report was generated — valuation ratios "
            "need today's CSE trading price, which isn't in the annual report itself. "
            "Re-generate this report from the app after entering a price to include P/E, "
            "P/B, and Dividend Yield.", styles["Body"]))

    # ---------------- 6. Risk pattern flags ----------------
    story.append(Paragraph("6. Risk Pattern Flags", styles["SectionHead"]))
    for item in pb.get("risk_items", []):
        color = STATUS_COLORS.get(item["status"], colors.black)
        label = STATUS_LABEL.get(item["status"], item["status"].upper())
        story.append(Paragraph(
            f'<font color="{color.hexval()}"><b>[{label}]</b></font> <b>{item["title"]}</b>',
            styles["Body"]))
        story.append(Paragraph(item["detail"], styles["Small"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by a deterministic PDF-extraction pipeline (no AI-guessed figures). "
        "Every underlying number is traceable to a page and source line in the app's "
        "Table and Verification tabs. This document is for personal research only and "
        "does not constitute investment advice.", styles["Small"]))

    doc.build(story)
    return output_path
