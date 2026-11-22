"""Sanity-check the dataset before you deploy it. Exit code 1 if anything is broken.

    python -m pipelines.validate_dataset
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def validate(data_dir: Path) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warns: list[str] = []
    funds = json.loads((data_dir / "funds.json").read_text("utf-8"))
    companies = json.loads((data_dir / "companies.json").read_text("utf-8"))
    stats = {"schemes": len(funds), "companies": len(companies)}

    ids = set()
    for f in funds:
        name = f.get("name", "?")
        if f["scheme_id"] in ids:
            errors.append(f"duplicate scheme_id {f['scheme_id']}")
        ids.add(f["scheme_id"])
        total = sum(h["weight"] for h in f["holdings"])
        if not 0.05 <= total <= 1.02:
            errors.append(f"{name}: holdings sum to {total:.2f} (expected 0.05-1.02)")
        if any(h["weight"] < 0 for h in f["holdings"]):
            errors.append(f"{name}: negative weight")
        plans = f.get("plans", {})
        if not plans:
            errors.append(f"{name}: no plans")
        if set(plans) != {"direct", "regular"} and not re.search(r"\bETF\b", name, re.I):  # ETFs have one plan
            warns.append(f"{name}: only {sorted(plans)} plan(s)")
        for p, v in plans.items():
            if v.get("ter") is None:
                warns.append(f"{name}: no TER for {p} plan")
        if plans.get("regular", {}).get("ter") is not None and plans.get("direct", {}).get("ter") is not None:
            if plans["regular"]["ter"] < plans["direct"]["ter"]:
                errors.append(f"{name}: regular TER below direct TER (columns swapped?)")
        for h in f["holdings"]:
            if h["isin"] not in companies:
                errors.append(f"{name}: holding {h['isin']} missing from companies.json")
                break

    cards = list((data_dir / "scorecards").glob("*.json")) if (data_dir / "scorecards").exists() else []
    stats["scorecards"] = len(cards)
    nf = tot = heur = 0
    for c in cards:
        card = json.loads(c.read_text("utf-8"))
        if not (data_dir / "chunks" / f"{card['isin']}.jsonl").exists():
            errors.append(f"{card['name']}: scorecard without page text (chunks/{card['isin']}.jsonl)")
        for chk in card["checks"]:
            tot += 1
            nf += chk["status"] in ("not_found", "unverified")
            heur += chk["method"] == "heuristic"
            if chk["status"] == "flagged" and not any(e.get("verified") for e in chk["evidence"]):
                errors.append(f"{card['name']}: flagged '{chk['id']}' without verified evidence")
    if tot:
        stats["checks_not_found_pct"] = round(nf / tot * 100, 1)
        stats["checks_heuristic_pct"] = round(heur / tot * 100, 1)
        if nf / tot > 0.4:
            warns.append(f"{nf / tot:.0%} of checks found no figures. On real reports set an LLM key and rerun build_redflags --force.")

    sp = data_dir / "sample_portfolio.json"
    if not sp.exists():
        errors.append("sample_portfolio.json missing (run build_dataset --sample)")
    else:
        for h in json.loads(sp.read_text("utf-8"))["holdings"]:
            if h["scheme_id"] not in ids:
                errors.append(f"sample portfolio uses unknown scheme {h['scheme_id']} (run build_dataset --sample)")
    return errors, warns, stats


def main() -> None:
    from app.config import settings

    errors, warns, stats = validate(settings.data_dir)
    print("Dataset:", json.dumps(stats))
    for w in warns[:30]:
        print("  warn:", w)
    if len(warns) > 30:
        print(f"  … {len(warns) - 30} more warnings")
    for e in errors:
        print("  ERROR:", e)
    print("OK" if not errors else f"{len(errors)} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
