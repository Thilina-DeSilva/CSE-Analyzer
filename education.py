"""
Plain-language education layer. Nothing here is shown unless the user
explicitly opens it (a "Learn" tab, or an expander toggle) - the report
itself stays clean and number-focused by default.
"""

GLOSSARY = {
    "revenue": {
        "plain": "The total money the company earned from its normal business (selling goods/services) before any costs are subtracted. Think of it as the top-line 'sales' number.",
        "watch_for": "Growing revenue is good, but only matters if profit grows too — a company can grow sales while losing more money.",
        "learn_more": [
            {"title": "Investopedia: Revenue", "url": "https://www.investopedia.com/terms/r/revenue.asp"},
        ],
    },
    "gross_income": {
        "plain": "For a BANK specifically: total income from interest (on loans) plus fees, before operating costs. Not directly comparable to an industrial company's 'Revenue'.",
        "watch_for": "Banks make money differently — don't compare this number directly to a manufacturing or retail company's revenue.",
        "learn_more": [
            {"title": "Investopedia: How Banks Make Money", "url": "https://www.investopedia.com/ask/answers/032315/how-do-banks-make-money.asp"},
        ],
    },
    "net_interest_income": {
        "plain": "For a bank: interest earned on loans, minus interest paid on deposits/borrowings. This is the bank's 'core' profit engine before fees and costs.",
        "watch_for": "A shrinking net interest income can mean rising deposit costs or weak loan demand.",
        "learn_more": [
            {"title": "Investopedia: Net Interest Income", "url": "https://www.investopedia.com/terms/n/netinterest-income.asp"},
        ],
    },
    "gross_profit": {
        "plain": "Revenue minus the direct cost of making/buying what was sold. Shows how much room the company has before other expenses (rent, salaries, marketing) are paid.",
        "watch_for": "A shrinking gross profit margin (gross profit ÷ revenue) often means rising input costs or price competition.",
        "learn_more": [
            {"title": "Investopedia: Gross Profit", "url": "https://www.investopedia.com/terms/g/grossprofit.asp"},
        ],
    },
    "operating_profit": {
        "plain": "Profit from the company's core business operations, after gross profit but before interest and tax. Shows how well the actual business runs, separate from financing/tax decisions.",
        "watch_for": "Operating profit growing slower than revenue can mean costs are creeping up.",
        "learn_more": [
            {"title": "Investopedia: Operating Profit", "url": "https://www.investopedia.com/terms/o/operating_profit.asp"},
        ],
    },
    "profit_before_tax": {
        "plain": "Profit after all operating and financing costs, but before the tax bill is subtracted.",
        "watch_for": "Useful for comparing companies with very different tax situations.",
        "learn_more": [
            {"title": "Investopedia: Earnings Before Tax (EBT)", "url": "https://www.investopedia.com/terms/e/ebt.asp"},
        ],
    },
    "net_profit": {
        "plain": "The 'bottom line' — what's actually left for shareholders after every single expense, interest, and tax. Often called 'profit for the year' or 'earnings'.",
        "watch_for": "This is the number dividends and EPS are based on. Negative net profit means the company lost money that year.",
        "learn_more": [
            {"title": "Investopedia: Net Income", "url": "https://www.investopedia.com/terms/n/netincome.asp"},
        ],
    },
    "eps": {
        "plain": "Earnings Per Share — net profit divided by the number of shares that exist. Tells you how much profit is 'attributable' to each single share you'd own.",
        "watch_for": "A company can grow EPS by buying back shares even if total profit is flat — always check if profit itself is growing too.",
        "learn_more": [
            {"title": "Investopedia: Earnings Per Share (EPS)", "url": "https://www.investopedia.com/terms/e/eps.asp"},
        ],
    },
    "total_assets": {
        "plain": "Everything the company owns and controls that has value — cash, buildings, equipment, inventory, money owed to it by customers, investments, etc.",
        "watch_for": "Assets growing mainly through debt (not equity/profit) can be a warning sign.",
        "learn_more": [
            {"title": "Investopedia: Asset", "url": "https://www.investopedia.com/terms/a/asset.asp"},
            {"title": "Investopedia: Balance Sheet", "url": "https://www.investopedia.com/terms/b/balancesheet.asp"},
        ],
    },
    "total_liabilities": {
        "plain": "Everything the company owes to others — loans, unpaid bills, deposits (for banks), taxes owed, etc.",
        "watch_for": "Compare to Total Equity — if liabilities are many times larger than equity, the company is highly leveraged (risky if things go wrong).",
        "learn_more": [
            {"title": "Investopedia: Liability", "url": "https://www.investopedia.com/terms/l/liability.asp"},
        ],
    },
    "total_equity": {
        "plain": "What's left over for shareholders if the company sold everything and paid off every debt: Total Assets − Total Liabilities. Also called 'net worth' or 'book value'.",
        "watch_for": "Equity should generally grow over time as the company retains profit. Shrinking equity is a red flag.",
        "learn_more": [
            {"title": "Investopedia: Shareholder Equity", "url": "https://www.investopedia.com/terms/s/shareholdersequity.asp"},
        ],
    },
    "cash_and_equivalents": {
        "plain": "Actual cash and things that convert to cash almost instantly (like short-term deposits). The company's 'liquid' buffer.",
        "watch_for": "A company can be profitable on paper but run out of actual cash — this number matters for survival.",
        "learn_more": [
            {"title": "Investopedia: Cash and Cash Equivalents (CCE)", "url": "https://www.investopedia.com/terms/c/cashandcashequivalents.asp"},
        ],
    },
    "total_debt": {
        "plain": "Interest-bearing borrowings — bank loans, bonds, subordinated debt. This is a BEST-EFFORT sum from lines mentioning borrowings; always marked for manual verification since companies label debt differently.",
        "watch_for": "For banks, this deliberately excludes customer deposits (deposits fund banks, they aren't 'debt' in the usual sense).",
        "learn_more": [
            {"title": "Investopedia: Total Debt", "url": "https://www.investopedia.com/terms/t/total-debt.asp"},
        ],
    },
    "operating_cash_flow": {
        "plain": "Actual CASH generated (or used) by the core business during the year — different from 'net profit', which includes non-cash accounting items.",
        "watch_for": "A company reporting a profit but NEGATIVE operating cash flow, year after year, deserves a closer look — profit on paper isn't cash in the bank.",
        "learn_more": [
            {"title": "Investopedia: Operating Cash Flow (OCF)", "url": "https://www.investopedia.com/terms/o/operatingcashflow.asp"},
            {"title": "Investopedia: Statement of Cash Flows", "url": "https://www.investopedia.com/investing/what-is-a-cash-flow-statement/"},
        ],
    },
    "dividend_paid": {
        "plain": "Cash actually paid out to shareholders during the year, shown as a cash outflow (often a negative number in the cash flow statement).",
        "watch_for": "Paying large dividends while profit is falling or debt is rising can be unsustainable.",
        "learn_more": [
            {"title": "Investopedia: Dividend", "url": "https://www.investopedia.com/terms/d/dividend.asp"},
        ],
    },
    # ratios
    "net_profit_margin_pct": {
        "plain": "Net Profit ÷ Revenue (or Gross Income for banks) × 100. Out of every Rs. 100 earned, how much ends up as actual profit.",
        "watch_for": "A shrinking margin over time — even with growing revenue — often signals rising costs or pricing pressure.",
        "learn_more": [
            {"title": "Investopedia: Net Profit Margin", "url": "https://www.investopedia.com/terms/n/net_margin.asp"},
        ],
    },
    "roe_pct": {
        "plain": "Return on Equity — Net Profit ÷ Shareholders' Equity × 100. How efficiently the company turns shareholders' money into profit.",
        "watch_for": "Very high ROE can sometimes come from very high debt (leverage) rather than genuine efficiency — check Debt/Equity alongside it.",
        "learn_more": [
            {"title": "Investopedia: Return on Equity (ROE)", "url": "https://www.investopedia.com/terms/r/returnonequity.asp"},
        ],
    },
    "roa_pct": {
        "plain": "Return on Assets — Net Profit ÷ Total Assets × 100. How efficiently the company uses everything it owns to generate profit.",
        "watch_for": "Useful alongside ROE — if ROE is high but ROA is low, the company is relying heavily on debt.",
        "learn_more": [
            {"title": "Investopedia: Return on Assets (ROA)", "url": "https://www.investopedia.com/terms/r/returnonassets.asp"},
        ],
    },
    "debt_to_equity": {
        "plain": "Total Debt ÷ Total Equity. How many rupees of debt exist for every rupee of shareholder money.",
        "watch_for": "Higher = more leveraged = more risk if profits fall or interest rates rise. 'High' varies a lot by industry — banks naturally run much higher leverage than manufacturers.",
        "learn_more": [
            {"title": "Investopedia: Debt-to-Equity (D/E) Ratio", "url": "https://www.investopedia.com/terms/d/debtequityratio.asp"},
        ],
    },
    "liabilities_to_equity": {
        "plain": "ALL liabilities (not just interest-bearing debt) ÷ Total Equity. A broader leverage measure than Debt/Equity.",
        "watch_for": "For banks this is naturally very high (deposits are liabilities) — not directly comparable to an industrial company.",
        "learn_more": [
            {"title": "Investopedia: Financial Leverage", "url": "https://www.investopedia.com/terms/l/leverage.asp"},
        ],
    },
    "revenue_growth_pct": {
        "plain": "How much Revenue (or Gross Income) grew compared to the prior year, in percent.",
        "watch_for": "One good year doesn't make a trend — look at growth across multiple years if you have them.",
        "learn_more": [
            {"title": "Investopedia: Revenue Growth Rate", "url": "https://www.investopedia.com/ask/answers/070914/what-formula-calculating-revenue-growth.asp"},
        ],
    },
    "net_profit_growth_pct": {
        "plain": "How much Net Profit grew compared to the prior year, in percent.",
        "watch_for": "If revenue grows but profit doesn't (or shrinks), costs are outpacing sales.",
        "learn_more": [
            {"title": "Investopedia: Earnings Growth", "url": "https://www.investopedia.com/terms/e/earnings-growth.asp"},
        ],
    },
    "eps_growth_pct": {
        "plain": "How much EPS grew compared to the prior year, in percent.",
        "watch_for": "Check this against net profit growth — if EPS grows faster than profit, shares may have been bought back.",
        "learn_more": [
            {"title": "Investopedia: Earnings Per Share (EPS)", "url": "https://www.investopedia.com/terms/e/eps.asp"},
            {"title": "Investopedia: Share Buybacks", "url": "https://www.investopedia.com/terms/s/stockrepurchase.asp"},
        ],
    },
    "pe_ratio": {
        "plain": "Price ÷ EPS. How many years of CURRENT earnings it would take to 'earn back' the share price, if profit stayed flat. A rough measure of how expensive the stock is relative to its earnings.",
        "watch_for": "A high P/E can mean the market expects strong future growth — OR that the stock is simply overpriced. A low P/E can mean a bargain — OR that the market expects trouble ahead. P/E alone never tells you which.",
        "learn_more": [
            {"title": "Investopedia: Price-to-Earnings (P/E) Ratio", "url": "https://www.investopedia.com/terms/p/price-earningsratio.asp"},
        ],
    },
    "pb_ratio": {
        "plain": "Price ÷ Book Value Per Share. Compares what you'd pay per share to what the company's accounting 'net worth' is per share.",
        "watch_for": "Below 1 can mean the market thinks the company is worth less than its stated assets (or the assets are overstated). Above 1 is normal for profitable companies with good future prospects.",
        "learn_more": [
            {"title": "Investopedia: Price-to-Book (P/B) Ratio", "url": "https://www.investopedia.com/terms/p/price-to-bookratio.asp"},
        ],
    },
    "dividend_yield_pct": {
        "plain": "Annual dividend per share ÷ Share Price × 100. What % return you get from dividends alone at the current price, ignoring any share price change.",
        "watch_for": "A very high yield can sometimes mean the market expects the dividend to be CUT soon (which pushes the price down, mechanically raising the yield) — not always a genuinely good deal.",
        "learn_more": [
            {"title": "Investopedia: Dividend Yield", "url": "https://www.investopedia.com/terms/d/dividendyield.asp"},
        ],
    },
    # --- Pre-buy checklist terms ---
    "revenue_cagr": {
        "plain": "Compound Annual Growth Rate of revenue (or gross income for banks) over the years we have. It answers: 'If growth had been steady every year, what average yearly % growth would turn the first year's revenue into the latest year's?'",
        "watch_for": "One spectacular year can inflate a short-span CAGR. Prefer 4–5 year spans. Also compare to inflation and to peer companies in the same industry.",
        "learn_more": [
            {"title": "Investopedia: CAGR", "url": "https://www.investopedia.com/terms/c/cagr.asp"},
        ],
    },
    "eps_cagr": {
        "plain": "Compound Annual Growth Rate of Earnings Per Share. Shows how fast profit attributable to each share has compounded — the number that ultimately drives long-term share-price growth for many investors.",
        "watch_for": "EPS can rise from share buybacks even when total profit is flat. Cross-check against Net Profit CAGR. Negative start years make CAGR undefined — we skip those.",
        "learn_more": [
            {"title": "Investopedia: CAGR", "url": "https://www.investopedia.com/terms/c/cagr.asp"},
            {"title": "Investopedia: EPS", "url": "https://www.investopedia.com/terms/e/eps.asp"},
        ],
    },
    "net_profit_cagr": {
        "plain": "Compound Annual Growth Rate of the bottom-line Net Profit. The purest view of whether the business is becoming more (or less) profitable over time in absolute rupees.",
        "watch_for": "Volatile profits (big up one year, down the next) produce a CAGR that looks smooth but hides risk. Always glance at the year-by-year series too.",
        "learn_more": [
            {"title": "Investopedia: CAGR", "url": "https://www.investopedia.com/terms/c/cagr.asp"},
        ],
    },
    "interest_coverage": {
        "plain": "Operating Profit ÷ Interest (finance) expense. How many times the company's core operating profit covers the interest it must pay on debt. A buffer against rising rates or a profit dip.",
        "watch_for": "Below ~2–3× is uncomfortable for most non-financial companies; banks are different. This app does not extract interest expense yet — you need to read it from the income statement.",
        "learn_more": [
            {"title": "Investopedia: Interest Coverage Ratio", "url": "https://www.investopedia.com/terms/i/interestcoverageratio.asp"},
        ],
    },
    "navps": {
        "plain": "Net Asset Value Per Share (also called Book Value Per Share) — Total Equity ÷ number of shares. What the accounting books say each share is 'worth' if the company liquidated at stated values.",
        "watch_for": "Book values can be stale (property held at old cost) or optimistic. P/B < 1 can mean a bargain or that the market distrusts the asset values. We approximate shares as Net Profit ÷ EPS.",
        "learn_more": [
            {"title": "Investopedia: Book Value Per Share", "url": "https://www.investopedia.com/terms/b/bookvaluepershare.asp"},
        ],
    },
    "dividend_per_share": {
        "plain": "Cash dividend paid out for each ordinary share during the year. Approximated here as |Dividend Paid| ÷ (Net Profit ÷ EPS).",
        "watch_for": "A rising DPS while earnings fall is often unsustainable. Special / one-off dividends can distort the history — check the notes in the annual report.",
        "learn_more": [
            {"title": "Investopedia: Dividend", "url": "https://www.investopedia.com/terms/d/dividend.asp"},
        ],
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
3. When you are seriously considering a purchase, open the **Before You Buy** tab — it
   consolidates growth CAGRs, profitability, financial strength, shareholder value,
   valuation, and risk patterns into one checklist, with a deeper how-to guide.
4. Use the **glossary** (toggle "Explain these terms" anywhere in the app) whenever a word
   is unfamiliar — don't skip past terms you don't understand.
5. Use the **Valuation** tab for P/E, P/B and dividend yield — but remember they are
   *inputs to your own thinking*, not a verdict. They tell you if a stock is statistically
   cheap/expensive relative to earnings — not whether it's a *good* company.
6. **Never rely on one report alone.** Compare to at least one competitor in the same
   industry, and read the actual "Management Discussion" pages for context this app doesn't
   extract (strategy, risks, industry conditions).

### Important
This tool does financial-statement arithmetic. It does not, and should not, tell you what to
buy or how much. Investing decisions depend on your own goals, risk tolerance, and full
financial picture — things no tool reading one PDF can know about you.
"""


PRE_BUY_GUIDE = """
## 🔍 Before You Buy — How to Use This Checklist

This tab is a **structured pre-purchase review**. It does not tell you to buy or avoid
anything. It gathers the numbers experienced investors typically scan *before* putting
money into a stock, and flags patterns that deserve a second look.

### Why a checklist at all?
Buying a stock is buying a slice of a business. The annual report is the business's
report card. A checklist stops you from:
- Anchoring on one exciting number (e.g. a high ROE) while missing rising debt
- Ignoring multi-year trends and reacting to a single good (or bad) year
- Skipping cash-flow quality and relying only on accounting profit

### The six blocks — what each is asking

**1. Growth (5-year CAGR)**
- *Is the business getting bigger in a durable way?*
- Revenue CAGR, Net Profit CAGR, and EPS CAGR over the years we extracted.
- CAGR smooths the path between the first and last year. Always also glance at the
  year-by-year table — a smooth CAGR can hide a boom-and-bust middle.

**2. Profitability**
- *Does growth turn into real profit for owners?*
- ROE (return on equity), ROA (return on assets), and Net Profit Margin for the latest year.
- High ROE with low ROA often means heavy leverage — check Debt/Equity in the next block.

**3. Financial strength**
- *Can the company survive a rough patch?*
- Debt/Equity, Operating Cash Flow trend, and (manual) Interest Coverage.
- Interest coverage is not auto-filled yet: open the income statement, find
  "Finance costs" / "Interest expense", and divide Operating Profit by it.
  Rough rule of thumb for non-banks: above 3× is comfortable; below 1.5× is tight.

**4. Shareholder value**
- *Is value actually accruing to the owners of the shares?*
- NAVPS (book value per share) and its growth, plus approximate Dividend Per Share history.
- Rising NAVPS over time usually means retained profits are building the equity base.
- Dividends are optional; a company that reinvests well can create more wealth without
  paying a high yield.

**5. Valuation**
- *What are you paying relative to earnings, book value, and dividends?*
- P/E, P/B, Dividend Yield, and current price vs NAVPS — all need today's share price
  (enter it here or in the Valuation tab).
- These ratios are **inputs**, not verdicts. A low P/E can be a bargain or a value trap;
  a high P/E can be justified growth or pure optimism.

**6. Risk flags**
- *Any automatic warning patterns in the numbers we have?*
- Debt rising sharply, cash flow weaker than reported profit, inconsistent earnings
  (loss years in the sample).
- Green does **not** mean "safe". It only means these particular automated checks did
  not fire. Always read the auditor's opinion, related-party notes, and risk-factor
  section of the actual PDF.

### A practical order of work
1. Confirm the extraction looks sane (Verification tab + source lookup on the Table tab).
2. Scan Growth and Profitability for multi-year direction.
3. Check Financial strength and Risk flags for survival issues.
4. Only then look at Valuation — price a weak business attractively and you can still lose.
5. Compare at least one peer in the same industry; this app is single-company by design.
6. Read the Management Discussion in the original report for context the numbers cannot give.

### What this checklist deliberately does *not* do
- It does not score or rank the stock.
- It does not know your time horizon, risk tolerance, or portfolio concentration.
- It does not replace reading the PDF, competitor filings, or industry news.

Use it as a disciplined first pass. The final decision remains yours.
"""


def get_explanation(metric_key: str) -> dict:
    return GLOSSARY.get(metric_key, {"plain": "No explanation available yet.", "watch_for": ""})
