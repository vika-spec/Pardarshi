"""Re-apply the published rules to figures already extracted, without calling any AI.

    python -m pipelines.reapply_rules

Use after a rule or threshold changes: every scorecard's numeric checks are re-decided from their stored,
quote-verified figures. A check whose result changes from flagged to passed loses its second-model review
(that review was about a warning that no longer exists). Prints what changed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def reapply(card: dict) -> list[str]:
    from app.redflag.checks import CHECKS_BY_ID, IMPLAUSIBLE_TEXT, SHORT_TEXT, evaluate_numeric, finding_level
    from app.redflag.engine import _fmt
    from app.redflag.review import recount

    changes = []
    for c in card["checks"]:
        chk = CHECKS_BY_ID.get(c["id"])
        if not chk or chk.kind != "numeric" or c["status"] in ("not_applicable", "unverified"):
            continue
        res = evaluate_numeric(c["id"], c.get("values") or {})
        if res is None:
            continue
        status, derived = res
        if status == "flagged" and not any(e.get("verified") for e in c.get("evidence", [])):
            status = "unverified"
        old = c["status"]
        if old == "disputed" and status == "flagged":
            status = "disputed"  # the second model's disagreement still stands
        c["derived"] = {k: round(v, 2) for k, v in derived.items()}
        tpl = chk.flagged_text if status == "flagged" else chk.passed_text
        c["summary"] = {l: _fmt(tpl[l], derived) for l in ("en", "hi")} if status in ("flagged", "passed") else c.get("summary", {})
        if status == "flagged" and chk.id in SHORT_TEXT:
            c["summary"] = {l: c["summary"][l] or _fmt(SHORT_TEXT[chk.id][l], derived) for l in ("en", "hi")}
        if status == "unverified" and chk.id in IMPLAUSIBLE_TEXT:
            c["summary"] = {l: _fmt(IMPLAUSIBLE_TEXT[chk.id][l], derived) for l in ("en", "hi")}
        c["level"] = finding_level(chk.id, chk.severity, derived) if status == "flagged" else None
        if old in ("flagged", "disputed") and status in ("passed", "unverified"):
            c.pop("review", None)
        c["status"] = status
        if old != status:
            changes.append(f"{card['name']}: {c['id']} {old} -> {status}")
    recount(card)
    return changes


def main() -> None:
    from app.config import settings

    files = list((settings.data_dir / "scorecards").glob("*.json")) + list((settings.data_dir / "scorecards" / "history").glob("*/*.json"))
    total = []
    for p in files:
        card = json.loads(p.read_text("utf-8"))
        ch = reapply(card)
        if ch:
            p.write_text(json.dumps(card, ensure_ascii=False, indent=1), "utf-8")
            total += ch
    print("\n".join(total) if total else "No results changed.")


if __name__ == "__main__":
    main()
