"""
Advanced / Banking / Construction metrics and "Things to Investigate".

Everything here is deterministic arithmetic on figures already extracted
(records from merge_reports + ratios). Nothing in the original modules is
modified; results are stored under a new "_extra" key on each record.

Data layers (kept separate on purpose):
  raw data          -> record[key]            (extracted from the PDF)
  calculated        -> record["_ratios"]      (ratios.py, unchanged)
                       record["_extra"]       (this module)
  market data       -> entered by the user    (valuation.py, unchanged)
  derived signals   -> compute_investigate_flags()

A metric is None ("—" in the UI) whenever an input is missing. Never 0.
"""

from __future__ import annotations

from typing import Optional

from metrics import unit_to_scale


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _abs(v):
    return abs(v) if v is not None else None


def _div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def _pct(a, b):
    d = _div(a, b)
    return d * 100 if d is not None else None


def _growth(cur, prior):
    """Percent change; needs a non-zero prior. Uses abs(prior) so a
    move from a loss toward profit reads as positive."""
    if cur is None or prior in (None, 0):
        return None
    return (cur - prior) / abs(prior) * 100


def _sub(a, b):
    return None if a is None or b is None else a - b


def _add(*vals):
    """Sum, or None if the first value is missing. Later values are
    optional (treated as 0 when missing)."""
    if vals[0] is None:
        return None
    return sum(v for v in vals if v is not None)


def top_line(rec: dict):
    return rec.get("revenue") if rec.get("revenue") is not None else rec.get("gross_income")


def _prior_comparable(records: list, i: int) -> Optional[dict]:
    """The same period one year earlier (FY vs FY, Q1 vs Q1, H1 vs H1).
    Delegates to ratios.find_prior_comparable so growth rules stay consistent
    across the app (never compare unlike periods)."""
    from ratios import find_prior_comparable
    return find_prior_comparable(records, i)


def _shares_approx(rec: dict):
    """Net profit / EPS, scaled to a real share count. Approximation.

    Prefer profit attributable to equity holders (excludes NCI) when the
    report states it — that is the numerator used for published EPS.
    """
    np_ = rec.get("profit_attributable")
    if np_ is None:
        np_ = rec.get("net_profit")
    eps = rec.get("eps")
    if np_ is None or eps in (None, 0):
        return None
    extr = rec.get("_extractions") or {}
    unit_src = extr.get("profit_attributable") or extr.get("net_profit") or {}
    unit = unit_src.get("unit") if isinstance(unit_src, dict) else None
    return abs(np_) * unit_to_scale(unit or "unknown") / abs(eps)


def _dividend_total(rec: dict):
    v = rec.get("dividend_paid")
    return abs(v) if v not in (None, 0) else None


def _dps(rec: dict):
    v = rec.get("dividend_per_share")
    return v if v is not None else None


# --------------------------------------------------------------------------
# per-record calculation
# --------------------------------------------------------------------------

def compute_extra_for_record(rec: dict, prior: Optional[dict]) -> dict:
    x = {}
    is_fy = (rec.get("period_type") or "FY") == "FY"
    bank = rec.get("industry") == "bank"
    rev = top_line(rec)
    np_ = rec.get("net_profit")
    p = prior or {}

    # ---- A. detailed profitability ----
    gp, op, pbt = rec.get("gross_profit"), rec.get("operating_profit"), rec.get("profit_before_tax")
    fin = _abs(rec.get("finance_cost"))
    x["gross_margin_pct"] = _pct(gp, rev)
    x["operating_margin_pct"] = _pct(op, rev)
    x["pretax_margin_pct"] = _pct(pbt, rev)

    ebit = op if op is not None else (_add(pbt, fin) if pbt is not None and fin is not None else None)
    x["ebit"] = ebit
    dep, amo = _abs(rec.get("depreciation")), _abs(rec.get("amortisation"))
    x["ebitda"] = _add(ebit, dep, amo) if (ebit is not None and dep is not None) else None
    x["ebit_margin_pct"] = _pct(ebit, rev)
    x["ebitda_margin_pct"] = _pct(x["ebitda"], rev)
    tax = _abs(rec.get("income_tax"))
    x["effective_tax_rate_pct"] = _pct(tax, pbt) if (pbt is not None and pbt > 0) else None
    if not bank:
        x["interest_coverage"] = _div(ebit, fin)

    # ---- B. financial strength ----
    debt, cash = rec.get("total_debt"), rec.get("cash_and_equivalents")
    ta, tl, te = rec.get("total_assets"), rec.get("total_liabilities"), rec.get("total_equity")
    if not bank:
        x["net_debt"] = _sub(debt, cash)
        nd = x["net_debt"]
        x["net_debt_to_ebitda"] = _div(nd, x["ebitda"]) if x["ebitda"] and x["ebitda"] > 0 else None
        x["debt_to_assets"] = _div(debt, ta)
    x["liabilities_to_assets"] = _div(tl, ta)
    ca, cl, inv = rec.get("current_assets"), rec.get("current_liabilities"), rec.get("inventories")
    x["current_ratio"] = _div(ca, cl)
    x["quick_ratio"] = _div(_sub(ca, inv if inv is not None else 0), cl) if ca is not None else None
    x["working_capital"] = _sub(ca, cl)

    # ---- cash flow ----
    ocf, capex = rec.get("operating_cash_flow"), _abs(rec.get("capex"))
    fcf = _sub(ocf, capex) if (ocf is not None and capex is not None) else None
    x["free_cash_flow"] = fcf
    x["ocf_to_net_profit_pct"] = _pct(ocf, np_) if (np_ is not None and np_ > 0) else None
    x["fcf_to_net_profit_pct"] = _pct(fcf, np_) if (np_ is not None and np_ > 0) else None
    x["capex_to_revenue_pct"] = _pct(capex, rev)
    x["cash_conversion_pct"] = _pct(ocf, x["ebitda"]) if (x["ebitda"] and x["ebitda"] > 0) else None
    p_fcf = None
    if prior:
        p_ocf, p_capex = prior.get("operating_cash_flow"), _abs(prior.get("capex"))
        p_fcf = _sub(p_ocf, p_capex) if (p_ocf is not None and p_capex is not None) else None
        x["ocf_growth_pct"] = _growth(ocf, p_ocf)
        x["fcf_growth_pct"] = _growth(fcf, p_fcf)

    # ---- working capital (non-financial) ----
    rec_, pay = rec.get("receivables"), rec.get("payables")
    cost_of_sales = _sub(rev, gp) if (rev is not None and gp is not None) else None
    if not bank and is_fy:
        x["receivable_days"] = _div(rec_, rev) * 365 if _div(rec_, rev) is not None else None
        d = _div(inv, cost_of_sales)
        x["inventory_days"] = d * 365 if d is not None else None
        d = _div(pay, cost_of_sales)
        x["payable_days"] = d * 365 if d is not None else None
        x["cash_conversion_cycle"] = (
            x["receivable_days"] + (x["inventory_days"] or 0) - x["payable_days"]
            if x["receivable_days"] is not None and x["payable_days"] is not None else None
        )
    x["working_capital_to_revenue_pct"] = _pct(x["working_capital"], rev) if is_fy else None
    if prior:
        rev_g = _growth(rev, top_line(prior))
        x["revenue_growth_pct"] = rev_g
        rg = _growth(rec_, prior.get("receivables"))
        ig = _growth(inv, prior.get("inventories"))
        x["receivables_growth_pct"] = rg
        x["inventory_growth_pct"] = ig
        x["receivables_vs_revenue_growth_pts"] = _sub(rg, rev_g)
        x["inventory_vs_revenue_growth_pts"] = _sub(ig, rev_g)

    # ---- shareholder analysis ----
    sh = _shares_approx(rec)
    x["shares_outstanding_approx"] = sh
    # Prefer report-stated NAVPS / net assets per share when extracted;
    # otherwise approximate as Equity × EPS / Profit (≡ Equity / shares).
    direct_navps = rec.get("navps")
    if direct_navps is not None:
        x["navps"] = direct_navps
    else:
        # Use attributable profit when available (matches published EPS base)
        np_for_nav = rec.get("profit_attributable") if rec.get("profit_attributable") is not None else np_
        x["navps"] = (
            (te * rec["eps"] / np_for_nav)
            if (te is not None and np_for_nav not in (None, 0) and rec.get("eps") not in (None, 0))
            else None
        )
    re_ = rec.get("retained_earnings")
    div_total = _dividend_total(rec)
    x["dividend_payout_pct"] = _pct(div_total, np_) if (np_ is not None and np_ > 0 and div_total is not None) else None
    x["retention_ratio_pct"] = (100 - x["dividend_payout_pct"]) if x["dividend_payout_pct"] is not None else None
    x["dividend_cover"] = _div(np_, div_total) if (np_ is not None and np_ > 0 and div_total) else None
    if prior:
        p_sh = _shares_approx(prior)
        x["share_dilution_pct"] = _growth(sh, p_sh)
        x["equity_growth_pct"] = _growth(te, prior.get("total_equity"))
        x["retained_earnings_growth_pct"] = _growth(re_, prior.get("retained_earnings"))
        p_navps = prior.get("navps")  # direct from report if extracted
        if p_navps is None:
            pe = prior.get("total_equity")
            pn = prior.get("profit_attributable")
            if pn is None:
                pn = prior.get("net_profit")
            pp = prior.get("eps")
            if pe is not None and pn not in (None, 0) and pp not in (None, 0):
                p_navps = pe * pp / pn
        x["navps_growth_pct"] = _growth(x["navps"], p_navps)
        d_now = _dps(rec) if _dps(rec) is not None else div_total
        d_prev = _dps(prior) if _dps(prior) is not None else _dividend_total(prior)
        x["dividend_growth_pct"] = _growth(d_now, d_prev)

    # ---- bank mode ----
    loans, dep_c = rec.get("net_loans"), rec.get("customer_deposits")
    nii = rec.get("net_interest_income")
    x["loans_to_deposits_pct"] = _pct(loans, dep_c)
    tox, toi = _abs(rec.get("total_operating_expenses")), rec.get("total_operating_income")
    x["cost_to_income_pct"] = _pct(tox, toi) if (toi and toi > 0) else None
    nf = rec.get("net_fee_income")
    x["fee_income_share_pct"] = _pct(nf, _add(nii, nf)) if (nii is not None and nf is not None) else None
    avg_assets = (ta + p["total_assets"]) / 2 if (ta is not None and p.get("total_assets") is not None) else ta
    x["nii_to_avg_assets_pct"] = _pct(nii, avg_assets) if is_fy else None
    imp = _abs(rec.get("credit_impairment"))
    avg_loans = (loans + p["net_loans"]) / 2 if (loans is not None and p.get("net_loans") is not None) else loans
    x["cost_of_risk_pct"] = _pct(imp, avg_loans) if is_fy else None
    # ---- bank credit quality (Stage 1/2/3, coverage, NPL) ----
    # Base for the Stage % ratios: the reported gross loan figure; if that is missing,
    # the sum of the three stages. Never mix: both Stage % and NPL % use the same base.
    s1, s2, s3 = rec.get("stage1_loans"), rec.get("stage2_loans"), rec.get("stage3_loans")
    gross = rec.get("gross_loans")
    if gross is None and None not in (s1, s2, s3):
        gross = s1 + s2 + s3
    x["stage1_pct"] = _pct(s1, gross)
    x["stage2_pct"] = _pct(s2, gross)
    x["stage3_pct"] = _pct(s3, gross)          # = impaired loans ratio
    s3_imp = rec.get("stage3_impairment")
    x["stage3_coverage_pct"] = _pct(s3_imp, s3)
    # NPL / impaired loans: use the bank's own reported NPL line when printed,
    # otherwise Stage 3 gross carrying amount (the IFRS 9 impaired book).
    npl = rec.get("npl_loans")
    x["npl_amount"] = npl if npl is not None else s3
    x["npl_ratio_pct"] = _pct(x["npl_amount"], gross)
    x["total_coverage_pct"] = _pct(rec.get("total_loan_impairment"), gross)
    if prior:
        x["loan_growth_pct"] = _growth(loans, prior.get("net_loans"))
        x["deposit_growth_pct"] = _growth(dep_c, prior.get("customer_deposits"))
        x["nii_growth_pct"] = _growth(nii, prior.get("net_interest_income"))
        x["impairment_growth_pct"] = _growth(imp, _abs(prior.get("credit_impairment")))

    # ---- construction mode ----
    cas, cls_ = rec.get("contract_assets"), rec.get("contract_liabilities")
    x["contract_assets_to_revenue_pct"] = _pct(cas, rev) if is_fy else None
    x["net_contract_position"] = _sub(cas, cls_) if (cas is not None and cls_ is not None) else None
    if prior:
        cg = _growth(cas, prior.get("contract_assets"))
        x["contract_assets_growth_pct"] = cg
        x["contract_liabilities_growth_pct"] = _growth(cls_, prior.get("contract_liabilities"))
        x["contract_assets_vs_revenue_growth_pts"] = _sub(cg, _growth(rev, top_line(prior)))

    return x


def compute_extra_series(with_ratios: list) -> list:
    """Adds rec['_extra'] to every record. Input records are not mutated;
    a new list of shallow copies is returned (same as ratios.py)."""
    out = []
    for i, rec in enumerate(with_ratios):
        prior = _prior_comparable(with_ratios, i)
        r = dict(rec)
        try:
            r["_extra"] = compute_extra_for_record(rec, prior)
        except Exception as e:  # never let an extra metric break the app
            r["_extra"] = {"_error": str(e)}
        out.append(r)
    return out


# --------------------------------------------------------------------------
# multi-year CAGR (FY records only)
# --------------------------------------------------------------------------

def _cagr(start, end, years):
    if start is None or end is None or years < 1 or start <= 0 or end <= 0:
        return None
    try:
        return ((end / start) ** (1 / years) - 1) * 100
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


def _series_value(rec: dict, key: str):
    if key in rec:
        return rec.get(key)
    if key in (rec.get("_extra") or {}):
        return rec["_extra"].get(key)
    return (rec.get("_ratios") or {}).get(key)


def cagr_for(records: list, key: str, years: int):
    """CAGR of `key` over exactly `years` years ending at the latest FY
    that has the value. None if either endpoint year is missing."""
    fy = {r["year"]: _series_value(r, key) for r in records
          if (r.get("period_type") or "FY") == "FY" and r.get("year") is not None}
    fy = {y: v for y, v in fy.items() if v is not None}
    if not fy:
        return None
    end_y = max(fy)
    start_y = end_y - years
    if start_y not in fy:
        return None
    return _cagr(fy[start_y], fy[end_y], years)


CAGR_KEYS = [
    ("Revenue", "revenue"),
    ("Net Profit", "net_profit"),
    ("EPS", "eps"),
    ("NAVPS (approx.)", "navps"),
    ("Total Equity", "total_equity"),
    ("Dividend per share", "dividend_per_share"),
]


def compute_cagr_table(records: list) -> list:
    rows = []
    for label, key in CAGR_KEYS:
        # bank fallback for revenue
        k = key
        if key == "revenue" and not any(r.get("revenue") is not None for r in records):
            k = "gross_income"
            label = "Gross Income"
        rows.append({"Metric": label,
                     "3Y CAGR %": cagr_for(records, k, 3),
                     "5Y CAGR %": cagr_for(records, k, 5)})
    return rows


# --------------------------------------------------------------------------
# what to display: (key, label, format, why)   format: pct | x | num | days | rs
# --------------------------------------------------------------------------

SECTIONS = {
    "Detailed profitability": [
        ("gross_margin_pct", "Gross margin %", "pct", "Pricing power and direct-cost efficiency."),
        ("operating_margin_pct", "Operating margin %", "pct", "Core business efficiency before financing and tax."),
        ("pretax_margin_pct", "Pre-tax margin %", "pct", "Profitability after financing costs, before tax."),
        ("ebit", "EBIT", "num", "Operating profit (or pre-tax profit + finance cost if no operating profit line)."),
        ("ebit_margin_pct", "EBIT margin %", "pct", "EBIT relative to revenue."),
        ("ebitda", "EBITDA", "num", "EBIT + depreciation (+ amortisation). Needs those lines on the cash-flow statement."),
        ("ebitda_margin_pct", "EBITDA margin %", "pct", "Cash-style operating margin."),
        ("effective_tax_rate_pct", "Effective tax rate %", "pct", "Tax charge relative to pre-tax profit."),
        ("interest_coverage", "Interest coverage (x)", "x", "How many times EBIT covers finance cost. Below ~2x deserves a look."),
    ],
    "Cash flow": [
        ("free_cash_flow", "Free cash flow", "num", "Operating cash flow minus capex (PPE purchases)."),
        ("ocf_to_net_profit_pct", "OCF / Net profit %", "pct", "Does accounting profit turn into cash? Low % = profit not converting."),
        ("fcf_to_net_profit_pct", "FCF / Net profit %", "pct", "Cash left after investment relative to profit."),
        ("ocf_growth_pct", "Operating cash flow growth %", "pct", "Cash generation trend."),
        ("fcf_growth_pct", "Free cash flow growth %", "pct", "Free cash trend."),
        ("capex_to_revenue_pct", "Capex / Revenue %", "pct", "How capital-hungry the business is."),
        ("cash_conversion_pct", "Cash conversion (OCF / EBITDA) %", "pct", "Share of EBITDA that reaches operating cash."),
    ],
    "Leverage & liquidity": [
        ("net_debt", "Net debt", "num", "Debt minus cash."),
        ("net_debt_to_ebitda", "Net debt / EBITDA (x)", "x", "Years of EBITDA needed to repay net debt."),
        ("debt_to_assets", "Debt / Assets (x)", "x", "Share of assets funded by borrowing."),
        ("liabilities_to_assets", "Liabilities / Assets (x)", "x", "Share of assets funded by all obligations."),
        ("current_ratio", "Current ratio (x)", "x", "Short-term assets vs short-term obligations. Below 1 = tight."),
        ("quick_ratio", "Quick ratio (x)", "x", "Current ratio excluding inventories."),
        ("working_capital", "Working capital", "num", "Current assets minus current liabilities."),
    ],
    "Working capital (non-financial, full-year only)": [
        ("receivable_days", "Receivable days", "days", "Average time customers take to pay (year-end balance basis)."),
        ("inventory_days", "Inventory days", "days", "Days of cost of sales held in stock. Needs a gross profit line."),
        ("payable_days", "Payable days", "days", "Days of cost of sales owed to suppliers. Needs a gross profit line."),
        ("cash_conversion_cycle", "Cash conversion cycle (days)", "days", "Receivable + inventory − payable days."),
        ("working_capital_to_revenue_pct", "Working capital / Revenue %", "pct", "Capital tied up per rupee of sales."),
        ("receivables_vs_revenue_growth_pts", "Receivables growth − revenue growth (pts)", "pct", "Positive and large = sales may be booked faster than cash arrives."),
        ("inventory_vs_revenue_growth_pts", "Inventory growth − revenue growth (pts)", "pct", "Positive and large = stock building up."),
    ],
    "Share structure & shareholder analysis": [
        ("shares_outstanding_approx", "Shares outstanding (approx.)", "num", "Net profit ÷ EPS. An approximation, not the share register."),
        ("share_dilution_pct", "Share dilution % (approx.)", "pct", "Change in approximate share count vs prior year."),
        ("navps", "NAVPS (Rs., approx.)", "rs", "Equity ÷ approximate shares."),
        ("navps_growth_pct", "NAVPS growth %", "pct", "Book value per share trend."),
        ("equity_growth_pct", "Equity growth %", "pct", "Shareholder capital growth."),
        ("retained_earnings_growth_pct", "Retained earnings growth %", "pct", "Profit kept in the business."),
        ("dividend_growth_pct", "Dividend growth %", "pct", "Uses dividend/share when reported, else total dividend paid."),
        ("dividend_payout_pct", "Dividend payout %", "pct", "Dividend paid ÷ net profit (cash-flow basis)."),
        ("retention_ratio_pct", "Retention ratio %", "pct", "100 − payout."),
        ("dividend_cover", "Dividend cover (x)", "x", "Net profit ÷ dividend paid."),
    ],
}

BANK_SECTIONS = {
    "Lending & funding": [
        ("net_loans", "Loans to customers (net)", "raw", "Balance-sheet loan book."),
        ("loan_growth_pct", "Loan growth %", "pct", "How fast the loan book is expanding."),
        ("customer_deposits", "Customer deposits", "raw", "Main funding source."),
        ("deposit_growth_pct", "Deposit growth %", "pct", "Funding growth."),
        ("loans_to_deposits_pct", "Loans / Deposits %", "pct", "How much of deposits is lent out."),
    ],
    "Income & efficiency": [
        ("interest_income", "Interest income", "raw", "Gross interest earned."),
        ("interest_expense", "Interest expense", "raw", "Interest paid on funding."),
        ("net_interest_income", "Net interest income", "raw", "Core bank earnings."),
        ("nii_growth_pct", "NII growth %", "pct", "Trend in core earnings."),
        ("nii_to_avg_assets_pct", "NII / average assets % (NIM proxy)", "pct", "Proxy only: true NIM uses average earning assets, which is not extracted."),
        ("net_fee_income", "Net fee & commission income", "raw", "Non-interest earnings."),
        ("fee_income_share_pct", "Fee share of (NII + fees) %", "pct", "Income diversification."),
        ("cost_to_income_pct", "Cost-to-income %", "pct", "Operating expenses ÷ total operating income. Lower is more efficient."),
    ],
    "Bank credit-quality group": [
        ("gross_loans", "Gross loans", "raw", "Loan book before deducting the impairment allowance."),
        ("stage1_loans", "Stage 1 loans", "raw", "Performing loans with no significant increase in credit risk (12-month ECL)."),
        ("stage2_loans", "Stage 2 loans", "raw", "Loans with a significant rise in credit risk but not yet defaulted (lifetime ECL). An early-warning bucket."),
        ("stage3_loans", "Stage 3 loans", "raw", "Credit-impaired loans (lifetime ECL) - the IFRS 9 equivalent of non-performing loans."),
        ("stage1_pct", "Stage 1 %", "pct", "Share of gross loans that are performing normally."),
        ("stage2_pct", "Stage 2 %", "pct", "Share of gross loans under watch. Rising Stage 2 often leads Stage 3."),
        ("stage3_pct", "Stage 3 % (impaired loans ratio)", "pct", "Stage 3 loans / gross loans. The headline asset-quality ratio; lower is better."),
        ("stage3_impairment", "Stage 3 impairment", "raw", "ECL allowance held against Stage 3 loans."),
        ("stage3_coverage_pct", "Stage 3 coverage ratio %", "pct", "Stage 3 allowance / Stage 3 loans. How much of the bad book is already provided for."),
        ("total_loan_impairment", "Total loan impairment", "raw", "Total ECL allowance on loans across all stages (balance-sheet stock)."),
        ("cost_of_risk_pct", "Cost of risk % (charge / avg. net loans)", "pct", "Annual loan-loss charge as a share of the average loan book."),
        ("npl_amount", "NPL / impaired loans", "raw", "The bank's reported NPL line if printed, otherwise Stage 3 loans."),
        ("npl_ratio_pct", "NPL / impaired loans ratio %", "pct", "NPL / impaired loans divided by gross loans."),
        ("credit_impairment", "Loan loss / ECL provision (P&L charge)", "raw", "Impairment charge for the period through the income statement. Sign is as printed: brackets / negative = expense, positive = net reversal."),
        ("impairment_growth_pct", "Provision charge growth %", "pct", "Rising charges can signal deteriorating loans."),
        ("total_coverage_pct", "Total allowance / gross loans %", "pct", "Overall cushion held against the whole loan book."),
    ],
}

CONSTRUCTION_SECTIONS = {
    "Contracts": [
        ("contract_assets", "Contract assets", "raw", "Work done but not yet billed."),
        ("contract_liabilities", "Contract liabilities / advances", "raw", "Cash received ahead of work."),
        ("net_contract_position", "Net contract position", "num", "Contract assets − liabilities."),
        ("contract_assets_to_revenue_pct", "Contract assets / Revenue %", "pct", "How much revenue is still unbilled."),
        ("contract_assets_growth_pct", "Contract asset growth %", "pct", "Unbilled work trend."),
        ("contract_assets_vs_revenue_growth_pts", "Contract asset growth − revenue growth (pts)", "pct", "Positive and large = profit booked ahead of cash."),
        ("receivable_days", "Receivable days", "days", "Time customers take to pay."),
    ],
}

# Not extracted (needs notes / management commentary, not the four statements):
NOT_AVAILABLE = {
    "Bank": "CASA, CET1/Tier 1/Total CAR, RWA, LCR/NSFR",
    "Construction": "Order book, new contracts, backlog, retention receivables",
    "Manufacturing / Retail / Telecom": "Production volume, capacity utilisation, store counts, same-store sales, subscribers, ARPU, churn",
}


def format_value(v, fmt: str) -> str:
    if v is None:
        return "—"
    try:
        if fmt == "pct":
            return f"{v:,.1f}%"
        if fmt == "x":
            return f"{v:,.2f}x"
        if fmt == "days":
            return f"{v:,.0f}"
        if fmt == "rs":
            return f"{v:,.2f}"
        return f"{v:,.0f}"  # num / raw
    except (TypeError, ValueError):
        return "—"


def has_any(records: list, keys) -> bool:
    return any(_series_value(r, k) is not None for r in records for k in keys)


def sections_have_data(records: list, sections: dict) -> bool:
    return has_any(records, [row[0] for rows in sections.values() for row in rows])


# --------------------------------------------------------------------------
# metric history (any raw, ratio or extra metric)
# --------------------------------------------------------------------------

def metric_history(records: list, key: str) -> list:
    """[(period_label, value)] oldest -> newest for the History view."""
    return [(str(r.get("period_label") or r.get("year")), _series_value(r, key)) for r in records]


def all_history_keys(records: list) -> dict:
    """{key: label} for every metric that has at least one value."""
    from report_builder import METRIC_LABELS, RATIO_LABELS
    labels = {}
    for k, l in METRIC_LABELS.items():
        labels[k] = l
    for k, l in RATIO_LABELS.items():
        labels[k] = l
    for secs in (SECTIONS, BANK_SECTIONS, CONSTRUCTION_SECTIONS):
        for rows in secs.values():
            for k, l, _f, _w in rows:
                labels.setdefault(k, l)
    return {k: l for k, l in labels.items() if has_any(records, [k])}


# --------------------------------------------------------------------------
# Things to Investigate (never BUY / SELL)
# --------------------------------------------------------------------------

def _flag(sev, cat, title, detail):
    return {"severity": sev, "category": cat, "title": title, "detail": detail}


def compute_investigate_flags(records: list) -> list:
    """Cross-metric relationships worth a closer look. Works on the
    latest record vs the same period one year earlier. Complements (does
    not replace) red_flags.py."""
    flags = []
    if not records:
        return flags
    i = len(records) - 1
    cur = records[i]
    prior = _prior_comparable(records, i)
    x = cur.get("_extra") or {}
    label = cur.get("period_label") or cur.get("year")
    bank = cur.get("industry") == "bank"

    def g(key_cur, key_prior=None):
        return _growth(cur.get(key_cur), (prior or {}).get(key_prior or key_cur))

    if prior:
        plabel = prior.get("period_label") or prior.get("year")
        np_g, ocf_g = g("net_profit"), g("operating_cash_flow")
        if np_g is not None and ocf_g is not None and np_g > 5 and ocf_g < -10:
            flags.append(_flag("medium", "Cash conversion",
                               f"Profit up {np_g:.0f}% but operating cash flow down {abs(ocf_g):.0f}%",
                               f"{plabel} → {label}. Earnings grew while cash generation fell; check receivables, "
                               f"contract assets or inventory build-up."))
        debt_g, eq_g = g("total_debt"), g("total_equity")
        if not bank and debt_g is not None and eq_g is not None and debt_g > 25 and debt_g - eq_g > 20:
            flags.append(_flag("medium", "Leverage",
                               f"Debt up {debt_g:.0f}% while equity up only {eq_g:.0f}%",
                               f"{plabel} → {label}. Borrowing is growing much faster than shareholder capital."))
        dil = x.get("share_dilution_pct")
        eps_g, np_g2 = g("eps"), g("net_profit")
        if dil is not None and dil > 8 and eps_g is not None and np_g2 is not None and np_g2 - eps_g > 5:
            flags.append(_flag("medium", "Dilution",
                               f"Approx. share count up {dil:.0f}%; EPS growth ({eps_g:.0f}%) trails profit growth ({np_g2:.0f}%)",
                               "Share count is back-calculated (net profit ÷ EPS), so treat as indicative; "
                               "confirm against the share capital note."))
        gm_now, gm_prev = x.get("gross_margin_pct"), ((prior.get("_extra") or {}).get("gross_margin_pct"))
        rev_g = g("revenue") if cur.get("revenue") is not None else g("gross_income")
        if gm_now is not None and gm_prev is not None and rev_g is not None and rev_g > 5 and gm_prev - gm_now >= 3:
            flags.append(_flag("medium", "Margin pressure",
                               f"Revenue up {rev_g:.0f}% but gross margin fell {gm_prev:.1f}% → {gm_now:.1f}%",
                               f"{plabel} → {label}. Growth is coming at lower profitability."))
        rvr = x.get("receivables_vs_revenue_growth_pts")
        if rvr is not None and rvr > 20:
            flags.append(_flag("medium", "Working capital",
                               f"Receivables grew {rvr:.0f} pts faster than revenue",
                               "Sales may be growing faster than collections."))
        ivr = x.get("inventory_vs_revenue_growth_pts")
        if ivr is not None and ivr > 20:
            flags.append(_flag("low", "Working capital",
                               f"Inventory grew {ivr:.0f} pts faster than revenue",
                               "Stock is building up relative to sales."))
        cvr = x.get("contract_assets_vs_revenue_growth_pts")
        if cvr is not None and cvr > 20:
            flags.append(_flag("medium", "Contract assets",
                               f"Contract assets grew {cvr:.0f} pts faster than revenue",
                               "Profit may be recognised ahead of billing/cash."))
        dg = x.get("dividend_growth_pct")
        if dg is not None and dg < -5 and np_g is not None and np_g > 0:
            flags.append(_flag("low", "Dividend change",
                               f"Dividend down {abs(dg):.0f}% although profit rose {np_g:.0f}%",
                               "Could be reinvestment or a cash constraint; check the reason in the report."))
        if bank:
            lg, ig = x.get("loan_growth_pct"), x.get("impairment_growth_pct")
            if lg is not None and ig is not None and lg > 10 and ig > 20:
                flags.append(_flag("medium", "Bank credit risk",
                                   f"Loans up {lg:.0f}% and impairment charge up {ig:.0f}%",
                                   "Faster lending alongside higher loan-loss charges. Check the Stage 3 and "
                                   "coverage rows in the Banking tab."))
        # Stage 3 trend (needs the loan-note tables to have been found)
        s3_now = x.get("stage3_pct")
        s3_prev = (prior.get("_extra") or {}).get("stage3_pct")
        if s3_now is not None and s3_prev is not None and s3_now - s3_prev >= 1.0:
            flags.append(_flag("medium", "Bank credit quality",
                               f"Stage 3 ratio rose {s3_prev:.1f}% → {s3_now:.1f}%",
                               f"{plabel} → {label}. More of the loan book is credit-impaired."))
        s2_now = x.get("stage2_pct")
        s2_prev = (prior.get("_extra") or {}).get("stage2_pct")
        if s2_now is not None and s2_prev is not None and s2_now - s2_prev >= 3.0:
            flags.append(_flag("low", "Bank credit quality",
                               f"Stage 2 share rose {s2_prev:.1f}% → {s2_now:.1f}%",
                               f"{plabel} → {label}. Watch-list loans are growing; Stage 3 often follows."))

    # single-period bank check
    cov, s3p = x.get("stage3_coverage_pct"), x.get("stage3_pct")
    if bank and cov is not None and s3p is not None and cov < 40 and s3p > 3:
        flags.append(_flag("medium", "Bank credit quality",
                           f"Stage 3 coverage only {cov:.0f}% with Stage 3 at {s3p:.1f}% of loans",
                           f"{label}. A thin allowance against a sizeable impaired book; collateral may "
                           f"explain it, so check the notes."))

    # single-period checks (no prior needed)
    ic = x.get("interest_coverage")
    if ic is not None and ic < 2:
        flags.append(_flag("high" if ic < 1 else "medium", "Interest coverage",
                           f"EBIT covers finance cost only {ic:.1f}x", f"{label}."))
    cr = x.get("current_ratio")
    if cr is not None and cr < 1:
        flags.append(_flag("low", "Liquidity", f"Current ratio {cr:.2f}x is below 1",
                           f"{label}. Short-term obligations exceed short-term assets."))
    fcf = x.get("free_cash_flow")
    if fcf is not None and fcf < 0:
        flags.append(_flag("low", "Free cash flow", "Free cash flow is negative",
                           f"{label}. Operating cash flow did not cover capex."))
    oc = x.get("ocf_to_net_profit_pct")
    if oc is not None and oc < 50 and not any(f["category"] == "Cash conversion" for f in flags):
        flags.append(_flag("medium", "Cash conversion",
                           f"Operating cash flow is only {oc:.0f}% of net profit", f"{label}."))
    return flags
