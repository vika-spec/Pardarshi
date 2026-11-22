"""Second opinion: a different AI model independently re-checks every warning sign.

The first model found the figures or wording; code applied the rule and verified the quote is on
the page. The reviewer now gets the rule, the claim, and the FULL text of the cited pages, and must
say whether the warning is correctly supported. If it disagrees, the finding is marked 'disputed'
("models disagree, needs a human look") and is not shown or scored as a warning sign.
"""
from __future__ import annotations

import json

from ..llm import LLMClient, LLMUnavailable, parse_json
from .checks import CHECKS

_BY_ID = {c.id: c for c in CHECKS}

REVIEW_SYSTEM = (
    "You are an independent second reviewer checking another analyst's finding from an Indian company's annual report. "
    "Use ONLY the page text given. Be strict: agree only if the page text clearly supports the finding under the stated rule. "
    "Reply with one JSON object and nothing else."
)


def _claim(chk: dict) -> str:
    parts = [f"Finding: {chk['summary'].get('en', '')}"]
    if chk.get("values"):
        parts.append("Figures used: " + json.dumps(chk["values"]))
    if chk.get("derived"):
        parts.append("Calculated by code: " + json.dumps(chk["derived"]))
    if chk.get("breakdown"):
        parts.append("The related-party total has no single line in the report: code added up every row of the "
                     "related-party TRANSACTIONS table (directors' pay excluded). Totals by type, in crore: "
                     + "; ".join(f"{b['type']}: {b['current']}" for b in chk["breakdown"])
                     + ". Check that the rows on the pages are transactions during the year (not closing balances) with "
                       "related parties, and whether they support the rule (even the largest type alone vs revenue).")
    return "\n".join(parts)


async def review_check(llm: LLMClient, chk: dict, pages: dict[int, str], first_provider: str | None) -> dict | None:
    """Return {'agree', 'reason', 'by', 'same_model'} or None if no AI could be reached."""
    check = _BY_ID.get(chk["id"])
    if not check:
        return None
    cited = sorted({e["page"] for e in chk.get("evidence", []) if e.get("verified")})[:3]
    if chk.get("breakdown") and chk.get("seen_pages"):
        cited = list(dict.fromkeys(chk["seen_pages"]))[:4]  # the whole related-party table plus the revenue page
    if not cited:
        return None
    page_text = "\n\n".join(f"[page {p}]\n{pages.get(p, '')[:5000]}" for p in cited)
    quotes = "\n".join(f'- p. {e["page"]}: "{e["quote"]}"' for e in chk["evidence"] if e.get("verified"))
    prompt = (
        f"Check: {check.title['en']}\nRule: {check.rule}\n{_claim(chk)}\nQuotes the first analyst relied on:\n{quotes}\n\n"
        f"Full text of the cited pages:\n{page_text}\n\n"
        'Return: {"agree": true|false, "reason": "one plain sentence a beginner can understand"}'
    )
    try:
        text, provider = await llm.complete(
            [{"role": "system", "content": REVIEW_SYSTEM}, {"role": "user", "content": prompt}],
            json_mode=True, max_tokens=400, avoid=first_provider,
        )
        data = parse_json(text)
    except (LLMUnavailable, ValueError):
        return None
    if not isinstance(data.get("agree"), bool):
        return None
    return {"agree": data["agree"], "reason": str(data.get("reason", ""))[:300], "by": provider,
            "same_model": provider == first_provider}


def recount(card: dict) -> None:
    card["counts"] = {s: sum(1 for c in card["checks"] if c["status"] == s)
                      for s in ("flagged", "passed", "not_found", "unverified", "not_applicable", "disputed")}


async def review_card(llm: LLMClient, card: dict, pages: dict[int, str], *, redo: bool = False) -> int:
    """Review every flagged (or previously disputed) check in a scorecard. Returns how many were reviewed."""
    n = 0
    for chk in card["checks"]:
        if chk["status"] not in ("flagged", "disputed"):
            continue
        if chk.get("review") and not redo:
            continue
        first = chk.get("method", "").split("+")[0].replace("llm:", "") or None
        res = review_check(llm, chk, pages, first if first != "heuristic" else None)
        rev = await res
        if rev is None:
            continue
        chk["review"] = rev
        chk["status"] = "flagged" if rev["agree"] else "disputed"
        n += 1
    recount(card)
    return n
