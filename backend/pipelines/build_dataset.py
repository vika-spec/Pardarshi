"""Join AMFI schemes + parsed portfolios + expense ratios into the files the API serves.

Inputs, all in DATA_DIR/raw/:
  amfi_schemes.csv     from fetch_amfi.py
  holdings_raw.json    from parse_amc_portfolios.py
  ter.xlsx | ter.xls | ter.csv
                       AMFI "TER of MF Schemes" download, or any sheet with either
                       (a) an ISIN column + a total-TER column, or
                       (b) a scheme-name column + 'Regular … TER' and 'Direct … TER' columns, or
                       (c) the simple form: amfi,ter
  scheme_map.csv       optional manual fixes: sheet_or_scheme_name,amfi_code
  report_sources.csv   optional: isin,url,fy,event_date,event[,name,source,published]
                       (event = what later happened, for the 'Before the fall' backtest; source = a news link
                        for it; name lets you add a company no fund holds today, e.g. one that collapsed)

    python -m pipelines.build_dataset [--sample]

Writes DATA_DIR/funds.json, companies.json, meta.json,
       DATA_DIR/raw/reports_needed.csv  (which annual reports to download next)
       DATA_DIR/sample_portfolio.json   (with --sample, or if the current one points at demo funds)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.data_store import normalise_name  # noqa: E402

TER_TOTAL = re.compile(r"total\s*ter|ter[_\s]*total|total\s*expense\s*ratio|^ter\s*\(?%?\)?$|^ter$", re.I)


# ----------------------------------------------------------------------- TER
def _header_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Use the first row that mentions TER as the header (AMFI files have banner rows)."""
    for i in range(min(25, len(df))):
        row = [str(c) for c in df.iloc[i].tolist()]
        filled = [c for c in row if c.strip() and c.lower() != "nan"]
        if len(filled) >= 2 and any(re.search(r"\bTER\b|TER_|expense\s*ratio", c, re.I) for c in row):
            out = df.iloc[i + 1 :].copy()
            out.columns = [re.sub(r"\s+", " ", c).strip() for c in row]
            return out.reset_index(drop=True)
    return df


def _num(x) -> float | None:
    try:
        v = float(str(x).replace("%", "").strip())
        return v if 0 <= v < 5 else None  # TERs are a few percent at most
    except ValueError:
        return None


def load_ter(raw: Path) -> tuple[dict[str, float], dict[str, float], dict[tuple[str, str], float]]:
    """Return (by_isin, by_amfi, by_(normalised scheme name, plan))."""
    by_isin: dict[str, float] = {}
    by_amfi: dict[str, float] = {}
    by_name: dict[tuple[str, str], float] = {}
    files = [p for ext in ("xlsx", "xls", "csv") for p in raw.glob(f"ter*.{ext}")]
    for path in files:
        frames = [pd.read_csv(path, header=None, dtype=str)] if path.suffix == ".csv" else list(pd.read_excel(path, sheet_name=None, header=None, dtype=str).values())
        for raw_df in frames:
            df = _header_frame(raw_df)
            cols = list(df.columns)
            low = [c.lower() for c in cols]
            if "amfi" in low and "ter" in low:  # (c)
                for _, r in df.iterrows():
                    if (v := _num(r[cols[low.index("ter")]])) is not None:
                        by_amfi[str(r[cols[low.index("amfi")]]).strip()] = v
                continue
            isin_c = next((c for c in cols if "isin" in c.lower()), None)
            total_cs = [c for c in cols if TER_TOTAL.search(c)]
            if isin_c and total_cs:  # (a)
                for _, r in df.iterrows():
                    v = _num(r[total_cs[0]])
                    if v is not None:
                        by_isin[str(r[isin_c]).strip().upper()] = v
                continue
            name_c = next((c for c in cols if re.search(r"scheme\s*name|^scheme$", c, re.I)), None)
            reg_c = next((c for c in cols if re.search(r"regular", c, re.I) and re.search(r"total|ter", c, re.I)), None)
            dir_c = next((c for c in cols if re.search(r"direct", c, re.I) and re.search(r"total|ter", c, re.I)), None)
            if name_c and (reg_c or dir_c):  # (b)
                for _, r in df.iterrows():
                    key = normalise_name(str(r[name_c]))
                    for plan, c in (("regular", reg_c), ("direct", dir_c)):
                        if c and (v := _num(r[c])) is not None:
                            by_name[(key, plan)] = v
    return by_isin, by_amfi, by_name


# ----------------------------------------------------------------------- matching
def _option(r: dict) -> str:
    name = r.get("name", "")
    if re.search(r"idcw|dividend|bonus|payout|reinvest", name, re.I):
        return "idcw"
    if re.search(r"growth|\bgr\b|cumulative", name, re.I):
        return "growth"
    return r.get("option") or "other"


DIRECT = re.compile(r"direct|\bdir\b|\(d\)", re.I)


def _plan_of(r: dict) -> str:
    """AMFI spells plans many ways: 'Direct Plan', '-Direct-', 'DirectPlan', 'Dir'."""
    if DIRECT.search(r.get("name", "")):
        return "direct"
    if (r.get("plan") or "").lower() == "direct":
        return "direct"
    return "regular"


def _prefer_growth(rows: list[dict]) -> list[dict]:
    """One row per plan: the Growth option if there is one, else any non-IDCW, else whatever exists.
    (AMFI names don't always say 'Growth', so never drop a scheme just for that.)"""
    best: dict[str, dict] = {}
    rank = {"growth": 0, "other": 1, "idcw": 2}
    for r in rows:
        plan = _plan_of(r)
        r = {**r, "plan": plan}
        if plan not in best or rank[_option(r)] < rank[_option(best[plan])]:
            best[plan] = r
    return list(best.values())


def _tidy(name: str) -> str:
    """'SBI LARGE & MIDCAP FUND' -> 'SBI Large & Midcap Fund' (keeps short acronyms)."""
    if not name.isupper():
        return name
    keep = {"SBI", "HDFC", "ICICI", "UTI", "DSP", "LIC", "HSBC", "ETF", "BSE", "MSCI", "PSU", "PSE", "IT", "ESG", "MNC", "ELSS", "FMCG", "BFSI", "CPSE", "NJ", "PGIM", "ITI", "JM"}
    return " ".join(w if w in keep else w.capitalize() for w in name.split())


def _fix_amfi_rows(rows: list[dict]) -> list[dict]:
    """amfi_schemes.csv files saved by older fetch_amfi versions from the newer AMFI layout
    have the plan in 'nav' and the option in 'date'. Fold them back into the name."""
    for r in rows:
        nav = r.get("nav", "")
        if re.search(r"\bplan\b|direct|regular", nav, re.I):
            r["name"] = " - ".join(x for x in (r["name"], nav, r.get("date", "")) if x)
            r["plan"] = "direct" if re.search(r"direct", nav, re.I) else "regular"
            r["option"] = _option(r)
            r["nav"], r["date"] = "", ""
    return rows


def _amc_rows(amfi: list[dict], hint: str) -> list[dict]:
    if not hint:
        return amfi
    amcs = sorted({r["amc"] for r in amfi})
    best = process.extractOne(hint, amcs, scorer=fuzz.token_set_ratio)
    if best and best[1] >= 85:
        return [r for r in amfi if r["amc"] == best[0]]
    return amfi


def build(data_dir: Path, *, write_sample: bool = False, log=print) -> dict:
    raw = data_dir / "raw"
    amfi = _fix_amfi_rows(list(csv.DictReader((raw / "amfi_schemes.csv").open(encoding="utf-8"))))
    portfolios = json.loads((raw / "holdings_raw.json").read_text("utf-8"))
    ter_isin, ter_amfi, ter_name = load_ter(raw)
    if any(raw.glob("ter*")) and not (ter_isin or ter_amfi or ter_name):
        log("WARNING: found a ter file but couldn't recognise its columns. Expected an ISIN + total-TER column, "
            "scheme name + Regular/Direct TER columns, or amfi,ter. Costs will be skipped until this is fixed.")
    overrides: dict[str, str] = {}
    if (raw / "scheme_map.csv").exists():
        for r in csv.reader((raw / "scheme_map.csv").open(encoding="utf-8")):
            if len(r) >= 2 and r[1].strip().isdigit():
                overrides[r[0].strip().lower()] = r[1].strip()
    by_code = {r["amfi"]: r for r in amfi}

    funds, companies, misses = [], {}, []
    weight_sum: Counter = Counter()
    for pf in portfolios:
        rows: list[dict] = []
        key = next((k for k in (pf["scheme_name"].lower(), pf.get("sheet", "").lower(), pf.get("file", "").lower()) if k in overrides), None)
        if key:
            code = overrides[key]
            base = normalise_name(by_code[code]["name"]) if code in by_code else ""
            rows = _prefer_growth([r for r in amfi if normalise_name(r["name"]) == base]) or ([by_code[code]] if code in by_code else [])
        else:
            pool = _amc_rows(amfi, pf.get("amc_hint", ""))
            groups: dict[str, list[dict]] = {}
            for r in pool:
                groups.setdefault(normalise_name(r["name"]), []).append(r)
            hit = process.extractOne(normalise_name(pf["scheme_name"]), list(groups), scorer=fuzz.token_set_ratio) if groups else None
            if hit and hit[1] >= 88:
                rows = _prefer_growth(groups[hit[0]])
        if not rows:
            sugg = process.extract(normalise_name(pf["scheme_name"]), list({normalise_name(r["name"]) for r in amfi}), scorer=fuzz.token_set_ratio, limit=3)
            misses.append((pf["scheme_name"], pf.get("file", ""), [s[0] for s in sugg]))
            continue

        plans: dict[str, dict] = {}
        for r in rows:
            isins = [i for i in (r["isin_1"], r["isin_2"]) if i]
            ter = next((ter_isin[i] for i in isins if i in ter_isin), None)
            if ter is None:
                ter = ter_amfi.get(r["amfi"])
            if ter is None:
                ter = ter_name.get((normalise_name(r["name"]), r["plan"]))
            if r["plan"] not in plans:
                plans[r["plan"]] = {"isins": isins, "amfi": r["amfi"], "ter": ter}
        base = rows[0]
        funds.append({
            "scheme_id": f"AMFI-{min(r['amfi'] for r in rows)}",
            "name": _tidy(re.split(r"\s+-\s+", base["name"])[0].strip()),
            "amc": base["amc"],
            "category": re.sub(r"^.*?-\s*", "", base["category"]) if " - " in base["category"] else base["category"],
            "holdings_asof": pf.get("asof", ""),
            "plans": plans,
            "holdings": pf["holdings"],
        })
        for h in pf["holdings"]:
            companies.setdefault(h["isin"], {"name": h["name"], "sector": h.get("sector", "Other"), "fy": "", "report_url": ""})
            weight_sum[h["isin"]] += h["weight"]

    # de-duplicate schemes matched twice (e.g. two sheets for one scheme): keep the larger portfolio
    uniq: dict[str, dict] = {}
    for f in funds:
        if f["scheme_id"] not in uniq or len(f["holdings"]) > len(uniq[f["scheme_id"]]["holdings"]):
            uniq[f["scheme_id"]] = f
    funds = list(uniq.values())

    # keep report details from earlier runs (rename_reports sets fy), then apply report_sources.csv
    old_path = data_dir / "companies.json"
    old = json.loads(old_path.read_text("utf-8")) if old_path.exists() else {}
    for isin, c in companies.items():
        for k in ("fy", "source_url", "event", "published"):
            if old.get(isin, {}).get(k):
                c[k] = old[isin][k]
    if (raw / "report_sources.csv").exists():
        for r in csv.DictReader((raw / "report_sources.csv").open(encoding="utf-8")):
            isin = (r.get("isin") or "").strip().upper()
            if isin not in companies and (r.get("name") or "").strip() and re.match(r"^IN[A-Z0-9]{10}$", isin):
                # a backtest company no fund holds today (it may have collapsed or been delisted)
                companies[isin] = {"isin": isin, "name": r["name"].strip(), "sector": (r.get("sector") or "").strip() or "Other",
                                   "backtest_only": True}
            if isin in companies:
                if r.get("url"):
                    companies[isin]["source_url"] = r["url"].strip()
                if r.get("fy"):
                    companies[isin]["fy"] = r["fy"].strip()
                if (r.get("published") or "").strip():
                    companies[isin]["published"] = r["published"].strip()
                if r.get("event_date") and r.get("event"):
                    companies[isin]["event"] = {"date": r["event_date"].strip(), "summary": r["event"].strip(),
                                                **({"source": r["source"].strip()} if (r.get("source") or "").strip() else {}),
                                                **({"note": r["note"].strip()} if (r.get("note") or "").strip() else {})}
    reports = data_dir / "reports"
    reports.mkdir(exist_ok=True)
    for isin, c in companies.items():
        if (reports / f"{isin}.pdf").exists() or c.get("source_url") or (data_dir / "scorecards" / f"{isin}.json").exists():
            c["report_url"] = f"/api/reports/{isin}.pdf"

    (data_dir / "funds.json").write_text(json.dumps(funds, indent=1, ensure_ascii=False), "utf-8")
    (data_dir / "companies.json").write_text(json.dumps(companies, indent=1, ensure_ascii=False), "utf-8")
    asofs = sorted({f["holdings_asof"] for f in funds if f["holdings_asof"]})
    (data_dir / "meta.json").write_text(json.dumps({
        "dataset": "live",
        "notice": "",
        "holdings_source": "Fund house monthly portfolio disclosures (SEBI-mandated)" + (f", as of {asofs[-1]}" if asofs else ""),
        "ter_source": "AMFI total expense ratio (TER) disclosures",
        "built_at": dt.date.today().isoformat(),
    }, indent=1), "utf-8")

    # which annual reports matter most: companies most held across the dataset
    with (raw / "reports_needed.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "isin", "name", "sector", "held_by_n_schemes", "have_pdf"])
        held_by = Counter(h["isin"] for f in funds for h in f["holdings"])
        for rank, (isin, _) in enumerate(weight_sum.most_common(100), start=1):
            c = companies[isin]
            w.writerow([rank, isin, c["name"], c["sector"], held_by[isin], (reports / f"{isin}.pdf").exists()])

    sample_path = data_dir / "sample_portfolio.json"
    current = json.loads(sample_path.read_text("utf-8")) if sample_path.exists() else {}
    ids = {f["scheme_id"] for f in funds}
    if write_sample or not current or any(h["scheme_id"] not in ids for h in current.get("holdings", [])):
        write_sample_portfolio(data_dir, funds)
        log("Wrote a new sample_portfolio.json from real funds (edit it if you like).")

    missing_ter = [f["name"] for f in funds if any(p.get("ter") is None for p in f["plans"].values())]
    log(f"{len(funds)} schemes, {len(companies)} companies written.")
    if misses:
        log(f"{len(misses)} portfolio sheets did not match an AMFI scheme. Fix with raw/scheme_map.csv (name,amfi_code):")
        for name, file, sugg in misses[:40]:
            log(f"  - {name!r} [{file}]  closest: {'; '.join(sugg)}")
    if missing_ter:
        log(f"{len(missing_ter)} schemes have no TER for one plan; their cost row will be skipped. Examples: {missing_ter[:5]}")
    return {"funds": len(funds), "companies": len(companies), "unmatched": len(misses), "missing_ter": len(missing_ter)}


PREFERRED = ["large cap", "flexi cap", "index", "mid cap", "small cap", "elss"]


def write_sample_portfolio(data_dir: Path, funds: list[dict]) -> None:
    """A realistic example built from real schemes; amounts are made up and labelled so.
    Prefers one fund per popular category with both plans, but never writes an empty sample."""
    def has_both(f):
        return {"direct", "regular"} <= set(f["plans"])

    chosen: list[dict] = []
    for need_both in (True, False):
        for cat in PREFERRED:
            if len(chosen) >= 6:
                break
            f = next((f for f in funds if cat in (f["category"] + " " + f["name"]).lower() and f not in chosen and (has_both(f) or not need_both)), None)
            if f:
                chosen.append(f)
    for f in sorted(funds, key=lambda f: (not has_both(f), -len(f["holdings"]))):
        if len(chosen) >= 6:
            break
        if f not in chosen:
            chosen.append(f)
    amounts = [180000, 150000, 90000, 120000, 75000, 60000]
    want = ["regular", "regular", "direct", "regular", "direct", "regular"]
    holdings = []
    for i, f in enumerate(chosen[:6]):
        plan = want[i] if want[i] in f["plans"] else next(iter(f["plans"]))
        holdings.append({"scheme_id": f["scheme_id"], "plan": plan, "value": amounts[i]})
    sample = {"label": "Sample portfolio (real funds, made-up amounts)", "holdings": holdings}
    (data_dir / "sample_portfolio.json").write_text(json.dumps(sample, indent=1), "utf-8")


def main() -> None:
    from app.config import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="rewrite sample_portfolio.json from real funds")
    args = ap.parse_args()
    build(settings.data_dir, write_sample=args.sample)


if __name__ == "__main__":
    main()
