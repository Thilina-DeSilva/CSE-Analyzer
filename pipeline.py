"""
V4: Full pipeline for ONE annual report PDF.

  PDF -> find statement pages -> extract metrics from each -> merge
  -> derive anything missing -> return one clean structured result,
  with every number traceable to a page + source line.
"""

import pdfplumber
from find_statements import find_statement_pages
from metrics import extract_metrics_from_page, derive_missing_metrics, Extraction
from years import detect_years, detect_period
from industry import detect_industry


def process_report(pdf_path: str, verbose: bool = False) -> dict:
    located = find_statement_pages(pdf_path, verbose=verbose)

    all_metrics = {}
    pages_used = {}

    # detect BANK vs INDUSTRIAL from the income statement + balance
    # sheet text, before extracting - determines whether "revenue" or
    # "gross_income" is the right top-line concept, and how Debt is
    # annotated (a bank's deposits aren't conventional debt).
    income_pages = located.get("income_statement", [])
    balance_pages = located.get("balance_sheet", [])
    industry = detect_industry(
        income_pages[0]["text"] if income_pages else "",
        balance_pages[0]["text"] if balance_pages else "",
    )

    # income statement + balance sheet + cash flow, best page each.
    # Balance sheet and cash flow commonly spill onto a second page
    # (liabilities/equity, or financing activities) - we saw this for
    # real on LAUGFS Gas: Total Liabilities and half the Debt lines
    # were on the page AFTER the one our anchor matched. So for those
    # two statement types we also pull in page+1 and combine the text,
    # as long as it doesn't look like a different section has started
    # (i.e. it's still mostly numbers, not prose).
    with pdfplumber.open(pdf_path) as pdf:
        for stmt_type in ["income_statement", "balance_sheet", "cash_flow"]:
            candidates = located.get(stmt_type, [])
            if not candidates:
                continue
            best = candidates[0]
            page_num = best["page"]
            text = best["text"]

            # Statement tables often spill onto the next page (or repeat the
            # same statement title on a continuation page — common in interims).
            if stmt_type in ("income_statement", "balance_sheet", "cash_flow") and page_num + 1 < len(pdf.pages):
                next_text = pdf.pages[page_num + 1].extract_text() or ""
                pdf.pages[page_num + 1].flush_cache()
                head = next_text[:250].lower()
                # Always allow pure continuation. Block only when a DIFFERENT
                # major section clearly starts (notes / auditor / wrong statement).
                same_stmt = {
                    "income_statement": ("income statement", "profit or loss"),
                    "balance_sheet": ("financial position", "balance sheet"),
                    "cash_flow": ("cash flow",),
                }.get(stmt_type, ())
                is_same = any(s in head for s in same_stmt)
                is_other = (
                    "independent auditor" in head
                    or "notes to the financial statements" in head
                    or (stmt_type != "balance_sheet" and "financial position" in head and not is_same)
                    or (stmt_type != "cash_flow" and "statement of cash flows" in head and not is_same)
                    or (stmt_type != "income_statement" and "income statement" in head and "financial position" not in head and not is_same)
                )
                if is_same or not is_other:
                    # Heuristic: if page is still number-dense, keep it
                    import re as _re
                    money_n = len(_re.findall(r"\b\d{1,3}(?:,\d{3})+\b", next_text))
                    if is_same or money_n >= 8:
                        text = text + "\n" + next_text
                        pages_used.setdefault(stmt_type + "_pages", []).extend([page_num, page_num + 1])

            pages_used[stmt_type] = page_num
            page_metrics = extract_metrics_from_page(text, page_num, stmt_type=stmt_type,
                                                       industry=industry)
            for k, v in page_metrics.items():
                # don't overwrite an existing direct match with a weaker one
                if k not in all_metrics or all_metrics[k].method != "direct":
                    all_metrics[k] = v

        # Fallback: many CSE companies (e.g. Lanka IOC) publish a SINGLE
        # combined "Statement of Comprehensive Income" as their P&L -
        # Revenue through Net Profit, then Other Comprehensive Income,
        # all on one page - rather than a separate standalone "Income
        # Statement". Our anchor search files that under a different
        # category (comprehensive_income), so if the dedicated income
        # statement page came up empty on the core top-line/bottom-line
        # figures, retry against the comprehensive_income page(s) too -
        # the same line-matching patterns work fine on it since they
        # match the row content, not the page heading.
        have_topline = all_metrics.get("revenue") or all_metrics.get("gross_income")
        have_bottomline = all_metrics.get("net_profit")
        if not (have_topline and have_bottomline):
            ci_candidates = located.get("comprehensive_income", [])
            # Filter out "Statement of Changes in Equity" pages - they get
            # miscategorised as comprehensive_income (they often mention
            # "Other Comprehensive Income" further down the page) and have
            # their OWN "Profit for the Year" row, but as one column in a
            # multi-column equity-movement table, not a current/previous
            # year pair - matching it produced a real bug (Lanka IOC: read
            # a "-" nil cell as net_profit=0 instead of the real 882,634
            # from the actual combined P&L+OCI statement). Prefer pages
            # that actually look like a P&L (a revenue/turnover line near
            # the top) and process those first.
            def _looks_like_pl(c):
                head = c["text"][:250].lower()
                return "changes in equity" not in head and ("revenue" in c["text"][:700].lower()
                                                              or "turnover" in c["text"][:700].lower()
                                                              or "gross income" in c["text"][:700].lower())
            ci_candidates = sorted(ci_candidates, key=lambda c: not _looks_like_pl(c))

            for c in ci_candidates:
                if "changes in equity" in c["text"][:250].lower():
                    continue
                page_num, text = c["page"], c["text"]
                page_metrics = extract_metrics_from_page(text, page_num, stmt_type="income_statement",
                                                           industry=industry)
                for k, v in page_metrics.items():
                    if k not in all_metrics or all_metrics[k].method != "direct":
                        all_metrics[k] = v
                pages_used.setdefault("income_statement_fallback_comprehensive_income", []).append(page_num)
                have_topline = all_metrics.get("revenue") or all_metrics.get("gross_income")
                have_bottomline = all_metrics.get("net_profit")
                if have_topline and have_bottomline:
                    break

    all_metrics = derive_missing_metrics(all_metrics)

    # Period detection (annual FY or interim Q1/H1/...)
    period = {
        "current_year": None, "previous_year": None,
        "period_type": "FY", "period_key": None, "previous_period_key": None,
        "label": None, "previous_label": None, "doc_kind": "unknown",
    }
    if income_pages:
        period = detect_period(income_pages[0]["text"])
    elif balance_pages:
        period = detect_period(balance_pages[0]["text"])

    return {
        "pdf_path": pdf_path,
        "pages_used": pages_used,
        "metrics": all_metrics,
        "year_current": period.get("current_year"),
        "year_previous": period.get("previous_year"),
        "period": period,
        "industry": industry,
    }


def to_yearly_records(result: dict) -> list:
    """
    Reshape one report's {metric: Extraction(current, previous)} into
    one or two period records. Period key is "2024" for annual or
    "2026-H1" / "2026-Q1" for interim so they don't clobber each other.
    """
    period = result.get("period") or {}
    yc = result.get("year_current")
    yp = result.get("year_previous")
    industry = result.get("industry", "industrial")
    ptype = period.get("period_type") or "FY"
    cur_key = period.get("period_key") or (str(yc) if yc else None)
    prev_key = period.get("previous_period_key") or (str(yp) if yp else None)
    cur_label = period.get("label") or (str(yc) if yc else "—")
    prev_label = period.get("previous_label") or (str(yp) if yp else "—")
    doc_kind = period.get("doc_kind") or "unknown"

    def _blank(year, period_key, label, is_current):
        return {
            "year": year,
            "period_key": period_key,
            "period_type": ptype,
            "period_label": label,
            "source_pdf": result["pdf_path"],
            "industry": industry,
            "doc_kind": doc_kind,
            "_is_current": is_current,
            "_extractions": {},
        }

    cur_record = _blank(yc, cur_key, cur_label, True)
    prev_record = _blank(yp, prev_key, prev_label, False)

    for key, ext in result["metrics"].items():
        cur_record[key] = ext.current
        cur_record["_extractions"][key] = {
            "value": ext.current, "unit": ext.unit, "page": ext.page,
            "method": ext.method, "source_line": ext.source_line, "notes": ext.notes,
            "original_label": getattr(ext, "original_label", "") or "",
        }
        if ext.previous is not None and yp is not None:
            prev_record[key] = ext.previous
            prev_record["_extractions"][key] = {
                "value": ext.previous, "unit": ext.unit, "page": ext.page,
                "method": ext.method, "source_line": ext.source_line, "notes": ext.notes,
                "original_label": getattr(ext, "original_label", "") or "",
            }

    records = []
    if cur_key is not None:
        records.append(cur_record)
    if prev_key is not None and prev_key != cur_key:
        records.append(prev_record)
    return records


def print_report(result: dict):
    print(f"\n=== {result['pdf_path']} ===")
    print(f"Pages used: {result['pages_used']}")
    print(f"{'Metric':<28}{'Current':>18}{'Previous':>18}  Unit          Method    Page")
    print("-" * 100)
    for key, ext in result["metrics"].items():
        fmt = ",.2f" if key in ("eps", "dps") else ",.0f"
        cur = f"{ext.current:{fmt}}" if ext.current is not None else "—"
        prev = f"{ext.previous:{fmt}}" if ext.previous is not None else "—"
        print(f"{key:<28}{cur:>18}{prev:>18}  {ext.unit:<13} {ext.method:<9} {ext.page}")
        if ext.notes:
            print(f"    note: {ext.notes}")


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    result = process_report(path, verbose=True)
    print_report(result)
