"""Build a red-flag scorecard for one company's annual report.

Runs OFFLINE (pipelines/build_redflags.py), never inside a user request:
PDF -> page text -> retrieval per check -> extraction -> rule -> verified evidence.

Two extraction modes, recorded on every check so users can see which was used:
  * "llm:<provider>"  the model reads retrieved passages and returns JSON
                      (figures + exact quotes with page numbers)
  * "heuristic"       regular expressions over the same passages; used when no
                      LLM is configured or the LLM fails

Either way: numeric rules are applied by Python, and a check is only shown as
flagged if at least one quote was verified on its page.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from pathlib import Path

from ..llm import LLMClient, LLMUnavailable, parse_json
from ..retrieval import ReportIndex
from .checks import CHECKS, NOT_APPLICABLE_TEXT, NOT_FOR_FINANCIALS, Check, evaluate_numeric, finding_level, is_financial, required_fields, SHORT_TEXT, IMPLAUSIBLE_TEXT
from .verify import find_line, verify_quote, printed_page

log = logging.getLogger("pardarshi.redflag")

NUM = r"\(?-?[\d,]+(?:\.\d+)?\)?"


def read_pdf_pages(pdf_path: Path) -> dict[int, str]:
    import pymupdf

    pages: dict[int, str] = {}
    with pymupdf.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            pages[i] = page.get_text("text")
    return pages


def page_rows(page, gap: float = 10.0) -> str:
    """Rebuild a page line by line from word positions, so each table row keeps its label and its numbers
    together ("Trade receivables | 1,234.5 | 1,100.2"). Plain text extraction puts every table cell on its own
    line, which separates a figure from its label; this is the main reason figures went 'not found'."""
    words = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    rows: list[list] = []
    for w in words:
        yc = (w[1] + w[3]) / 2
        if rows and abs(yc - rows[-1][0]) <= 2.5:
            rows[-1][1].append(w)
        else:
            rows.append([yc, [w]])
    out = []
    for _, ws in rows:
        ws.sort(key=lambda w: w[0])
        line, last = "", None
        for w in ws:
            if last is not None:
                line += " | " if w[0] - last > gap else " "
            line += w[4]
            last = w[2]
        out.append(line)
    return "\n".join(out)


def read_pdf_rows(pdf_path: Path) -> dict[int, str]:
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        return {i: page_rows(page) for i, page in enumerate(doc, start=1)}


def unpipe_cells(text: str) -> str:
    """Rows with cells separated by single spaces, for the pattern reader (which reads a label and its figures per line)."""
    return "\n".join(unpipe(l) for l in text.splitlines())


def unpipe(s: str) -> str:
    return re.sub(r"\s*\|\s*", " ", s)


def pdf_date(pdf_path: Path) -> str:
    """Creation date stored inside the PDF (close to when the report was published), as YYYY-MM-DD."""
    import re as _re

    import pymupdf

    try:
        with pymupdf.open(pdf_path) as doc:
            raw = (doc.metadata or {}).get("creationDate") or (doc.metadata or {}).get("modDate") or ""
    except Exception:  # noqa: BLE001
        return ""
    m = _re.search(r"(\d{4})(\d{2})(\d{2})", raw)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _to_float(s: str) -> float:
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


# ----------------------------------------------------------------- heuristics
_LABELS: dict[str, re.Pattern] = {
    "pat": re.compile(r"^\s*(net\s+)?profit\s+(after\s+tax\s+)?for\s+the\s+(year|period)\b", re.I),
    "cfo": re.compile(r"net\s+cash\s+(flows?\s+)?(generated\s+)?(from|used\s+in|from\s*/\s*\(used\s+in\))\s+operating\s+activities", re.I),
    "revenue": re.compile(r"^\s*revenue\s+from\s+operations\b", re.I),
    "receivables": re.compile(r"^\s*trade\s+receivables\b", re.I),
    "rpt": re.compile(r"total\s+(of\s+)?(transactions|dealings)\s+with\s+related\s+parties", re.I),
    "contingent": re.compile(r"(total\s+)?contingent\s+liabilities(\s+not\s+provided\s+for)?\b.*\d", re.I),
    "equity": re.compile(r"^\s*total\s+equity\b", re.I),
}


def _two_numbers(line: str) -> tuple[float, float] | None:
    nums = re.findall(NUM, line)
    nums = [n for n in nums if re.search(r"\d", n) and not re.fullmatch(r"\(?\d{1,2}(\.\d)?\)?", n)  # note refs like (12), 23.2
            and not re.fullmatch(r"(19|20)\d\d", n)]  # years in the label
    if len(nums) >= 2:
        # columns run current year, previous year (and sometimes an older opening balance): take the first two
        cur, prev = _to_float(nums[0]), _to_float(nums[1])
        if cur == 0 and prev == 0:
            return None  # an empty row (e.g. a currency-exposure table), not the figure we want
        return cur, prev
    if len(nums) == 1:
        return _to_float(nums[0]), float("nan")
    return None


def _heuristic_values(pages: dict[int, str], prefer: list[int]) -> tuple[dict[str, float], dict[str, tuple[str, int]]]:
    vals: dict[str, float] = {}
    ev: dict[str, tuple[str, int]] = {}
    order = prefer + [p for p in sorted(pages) if p not in prefer]
    for key, pat in _LABELS.items():
        for page in order:
            found = False
            for line in pages[page].splitlines():
                if not pat.search(line):
                    continue
                pair = _two_numbers(line)
                if pair:
                    vals[f"{key}_current"], vals[f"{key}_previous"] = pair
                    ev[key] = (line.strip(), page)
                    found = True
                    break
            if found:
                break
    if "contingent_current" in vals:
        vals["contingent_liabilities"] = vals["contingent_current"]
    if "equity_current" in vals:
        vals["total_equity"] = vals["equity_current"]
    pledge = find_line(pages, re.compile(r"(pledged|encumbered).*\d\s*%", re.I), prefer)
    if pledge:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", pledge[0])
        if m:
            vals["pledged_pct_of_promoter_holding"] = float(m.group(1))
            ev["pledge"] = pledge
    return vals, ev


_FIELD_SOURCES = {
    "pledged_pct_of_promoter_holding": "pledge",
    "rpt_current": "rpt", "rpt_previous": "rpt",
    "revenue_current": "revenue", "revenue_previous": "revenue",
    "contingent_liabilities": "contingent", "total_equity": "equity",
    "pat_current": "pat", "pat_previous": "pat",
    "cfo_current": "cfo", "cfo_previous": "cfo",
    "receivables_current": "receivables", "receivables_previous": "receivables",
}

_TEXT_PATTERNS = {
    "auditor_opinion": (
        re.compile(r"(qualified|adverse)\s+opinion|disclaimer\s+of\s+opinion|material\s+uncertainty\s+related\s+to\s+going\s+concern", re.I),
        re.compile(r"(unmodified\s+opinion|give\s+a\s+true\s+and\s+fair\s+view|in\s+our\s+opinion)", re.I),
    ),
    "auditor_change": (
        re.compile(r"(auditors?,?\s+(has|have)\s+resigned|resignation\s+of\s+(the\s+)?(statutory\s+)?auditors?|casual\s+vacancy.*auditor)", re.I),
        re.compile(r"(appointed\s+as\s+(one\s+of\s+)?(the\s+)?(joint\s+)?statutory\s+auditors?|(joint\s+)?statutory\s+auditors?\s+of\s+the\s+(company|bank)"
                   r"|re-?appointment\s+of\s+.{0,60}statutory\s+auditors?)", re.I),
    ),
}


def _heuristic_check(check: Check, pages: dict[int, str], prefer: list[int], vals: dict, ev: dict) -> dict:
    if check.kind == "text":
        bad, good = _TEXT_PATTERNS[check.id]
        # 'qualified opinion' must not match 'unqualified opinion'
        hit = None
        for p in prefer + [p for p in sorted(pages) if p not in prefer]:
            for line in pages[p].splitlines():
                if bad.search(line) and not re.search(r"\bunqualified\b|\bnot\s+qualified\b|nothing\s+has\s+come", line, re.I):
                    hit = (line.strip(), p)
                    break
            if hit:
                break
        if hit:
            return {"status": "flagged", "evidence": [{"quote": hit[0], "page": hit[1]}], "values": {}}
        ok = find_line(pages, good, prefer)
        if ok:
            return {"status": "passed", "evidence": [{"quote": ok[0], "page": ok[1]}], "values": {}}
        return {"status": "not_found", "evidence": [], "values": {}}

    need = {k: vals[k] for k in check.fields if k in vals and vals[k] == vals[k]}  # drop NaN
    if any(f not in need for f in required_fields(check)):
        return {"status": "not_found", "evidence": [], "values": need}
    srcs = {_FIELD_SOURCES[f] for f in check.fields}
    evidence = [{"quote": ev[s][0], "page": ev[s][1]} for s in srcs if s in ev]
    return {"status": None, "evidence": evidence, "values": need}


def _has_verified(raw: dict, pages: dict[int, str]) -> bool:
    return any(verify_quote(str(e.get("quote", "")), int(e.get("page") or 0), pages)[0] for e in raw.get("evidence", []))


def _combine(check: Check, raw: dict, method: str, pages, prefer, vals, ev) -> tuple[dict | None, str]:
    """Use the AI first, but never throw away what the pattern reader can prove.
    Wording checks: if the AI found nothing provable, take the pattern result when it has a verifiable quote.
    Number checks: fill figures the AI couldn't find from the pattern reader."""
    if check.kind == "text":
        if raw.get("status") in ("flagged", "passed") and _has_verified(raw, pages):
            return raw, method
        alt = _heuristic_check(check, pages, prefer, vals, ev)
        if alt.get("status") in ("flagged", "passed") and _has_verified(alt, pages):
            return alt, method + "+pattern"
        return raw, method
    values = dict(raw.get("values") or {})
    if check.id == "promoter_pledge" and "pledged_pct_of_promoter_holding" not in values:
        nop = _no_promoter(pages, prefer)
        if nop:
            return {"status": None, "values": {"pledged_pct_of_promoter_holding": 0.0}, "evidence": [nop], "basis": "n/a"}, method + "+pattern"
    missing = [f for f in check.fields if f not in values]
    if missing:
        filled = {f: vals[f] for f in missing if f in vals and vals[f] == vals[f]}
        if any(f not in values and f not in filled for f in required_fields(check)):
            return None, "heuristic"  # still incomplete: let the pattern reader decide on its own
        values.update(filled)
        extra = [{"quote": ev[_FIELD_SOURCES[f]][0], "page": ev[_FIELD_SOURCES[f]][1]} for f in filled if _FIELD_SOURCES.get(f) in ev]
        raw = {**raw, "values": values, "evidence": list(raw.get("evidence") or []) + extra}
        method += "+pattern"
    return raw, method


_NO_PROMOTER = re.compile(r"(?:not\s+have\s+(?:an?\s+|any\s+)?(?:identified\s+|identifiable\s+)?promoters?|no\s+(?:identified\s+|identifiable\s+)?promoters?\b|"
                          r"(?:not|no)\s+(?:shares?\s+)?(?:pledged|encumbered)\s+by\s+(?:the\s+)?promoters?)", re.I)


def _no_promoter(pages: dict[int, str], prefer: list[int]) -> dict | None:
    for p in prefer + [p for p in sorted(pages) if p not in prefer]:
        flat = re.sub(r"\s+", " ", pages[p])
        m = _NO_PROMOTER.search(flat)
        if m:
            a = max(0, flat.rfind(". ", 0, m.start()) + 2)
            b = flat.find(".", m.end())
            return {"quote": flat[a: b if b > 0 else m.end()].strip()[:300], "page": p}
    return None


# ----------------------------------------------------------------- related-party table (code, not AI)
_CELL = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$|^[-–—]$|^nil$", re.I)
_UNIT = [(re.compile(r"in\s+crores?|crores?\)", re.I), 1.0), (re.compile(r"in\s+lakhs?|lakhs?\)|lacs", re.I), 0.01),
         (re.compile(r"in\s+millions?|mn\)", re.I), 0.1), (re.compile(r"in\s+(thousands?|'000)|'000\)|‘000", re.I), 0.0001)]
_SKIP_TYPES = re.compile(r"salary|remuneration|sitting\s+fee|commission\s+to\s+directors?", re.I)


def _cell(c: str) -> float:
    c = c.strip()
    if not c or c in "-–—" or c.lower() == "nil":
        return 0.0
    v = float(c.strip("()").replace(",", ""))
    return -v if c.startswith("(") else v


def _unit(text: str) -> float | None:
    for pat, mult in _UNIT:
        if pat.search(text):
            return mult  # multiplier to convert the page's figures to crore
    return None


def _basis(text: str) -> str:
    return "consolidated" if re.search(r"consolidated", text[:600], re.I) else "standalone"


def _rpt_by_code(rows: dict[int, str], vpages: dict[int, str]) -> dict | None:
    r = rpt_from_notes(rows)
    if not r:
        return None
    rev = revenue_for_basis(rows, r["basis"])
    if not rev:
        return None
    rc, rp, line, pg = rev
    values = {"rpt_current": r["rpt_current"], "revenue_current": round(rc, 2)}
    if r["rpt_previous"] and rp:
        values.update({"rpt_previous": r["rpt_previous"], "revenue_previous": round(rp, 2)})
    evidence = r["evidence"] + [{"quote": line, "page": pg}]
    return {"status": None, "values": values, "evidence": evidence, "basis": r["basis"], "seen_pages": r["pages"] + [pg],
            "breakdown": r["breakdown"][:6], "largest": {"type": r["largest_type"], "current": r["largest_current"]}}


def _paired_year_columns(text: str) -> bool:
    """True if a header row shows years alternating current/previous (e.g. 2024 | 2023 | 2024 | 2023)."""
    for line in text.splitlines()[:40]:
        years = re.findall(r"(20\d\d)", line)
        if len(years) >= 4 and line.count("|") >= 3:
            a, b = years[0], years[1]
            if a != b and all(y == (a if i % 2 == 0 else b) for i, y in enumerate(years)):
                return True
    return False


def rpt_from_notes(rows: dict[int, str]) -> dict | None:
    """Add up the related-party TRANSACTIONS table (not closing balances) in code.

    Annual reports list each transaction type (sales, loans given, ...) and each party in columns per
    group (subsidiaries / key managers / other related parties), current year then previous year, and
    usually no grand total, so an AI asked for 'the total' cannot quote one. We sum the rows instead.
    Directors' and managers' pay is left out. Prefers the consolidated note (deals inside the group are
    removed there, leaving deals with promoters' and other related companies). Figures are in crore."""
    runs: dict[str, dict] = {}
    for p in sorted(rows):
        t = rows[p]
        if not (re.search(r"related\s+part", t, re.I) and re.search(r"nature\s+of\s+transactions?", t, re.I)):
            continue
        if not _paired_year_columns(t):
            continue  # only tables laid out as current year | previous year pairs are summed; others go to the AI
        basis = _basis(t)
        run = runs.setdefault(basis, {"types": {}, "pages": [], "unit": None, "lines": [], "cur": None, "last": 0, "done": False})
        if run["done"]:
            continue
        run["unit"] = run["unit"] or _unit(t)
        cur = run["cur"] if p == run["last"] + 1 else None  # a transaction type can continue onto the next page
        for line in t.splitlines():
            if re.search(r"amounts?\s+(due|outstanding)|outstanding\s+balances?|balances?\s+(outstanding|as\s+at)|closing\s+balance", line, re.I):
                run["done"] = True
                break
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 1 and re.fullmatch(r"\(?[0-9]{1,2}[.)]?|[a-z][.)]", cells[0]) and re.search(r"[A-Za-z]{3}", cells[1]):
                cur = re.sub(r"[\s:\-–]+$", "", cells[1]).strip()
                continue
            if len(cells) == 1 and re.search(r":-?\s*$", line) and cur is None:
                cur = line.strip(" :-")
                continue
            vals = cells[1:]
            if cur and len(vals) >= 2 and len(vals) % 2 == 0 and all(_CELL.match(v) for v in vals) and re.search(r"[A-Za-z]{2}", cells[0]):
                if _SKIP_TYPES.search(cur):
                    continue
                nums = [_cell(v) for v in vals]
                agg = run["types"].setdefault(cur, [0.0, 0.0])
                agg[0] += sum(abs(x) for x in nums[0::2])
                agg[1] += sum(abs(x) for x in nums[1::2])
                if p not in run["pages"]:
                    run["pages"].append(p)
                if max(nums[0::2]) > 0:
                    run["lines"].append((max(nums[0::2]), unpipe(line), p))
        run["cur"], run["last"] = cur, p
    run = runs.get("consolidated") if runs.get("consolidated", {}).get("types") else runs.get("standalone")
    if not run or not run["types"]:
        return None
    unit = run["unit"] or 1.0
    cur_total = sum(v[0] for v in run["types"].values()) * unit
    prev_total = sum(v[1] for v in run["types"].values()) * unit
    if cur_total <= 0:
        return None
    biggest = max(run["types"].items(), key=lambda kv: kv[1][0])
    top_lines = sorted(run["lines"], reverse=True)[:3]
    return {
        "basis": "consolidated" if run is runs.get("consolidated") else "standalone",
        "rpt_current": round(cur_total, 2), "rpt_previous": round(prev_total, 2) if prev_total > 0 else None,
        "largest_type": biggest[0], "largest_current": round(biggest[1][0] * unit, 2),
        "breakdown": [{"type": k, "current": round(v[0] * unit, 2), "previous": round(v[1] * unit, 2)}
                      for k, v in sorted(run["types"].items(), key=lambda kv: -kv[1][0])],
        "evidence": [{"quote": q, "page": pg} for _, q, pg in top_lines],
        "pages": run["pages"],
    }


def revenue_for_basis(rows: dict[int, str], basis: str) -> tuple[float, float | None, str, int] | None:
    """Revenue from operations (in crore) from the profit and loss statement on the same basis."""
    for p in sorted(rows):
        t = rows[p]
        if _basis(t) != basis or not re.search(r"profit\s+and\s+loss|statement\s+of\s+profit", t[:800], re.I):
            continue
        unit = _unit(t) or 1.0
        for line in t.splitlines():
            if _LABELS["revenue"].search(unpipe(line)):
                cells = [c for c in line.split("|")[1:] if _CELL.match(c.strip()) and re.search(r"\d", c)]
                nums = [_cell(c) for c in cells if not re.fullmatch(r"\(?\d{1,2}\)?", c.strip())]
                if nums:
                    return nums[-2] * unit if len(nums) >= 2 else nums[-1] * unit, (nums[-1] * unit if len(nums) >= 2 else None), unpipe(line), p
    return None


# ----------------------------------------------------------------- LLM path
_SYSTEM = (
    "You are a careful forensic accounting assistant reading an Indian company's annual report. "
    "Use ONLY the passages given. Every passage starts with [page N]. Quote text EXACTLY as it appears, "
    "copying a short span (8-30 words) that contains the evidence. Never invent figures. If the passages do "
    "not contain what is needed, say so. Reply with a single JSON object and nothing else."
)


_HINTS = {
    "auditor_opinion": "An 'unmodified' opinion, or 'In our opinion ... give a true and fair view' with no 'Basis for Qualified/Adverse "
                       "Opinion' heading, is CLEAN: answer passed and quote that sentence. Only answer flagged for a qualified, adverse "
                       "or disclaimer opinion, or a 'Material Uncertainty Related to Going Concern' section. An 'Emphasis of Matter' "
                       "alone is passed.",
    "auditor_change": "If the passages show the statutory auditors were appointed, re-appointed or continue in office (including a "
                      "scheduled rotation at the end of a term) and nothing says an auditor resigned mid-term, answer passed and quote "
                      "the appointment sentence. Answer flagged only for a resignation or removal before the term ended.",
    "promoter_pledge": "Report pledged/encumbered promoter shares as a percentage of the promoter group's holding. If the report says "
                       "the company has no promoter / no identified promoter, or that no promoter shares are pledged or encumbered, "
                       "return pledged_pct_of_promoter_holding = 0 and quote that sentence.",
    "related_party": "Use the total value of related party TRANSACTIONS during the year (sales, purchases, services, loans given), "
                     "not closing balances, and revenue from operations (for banks: total income), same unit. If the report has no "
                     "single total, give the largest stated transaction total (e.g. 'Sale of goods / services to related parties') "
                     "and quote it. Previous-year figures are optional: use null if not shown.",
    "contingent_liabilities": "Use the total of contingent liabilities not provided for (claims not acknowledged as debts, guarantees, "
                              "tax disputes) and total equity (equity share capital + other equity) for the same year and basis.",
    "cash_vs_profit": "Use 'Net cash generated from / (used in) operating activities' and 'Profit for the year' (after tax) for "
                      "the current and previous year. Negative cash flow must be a negative number.",
    "receivables": "Use trade receivables (current + non-current) and revenue from operations for the current and previous year.",
}


def _llm_prompt(check: Check, passages: str) -> str:
    hint = f"Guidance: {_HINTS[check.id]}\n" if check.id in _HINTS else ""
    if check.kind == "numeric":
        fields = ", ".join(f'"{f}": number|null' for f in check.fields)
        return (
            f"Task: extract figures for the check '{check.title['en']}'.\nRule (applied later by code): {check.rule}\n{hint}"
            "Use the same unit for current and previous year. 'current' = latest financial year in the report; "
            "use consolidated figures if both standalone and consolidated appear and say which in 'basis'.\n"
            "Tables are shown one row per line with ' | ' between cells; columns are usually current year then previous year. "
            "In quotes, copy the row label and its figures.\n"
            f'Return: {{"values": {{{fields}}}, "basis": "standalone|consolidated|unknown", '
            '"evidence": [{"quote": "exact text", "page": N}]}\n\n'
            f"Passages:\n{passages}"
        )
    return (
        f"Task: decide the check '{check.title['en']}'.\nRule: {check.rule}\n{hint}"
        'Return: {"status": "flagged"|"passed"|"not_found", "reason": "one plain sentence", '
        '"evidence": [{"quote": "exact text", "page": N}]}\n\n'
        f"Passages:\n{passages}"
    )


_PASSAGES = int(__import__("os").environ.get("REDFLAG_PASSAGES", "6"))  # fewer passages = fewer tokens per call


async def _llm_check(llm: LLMClient, check: Check, index: ReportIndex, row_index: ReportIndex | None = None) -> dict:
    if check.kind == "numeric" and row_index is not None:
        index = row_index  # table rows keep each label next to its figures
    chunks = index.search_many(check.queries, k=_PASSAGES + (4 if check.kind == "numeric" else 0))
    passages = "\n\n".join(f"[page {c.page}]\n{c.text}" for c in chunks)
    text, provider = await llm.complete(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": _llm_prompt(check, passages)}],
        json_mode=True,
        max_tokens=900,
    )
    data = parse_json(text)
    ev = [{**e, "quote": unpipe(str(e.get("quote", "")))} for e in (data.get("evidence") or []) if isinstance(e, dict)]
    out = {"evidence": ev, "provider": provider, "seen_pages": sorted({c.page for c in chunks})}
    if check.kind == "numeric":
        out["values"] = {k: v for k, v in (data.get("values") or {}).items() if isinstance(v, (int, float))}
        out["basis"] = data.get("basis", "unknown")
        out["status"] = None
    else:
        out["values"] = {}
        out["status"] = data.get("status") if data.get("status") in ("flagged", "passed", "not_found") else "not_found"
        out["reason"] = data.get("reason", "")
    return out


# ----------------------------------------------------------------- assemble
def _fmt(template: str, d: dict) -> str:
    try:
        return template.format(**d)
    except (KeyError, ValueError):
        return ""


async def build_scorecard(company: dict, pdf_path: Path, llm: LLMClient | None = None, *, dense_model=None, reranker=None, pause_s: float = 0.0) -> tuple[dict, dict[int, str]]:
    pages = read_pdf_pages(pdf_path)
    rows = read_pdf_rows(pdf_path)
    index = ReportIndex(pages, dense_model=dense_model, reranker=reranker)
    row_index = ReportIndex(rows)
    # what a quote is checked against: the page as extracted, plus the same page rebuilt row by row
    vpages = {p: pages[p] + "\n" + unpipe(rows.get(p, "")) for p in pages}
    vals, ev = _heuristic_values({p: unpipe_cells(t) for p, t in rows.items()}, [])

    results = []
    financial = is_financial(company)
    for check in CHECKS:
        if financial and check.id in NOT_FOR_FINANCIALS:
            results.append({"id": check.id, "title": check.title, "what": check.what, "rule": check.rule, "severity": check.severity,
                            "status": "not_applicable", "summary": dict(NOT_APPLICABLE_TEXT), "values": {}, "derived": {},
                            "basis": None, "evidence": [], "method": "rule", "confidence": "high"})
            continue
        t0 = __import__("time").perf_counter()
        prefer = sorted({c.page for c in index.search_many(check.queries, k=6)})
        method = "heuristic"
        raw = None
        if check.id == "related_party":
            raw = _rpt_by_code(rows, vpages)
            if raw:
                method = "table"
        if raw is None and llm is not None and llm.enabled:
            try:
                if pause_s:
                    await asyncio.sleep(pause_s)
                raw = await _llm_check(llm, check, index, row_index)
                method = f"llm:{raw['provider']}"
                raw, method = _combine(check, raw, method, vpages, prefer, vals, ev)
            except (LLMUnavailable, ValueError, KeyError) as exc:
                log.warning("%s: LLM check %s failed (%s); using heuristic", company["name"], check.id, exc)
                raw = None
        if raw is None:
            raw = _heuristic_check(check, vpages, prefer, vals, ev)
            if check.id == "promoter_pledge" and raw.get("status") == "not_found":
                nop = _no_promoter(pages, prefer)
                if nop:
                    raw = {"status": None, "values": {"pledged_pct_of_promoter_holding": 0.0}, "evidence": [nop], "basis": "n/a"}

        derived: dict = {}
        status = raw.get("status")
        if check.kind == "numeric":
            res = evaluate_numeric(check.id, raw.get("values", {}))
            if res is None:
                status = "not_found"
            else:
                status, derived = res

        evidence = []
        for e in raw.get("evidence", [])[:4]:
            q, p = str(e.get("quote", "")).strip(), int(e.get("page") or 0)
            ok, page_found, score = verify_quote(q, p, vpages)
            evidence.append({"quote": q, "page": page_found, "printed_page": printed_page(pages, page_found),
                             "verified": ok, "match": round(score, 1)})
        verified_any = any(e["verified"] for e in evidence)
        if status == "flagged" and not verified_any:
            status = "unverified"  # never show an accusation we can't point to

        summary = {
            "en": _fmt(check.flagged_text["en"] if status == "flagged" else check.passed_text["en"], derived) if status in ("flagged", "passed") else "",
            "hi": _fmt(check.flagged_text["hi"] if status == "flagged" else check.passed_text["hi"], derived) if status in ("flagged", "passed") else "",
        }
        if status == "flagged" and check.id in SHORT_TEXT:
            for lang in ("en", "hi"):
                summary[lang] = summary[lang] or _fmt(SHORT_TEXT[check.id][lang], derived)
        if status == "unverified" and derived and check.id in IMPLAUSIBLE_TEXT:
            summary = {lang: _fmt(IMPLAUSIBLE_TEXT[check.id][lang], derived) for lang in ("en", "hi")}
        results.append(
            {
                "id": check.id,
                "title": check.title,
                "what": check.what,
                "rule": check.rule,
                "severity": check.severity,
                "status": status,
                "summary": summary,
                "values": raw.get("values", {}),
                "derived": {k: round(v, 2) for k, v in derived.items()},
                "basis": raw.get("basis"),
                "evidence": [e for e in evidence if e["verified"]] or evidence[:1],
                "method": method,
                "seen_pages": (raw.get("seen_pages") or prefer) if status != "not_applicable" else [],
                "ms": max(0, round((__import__("time").perf_counter() - t0 - (pause_s if method.startswith("llm") else 0)) * 1000)),
                **({"breakdown": raw["breakdown"], "largest": raw.get("largest")} if raw.get("breakdown") else {}),
                "confidence": "high" if method.startswith("llm") and verified_any else ("medium" if verified_any else "low"),
                "level": finding_level(check.id, check.severity, derived) if status == "flagged" else None,
            }
        )

    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("flagged", "passed", "not_found", "unverified", "not_applicable", "disputed")}
    card = {
        "isin": company["isin"],
        "name": company["name"],
        "fy": company.get("fy", ""),
        "report_url": company.get("report_url", ""),
        "n_pages": len(pages),
        "report_date": pdf_date(pdf_path),
        "checks": results,
        "counts": counts,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "page_numbering": "PDF page numbers (open the PDF at #page=N)",
    }
    return card, pages
