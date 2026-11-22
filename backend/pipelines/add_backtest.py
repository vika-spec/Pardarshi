"""Add a 'Before the fall' backtest company to data/raw/report_sources.csv.

    python -m pipelines.add_backtest gensol          # a prepared case
    python -m pipelines.add_backtest --list

Then put that company's PRE-event annual report PDF in data/raw/reports_in/ and run:
    python -m pipelines.build_dataset
    python -m pipelines.rename_reports data/raw/reports_in --fy <FY of the case>
    python -m pipelines.build_redflags --isin <ISIN> --force --pause 6
Run with --list to see the prepared cases.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIELDS = ["isin", "url", "fy", "event_date", "event", "name", "source", "published", "note"]
CASES = {
    "gensol": {
        "isin": "INE06H201014", "url": "", "fy": "FY2023-24", "event_date": "2025-04-15",
        "event": "SEBI's interim order barred the company and its promoters over alleged diversion of borrowed funds and governance lapses; the share fell over 90%.",
        "name": "Gensol Engineering Ltd",
        "source": "https://www.businesstoday.in/markets/company-stock/story/sebi-bars-gensol-engineering-its-promoters-from-accessing-markets-in-fund-diversion-case-472151-2025-04-15",
        "note": "Promoter share pledges (over 80% of the promoters' holding by early 2025) were disclosed in the quarterly "
                "shareholding filings to the stock exchanges, not in this annual report, so our pledge check shows 'not found' here. "
                "Reading exchange filings is on our roadmap.",
        "published": "",  # filled from the PDF; or set the BSE filing date (YYYY-MM-DD) in report_sources.csv
    },
    "coffeeday": {
        "isin": "INE335K01011", "url": "", "fy": "FY2017-18", "event_date": "2019-07-31",
        "event": "After the founder's death in July 2019, investigations found Rs 3,535 crore had been moved from seven subsidiaries "
                 "to Mysore Amalgamated Coffee Estates, a company controlled by the promoters; SEBI later fined the company Rs 26 crore.",
        "name": "Coffee Day Enterprises Ltd",
        "source": "https://theprint.in/economy/sebi-slaps-rs-25-crore-penalty-on-coffee-day-enterprises/1334652/",
        "note": "", "published": "",
    },
    "brightcom": {
        "isin": "INE425B01027", "url": "", "fy": "FY2021-22", "event_date": "2023-04-13",
        "event": "SEBI's interim order alleged misstatements in the financial statements; a second order in August 2023 barred the "
                 "chairman and CFO over fictitious accounting of share-issue money.",
        "name": "Brightcom Group Ltd",
        "source": "https://business-standard.com/markets/news/sebi-bars-brightcom-group-s-chairman-sk-reddy-and-cfo-narayan-raju-123082200898_1.html",
        "note": "", "published": "",
    },
}


def add(row: dict, path: Path) -> str:
    rows = list(csv.DictReader(path.open(encoding="utf-8"))) if path.exists() else []
    rows = [r for r in rows if (r.get("isin") or "").strip().upper() != row["isin"]]
    rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in FIELDS} for r in rows])
    return f"{row['name']} ({row['isin']}, report {row['fy']}, event {row['event_date']}) saved to {path}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", nargs="*")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not a.case:
        for k, v in CASES.items():
            print(f"{k:10} {v['name']}  report {v['fy']}  event {v['event_date']}")
        return
    from app.config import settings

    for case in a.case:
        if case.lower() not in CASES:
            sys.exit(f"Unknown case '{case}'. Use --list.")
        print(add(dict(CASES[case.lower()]), settings.data_dir / "raw" / "report_sources.csv"))


if __name__ == "__main__":
    main()
