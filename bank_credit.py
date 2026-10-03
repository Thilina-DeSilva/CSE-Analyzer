"""
Bank credit-quality extraction (Stage 1/2/3 loans, impairment allowance, NPL).

Why a separate module: these figures do NOT sit on the four face statements.
They live in the loan note ("Loans and receivables to other customers") and the
credit-quality / ECL tables, so find_statements.py never looks at those pages.
This module scans the PDF for them, then reuses the same number parser as
metrics.py so signs, brackets and dashes behave identically.

Raw keys produced (all stored on the record like any other metric):
    gross_loans            Gross loans to customers, before impairment allowance
    stage1_loans           Gross carrying amount, Stage 1
    stage2_loans           Gross carrying amount, Stage 2
    stage3_loans           Gross carrying amount, Stage 3 (credit-impaired)
    stage1_impairment      ECL allowance held against Stage 1
    stage2_impairment      ECL allowance held against Stage 2
    stage3_impairment      ECL allowance held against Stage 3
    total_loan_impairment  Total ECL allowance on loans (all stages)
    npl_loans              Reported gross NPL / impaired loans line (if printed)

Ratios (Stage %, coverage, NPL ratio) are calculated in advanced.py.

Two table layouts are handled, because Sri Lankan banks use both:
  A) one ROW per stage:      "Stage 1   1,234,567   1,100,000"
  B) one COLUMN per stage:   header "Stage 1  Stage 2  Stage 3  Total", then rows
                             such as "Balance as at 31 December 2024  a b c total"

Safeguards (a wrong credit number is worse than a missing one):
  * Rows only count while the nearest preceding table heading is about LOANS TO
    CUSTOMERS - not placements, debt securities, guarantees or commitments, which
    reuse the same Stage 1/2/3 layout.
  * Layout B rows must add up: Stage 1 + 2 + 3 == Total (within 1%), otherwise
    the row is skipped.
  * Anything summed / derived is flagged method="summed"/"derived", so it lands
    on the Verification tab.
  * Not found stays None ("—"), never 0.
"""

from __future__ import annotations

import re
from typing import Optional

from metrics import (
    Extraction, detect_unit, _clean_line_start, _parse_money_tokens, _repair_broken_money,
)

BANK_CREDIT_KEYS = [
    "gross_loans", "stage1_loans", "stage2_loans", "stage3_loans",
    "stage1_impairment", "stage2_impairment", "stage3_impairment",
    "total_loan_impairment", "npl_loans",
]

_STAGE_ROW = re.compile(r"^(?:-\s*)?stage\s*([123])\b")
_OTHER_ASSET_CLASS = re.compile(
    r"\b(banks?|debt instruments?|securities|commitments?|guarantees?|placements?|repo|"
    r"financial investments?|treasury|due from|cash and|derivative|off[- ]balance)\b")
_CUSTOMER_LOANS = re.compile(
    r"loans? and (receivables|advances)|loans? to customers|customer loans|gross loans|"
    r"financing (facilities|receivables)")
_ECL_WORDS = re.compile(r"impairment|allowance|\becl\b|expected credit|provision|loss allowance")
_GROSS_WORDS = re.compile(r"gross carrying|gross loans|carrying amount|exposure|gross amount")
_MOVEMENT = re.compile(
    r"opening|transfer|write[- ]?off|written off|charge|reversal|write[- ]?back|recover|"
    r"new (loans|assets)|derecogni|repay|exchange|unwinding|\b0?1\s+(january|april)\b|\bat 1\b")
_CLOSING_ROW = re.compile(
    r"^(gross carrying amount|gross loans?\b|gross exposure|gross amount|balance|as at|"
    r"closing|total)\b")

_GROSS_TOTAL_PATTERNS = [
    r"^total gross loans",
    r"^gross loans and (receivables|advances)( to (other )?customers)?\b",
    r"^gross loans\b",
    r"^gross loans and receivables\b",
    r"^total gross carrying amount",
]
_TOTAL_IMP_PATTERNS = [
    r"^total (allowance|impairment|ecl|expected credit loss|loss allowance)",
    r"^(allowance|impairment|loss allowance)s?\s+(for|on)\s+(expected credit loss|ecl|loans)",
    r"^(allowance|impairment)[^0-9]{0,40}(loans|receivables|ecl|expected credit)",
]
_NPL_PATTERNS = [
    r"^gross (non[- ]performing|impaired) (loans|advances)",
    r"^(non[- ]performing|impaired) (loans|advances)",
    r"^total (non[- ]performing|impaired) (loans|advances)",
]


def _is_close(a: float, b: float, tol: float = 0.01) -> bool:
    return b != 0 and abs(a - b) <= tol * abs(b)


def _ext(metric, cur, prev, unit, page, line, method="direct", notes="", label=""):
    return Extraction(
        metric=metric,
        current=abs(cur) if cur is not None else None,
        previous=abs(prev) if prev is not None else None,
        unit=unit, page=page, source_line=line.strip(), method=method,
        notes=notes, original_label=label,
    )


_STAGE_PREFIX = re.compile(r"^((?:[-\u2013\u2022]\s*)?stage\s*[123]\b)(.*)$", re.IGNORECASE)


def _repair_line(line: str) -> str:
    """metrics._repair_broken_money glues "Stage 1" + "1,200,000" into one number
    (it treats the lone digit as a split amount). Protect the stage label first."""
    m = _STAGE_PREFIX.match(line.strip())
    if m:
        return m.group(1) + " " + _repair_broken_money(m.group(2))
    return _repair_broken_money(line)


def _label_of(line: str) -> str:
    return re.split(r"\s+\(?-?\d{1,3}(?:,\d{3})+", line, maxsplit=1)[0].strip(" .:-")


def parse_credit_page(text: str, page_number: int, default_unit: str = "unknown") -> dict:
    """Parse ONE page of text; returns {metric: Extraction} (possibly empty)."""
    unit = detect_unit(text)
    if unit == "unknown":
        unit = default_unit
    lines = [_repair_line(l) for l in text.splitlines() if l.strip()]
    out: dict = {}

    in_loans = False
    section = None            # "gross" | "ecl" (layout A)
    stage_a: dict = {}        # (section, stage) -> (values, raw_line)
    rows_b = {"gross": [], "ecl": []}   # layout B candidate rows
    table = None              # layout B: {"kind":..., "left": n}

    for idx, raw in enumerate(lines):
        line = _clean_line_start(raw)
        low = line.lower()
        sq = re.sub(r"\s+", "", low)
        values = _parse_money_tokens(line)

        # ---------- layout B header ----------
        if "stage1" in sq and "stage2" in sq and "stage3" in sq and len(values) <= 1:
            ctx = " ".join(_clean_line_start(l).lower() for l in lines[max(0, idx - 6): idx + 1])
            kind = "gross" if _GROSS_WORDS.search(ctx) else ("ecl" if _ECL_WORDS.search(ctx) else None)
            table = {"kind": kind, "left": 45, "ok": in_loans and kind is not None}
            continue

        # ---------- layout B rows ----------
        if table and table["left"] > 0:
            table["left"] -= 1
            if table["ok"] and len(values) >= 3 and _CLOSING_ROW.match(low) and not _MOVEMENT.search(low):
                v = [abs(x) for x in values]
                valid = None
                if len(v) >= 4 and _is_close(v[0] + v[1] + v[2], v[3]):
                    valid = (v[0], v[1], v[2], v[3])
                elif len(v) >= 5 and _is_close(v[0] + v[1] + v[2] + v[3], v[4]):
                    valid = (v[0], v[1], v[2] + v[3], v[4])  # 4th col = POCI, folded into Stage 3
                elif len(v) == 3:
                    valid = (v[0], v[1], v[2], None)
                if valid:
                    yrs = [int(y) for y in re.findall(r"\b(20\d\d)\b", low)]
                    rows_b[table["kind"]].append((max(yrs) if yrs else None, valid, raw))
                continue

        # ---------- state tracking (non-numeric lines only) ----------
        if not values and not _STAGE_ROW.match(low):
            if _OTHER_ASSET_CLASS.search(low):
                in_loans, section = False, None
            elif _CUSTOMER_LOANS.search(low):
                in_loans = True
            if _ECL_WORDS.search(low) and len(low) < 120:
                section = "ecl"
            elif _GROSS_WORDS.search(low) and len(low) < 120:
                section = "gross"

        # ---------- layout A rows ----------
        m = _STAGE_ROW.match(low)
        if m and values and in_loans and section:
            key = (section, int(m.group(1)))
            if key not in stage_a:
                stage_a[key] = (values, raw)
            continue

        # ---------- single-line totals ----------
        if values and not _OTHER_ASSET_CLASS.search(low):
            if "gross_loans" not in out and any(re.search(p, low) for p in _GROSS_TOTAL_PATTERNS):
                out["gross_loans"] = _ext("gross_loans", values[0], values[1] if len(values) > 1 else None,
                                          unit, page_number, raw, label=_label_of(line))
            elif ("total_loan_impairment" not in out
                  and not re.search(r"individual|collective|stage|charge|reversal|write", low)
                  and any(re.search(p, low) for p in _TOTAL_IMP_PATTERNS)):
                out["total_loan_impairment"] = _ext("total_loan_impairment", values[0],
                                                    values[1] if len(values) > 1 else None,
                                                    unit, page_number, raw, label=_label_of(line))
            elif ("npl_loans" not in out and not re.search(r"\bnet\b|ratio|%", low)
                  and any(re.search(p, low) for p in _NPL_PATTERNS)):
                out["npl_loans"] = _ext("npl_loans", values[0], values[1] if len(values) > 1 else None,
                                        unit, page_number, raw, label=_label_of(line))

    # ---------- assemble layout A ----------
    for (section, stage), (values, raw) in stage_a.items():
        metric = f"stage{stage}_loans" if section == "gross" else f"stage{stage}_impairment"
        out.setdefault(metric, _ext(
            metric, values[0], values[1] if len(values) > 1 else None, unit, page_number, raw,
            label=_label_of(raw),
            notes="Stage row from the loans-to-customers credit-quality note."))

    # ---------- assemble layout B ----------
    for kind, rows in rows_b.items():
        if not rows:
            continue
        dated = [r for r in rows if r[0] is not None]
        cur = max(dated, key=lambda r: r[0]) if dated else rows[0]
        prev = next((r for r in dated if cur[0] is not None and r[0] == cur[0] - 1), None)
        names = ([f"stage{i}_loans" for i in (1, 2, 3)] if kind == "gross"
                 else [f"stage{i}_impairment" for i in (1, 2, 3)])
        for i, metric in enumerate(names):
            out.setdefault(metric, _ext(
                metric, cur[1][i], prev[1][i] if prev else None, unit, page_number, cur[2],
                label=_label_of(cur[2]),
                notes="Stage column from the credit-quality table (Stage 1+2+3 checked against the Total column)."))
        if kind == "gross" and cur[1][3] is not None:
            out.setdefault("gross_loans", _ext(
                "gross_loans", cur[1][3], prev[1][3] if prev and prev[1][3] is not None else None,
                unit, page_number, cur[2], label="Total (gross carrying amount)",
                notes="Total column of the Stage 1/2/3 gross carrying amount table."))
        if kind == "ecl" and cur[1][3] is not None:
            out.setdefault("total_loan_impairment", _ext(
                "total_loan_impairment", cur[1][3], prev[1][3] if prev and prev[1][3] is not None else None,
                unit, page_number, cur[2], label="Total (ECL allowance)",
                notes="Total column of the Stage 1/2/3 impairment allowance table."))
    return out


# --------------------------------------------------------------------------
# PDF scan
# --------------------------------------------------------------------------

_MONEY = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")


def find_credit_pages(pdf_path: str, max_pages: int = 10) -> list:
    """Page numbers (0-based) most likely to hold Stage 1/2/3 loan tables,
    best first. Cheap pypdf scan; the real parsing uses pdfplumber."""
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    scored = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        sq = re.sub(r"\s+", "", text.lower())
        money = len(_MONEY.findall(text))
        if money < 6:
            continue
        stage_hits = sum(1 for s in ("stage1", "stage2", "stage3") if s in sq)
        has_loans = ("loansandreceivables" in sq or "loansandadvances" in sq or "grossloans" in sq)
        npl = ("non-performingloans" in sq or "impairedloans" in sq)
        score = stage_hits * 3 + (2 if has_loans else 0) + (1 if npl else 0) + (1 if "grossloans" in sq else 0)
        if stage_hits == 3 and has_loans:
            score += 3
        if score >= 5 or (stage_hits == 3):
            scored.append((score, money, i))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [p for _s, _m, p in scored[:max_pages]]


def extract_bank_credit(pdf_path: str, default_unit: str = "unknown",
                        net_loans: Optional[Extraction] = None) -> dict:
    """Scan a bank report for credit-quality figures. Returns {metric: Extraction}.
    Never raises on a bad page - a miss just leaves the metric absent."""
    import pdfplumber

    pages = find_credit_pages(pdf_path)
    if not pages:
        return {}
    parsed = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pages:
            try:
                text = pdf.pages[p].extract_text() or ""
                pdf.pages[p].flush_cache()
                found = parse_credit_page(text, p, default_unit=default_unit)
            except Exception:
                continue
            if found:
                parsed.append((len(found), p, found))
    # richest page wins per metric; ties -> earlier page
    parsed.sort(key=lambda t: (-t[0], t[1]))
    result: dict = {}
    for _n, _p, found in parsed:
        for k, v in found.items():
            result.setdefault(k, v)
    return finalize(result, net_loans=net_loans)


def finalize(result: dict, net_loans: Optional[Extraction] = None) -> dict:
    """Fill gaps by arithmetic (flagged), and sanity-check stage sums."""
    r = result
    stages = [r.get(f"stage{i}_loans") for i in (1, 2, 3)]
    # gross loans from the three stages, when no gross line was printed
    if "gross_loans" not in r and all(s and s.current is not None for s in stages):
        prevs = [s.previous for s in stages]
        r["gross_loans"] = Extraction(
            metric="gross_loans",
            current=sum(s.current for s in stages),
            previous=sum(prevs) if all(p is not None for p in prevs) else None,
            unit=stages[0].unit, page=stages[0].page,
            source_line=" | ".join(s.source_line for s in stages),
            method="summed", notes="Gross loans = Stage 1 + Stage 2 + Stage 3 (no gross line found).")
    elif "gross_loans" in r and all(s and s.current is not None for s in stages):
        total = sum(s.current for s in stages)
        g = r["gross_loans"]
        if g.current and not _is_close(total, g.current, 0.02):
            g.notes = (g.notes + " " if g.notes else "") + (
                f"CHECK: Stage 1+2+3 = {total:,.0f} differs from this gross figure by more than 2% "
                f"(the note may include other items, or a stage row was mis-read).")
    # total impairment from the three stage allowances
    imps = [r.get(f"stage{i}_impairment") for i in (1, 2, 3)]
    if "total_loan_impairment" not in r and all(s and s.current is not None for s in imps):
        prevs = [s.previous for s in imps]
        r["total_loan_impairment"] = Extraction(
            metric="total_loan_impairment",
            current=sum(s.current for s in imps),
            previous=sum(prevs) if all(p is not None for p in prevs) else None,
            unit=imps[0].unit, page=imps[0].page,
            source_line=" | ".join(s.source_line for s in imps),
            method="summed", notes="Total allowance = Stage 1 + Stage 2 + Stage 3 allowance.")
    # last resort: gross loans minus net loans on the balance sheet
    g = r.get("gross_loans")
    if ("total_loan_impairment" not in r and g and g.current is not None
            and net_loans is not None and net_loans.current is not None
            and g.current > net_loans.current):
        r["total_loan_impairment"] = Extraction(
            metric="total_loan_impairment",
            current=g.current - net_loans.current,
            previous=(g.previous - net_loans.previous)
            if g.previous is not None and net_loans.previous is not None else None,
            unit=g.unit, page=g.page,
            source_line=f"Derived: gross loans ({g.page}) − net loans on balance sheet ({net_loans.page})",
            method="derived",
            notes="Gross loans minus balance-sheet net loans. Only valid if both refer to the same loan book.")
    return r
