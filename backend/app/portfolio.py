"""Deterministic portfolio maths. No LLM touches these numbers.

Every result carries a `working` block: formula, inputs and data source, so the
UI can show how each figure was produced.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data_store import DataStore


@dataclass
class Position:
    scheme_idx: int
    plan: str  # "direct" | "regular"
    value: float  # current market value in rupees
    matched_by: str = "manual"


def _fv(value: float, annual_rate: float, years: float) -> float:
    return value * (1.0 + annual_rate) ** years


def overlap_pct(wa: np.ndarray, wb: np.ndarray) -> float:
    """Weighted overlap: sum over stocks of min(weight in A, weight in B).

    Weights are first normalised to each fund's equity book so a fund holding
    5% cash is not penalised. Result is 0..1; a fund compared with itself is 1.
    """
    sa, sb = wa.sum(), wb.sum()
    if sa <= 0 or sb <= 0:
        return 0.0
    return float(np.minimum(wa / sa, wb / sb).sum())


def analyse(store: DataStore, positions: list[Position], *, years: float, gross_return: float) -> dict:
    positions = [p for p in positions if p.value > 0]
    if not positions:
        raise ValueError("No holdings with a positive value were found.")

    total = float(sum(p.value for p in positions))
    values = np.array([p.value for p in positions])
    W = store.weights[[p.scheme_idx for p in positions]]  # (k, n_stocks)

    # ---------------------------------------------------------------- exposure
    stock_rupees = values @ W  # rupees in each stock via all funds
    invested_in_stocks = float(stock_rupees.sum())
    other = total - invested_in_stocks  # cash, debt, unlisted, unmapped
    order = np.argsort(-stock_rupees)
    top = []
    for j in order[:25]:
        if stock_rupees[j] <= 0:
            break
        contributors = []
        for k, p in enumerate(positions):
            r = values[k] * W[k, j]
            if r > 0:
                contributors.append({"fund": store.funds[p.scheme_idx]["name"], "rupees": round(float(r), 2)})
        isin = store.stock_isins[j]
        top.append(
            {
                "isin": isin,
                "name": store.stock_names[isin],
                "sector": store.stock_sectors[isin],
                "rupees": round(float(stock_rupees[j]), 2),
                "pct_of_portfolio": round(float(stock_rupees[j] / total) * 100, 2),
                "held_by_n_funds": len(contributors),
                "via": contributors,
                "has_scorecard": isin in store.covered_isins,
            }
        )
    shares = stock_rupees / invested_in_stocks if invested_in_stocks > 0 else stock_rupees
    hhi = float((shares**2).sum())
    top10_pct = float(np.sort(stock_rupees)[::-1][:10].sum() / total * 100)

    sectors: dict[str, float] = {}
    for j, r in enumerate(stock_rupees):
        if r > 0:
            s = store.stock_sectors[store.stock_isins[j]]
            sectors[s] = sectors.get(s, 0.0) + float(r)
    sector_list = sorted(
        ({"sector": s, "rupees": round(r, 2), "pct_of_portfolio": round(r / total * 100, 2)} for s, r in sectors.items()),
        key=lambda x: -x["rupees"],
    )

    # ---------------------------------------------------------------- overlap
    k = len(positions)
    O = np.eye(k)
    for a in range(k):
        for b in range(a + 1, k):
            O[a, b] = O[b, a] = overlap_pct(W[a], W[b])
    weights_v = values / total
    effective_funds = float(1.0 / (weights_v @ O @ weights_v))
    pairs = []
    for a in range(k):
        for b in range(a + 1, k):
            pairs.append(
                {
                    "a": store.funds[positions[a].scheme_idx]["name"],
                    "b": store.funds[positions[b].scheme_idx]["name"],
                    "overlap_pct": round(O[a, b] * 100, 1),
                    "shared_stocks": int(((W[a] > 0) & (W[b] > 0)).sum()),
                }
            )
    pairs.sort(key=lambda x: -x["overlap_pct"])

    # ---------------------------------------------------------------- cost
    cost_rows = []
    total_loss = 0.0
    annual_now = 0.0
    for p in positions:
        f = store.funds[p.scheme_idx]
        plans = f.get("plans", {})
        ter_reg = plans.get("regular", {}).get("ter")
        ter_dir = plans.get("direct", {}).get("ter")
        row = {
            "fund": f["name"],
            "plan": p.plan,
            "value": round(p.value, 2),
            "ter_regular_pct": ter_reg,
            "ter_direct_pct": ter_dir,
        }
        if p.plan == "regular" and ter_reg is not None and ter_dir is not None:
            gap = (ter_reg - ter_dir) / 100.0
            fv_direct = _fv(p.value, gross_return - ter_dir / 100.0, years)
            fv_regular = _fv(p.value, gross_return - ter_reg / 100.0, years)
            loss = fv_direct - fv_regular
            row.update({"extra_cost_pct": round(gap * 100, 2), "projected_loss": round(loss, 2), "annual_cost_now": round(p.value * gap, 2)})
            total_loss += loss
            annual_now += p.value * gap
        cost_rows.append(row)
    n_regular = sum(1 for p in positions if p.plan == "regular")

    holdings_asof = sorted({store.funds[p.scheme_idx].get("holdings_asof", "") for p in positions} - {""})
    source = store.meta.get("holdings_source", "Fund house monthly portfolio disclosures")

    return {
        "total_value": round(total, 2),
        "funds": [
            {
                "scheme_id": store.funds[p.scheme_idx]["scheme_id"],
                "name": store.funds[p.scheme_idx]["name"],
                "amc": store.funds[p.scheme_idx].get("amc", ""),
                "category": store.funds[p.scheme_idx].get("category", ""),
                "plan": p.plan,
                "value": round(p.value, 2),
                "pct_of_portfolio": round(p.value / total * 100, 2),
                "matched_by": p.matched_by,
            }
            for p in positions
        ],
        "exposure": {
            "top_stocks": top,
            "sectors": sector_list,
            "top10_pct": round(top10_pct, 1),
            "effective_stocks": round(1.0 / hhi, 1) if hhi > 0 else 0.0,
            "in_stocks_pct": round(invested_in_stocks / total * 100, 1),
            "other_pct": round(other / total * 100, 1),
            "working": {
                "formula": "exposure(stock) = Σ over funds of (your value in fund × fund's weight in stock)",
                "plain": "We open each fund, take its share in every company, and multiply by the money you have in that fund.",
                "inputs": f"{k} funds, {int((stock_rupees > 0).sum())} companies",
                "source": f"{source}; holdings as of {', '.join(holdings_asof) or 'n/a'}",
            },
        },
        "overlap": {
            "n_funds": k,
            "effective_funds": round(effective_funds, 1),
            "pairs": pairs,
            "matrix": [[round(x * 100, 1) for x in row] for row in O.tolist()],
            "labels": [store.funds[p.scheme_idx]["name"] for p in positions],
            "working": {
                "formula": "overlap(A,B) = Σ min(wA, wB); effective funds = 1 / (vᵀ O v)",
                "plain": "For each company two funds share, take the smaller weight and add them up. "
                "'Behaves like N funds' weights every pair's overlap by how much money is in each.",
                "inputs": f"{k} funds, {len(pairs)} pairs",
                "source": f"{source}; holdings as of {', '.join(holdings_asof) or 'n/a'}",
            },
        },
        "cost": {
            "years": years,
            "gross_return_pct": round(gross_return * 100, 1),
            "n_regular": n_regular,
            "projected_loss": round(total_loss, 2),
            "annual_cost_now": round(annual_now, 2),
            "rows": cost_rows,
            "working": {
                "formula": "loss = V(1 + r − TER_direct)^n − V(1 + r − TER_regular)^n",
                "plain": f"We grow today's value for {years:g} years at an assumed {gross_return*100:.0f}% before costs, once with the "
                "direct plan's expense ratio and once with the regular plan's, then subtract. Future SIPs are not included.",
                "inputs": f"{n_regular} regular-plan holdings",
                "source": store.meta.get("ter_source", "AMFI total expense ratio (TER) disclosures"),
            },
        },
    }
