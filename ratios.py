"""
V6: Compute standard ratios from the merged multi-year dataset.

All deterministic arithmetic on numbers we already extracted - no AI
involved, so these are as reliable as the underlying extraction. Each
ratio function guards against missing inputs (returns None rather than
crashing or guessing) since not every company/report has every metric.

Note on averages: ROE/ROA classically use AVERAGE equity/assets
(beginning + ending) / 2. We use average when we have the prior year's
balance sheet figure, otherwise fall back to ending-balance (simple)
version - either way it's labeled so the reader can tell which was used.
"""


def _safe_div(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def compute_ratios_for_year(record: dict, prior_record: dict = None) -> dict:
    """record: one year's metric dict (from to_yearly_records/merge).
    prior_record: the previous year's record, if available, used for
    average-balance ratios and growth rates."""
    r = {}

    # "revenue-like" top line: Revenue for industrial companies,
    # Gross Income for banks (kept as separate extracted fields, but
    # ratios like margin/growth need *a* top line to divide by).
    revenue = record.get("revenue") if record.get("revenue") is not None else record.get("gross_income")
    net_profit = record.get("net_profit")
    total_assets = record.get("total_assets")
    total_equity = record.get("total_equity")
    total_liabilities = record.get("total_liabilities")
    total_debt = record.get("total_debt")
    eps = record.get("eps")

    prior_assets = prior_record.get("total_assets") if prior_record else None
    prior_equity = prior_record.get("total_equity") if prior_record else None
    prior_revenue = (
        prior_record.get("revenue") if prior_record.get("revenue") is not None
        else prior_record.get("gross_income")
    ) if prior_record else None
    prior_eps = prior_record.get("eps") if prior_record else None
    prior_net_profit = prior_record.get("net_profit") if prior_record else None

    # profitability
    r["net_profit_margin_pct"] = _safe_div(net_profit, revenue)
    if r["net_profit_margin_pct"] is not None:
        r["net_profit_margin_pct"] *= 100

    avg_equity = (
        (total_equity + prior_equity) / 2
        if total_equity is not None and prior_equity is not None
        else total_equity
    )
    r["roe_pct"] = _safe_div(net_profit, avg_equity)
    r["roe_basis"] = "average equity" if prior_equity is not None else "ending equity"
    if r["roe_pct"] is not None:
        r["roe_pct"] *= 100

    avg_assets = (
        (total_assets + prior_assets) / 2
        if total_assets is not None and prior_assets is not None
        else total_assets
    )
    r["roa_pct"] = _safe_div(net_profit, avg_assets)
    r["roa_basis"] = "average assets" if prior_assets is not None else "ending assets"
    if r["roa_pct"] is not None:
        r["roa_pct"] *= 100

    # leverage
    r["debt_to_equity"] = _safe_div(total_debt, total_equity)
    r["liabilities_to_equity"] = _safe_div(total_liabilities, total_equity)

    # growth (needs prior year)
    r["revenue_growth_pct"] = _safe_div(
        (revenue - prior_revenue) if revenue is not None and prior_revenue is not None else None,
        prior_revenue,
    )
    if r["revenue_growth_pct"] is not None:
        r["revenue_growth_pct"] *= 100

    r["net_profit_growth_pct"] = _safe_div(
        (net_profit - prior_net_profit) if net_profit is not None and prior_net_profit is not None else None,
        abs(prior_net_profit) if prior_net_profit else None,
    )
    if r["net_profit_growth_pct"] is not None:
        r["net_profit_growth_pct"] *= 100

    r["eps_growth_pct"] = _safe_div(
        (eps - prior_eps) if eps is not None and prior_eps is not None else None,
        abs(prior_eps) if prior_eps else None,
    )
    if r["eps_growth_pct"] is not None:
        r["eps_growth_pct"] *= 100

    return r


def compute_ratios_for_series(merged_records: list) -> list:
    """merged_records: output of merge_yearly_records(), sorted oldest
    to newest. Returns the same records with a "_ratios" key added to
    each (using the immediately preceding year as the prior record)."""
    out = []
    for i, rec in enumerate(merged_records):
        prior = merged_records[i - 1] if i > 0 else None
        rec = dict(rec)
        rec["_ratios"] = compute_ratios_for_year(rec, prior)
        out.append(rec)
    return out
