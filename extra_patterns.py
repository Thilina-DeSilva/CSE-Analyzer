"""
Extra line items for the Advanced / Banking / Construction modes.

These are ADDED to metrics.METRIC_PATTERNS / RESTRICT_TO_STMT_TYPE (see
the two-line hook at the bottom of the pattern block in metrics.py).
They never touch the original ~14 metrics: the extractor loops over each
metric independently, so a miss here can't change an existing figure.

Same rules as metrics.py: regexes are tested against the lowercased,
prefix-stripped START of a line, most specific first, and each metric is
restricted to the statement type where it legitimately lives.

Sign note: costs are usually printed in brackets, e.g. "(1,234)", and the
parser turns that into a negative number. The calculations in
advanced.py always use abs() for these (finance cost, tax, capex,
depreciation) so the sign convention of a given report doesn't matter.

IMPORTANT: these patterns were written from common Sri Lankan statement
wording and checked against synthetic lines only. When one misses on a
real report, add the printed label here - every fix applies to all
future reports.
"""

EXTRA_METRIC_PATTERNS = {
    # ---------------- income statement ----------------
    "finance_cost": [
        r"^finance costs?\b",
        r"^finance expenses?\b",
        r"^interest expenses?\b",
        r"^interest on (borrowings|loans)",
    ],
    "income_tax": [
        r"^income tax (expenses?|charge|\(expenses?\)|\(charge\)|/\(reversal\)|reversal)",
        r"^income tax\s*(expenses?|charge)?\s*/?\s*\(?(reversal|credit)?\)?\s*$",
        r"^tax expenses?\b",
        r"^taxation\b",
    ],
    # bank income statement lines
    "interest_income": [
        r"^interest income\b",
    ],
    "interest_expense": [
        r"^interest expenses?\b",
    ],
    "net_fee_income": [
        r"^net fee and commission income",
        r"^net fee & commission income",
        r"^net fees? and commissions? income",
    ],
    "total_operating_income": [
        r"^total operating income\b",
        r"^net operating income\b(?!.*before)",
    ],
    "total_operating_expenses": [
        r"^total operating expenses\b",
        r"^total operating costs\b",
    ],

    # ---------------- cash flow ----------------
    "depreciation": [
        r"^depreciation( and amorti[sz]ation)?\b",
        r"^depreciation of property",
    ],
    "amortisation": [
        r"^amorti[sz]ation of\b",
        r"^amorti[sz]ation\b",
    ],
    "capex": [
        r"^(acquisition|purchases?) of property,? plant (and|&) equipment",
        r"^(acquisition|purchases?) of (property|plant|fixed assets|non[- ]current assets)",
        r"^additions to (property|plant|fixed assets)",
        r"^capital expenditure\b",
    ],

    # ---------------- balance sheet ----------------
    "current_assets": [
        r"^total current assets\b",
    ],
    "current_liabilities": [
        r"^total current liabilities\b",
    ],
    "inventories": [
        r"^inventories\b",
        r"^inventory\b",
    ],
    "receivables": [
        r"^trade and other receivables\b",
        r"^trade & other receivables\b",
        r"^trade receivables\b",
        r"^trade and other debtors\b",
    ],
    "payables": [
        r"^trade and other payables\b",
        r"^trade & other payables\b",
        r"^trade payables\b",
        r"^trade and other creditors\b",
    ],
    "retained_earnings": [
        r"^retained earnings\b",
        r"^retained profit\b",
    ],
    "contract_assets": [
        r"^contract assets\b",
        r"^amounts due from customers for contract work",
        r"^gross amount due from customers",
    ],
    "contract_liabilities": [
        r"^contract liabilities\b",
        r"^amounts due to customers for contract work",
        r"^advances? (received )?from customers",
    ],
    # bank balance sheet lines
    "net_loans": [
        r"^loans and advances to customers\b",
        r"^loans and receivables to other customers\b",
        r"^loans and receivables\b",
        r"^loans and advances\b",
    ],
    "customer_deposits": [
        r"^due to depositors\b",
        r"^deposits from customers\b",
        r"^customer deposits\b",
        r"^due to customers\b",
        r"^deposits due to customers\b",
    ],
}

EXTRA_RESTRICT_TO_STMT_TYPE = {
    "finance_cost": "income_statement",
    "income_tax": "income_statement",
    "interest_income": "income_statement",
    "interest_expense": "income_statement",
    "net_fee_income": "income_statement",
    "total_operating_income": "income_statement",
    "total_operating_expenses": "income_statement",
    "depreciation": "cash_flow",
    "amortisation": "cash_flow",
    "capex": "cash_flow",
    "current_assets": "balance_sheet",
    "current_liabilities": "balance_sheet",
    "inventories": "balance_sheet",
    "receivables": "balance_sheet",
    "payables": "balance_sheet",
    "retained_earnings": "balance_sheet",
    "contract_assets": "balance_sheet",
    "contract_liabilities": "balance_sheet",
    "net_loans": "balance_sheet",
    "customer_deposits": "balance_sheet",
}
