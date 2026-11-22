"""Match downloaded annual report PDFs to companies and file them as <ISIN>.pdf.

Download reports with whatever names the websites give them
(e.g. 'AR_2025-26_Final.pdf', 'tcs-annual-report.pdf') into one folder, then:

    python -m pipelines.rename_reports ~/Downloads/annual_reports [--fy FY2025-26] [--dry-run]
    python -m pipelines.rename_reports ~/Downloads/older_reports --fy FY2024-25 --history

--history files older reports under DATA_DIR/reports/history/<ISIN>/<FY>.pdf for the
multi-year timeline instead of replacing the current report.

For each PDF we look for a company name from companies.json in the file name,
then in the first three pages. Matches are copied to DATA_DIR/reports/<ISIN>.pdf;
anything unsure is listed for you to rename by hand.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_SUFFIX = re.compile(r"\b(limited|ltd|pvt|private|india|co|company|corporation|corp|the|and|&)\b\.?", re.I)


def core(name: str) -> str:
    s = _SUFFIX.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"\s+", " ", s)).strip()


def first_pages_text(pdf: Path, n: int = 3) -> str:
    import pymupdf

    try:
        with pymupdf.open(pdf) as doc:
            return " ".join(doc[i].get_text("text") for i in range(min(n, len(doc))))
    except Exception:  # noqa: BLE001
        return ""


def match(pdf: Path, choices: dict[str, str]) -> tuple[str | None, str, float]:
    keys = list(choices)
    stem = core(re.sub(r"[_\-]+", " ", pdf.stem))
    hit = process.extractOne(stem, keys, scorer=fuzz.token_set_ratio)
    if hit and hit[1] >= 92 and len(hit[0]) >= 4:
        return choices[hit[0]], "file name", hit[1]
    text = core(first_pages_text(pdf))[:6000]
    best = (None, 0.0)
    for k in keys:
        if len(k) >= 4 and re.search(rf"\b{re.escape(k)}\b", text):
            score = 100.0 + len(k)  # longer exact names win ("hdfc bank" over "hdfc")
            if score > best[1]:
                best = (k, score)
    if best[0]:
        return choices[best[0]], "first pages", 100.0
    return None, "", hit[1] if hit else 0.0


def main() -> None:
    from app.config import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--fy", default="", help="financial year label to record, e.g. FY2025-26")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--history", action="store_true", help="file as an older year for the timeline (needs --fy)")
    args = ap.parse_args()

    companies: dict = json.loads((settings.data_dir / "companies.json").read_text("utf-8"))
    choices = {core(c["name"]): isin for isin, c in companies.items() if core(c["name"])}
    dest = settings.data_dir / "reports"
    dest.mkdir(exist_ok=True)
    unsure = []
    folder = Path(args.folder).expanduser()
    pdfs = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf") if folder.is_dir() else []
    if not pdfs:
        where = folder.resolve()
        print(f"No PDF files found in {where}" + ("" if folder.is_dir() else "  (this folder does not exist yet)"))
        print("Download the annual reports first (see: python -m pipelines.report_list) and save them there.")
        return
    print(f"Found {len(pdfs)} PDF(s) in {folder.resolve()}{'  (dry run: nothing copied)' if args.dry_run else ''}")
    for pdf in pdfs:
        isin, how, score = match(pdf, choices)
        if not isin:
            unsure.append(pdf.name)
            continue
        print(f"  {pdf.name}  ->  {isin}.pdf  ({companies[isin]['name']}, matched by {how})")
        if not args.dry_run and args.history:
            if not args.fy:
                sys.exit("--history needs --fy, e.g. --fy FY2024-25")
            hdir = dest / "history" / isin
            hdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, hdir / f"{args.fy}.pdf")
            continue
        if not args.dry_run:
            shutil.copy2(pdf, dest / f"{isin}.pdf")
            companies[isin]["report_url"] = f"/api/reports/{isin}.pdf"
            if args.fy:
                companies[isin]["fy"] = args.fy
    if not args.dry_run:
        (settings.data_dir / "companies.json").write_text(json.dumps(companies, indent=1, ensure_ascii=False), "utf-8")
    if unsure:
        print(f"\n{len(unsure)} file(s) not matched. Rename them to <ISIN>.pdf yourself (ISINs are in raw/reports_needed.csv):")
        for n in unsure:
            print("  -", n)


if __name__ == "__main__":
    main()
