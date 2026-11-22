"""Build the demo portfolio from REAL funds: what a typical investor ends up holding.

    python -m pipelines.make_demo_portfolio            # prints the story and writes data/sample_portfolio.json
    python -m pipelines.make_demo_portfolio --dry-run  # prints only

Many investors buy one 'top' actively managed large-cap or flexi-cap fund from each of several fund houses, believing that
spreads their risk. This picks 5 such real funds from 5 different fund houses whose holdings overlap the most,
so the demo shows the hidden concentration an ordinary tracker misses. Amounts are made up and labelled so.
The old sample is kept as sample_portfolio.prev.json.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

POPULAR = re.compile(r"large\s*cap|bluechip|blue\s*chip|flexi\s*cap|large\s*&\s*mid|focused|elss|tax\s*saver|multi\s*cap|value\s+fund", re.I)
# index funds and ETFs overlapping is obvious; the surprise is ACTIVE funds from different houses holding the same stocks
PASSIVE = re.compile(r"\bindex\b|\betf\b|nifty|sensex|bse\s*\d|fund\s+of\s+funds|\bfof\b", re.I)
AMOUNTS = [200000, 150000, 100000, 100000, 50000]


def pick(store, k: int = 5, min_holdings: int = 20) -> list[int]:
    from app.portfolio import overlap_pct

    W = store.weights
    cov = getattr(store, "covered_isins", None)
    covered = set((cov() if callable(cov) else cov) or [])
    cov_w = [sum(W[i, store.stock_index[c]] for c in covered if c in store.stock_index) for i in range(len(store.funds))]
    best_by_amc: dict[str, list[int]] = {}
    for i, f in enumerate(store.funds):
        text = f"{f.get('category', '')} {f['name']}"
        if POPULAR.search(text) and not PASSIVE.search(text) and len(f["holdings"]) >= min_holdings and W[i].sum() > 0.6:
            best_by_amc.setdefault(f.get("amc") or f["name"].split()[0], []).append(i)
    cands = [i for v in best_by_amc.values() for i in v]
    if len(cands) < 2:
        return cands
    ov = {}
    for a, b in itertools.combinations(cands, 2):
        ov[(a, b)] = ov[(b, a)] = overlap_pct(W[a], W[b])

    def amc(i):
        return store.funds[i].get("amc") or store.funds[i]["name"].split()[0]

    pairs = [(a, b) for a, b in itertools.combinations(cands, 2) if amc(a) != amc(b)] or list(itertools.combinations(cands, 2))
    a, b = max(pairs, key=lambda p: ov[p] + 20 * (cov_w[p[0]] + cov_w[p[1]]))
    chosen = [a, b]
    while len(chosen) < k:
        rest = [i for i in cands if i not in chosen and amc(i) not in {amc(c) for c in chosen}]
        if not rest:
            rest = [i for i in cands if i not in chosen]
        if not rest:
            break
        chosen.append(max(rest, key=lambda i: sum(ov[(i, c)] for c in chosen) / len(chosen) + 20 * cov_w[i]))
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--funds", type=int, default=5)
    ap.add_argument("--min-holdings", type=int, default=20)
    a = ap.parse_args()
    from app.config import settings
    from app.data_store import DataStore
    from app.portfolio import Position, analyse

    store = DataStore(settings.data_dir)
    idx = pick(store, a.funds, a.min_holdings)
    if len(idx) < 2:
        sys.exit("Not enough popular equity funds in funds.json. Parse more fund houses first.")
    holdings, positions = [], []
    for n, i in enumerate(idx):
        f = store.funds[i]
        plan = "regular" if "regular" in f["plans"] else next(iter(f["plans"]))
        v = AMOUNTS[n % len(AMOUNTS)]
        holdings.append({"scheme_id": f["scheme_id"], "plan": plan, "value": v})
        positions.append(Position(i, plan, v))
    r = analyse(store, positions, years=20, gross_return=0.12)

    print("Demo portfolio (real funds, made-up amounts):")
    for h, f in zip(holdings, (store.funds[i] for i in idx)):
        print(f"  Rs {h['value']:>9,}  {f['name']}  ({h['plan']})")
    ovl = r["overlap"]
    print(f"\n  {ovl['n_funds']} funds from different fund houses behave like {ovl['effective_funds']} funds.")
    for s in r["exposure"]["top_stocks"][:3]:
        print(f"  Rs {s['rupees']:>9,.0f} ({s['pct_of_portfolio']}%) in {s['name']}, through {s['held_by_n_funds']} of your funds")
    print(f"  Commission over 20 years in regular plans: Rs {r['cost']['projected_loss']:,.0f}")
    if a.dry_run:
        return
    out = settings.data_dir / "sample_portfolio.json"
    if out.exists():
        (settings.data_dir / "sample_portfolio.prev.json").write_text(out.read_text("utf-8"), "utf-8")
    out.write_text(json.dumps({"label": "Sample portfolio: 5 popular funds from 5 fund houses (real funds, made-up amounts)",
                               "holdings": holdings}, indent=1), "utf-8")
    print(f"\nSaved to {out}. Run python -m pipelines.export_demo to refresh the offline demo.")


if __name__ == "__main__":
    main()
