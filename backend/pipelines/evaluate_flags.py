"""Measure red-flag accuracy against your own hand labels (a slide judges love).

1. python -m pipelines.make_label_sheet   (writes data/eval/labels.csv with one row per check and where to look)
   Read the report yourself and fill:  expected (flagged | passed), gold_page (PDF page with the evidence)
   check_id is one of: auditor_opinion, auditor_change, promoter_pledge,
   related_party, contingent_liabilities, cash_vs_profit, receivables
2. python -m pipelines.evaluate_flags

Prints flag precision/recall, overall agreement, coverage (how often a check
produced an answer) and the share of shown evidence that was verified on its page.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def evaluate(data_dir: Path, labels_path: Path) -> dict:
    labels = list(csv.DictReader(labels_path.open(encoding="utf-8")))
    cm: Counter = Counter()
    answered = agree = total = 0
    ev_total = ev_ok = 0
    rows = []
    ret_n = ret_hit = page_n = page_hit = 0
    for lab in labels:
        isin, cid, exp = lab["isin"].strip(), lab["check_id"].strip(), (lab.get("expected") or "").strip().lower()
        if exp not in ("flagged", "passed"):
            continue  # not labelled yet
        card_p = data_dir / "scorecards" / f"{isin}.json"
        if not card_p.exists():
            continue
        chk = next((c for c in json.loads(card_p.read_text("utf-8"))["checks"] if c["id"] == cid), None)
        if not chk:
            continue
        got = chk["status"]
        if got == "not_applicable":  # deliberately skipped (e.g. a cash-flow test on a bank)
            continue
        total += 1
        gold = str(lab.get("gold_page") or "").strip()
        if gold.isdigit():
            g = int(gold)
            # stage 1, retrieval: was the page with the answer among the passages the AI read?
            ret_n += 1
            ret_hit += any(abs(g - p) <= 1 for p in chk.get("seen_pages") or [])
            # stage 2, evidence: when the app answered, did it cite the right page?
            if got in ("flagged", "passed") and chk["evidence"]:
                page_n += 1
                page_hit += any(abs(g - int(e.get("page") or 0)) <= 1 for e in chk["evidence"])
        for e in chk["evidence"]:
            ev_total += 1
            ev_ok += bool(e.get("verified"))
        if got in ("flagged", "passed"):
            answered += 1
            agree += got == exp
            cm[(exp, got)] += 1
        rows.append((isin, cid, exp, got))
    tp, fp, fn = cm[("flagged", "flagged")], cm[("passed", "flagged")], cm[("flagged", "passed")]
    missed_flags = sum(1 for r in rows if r[2] == "flagged" and r[3] != "flagged")  # incl. not found
    exp_flags = sum(1 for r in rows if r[2] == "flagged")
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    return {
        "flag_f1": round(2 * prec * rec / (prec + rec), 3) if prec and rec else None,
        "false_negative_rate": round(missed_flags / exp_flags, 3) if exp_flags else None,
        "retrieval_hit_rate": round(ret_hit / ret_n, 3) if ret_n else None,
        "evidence_page_accuracy": round(page_hit / page_n, 3) if page_n else None,
        "stages_labelled": ret_n,
        "labelled_checks": total,
        "coverage": round(answered / total, 3) if total else None,
        "agreement_when_answered": round(agree / answered, 3) if answered else None,
        "flag_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "flag_recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "evidence_verified_rate": round(ev_ok / ev_total, 3) if ev_total else None,
        "confusion": {f"{e}->{g}": n for (e, g), n in cm.items()},
        "disagreements": [r for r in rows if r[3] in ("flagged", "passed") and r[2] != r[3]],
        "false_positives": fp,
        "false_negatives": fn,
        "examples": _examples(data_dir, rows),
    }


def _examples(data_dir: Path, rows: list[tuple]) -> list[dict]:
    """Up to 8 disagreements with readable names, for the Methodology page (honest misses build trust)."""
    names: dict = {}
    p = data_dir / "companies.json"
    if p.exists():
        names = {k: v.get("name", k) for k, v in json.loads(p.read_text("utf-8")).items()}
    out = []
    for isin, cid, exp, got in rows:
        if got in ("flagged", "passed") and exp != got:
            out.append({"company": names.get(isin, isin), "check": cid, "human": exp, "app": got,
                        "kind": "false alarm" if got == "flagged" else "missed"})
    return out[:8]


def main() -> None:
    from app.config import settings

    path = settings.data_dir / "eval" / "labels.csv"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("isin,check_id,expected\n", "utf-8")
        sys.exit(f"Created an empty {path}. Add your hand labels and run again.")
    res = evaluate(settings.data_dir, path)
    summary = {k: v for k, v in res.items() if k != "disagreements"}
    import datetime as dt

    summary["evaluated_at"] = dt.date.today().isoformat()
    (settings.data_dir / "eval" / "results.json").write_text(json.dumps(summary, indent=1), "utf-8")
    print(json.dumps(summary, indent=1))
    print(f"Saved to {settings.data_dir / 'eval' / 'results.json'} (shown on the methodology page)")
    for d in res["disagreements"]:
        print("  disagree:", d)


if __name__ == "__main__":
    main()
