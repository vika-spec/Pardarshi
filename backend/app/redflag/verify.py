"""Citation verification: a quote is only shown if it can be found on its page.

LLMs sometimes paraphrase or invent quotes. We fuzzy-match each quote against
the text of the cited page (and the pages either side, in case of a page-break
off-by-one) and keep the page where it actually appears.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

VERIFY_THRESHOLD = 90
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def verify_quote(quote: str, page: int, pages: dict[int, str]) -> tuple[bool, int, float]:
    """Return (verified, page_where_found, score)."""
    q = _norm(quote)
    if len(q) < 12:
        return False, page, 0.0
    numbers = _NUM.findall(q)
    best_page, best = page, 0.0
    for p in (page, page - 1, page + 1):
        text = pages.get(p)
        if not text:
            continue
        t = _norm(text)
        if len(q) > len(t) + 5:
            continue  # a quote can't be longer than the page it came from
        if any(n not in t for n in numbers):
            continue  # every figure in the quote must appear exactly on the page
        score = fuzz.partial_ratio(q, t)
        if score > best:
            best_page, best = p, score
    return best >= VERIFY_THRESHOLD, best_page, best


def find_line(pages: dict[int, str], pattern: re.Pattern, prefer: list[int] | None = None) -> tuple[str, int] | None:
    """Find the first line matching pattern; used by the heuristic extractor for evidence."""
    order = (prefer or []) + [p for p in sorted(pages) if p not in (prefer or [])]
    for p in order:
        for line in pages.get(p, "").splitlines():
            if pattern.search(line):
                return line.strip(), p
    return None


_PAGE_NO = re.compile(r"^\d{1,4}$")


def _printed_on(text: str | None, pdf_page: int) -> int | None:
    if not text:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    best = None
    for l in lines[:3] + lines[-3:]:
        if _PAGE_NO.match(l):
            n = int(l)
            if abs(n - pdf_page) <= 60 and (best is None or abs(n - pdf_page) < abs(best - pdf_page)):
                best = n
    return best


def printed_page(pages: dict[int, str], pdf_page: int) -> int | None:
    """The page number printed on the page itself (reports' own numbering often differs from the
    PDF's page index because of covers and inserts). Falls back to a neighbour's number ± 1."""
    n = _printed_on(pages.get(pdf_page), pdf_page)
    if n is not None:
        return n
    for d in (1, -1, 2, -2):
        m = _printed_on(pages.get(pdf_page + d), pdf_page + d)
        if m is not None:
            return m - d
    return None
