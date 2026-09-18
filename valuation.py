"""
Valuation metrics (need a manually-entered share price — not in the
annual report itself) and a position-sizing calculator.

Deliberately does ONLY arithmetic. Nothing here recommends buying,
selling, or how much to invest - it takes numbers the user chooses
(their budget, their allocation %) and just computes the result.
"""


def compute_valuation(share_price: float, eps: float, total_equity: float,
                       net_profit: float, dividend_paid: float = None) -> dict:
    """
    Shares outstanding isn't something we extract directly, so we
    APPROXIMATE it as net_profit / eps (since EPS = net profit / shares
    outstanding, by definition). This is clearly labeled as an
    approximation - a real shares-outstanding figure (from the annual
    report's cover page or share register note) would be more precise.
    """
    result = {"approximate_shares_outstanding": None, "book_value_per_share": None,
              "pe_ratio": None, "pb_ratio": None, "dividend_per_share_approx": None,
              "dividend_yield_pct": None}

    if not share_price or share_price <= 0:
        return result

    if eps and eps != 0:
        result["pe_ratio"] = share_price / eps

    if net_profit and eps and eps != 0:
        shares_outstanding = net_profit / eps
        result["approximate_shares_outstanding"] = shares_outstanding
        if total_equity and shares_outstanding:
            bvps = total_equity / shares_outstanding
            result["book_value_per_share"] = bvps
            if bvps != 0:
                result["pb_ratio"] = share_price / bvps
        if dividend_paid and shares_outstanding:
            dps = abs(dividend_paid) / shares_outstanding
            result["dividend_per_share_approx"] = dps
            result["dividend_yield_pct"] = (dps / share_price) * 100

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
