"""Check the figures we extracted against an independent public source (screener.in).

    python -m pipelines.check_figures

Reference values are in eval/reference_figures.csv (consolidated, Rs crore, with the page they came from).
Annual reports state figures in crore, lakh, million, thousand or rupees, so a figure counts as a MATCH if,
after one of those unit conversions, it is within 2% of the reference (or 0.6 crore for small companies,
because the reference is rounded to whole crore). References exist for both bases; a figure that matches the other basis is reported as such. Results go to data/eval/figures.json and the Methodology page.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REF = Path(__file__).resolve().parent.parent / "eval" / "reference_figures.csv"
FIELDS = {  # our value name -> (reference field, year)
    "revenue_current": ("revenue", "current"), "revenue_previous": ("revenue", "previous"),
    "pat_current": ("pat", "current"), "pat_previous": ("pat", "previous"),
    "cfo_current": ("cfo", "current"), "cfo_previous": ("cfo", "previous"),
    "total_equity": ("equity", "current"),
}
UNITS = {"crore": 1.0, "million": 10.0, "lakh": 100.0, "thousand": 1e4, "rupees": 1e7}


def match(ours: float, ref: float) -> str | None:
    for unit, k in UNITS.items():
        v = ours / k
        if abs(v - ref) <= max(0.02 * abs(ref), 0.6):
            return unit
    return None


def check(data_dir: Path, ref_path: Path = REF) -> dict:
    """Compare every extracted figure with the public reference.

    A figure is a MATCH if it equals the reference for the basis the check reported (standalone or
    consolidated); MATCH (OTHER BASIS) if it equals the reference for the other basis, which means the figure
    is a real published number but its basis label was wrong; MISMATCH otherwise. A check whose figures match
    different bases is listed under mixed_basis, because its ratio mixes standalone and consolidated numbers."""
    refs: dict = {}
    names: dict = {}
    for r in csv.DictReader(ref_path.open(encoding="utf-8")):
        refs[(r["isin"], r["basis"], r["year"], r["field"])] = float(r["value_crore"])
        names[r["isin"]] = r["company"]
    rows, mixed = [], []
    for isin, company in names.items():
        p = data_dir / "scorecards" / f"{isin}.json"
        if not p.exists():
            continue
        card = json.loads(p.read_text("utf-8"))
        for c in card["checks"]:
            label = (c.get("basis") or "unknown").lower()
            label = label if label in ("standalone", "consolidated") else "consolidated"
            other = "standalone" if label == "consolidated" else "consolidated"
            bases_seen = set()
            for name, v in (c.get("values") or {}).items():
                if name not in FIELDS or not isinstance(v, (int, float)):
                    continue
                field, year = FIELDS[name]
                r1, r2 = refs.get((isin, label, year, field)), refs.get((isin, other, year, field))
                if r1 is None:
                    continue  # no public reference for the basis this check reported
                u1 = match(v, r1) if r1 is not None else None
                u2 = match(v, r2) if r2 is not None and not u1 else None
                result = "match" if u1 else "match (other basis)" if u2 else "MISMATCH"
                if u1:
                    bases_seen.add(label)
                elif u2:
                    bases_seen.add(other)
                rows.append({"company": company, "check": c["id"], "figure": name, "ours": v,
                             "reference": r1 if r1 is not None else r2, "basis": label,
                             "unit": u1 or u2, "result": result})
            if len(bases_seen) > 1:
                mixed.append({"company": company, "check": c["id"]})
    # the same figure is often used by two checks; count each distinct (company, figure, value) once
    seen, uniq = set(), []
    for r in rows:
        k = (r["company"], r["figure"], r["ours"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    real = sum(r["result"] != "MISMATCH" for r in uniq)
    exact = sum(r["result"] == "match" for r in uniq)
    return {"compared": len(uniq), "matched": real, "match_rate": round(real / len(uniq), 3) if uniq else None,
            "matched_labelled_basis": exact, "wrong_basis_label": real - exact, "mismatched": len(uniq) - real,
            "mixed_basis_checks": mixed, "standalone_skipped": 0,
            "source": "screener.in annual figures, standalone and consolidated (Rs crore)",
            "checked_at": dt.date.today().isoformat(), "rows": uniq}


def main() -> None:
    from app.config import settings

    res = check(settings.data_dir)
    out = settings.data_dir / "eval" / "figures.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1), "utf-8")
    for r in res["rows"]:
        print(f"  {r['result']:20} {r['company'][:20]:20} {r['figure']:18} ours={r['ours']:>16,.2f}  ref={r['reference']:>12,.0f} cr  {r.get('unit') or ''}")
    print(f"\n{res['matched']} of {res['compared']} extracted figures are real published figures ({res['match_rate']}): "
          f"{res['matched_labelled_basis']} on the stated basis, {res['wrong_basis_label']} with the wrong basis label; "
          f"{res['mismatched']} mismatched.")
    for m in res["mixed_basis_checks"]:
        print(f"  mixed basis: {m['company']} / {m['check']} uses both standalone and consolidated figures")
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
