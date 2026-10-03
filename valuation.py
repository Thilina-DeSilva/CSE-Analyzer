"""
Valuation metrics (need a manually-entered share price — not in the
annual report itself) and a position-sizing calculator.

Deliberately does ONLY arithmetic. Nothing here recommends buying,
selling, or how much to invest - it takes numbers the user chooses
(their budget, their allocation %) and just computes the result.
"""


def compute_valuation(share_price: float, eps: float, total_equity: float,
                       net_profit: float, dividend_paid: float = None,
                       dividend_per_share_direct: float = None) -> dict:
    """
    Shares outstanding isn't something we extract directly, so we
    APPROXIMATE it as net_profit / eps (since EPS = net profit / shares
    outstanding, by definition). This is clearly labeled as an
    approximation - a real shares-outstanding figure (from the annual
    report's cover page or share register note) would be more precise.

    dividend_per_share_direct: when the report states "Dividend Per
    Share" explicitly as its own line, pass it here - it's exact, and
    is ALWAYS preferred over back-calculating DPS from total dividend
    paid ÷ approximated share count, which is a two-step approximation.
    """
    result = {"approximate_shares_outstanding": None, "book_value_per_share": None,
              "pe_ratio": None, "pb_ratio": None, "dividend_per_share_approx": None,
              "dividend_yield_pct": None, "dps_is_exact": False}

    if not share_price or share_price <= 0:
        return result

    if eps and eps != 0:
        result["pe_ratio"] = share_price / eps

    if dividend_per_share_direct is not None:
        result["dividend_per_share_approx"] = dividend_per_share_direct
        result["dps_is_exact"] = True
        result["dividend_yield_pct"] = (dividend_per_share_direct / share_price) * 100

    # Shares ≈ Net Profit / EPS. CRITICAL: net_profit and total_equity must
    # be in the SAME unit (both Rs.'000 or both full Rs.). If the report
    # uses Rs.'000, the share count is still correct because the scale
    # cancels (profit_in_thousands / eps = shares). P/B also cancels.
    # Dividend yield is only reliable when dividend_paid is in the same unit.
    if net_profit and eps and eps != 0:
        shares_outstanding = abs(net_profit) / abs(eps)
        result["approximate_shares_outstanding"] = shares_outstanding
        if total_equity is not None and shares_outstanding:
            bvps = total_equity / shares_outstanding
            # If equity was in Rs.'000 and eps in Rs, bvps is still in Rs.'000
            # per share — that would make P/B nonsense. Heuristic: if |bvps|
            # is absurdly large vs share price (>1000x), assume unit mismatch
            # and scale equity down by 1000 (common Rs.'000 case).
            if share_price > 0 and abs(bvps) > share_price * 500:
                bvps = bvps / 1000.0
                result["book_value_per_share"] = bvps
                result["unit_heuristic_applied"] = True
            else:
                result["book_value_per_share"] = bvps
            if bvps != 0:
                result["pb_ratio"] = share_price / bvps
        # Only fall back to the approximated DPS if we don't already have
        # the exact, report-stated figure from above.
        if not result["dps_is_exact"] and dividend_paid is not None and shares_outstanding:
            dps = abs(dividend_paid) / shares_outstanding
            if share_price > 0 and dps > share_price * 2:
                # likely dividend was in Rs.'000 while we need Rs per share
                dps = dps / 1000.0
            result["dividend_per_share_approx"] = dps
            result["dividend_yield_pct"] = (dps / share_price) * 100 if share_price else None

    return result


def compute_position_size(budget: float, allocation_pct: float, share_price: float,
                            total_portfolio_value: float = None) -> dict:
    """
    Pure arithmetic: given a budget and a user-chosen allocation % (the
    % of that budget they've decided to put toward THIS stock - their
    decision, not ours), work out how many shares that buys and what
    it costs. If they also give total portfolio value, show what % of
    their overall portfolio this position would represent.
    """
    result = {"amount_to_invest": None, "shares_you_can_buy": None,
              "actual_amount_spent": None, "leftover_cash": None,
              "pct_of_total_portfolio": None}

    if not budget or budget <= 0 or not share_price or share_price <= 0:
        return result

    amount_to_invest = budget * (allocation_pct / 100)
    shares = int(amount_to_invest // share_price)
    spent = shares * share_price

    result["amount_to_invest"] = amount_to_invest
    result["shares_you_can_buy"] = shares
    result["actual_amount_spent"] = spent
    result["leftover_cash"] = amount_to_invest - spent

    if total_portfolio_value and total_portfolio_value > 0:
        result["pct_of_total_portfolio"] = (spent / total_portfolio_value) * 100

    return result
