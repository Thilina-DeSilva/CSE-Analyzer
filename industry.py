"""
Detect whether a report is a BANK/financial-institution or a
NON-BANK/industrial company, so we don't force bank-specific concepts
(Gross Income, which includes interest+fee income) into a generic
"Revenue" bucket, and so Debt is interpreted correctly (a bank's
primary funding is customer deposits, not "debt" in the conventional
sense - lumping them together would be misleading).
"""

BANK_SIGNALS = [
    "net interest income",
    "due to depositors",
    "due to banks",
    "loans and advances to customers",
    "interest income",
    "interest expense",
    "impairment charges for loans",
]


def detect_industry(*page_texts: str) -> str:
    """Returns 'bank' or 'industrial'. Needs 2+ bank-specific signals
    to classify as a bank, to avoid misclassifying an industrial firm
    that merely mentions "interest income" from a bank deposit once."""
    combined = " ".join(page_texts).lower()
    score = sum(1 for s in BANK_SIGNALS if s in combined)
    return "bank" if score >= 2 else "industrial"
