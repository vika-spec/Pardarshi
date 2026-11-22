"""Which annual reports to download next, in the order that matters most for the demo.

    python -m pipelines.report_list            # top 20 for the sample portfolio, then across all funds
    python -m pipelines.report_list -n 30

Ranks companies by how many rupees the SAMPLE portfolio has in them (that's the report judges
see first), then fills up with the most-held companies across all loaded funds. Marks which ones
already have a PDF or a finished scorecard, and writes DATA_DIR/raw/reports_todo.csv.

How to get each report (2 minutes each):
  1. bseindia.com -> type the company name in the search box -> open the company page
  2. Corp Information (or "Financials") -> Annual Reports -> download the latest year's PDF
     (or nseindia.com -> company page -> Corporate Filings -> Annual Reports)
  3. Save it into data/raw/reports_in/ with any file name; rename_reports matches it by name.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def ranked(data_dir: Path, n: int = 20) -> list[dict]:
    funds = json.loads((data_dir / "funds.json").read_text("utf-8"))
    companies = json.loads((data_dir / "companies.json").read_text("utf-8"))
    by_id = {f["scheme_id"]: f for f in funds}
    sample_path = data_dir / "sample_portfolio.json"
    sample = json.loads(sample_path.read_text("utf-8")) if sample_path.exists() else {"holdings": []}

    rupees: dict[str, float] = defaultdict(float)
    via: dict[str, set] = defaultdict(set)
    for h in sample.get("holdings", []):
        f = by_id.get(h["scheme_id"])
        if not f:
            continue
        for s in f["holdings"]:
            rupees[s["isin"]] += float(h["value"]) * float(s["weight"])
            via[s["isin"]].add(f["name"])
    breadth: dict[str, float] = defaultdict(float)
    for f in funds:
        for s in f["holdings"]:
            breadth[s["isin"]] += float(s["weight"])

    order = sorted(rupees, key=lambda i: -rupees[i])
    order += [i for i in sorted(breadth, key=lambda i: -breadth[i]) if i not in rupees]
    rows = []
    for isin in order[:n]:
        c = companies.get(isin, {})
        rows.append({
            "rank": len(rows) + 1,
            "isin": isin,
            "name": c.get("name", isin),
            "in_sample_rupees": round(rupees.get(isin, 0.0)),
            "sample_funds": "; ".join(sorted(via.get(isin, ()))),
            "have_pdf": (data_dir / "reports" / f"{isin}.pdf").exists(),
            "have_scorecard": (data_dir / "scorecards" / f"{isin}.json").exists(),
        })
    return rows


def main() -> None:
    from app.config import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20)
    a = ap.parse_args()
    rows = ranked(settings.data_dir, a.n)
    dest = settings.data_dir / "raw" / "reports_todo.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{'#':>3}  {'status':<10} {'in sample':>11}  company (ISIN)")
    for r in rows:
        status = "done" if r["have_scorecard"] else ("have PDF" if r["have_pdf"] else "DOWNLOAD")
        amt = f"Rs {r['in_sample_rupees']:,}" if r["in_sample_rupees"] else "-"
        print(f"{r['rank']:>3}  {status:<10} {amt:>11}  {r['name']} ({r['isin']})")
    todo = sum(1 for r in rows if not r["have_pdf"] and not r["have_scorecard"])
    print(f"\n{todo} to download. Get each from bseindia.com -> company -> Annual Reports (latest year), "
          f"save into data/raw/reports_in/, then:\n"
          f"  python -m pipelines.rename_reports data/raw/reports_in --fy FY2025-26\n  python -m pipelines.build_redflags --pause 6\nList saved to {dest}")


if __name__ == "__main__":
    main()
