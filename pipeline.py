"""
V4: Full pipeline for ONE annual report PDF.

  PDF -> find statement pages -> extract metrics from each -> merge
  -> derive anything missing -> return one clean structured result,
  with every number traceable to a page + source line.
"""

import pdfplumber
from find_statements import find_statement_pages
from metrics import extract_metrics_from_page, derive_missing_metrics, Extraction
from years import detect_years


def process_report(pdf_path: str, verbose: bool = False) -> dict:
    located = find_statement_pages(pdf_path, verbose=verbose)

    all_metrics = {}
    pages_used = {}

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

            if stmt_type in ("balance_sheet", "cash_flow") and page_num + 1 < len(pdf.pages):
                next_text = pdf.pages[page_num + 1].extract_text() or ""
                pdf.pages[page_num + 1].flush_cache()
                # crude continuation check: still numbers-dense, not a
                # new "Notes to the Financial Statements" section
                if "notes to the financial statements" not in next_text[:200].lower():
                    text = text + "\n" + next_text
                    pages_used.setdefault(stmt_type + "_pages", []).extend([page_num, page_num + 1])

            pages_used[stmt_type] = page_num
            page_metrics = extract_metrics_from_page(text, page_num, stmt_type=stmt_type)
            for k, v in page_metrics.items():
                # don't overwrite an existing direct match with a weaker one
                if k not in all_metrics or all_metrics[k].method != "direct":
                    all_metrics[k] = v

    all_metrics = derive_missing_metrics(all_metrics)

    # figure out which two fiscal years the current/previous columns
    # represent, from the income statement page's header line
    year_current, year_previous = None, None
    income_pages = located.get("income_statement", [])
    if income_pages:
        year_current, year_previous = detect_years(income_pages[0]["text"])

    return {
        "pdf_path": pdf_path,
        "pages_used": pages_used,
        "metrics": all_metrics,
        "year_current": year_current,
        "year_previous": year_previous,
    }


def to_yearly_records(result: dict) -> list:
    """
    Reshape one report's {metric: Extraction(current, previous)} into
    two flat per-year dicts, e.g.:
      [{"year": 2024, "revenue": ..., "net_profit": ..., ...},
       {"year": 2023, "revenue": ..., "net_profit": ..., ...}]
    This is the shape we merge across multiple reports/years later.
    """
    yc, yp = result["year_current"], result["year_previous"]
    cur_record = {"year": yc, "source_pdf": result["pdf_path"], "_extractions": {}}
    prev_record = {"year": yp, "source_pdf": result["pdf_path"], "_extractions": {}}

    for key, ext in result["metrics"].items():
        cur_record[key] = ext.current
        cur_record["_extractions"][key] = {
            "value": ext.current, "unit": ext.unit, "page": ext.page,
            "method": ext.method, "source_line": ext.source_line, "notes": ext.notes,
        }
        if ext.previous is not None and yp is not None:
            prev_record[key] = ext.previous
            prev_record["_extractions"][key] = {
                "value": ext.previous, "unit": ext.unit, "page": ext.page,
                "method": ext.method, "source_line": ext.source_line, "notes": ext.notes,
            }

    records = []
    if yc is not None:
        records.append(cur_record)
    if yp is not None:
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
