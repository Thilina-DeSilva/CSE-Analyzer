"""
Pre-buy company analysis checklist.

Pulls together 5-year growth (CAGR), profitability, financial strength,
shareholder value, valuation inputs, and risk-pattern flags into one
structured view. Everything is deterministic arithmetic on numbers
already extracted — nothing is invented.

Interest coverage is left as a manual check because interest/finance
cost is not currently extracted as a line item.
"""

from __future__ import annotations

from typing import Optional


def _safe_div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def _cagr(start: Optional[float], end: Optional[float], years: int) -> Optional[float]:
    """Compound annual growth rate as a percent. Needs positive start
    and at least 1 year span. Returns None if not computable."""
    if start is None or end is None or years < 1:
        return None
    if start <= 0:
        # Negative or zero base makes CAGR undefined / misleading
        return None
    try:
        return ((end / start) ** (1 / years) - 1) * 100
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


def _first_last_present(records: list, key: str):
    """Return (first_value, last_value, year_span) for a metric key,
    skipping years where the value is missing. year_span is number of
    intervals between first and last present year."""
    pairs = [(r["year"], r.get(key)) for r in records if r.get(key) is not None]
    if len(pairs) < 2:
        return None, None, 0
    y0, v0 = pairs[0]
    y1, v1 = pairs[-1]
    return v0, v1, max(0, y1 - y0)


def _top_line(record: dict) -> Optional[float]:
    if record.get("revenue") is not None:
        return record["revenue"]
    return record.get("gross_income")


def compute_pre_buy(with_ratios: list, share_price: float = 0.0) -> dict:
    """
    Build the full pre-buy checklist dict from merged, ratio'd records
    (oldest → newest) and an optional current share price.
    """
    if not with_ratios:
        return {"years": [], "sections": {}}

    from ratios import find_prior_comparable, _period_type

    latest = with_ratios[-1]
    # Same-period prior only (FY→FY, Q1→Q1, H1→H1, …)
    prior = find_prior_comparable(with_ratios, len(with_ratios) - 1)
    latest_r = latest.get("_ratios", {})
    prior_r = prior.get("_ratios", {}) if prior else {}

    # For multi-year CAGR use only records matching the latest period type
    # so a Q1 series never compounds against full-year annuals.
    pt = _period_type(latest)
    peer_series = [r for r in with_ratios if _period_type(r) == pt]
    years = [r["year"] for r in peer_series if r.get("year") is not None]
    n_intervals = years[-1] - years[0] if len(years) >= 2 else 0

    # --- Growth (CAGR over available same-period span) ---
    rev_pairs = [(r["year"], _top_line(r)) for r in peer_series if _top_line(r) is not None]
    if len(rev_pairs) >= 2:
        rev0, rev1 = rev_pairs[0][1], rev_pairs[-1][1]
        rev_span = rev_pairs[-1][0] - rev_pairs[0][0]
    else:
        rev0 = rev1 = None
        rev_span = 0

    np_pairs = [(r["year"], r.get("net_profit")) for r in peer_series if r.get("net_profit") is not None]
    if len(np_pairs) >= 2:
        np0, np1 = np_pairs[0][1], np_pairs[-1][1]
        np_span = np_pairs[-1][0] - np_pairs[0][0]
    else:
        np0 = np1 = None
        np_span = 0

    eps_pairs = [(r["year"], r.get("eps")) for r in peer_series if r.get("eps") is not None]
    if len(eps_pairs) >= 2:
        eps0, eps1 = eps_pairs[0][1], eps_pairs[-1][1]
        eps_span = eps_pairs[-1][0] - eps_pairs[0][0]
    else:
        eps0 = eps1 = None
        eps_span = 0

    growth = {
        "revenue_cagr_pct": _cagr(rev0, rev1, rev_span) if rev_span else None,
        "revenue_span_years": rev_span,
        "net_profit_cagr_pct": _cagr(np0, np1, np_span) if np_span else None,
        "net_profit_span_years": np_span,
        "eps_cagr_pct": _cagr(eps0, eps1, eps_span) if eps_span else None,
        "eps_span_years": eps_span,
        "n_years_available": len(years),
    }

    # --- Profitability (latest + trend) ---
    profitability = {
        "roe_pct": latest_r.get("roe_pct"),
        "roe_basis": latest_r.get("roe_basis"),
        "roa_pct": latest_r.get("roa_pct"),
        "roa_basis": latest_r.get("roa_basis"),
        "net_profit_margin_pct": latest_r.get("net_profit_margin_pct"),
        "margin_trend": None,  # "up" | "down" | "flat" | None
    }
    m1 = prior_r.get("net_profit_margin_pct")
    m2 = latest_r.get("net_profit_margin_pct")
    if m1 is not None and m2 is not None:
        if m2 > m1 + 0.5:
            profitability["margin_trend"] = "up"
        elif m2 < m1 - 0.5:
            profitability["margin_trend"] = "down"
        else:
            profitability["margin_trend"] = "flat"

    # --- Financial strength ---
    ocf_series = [r.get("operating_cash_flow") for r in with_ratios]
    strength = {
        "debt_to_equity": latest_r.get("debt_to_equity"),
        "debt_to_equity_prior": prior_r.get("debt_to_equity") if prior else None,
        "operating_cash_flow_latest": latest.get("operating_cash_flow"),
        "operating_cash_flow_series": ocf_series,
        "interest_coverage": None,  # not extractable yet
        "interest_coverage_note": (
            "Not auto-calculated — look up 'Finance costs' / 'Interest expense' "
            "on the income statement and divide Operating Profit by that figure. "
            "Rule of thumb: >3× is comfortable for most non-financial companies."
        ),
    }

    # --- Shareholder value (NAVPS ≈ book value per share via approx shares) ---
    # Restricted to same period type as latest (FY series, or Q1 series, …)
    navps_by_year = []
    dps_by_year = []
    for r in peer_series:
        np_ = r.get("profit_attributable")
        if np_ is None:
            np_ = r.get("net_profit")
        eps = r.get("eps")
        eq = r.get("total_equity")
        div = r.get("dividend_paid")
        direct_dps = r.get("dividend_per_share")  # exact, when the report states it
        direct_navps = r.get("navps")
        shares = None
        if np_ is not None and eps and eps != 0:
            shares = np_ / eps
        if direct_navps is not None:
            navps = direct_navps
        else:
            navps = (eq / shares) if (eq is not None and shares) else None
        if direct_dps is not None:
            dps = direct_dps
            dps_is_exact = True
        else:
            dps = (abs(div) / shares) if (div is not None and shares) else None
            dps_is_exact = False
        navps_by_year.append({"year": r["year"], "navps": navps, "approx_shares": shares})
        dps_by_year.append({"year": r["year"], "dps": dps, "dividend_paid": div, "dps_is_exact": dps_is_exact})

    nav_vals = [x["navps"] for x in navps_by_year if x["navps"] is not None]
    nav_growth = None
    if len(nav_vals) >= 2 and nav_vals[0] and nav_vals[0] > 0:
        span = years[-1] - years[0]
        if span >= 1:
            nav_growth = _cagr(nav_vals[0], nav_vals[-1], span)

    shareholder = {
        "navps_latest": navps_by_year[-1]["navps"] if navps_by_year else None,
        "navps_by_year": navps_by_year,
        "navps_cagr_pct": nav_growth,
        "dps_by_year": dps_by_year,
        "dps_latest": dps_by_year[-1]["dps"] if dps_by_year else None,
        "dividend_history_note": (
            "DPS is approximated as |Dividend Paid| ÷ (Net Profit ÷ EPS). "
            "Treat as indicative — preferred shares / special dividends can distort it."
        ),
    }

    # --- Valuation (needs price) ---
    valuation = {
        "share_price": share_price if share_price and share_price > 0 else None,
        "pe_ratio": None,
        "pb_ratio": None,
        "dividend_yield_pct": None,
        "price_vs_navps": None,  # price / navps
        "note": "Enter current share price in the Valuation tab (or below) to fill these.",
    }
    if share_price and share_price > 0:
        eps_l = latest.get("eps")
        if eps_l and eps_l != 0:
            valuation["pe_ratio"] = share_price / eps_l
        nav = shareholder["navps_latest"]
        if nav and nav != 0:
            valuation["pb_ratio"] = share_price / nav
            valuation["price_vs_navps"] = share_price / nav
        dps_l = shareholder["dps_latest"]
        if dps_l is not None and share_price:
            valuation["dividend_yield_pct"] = (dps_l / share_price) * 100

    # --- Risk pattern flags (checklist style) ---
    risk_items = []

    # Debt rising
    d1 = strength["debt_to_equity_prior"]
    d2 = strength["debt_to_equity"]
    if d1 is not None and d2 is not None and d1 > 0 and d2 > d1 * 1.15:
        risk_items.append({
            "id": "debt_rising",
            "status": "warn",
            "title": "Debt rising",
            "detail": f"Debt/Equity moved from {d1:.2f} → {d2:.2f}. Check what the extra debt funded and whether interest is covered.",
        })
    elif d2 is not None:
        risk_items.append({
            "id": "debt_rising",
            "status": "ok",
            "title": "Debt not rising sharply",
            "detail": f"Latest Debt/Equity is {d2:.2f}." + (f" Prior year was {d1:.2f}." if d1 is not None else ""),
        })
    else:
        risk_items.append({
            "id": "debt_rising",
            "status": "unknown",
            "title": "Debt trend unknown",
            "detail": "Debt or equity not fully extracted for comparison.",
        })

    # Cash flow weaker than profit
    ocf = latest.get("operating_cash_flow")
    np_ = latest.get("net_profit")
    if ocf is not None and np_ is not None:
        if np_ > 0 and ocf < np_ * 0.7:
            risk_items.append({
                "id": "cf_weaker",
                "status": "warn",
                "title": "Cash flow weaker than profit",
                "detail": (
                    f"Operating cash flow ({ocf:,.0f}) is well below net profit ({np_:,.0f}). "
                    "Can be working-capital timing, or a sign earnings quality needs a closer look."
                ),
            })
        elif ocf < 0 and np_ is not None and np_ > 0:
            risk_items.append({
                "id": "cf_weaker",
                "status": "warn",
                "title": "Cash flow weaker than profit",
                "detail": f"Profitable on paper ({np_:,.0f}) but operating cash flow is negative ({ocf:,.0f}).",
            })
        else:
            risk_items.append({
                "id": "cf_weaker",
                "status": "ok",
                "title": "Cash flow vs profit looks reasonable",
                "detail": f"OCF {ocf:,.0f} vs net profit {np_:,.0f}.",
            })
    else:
        risk_items.append({
            "id": "cf_weaker",
            "status": "unknown",
            "title": "Cash flow vs profit unknown",
            "detail": "Need both operating cash flow and net profit for this check.",
        })

    # Consistent earnings (no loss years in the series, and not wildly volatile)
    profits = [r.get("net_profit") for r in with_ratios if r.get("net_profit") is not None]
    if profits:
        loss_years = sum(1 for p in profits if p < 0)
        if loss_years == 0 and len(profits) >= 2:
            # simple volatility: max abs YoY change ratio
            risk_items.append({
                "id": "consistent_earnings",
                "status": "ok",
                "title": "Consistent earnings (no loss years in sample)",
                "detail": f"{len(profits)} years of positive net profit in the extracted series.",
            })
        elif loss_years > 0:
            risk_items.append({
                "id": "consistent_earnings",
                "status": "warn",
                "title": "Earnings not fully consistent",
                "detail": f"{loss_years} loss year(s) in the extracted series — review those years' notes.",
            })
        else:
            risk_items.append({
                "id": "consistent_earnings",
                "status": "unknown",
                "title": "Earnings consistency hard to judge",
                "detail": "Only one year of profit data available.",
            })
    else:
        risk_items.append({
            "id": "consistent_earnings",
            "status": "unknown",
            "title": "Earnings consistency unknown",
            "detail": "Net profit not extracted.",
        })

    return {
        "years": years,
        "growth": growth,
        "profitability": profitability,
        "strength": strength,
        "shareholder": shareholder,
        "valuation": valuation,
        "risk_items": risk_items,
    }
