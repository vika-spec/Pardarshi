"""Download (or read) AMFI's public scheme master + NAV file.

AMFI publishes every open-ended scheme with its AMFI code, ISINs and NAV at
https://www.amfiindia.com/spages/NAVAll.txt (semicolon separated, grouped
under AMC headings).

    python -m pipelines.fetch_amfi                 # download
    python -m pipelines.fetch_amfi --file NAVAll.txt   # parse a saved copy

Writes DATA_DIR/raw/amfi_schemes.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402

URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def _is_num(x: str) -> bool:
    try:
        float(x.replace(",", ""))
        return True
    except ValueError:
        return False


def parse(text: str) -> list[dict]:
    """Parse NAVAll.txt. Handles the old 6-column layout and the newer one with
    separate Plan and Option columns (code;isin;isin;name;plan;option;nav;date)."""
    rows, amc, category = [], "", ""
    cols: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if line.startswith("Scheme Code"):
            cols = {p.lower(): i for i, p in enumerate(parts)}
            continue
        if len(parts) < 6:
            m = re.search(r"\((.+)\)", line)
            if m and "Scheme" in line:
                category = m.group(1)
            else:
                amc = line
            continue
        code, isin1, isin2, name = parts[:4]
        plan_i = next((i for k, i in cols.items() if "plan" in k), None)
        opt_i = next((i for k, i in cols.items() if "option" in k), None)
        if plan_i is None and len(parts) >= 8 and not _is_num(parts[4]):
            plan_i, opt_i = 4, 5  # new layout without a header line
        if plan_i is not None:
            plan_txt, opt_txt = parts[plan_i], (parts[opt_i] if opt_i is not None else "")
            name = " - ".join(x for x in (name, plan_txt, opt_txt) if x)
            nav, date = parts[-2], parts[-1]
        else:
            nav, date = parts[4], parts[5]
        plan = "direct" if re.search(r"\bdirect\b", name, re.I) else "regular"
        option = "growth" if re.search(r"growth", name, re.I) else ("idcw" if re.search(r"idcw|dividend", name, re.I) else "other")
        rows.append({"amfi": code, "isin_1": isin1 if isin1 != "-" else "", "isin_2": isin2 if isin2 != "-" else "", "name": name,
                     "nav": nav, "date": date, "amc": amc, "category": category, "plan": plan, "option": option})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="parse a saved NAVAll.txt instead of downloading")
    args = ap.parse_args()
    if args.file:
        text = Path(args.file).read_text("utf-8", errors="replace")
    else:
        import httpx

        text = httpx.get(URL, timeout=60, follow_redirects=True).text
    rows = parse(text)
    out = settings.data_dir / "raw" / "amfi_schemes.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} schemes -> {out}")


if __name__ == "__main__":
    main()
