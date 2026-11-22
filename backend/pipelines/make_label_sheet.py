"""Make the hand-labelling sheet for evaluate_flags.

    python -m pipelines.make_label_sheet

Writes data/eval/labels.csv (or labels_new.csv if labels.csv already has your answers) with one row per
check for every company that has a scorecard. For each row it gives the question in plain words and the PDF
pages where to start looking. It does NOT show the app's answer, so your label is independent.

Fill two columns while reading the report yourself:
    expected   flagged | passed   (leave empty if you could not decide)
    gold_page  the PDF page where you found the evidence
Then run: python -m pipelines.evaluate_flags
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

QUESTIONS = {
    "auditor_opinion": "Does the auditor's report give a qualified/adverse/disclaimer opinion or a going-concern doubt? (flagged if yes)",
    "auditor_change": "Did the statutory auditor resign or leave mid-term this year? (flagged if yes)",
    "promoter_pledge": "Are more than 10% of the promoter group's shares pledged or encumbered? (flagged if yes; no promoter = passed)",
    "related_party": "Are related-party transactions more than 10% of revenue, or growing 20+ points faster than revenue?",
    "contingent_liabilities": "Are contingent liabilities more than 25% of total equity (net worth)?",
    "cash_vs_profit": "Is 2-year operating cash flow below half of 2-year profit, or did cash fall while profit rose?",
    "receivables": "Did trade receivables grow 20+ points faster than revenue?",
}
FIELDS = ["isin", "company", "fy", "check_id", "question", "look_at_pages", "expected", "gold_page", "notes"]


def main() -> None:
    from app.config import settings

    out_dir = settings.data_dir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted((settings.data_dir / "scorecards").glob("*.json")):
        card = json.loads(p.read_text("utf-8"))
        for c in card["checks"]:
            if c["status"] == "not_applicable":
                continue
            rows.append({"isin": card["isin"], "company": card["name"], "fy": card.get("fy", ""), "check_id": c["id"],
                         "question": QUESTIONS.get(c["id"], ""), "look_at_pages": " ".join(map(str, (c.get("seen_pages") or [])[:6])),
                         "expected": "", "gold_page": "", "notes": ""})
    target = out_dir / "labels.csv"
    if target.exists() and any(r.get("expected") for r in csv.DictReader(target.open(encoding="utf-8"))):
        target = out_dir / "labels_new.csv"
    with target.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} checks to {target}. Open it in Excel, fill 'expected' and 'gold_page', save as CSV,")
    print("then run: python -m pipelines.evaluate_flags")


if __name__ == "__main__":
    main()
