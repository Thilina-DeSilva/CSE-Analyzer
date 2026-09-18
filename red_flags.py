"""
Rule-based red-flags checklist, computed purely from the numbers
already extracted. Deliberately phrased as "here's what to look
closer at", never as "sell" or "this is bad" - the point is to teach
pattern-recognition, not replace judgment.
"""


def compute_red_flags(with_ratios: list) -> list:
    """with_ratios: merged, ratio'd yearly records, sorted oldest->newest.
    Returns a list of {severity, title, detail} dicts."""
    flags = []
    if len(with_ratios) < 2:
        return flags

    latest = with_ratios[-1]
    prior = with_ratios[-2]
    latest_r = latest.get("_ratios", {})
    prior_r = prior.get("_ratios", {})

    # 1. Negative operating cash flow
    ocf = latest.get("operating_cash_flow")
    if ocf is not None and ocf < 0:
        flags.append({
            "severity": "high",
            "title": f"Negative operating cash flow in {latest['year']}",
            "detail": (f"The core business used cash rather than generating it "
                       f"({ocf:,.0f}). A company can report a profit and still have "
                       f"this happen — worth checking WHY (one-off working-capital "
                       f"swing, or a recurring pattern? look at more years if you have them)."),
        })

    # 2. Net loss
    net_profit = latest.get("net_profit")
    if net_profit is not None and net_profit < 0:
        flags.append({
            "severity": "high",
            "title": f"Net loss in {latest['year']}",
            "detail": f"The company reported a loss of {abs(net_profit):,.0f} for the year.",
        })

    # 3. Declining net margin
    m1 = prior_r.get("net_profit_margin_pct")
    m2 = latest_r.get("net_profit_margin_pct")
    if m1 is not None and m2 is not None and m2 < m1 - 2:  # drop of >2 percentage points
        flags.append({
            "severity": "medium",
            "title": f"Net profit margin declined ({m1:.1f}% → {m2:.1f}%)",
            "detail": "Profitability per rupee of revenue/income is shrinking year over year. "
                      "Could be rising costs, pricing pressure, or one-off items — check the "
                      "Management Discussion section of the report for the stated reason.",
        })

    # 4. Rising leverage
    d1 = prior_r.get("debt_to_equity")
    d2 = latest_r.get("debt_to_equity")
    if d1 is not None and d2 is not None and d1 > 0 and d2 > d1 * 1.2:  # 20%+ relative rise
        flags.append({
            "severity": "medium",
            "title": f"Debt/Equity rose noticeably ({d1:.2f} → {d2:.2f})",
            "detail": "The company took on relatively more debt versus its equity base. "
                      "Not automatically bad (could be funding growth) but worth checking "
                      "what the new debt was used for and whether interest costs are covered.",
        })

    # 5. Declining revenue/gross income
    rev1 = prior.get("revenue") if prior.get("revenue") is not None else prior.get("gross_income")
    rev2 = latest.get("revenue") if latest.get("revenue") is not None else latest.get("gross_income")
    if rev1 is not None and rev2 is not None and rev2 < rev1:
        pct = ((rev2 - rev1) / rev1) * 100
        flags.append({
            "severity": "medium",
            "title": f"Revenue/Gross Income declined ({pct:.1f}%)",
            "detail": "Top-line shrank year over year. Check if this is industry-wide "
                      "(economic conditions) or specific to this company (losing market share).",
        })

    # 6. EPS declining while revenue grows (cost/efficiency concern)
    eps1, eps2 = prior.get("eps"), latest.get("eps")
    if (eps1 is not None and eps2 is not None and eps2 < eps1
            and rev1 is not None and rev2 is not None and rev2 > rev1):
        flags.append({
            "severity": "low",
            "title": "Revenue grew but EPS fell",
            "detail": "Sales grew but earnings-per-share didn't follow — could mean rising "
                      "costs, more shares issued (dilution), or one-off charges. Worth a "
                      "closer look at the full income statement.",
        })

    if not flags:
        flags.append({
            "severity": "none",
            "title": "No automatic red flags triggered",
            "detail": "This checks a handful of common warning patterns only — it is NOT a "
                      "complete due-diligence process. Always read the actual report, "
                      "especially the auditor's opinion and risk-factors sections, which "
                      "this tool doesn't check yet.",
        })

    return flags
