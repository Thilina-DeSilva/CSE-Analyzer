"""
Plain-language education layer. Nothing here is shown unless the user
explicitly opens it (a "Learn" tab, or an expander toggle) - the report
itself stays clean and number-focused by default.
"""

GLOSSARY = {
    "revenue": {
        "plain": "The total money the company earned from its normal business (selling goods/services) before any costs are subtracted. Think of it as the top-line 'sales' number.",
        "watch_for": "Growing revenue is good, but only matters if profit grows too — a company can grow sales while losing more money.",
    },
    "gross_income": {
        "plain": "For a BANK specifically: total income from interest (on loans) plus fees, before operating costs. Not directly comparable to an industrial company's 'Revenue'.",
        "watch_for": "Banks make money differently — don't compare this number directly to a manufacturing or retail company's revenue.",
    },
    "net_interest_income": {
        "plain": "For a bank: interest earned on loans, minus interest paid on deposits/borrowings. This is the bank's 'core' profit engine before fees and costs.",
        "watch_for": "A shrinking net interest income can mean rising deposit costs or weak loan demand.",
    },
    "gross_profit": {
        "plain": "Revenue minus the direct cost of making/buying what was sold. Shows how much room the company has before other expenses (rent, salaries, marketing) are paid.",
        "watch_for": "A shrinking gross profit margin (gross profit ÷ revenue) often means rising input costs or price competition.",
    },
    "operating_profit": {
        "plain": "Profit from the company's core business operations, after gross profit but before interest and tax. Shows how well the actual business runs, separate from financing/tax decisions.",
        "watch_for": "Operating profit growing slower than revenue can mean costs are creeping up.",
    },
    "profit_before_tax": {
        "plain": "Profit after all operating and financing costs, but before the tax bill is subtracted.",
        "watch_for": "Useful for comparing companies with very different tax situations.",
    },
    "net_profit": {
        "plain": "The 'bottom line' — what's actually left for shareholders after every single expense, interest, and tax. Often called 'profit for the year' or 'earnings'.",
        "watch_for": "This is the number dividends and EPS are based on. Negative net profit means the company lost money that year.",
    },
    "eps": {
        "plain": "Earnings Per Share — net profit divided by the number of shares that exist. Tells you how much profit is 'attributable' to each single share you'd own.",
        "watch_for": "A company can grow EPS by buying back shares even if total profit is flat — always check if profit itself is growing too.",
    },
    "total_assets": {
        "plain": "Everything the company owns and controls that has value — cash, buildings, equipment, inventory, money owed to it by customers, investments, etc.",
        "watch_for": "Assets growing mainly through debt (not equity/profit) can be a warning sign.",
    },
    "total_liabilities": {
        "plain": "Everything the company owes to others — loans, unpaid bills, deposits (for banks), taxes owed, etc.",
        "watch_for": "Compare to Total Equity — if liabilities are many times larger than equity, the company is highly leveraged (risky if things go wrong).",
    },
    "total_equity": {
        "plain": "What's left over for shareholders if the company sold everything and paid off every debt: Total Assets − Total Liabilities. Also called 'net worth' or 'book value'.",
        "watch_for": "Equity should generally grow over time as the company retains profit. Shrinking equity is a red flag.",
    },
    "cash_and_equivalents": {
        "plain": "Actual cash and things that convert to cash almost instantly (like short-term deposits). The company's 'liquid' buffer.",
        "watch_for": "A company can be profitable on paper but run out of actual cash — this number matters for survival.",
    },
    "total_debt": {
        "plain": "Interest-bearing borrowings — bank loans, bonds, subordinated debt. This is a BEST-EFFORT sum from lines mentioning borrowings; always marked for manual verification since companies label debt differently.",
        "watch_for": "For banks, this deliberately excludes customer deposits (deposits fund banks, they aren't 'debt' in the usual sense).",
    },
    "operating_cash_flow": {
        "plain": "Actual CASH generated (or used) by the core business during the year — different from 'net profit', which includes non-cash accounting items.",
        "watch_for": "A company reporting a profit but NEGATIVE operating cash flow, year after year, deserves a closer look — profit on paper isn't cash in the bank.",
    },
    "dividend_paid": {
        "plain": "Cash actually paid out to shareholders during the year, shown as a cash outflow (often a negative number in the cash flow statement).",
        "watch_for": "Paying large dividends while profit is falling or debt is rising can be unsustainable.",
    },
    # ratios
    "net_profit_margin_pct": {
        "plain": "Net Profit ÷ Revenue (or Gross Income for banks) × 100. Out of every Rs. 100 earned, how much ends up as actual profit.",
        "watch_for": "A shrinking margin over time — even with growing revenue — often signals rising costs or pricing pressure.",
    },
    "roe_pct": {
        "plain": "Return on Equity — Net Profit ÷ Shareholders' Equity × 100. How efficiently the company turns shareholders' money into profit.",
        "watch_for": "Very high ROE can sometimes come from very high debt (leverage) rather than genuine efficiency — check Debt/Equity alongside it.",
    },
    "roa_pct": {
        "plain": "Return on Assets — Net Profit ÷ Total Assets × 100. How efficiently the company uses everything it owns to generate profit.",
        "watch_for": "Useful alongside ROE — if ROE is high but ROA is low, the company is relying heavily on debt.",
    },
    "debt_to_equity": {
        "plain": "Total Debt ÷ Total Equity. How many rupees of debt exist for every rupee of shareholder money.",
        "watch_for": "Higher = more leveraged = more risk if profits fall or interest rates rise. 'High' varies a lot by industry — banks naturally run much higher leverage than manufacturers.",
    },
    "liabilities_to_equity": {
        "plain": "ALL liabilities (not just interest-bearing debt) ÷ Total Equity. A broader leverage measure than Debt/Equity.",
        "watch_for": "For banks this is naturally very high (deposits are liabilities) — not directly comparable to an industrial company.",
    },
    "revenue_growth_pct": {
        "plain": "How much Revenue (or Gross Income) grew compared to the prior year, in percent.",
        "watch_for": "One good year doesn't make a trend — look at growth across multiple years if you have them.",
    },
    "net_profit_growth_pct": {
        "plain": "How much Net Profit grew compared to the prior year, in percent.",
        "watch_for": "If revenue grows but profit doesn't (or shrinks), costs are outpacing sales.",
    },
    "eps_growth_pct": {
        "plain": "How much EPS grew compared to the prior year, in percent.",
        "watch_for": "Check this against net profit growth — if EPS grows faster than profit, shares may have been bought back.",
    },
    "pe_ratio": {
        "plain": "Price ÷ EPS. How many years of CURRENT earnings it would take to 'earn back' the share price, if profit stayed flat. A rough measure of how expensive the stock is relative to its earnings.",
        "watch_for": "A high P/E can mean the market expects strong future growth — OR that the stock is simply overpriced. A low P/E can mean a bargain — OR that the market expects trouble ahead. P/E alone never tells you which.",
    },
    "pb_ratio": {
        "plain": "Price ÷ Book Value Per Share. Compares what you'd pay per share to what the company's accounting 'net worth' is per share.",
        "watch_for": "Below 1 can mean the market thinks the company is worth less than its stated assets (or the assets are overstated). Above 1 is normal for profitable companies with good future prospects.",
    },
    "dividend_yield_pct": {
        "plain": "Annual dividend per share ÷ Share Price × 100. What % return you get from dividends alone at the current price, ignoring any share price change.",
        "watch_for": "A very high yield can sometimes mean the market expects the dividend to be CUT soon (which pushes the price down, mechanically raising the yield) — not always a genuinely good deal.",
    },
}


BEGINNER_GUIDE = """
## 📚 How to Read This Report — A Beginner's Guide

### What even IS an annual report?
Every company listed on the Colombo Stock Exchange (CSE) is legally required to publish a
detailed report every year explaining how the business performed. It's long (often 200-500
pages) because it includes legal disclosures, photos, chairman's letters, and governance
details — but the part that actually matters for investing is usually under 30 pages: the
**three financial statements**.

### The 3 statements that matter

**1. Income Statement** (a.k.a. Statement of Profit or Loss)
Answers: *"Did the company make money this year?"*
Revenue in, costs out, profit left over. Read top to bottom: Revenue → minus costs →
Operating Profit → minus interest & tax → Net Profit (the real bottom line).

**2. Statement of Financial Position** (a.k.a. Balance Sheet)
Answers: *"What does the company own, and who does it owe?"*
A snapshot on ONE specific date (not "for the year", but "as at" a date).
`Assets = Liabilities + Equity` always. If Assets grew mostly because Liabilities (debt) grew,
that's worth noticing — growth funded by debt is riskier than growth funded by profit.

**3. Statement of Cash Flows**
Answers: *"Did actual CASH come in or go out?"*
This is the one most beginners skip — but it's arguably the most honest number, because
profit can include accounting entries that aren't real cash yet. A company can report a
profit and still be low on cash.

### How this app fits in
This app reads all three statements from the PDF and pulls out the ~13 key numbers, plus
calculates common ratios from them. Every number shown links back to the exact page and
line it came from — click "🔍 Look up a value's source" in the Table tab to verify anything
yourself against the original PDF.

### A realistic way to use this as a beginner
1. Look at the **5-year trend**, not one year. Is revenue/profit generally growing?
2. Check the **Red Flags** tab — it surfaces the specific things experienced investors check
   first (falling margins, rising debt, negative cash flow).
3. Use the **glossary** (toggle "Explain these terms" anywhere in the app) whenever a word
   is unfamiliar — don't skip past terms you don't understand.
4. If you're considering buying, use the **Valuation** tab — but remember P/E, P/B and
   dividend yield are *inputs to your own thinking*, not a verdict. They tell you if a stock
   is statistically cheap/expensive relative to earnings — not whether it's a *good* company.
5. **Never rely on one report alone.** Compare to at least one competitor in the same
   industry, and read the actual "Management Discussion" pages for context this app doesn't
   extract (strategy, risks, industry conditions).

### Important
This tool does financial-statement arithmetic. It does not, and should not, tell you what to
buy or how much. Investing decisions depend on your own goals, risk tolerance, and full
financial picture — things no tool reading one PDF can know about you.
"""


def get_explanation(metric_key: str) -> dict:
    return GLOSSARY.get(metric_key, {"plain": "No explanation available yet.", "watch_for": ""})
