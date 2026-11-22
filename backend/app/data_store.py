"""Loads the prepared dataset once at startup and keeps it in memory.

Files under DATA_DIR (built by the pipelines/ scripts):
  funds.json            schemes, their direct/regular plans, TERs and holdings
  companies.json        listed companies we can show (name, sector, report info)
  scorecards/<ISIN>.json  red-flag results per company (built offline)
  chunks/<ISIN>.jsonl   page-tagged text of each annual report (for chat + evidence)

All fund holdings are packed into one dense weight matrix (funds x stocks) so
exposure and overlap are a couple of vectorised numpy operations per request.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz, process

log = logging.getLogger("pardarshi.data")

_NAME_NOISE = re.compile(
    r"\b(direct|regular|plan|growth|option|idcw|dividend|payout|reinvestment|fund|scheme|the|-|\(|\))\b",
    re.I,
)


def normalise_name(name: str) -> str:
    """Strip plan/option words so 'X Fund - Direct Plan - Growth' ~ 'X Fund Regular Growth'."""
    s = _NAME_NOISE.sub(" ", name.lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass(frozen=True)
class PlanRef:
    scheme_idx: int
    plan: str  # "direct" | "regular"


class DataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.funds: list[dict] = json.loads((data_dir / "funds.json").read_text("utf-8"))
        self.companies: dict[str, dict] = json.loads((data_dir / "companies.json").read_text("utf-8"))
        meta_path = data_dir / "meta.json"
        self.meta: dict = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
        self._scorecards: dict[str, dict] = {}
        self._pages: dict[str, dict[int, str]] = {}
        self._build_indexes()
        log.info("Loaded %d schemes, %d stocks, %d companies", len(self.funds), len(self.stock_isins), len(self.companies))

    # ------------------------------------------------------------------ indexes
    def _build_indexes(self) -> None:
        stock_set: dict[str, int] = {}
        for f in self.funds:
            for h in f["holdings"]:
                stock_set.setdefault(h["isin"], len(stock_set))
        self.stock_isins: list[str] = list(stock_set)
        self.stock_index: dict[str, int] = stock_set
        self.stock_names: dict[str, str] = {}
        self.stock_sectors: dict[str, str] = {}

        w = np.zeros((len(self.funds), len(self.stock_isins)), dtype=np.float64)
        for i, f in enumerate(self.funds):
            for h in f["holdings"]:
                j = stock_set[h["isin"]]
                w[i, j] += float(h["weight"])
                self.stock_names.setdefault(h["isin"], h.get("name", h["isin"]))
                self.stock_sectors.setdefault(h["isin"], h.get("sector", "Other"))
        self.weights = w  # fraction of each fund's NAV held in each stock

        self.by_isin: dict[str, PlanRef] = {}
        self.by_amfi: dict[str, PlanRef] = {}
        self._name_choices: dict[str, int] = {}
        for i, f in enumerate(self.funds):
            for plan_name, plan in f.get("plans", {}).items():
                ref = PlanRef(i, plan_name)
                for isin in plan.get("isins", []):
                    self.by_isin[isin.upper()] = ref
                if plan.get("amfi"):
                    self.by_amfi[str(plan["amfi"])] = ref
            self._name_choices[normalise_name(f["name"])] = i

    # ------------------------------------------------------------------ lookups
    def match_scheme(self, name: str, isin: str | None = None, amfi: str | None = None) -> tuple[PlanRef | None, str]:
        """Find a scheme+plan. Returns (ref, how) where how is isin|amfi|name|none."""
        if isin and isin.upper() in self.by_isin:
            return self.by_isin[isin.upper()], "isin"
        if amfi and str(amfi) in self.by_amfi:
            return self.by_amfi[str(amfi)], "amfi"
        if not name:
            return None, "none"
        best = process.extractOne(normalise_name(name), list(self._name_choices), scorer=fuzz.token_set_ratio)
        if best and best[1] >= 90:
            idx = self._name_choices[best[0]]
            plan = "direct" if re.search(r"\bdirect\b", name, re.I) else "regular"
            if plan not in self.funds[idx].get("plans", {}):
                plan = next(iter(self.funds[idx]["plans"]))
            return PlanRef(idx, plan), "name"
        return None, "none"

    def search_funds(self, query: str, limit: int = 8) -> list[dict]:
        if not query.strip():
            return []
        hits = process.extract(normalise_name(query), list(self._name_choices), scorer=fuzz.WRatio, limit=limit)
        out = []
        for key, score, _ in hits:
            if score < 55:
                continue
            f = self.funds[self._name_choices[key]]
            out.append({"scheme_id": f["scheme_id"], "name": f["name"], "amc": f.get("amc", ""), "category": f.get("category", ""), "plans": list(f.get("plans", {}))})
        return out

    def scheme_by_id(self, scheme_id: str) -> int | None:
        for i, f in enumerate(self.funds):
            if f["scheme_id"] == scheme_id:
                return i
        return None

    # ------------------------------------------------------------------ red flags
    def scorecard(self, isin: str) -> dict | None:
        if isin not in self._scorecards:
            p = self.data_dir / "scorecards" / f"{isin}.json"
            if not p.exists():
                return None
            self._scorecards[isin] = json.loads(p.read_text("utf-8"))
        return self._scorecards[isin]

    def pages(self, isin: str) -> dict[int, str]:
        if isin not in self._pages:
            p = self.data_dir / "chunks" / f"{isin}.jsonl"
            pages: dict[int, str] = {}
            if p.exists():
                for line in p.read_text("utf-8").splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        pages[int(rec["page"])] = rec["text"]
            self._pages[isin] = pages
        return self._pages[isin]

    def history(self, isin: str) -> list[dict]:
        """Scorecards from earlier financial years (data/scorecards/history/<ISIN>/<FY>.json)."""
        d = self.data_dir / "scorecards" / "history" / isin
        if not d.is_dir():
            return []
        out = []
        for p in sorted(d.glob("*.json")):
            try:
                out.append(json.loads(p.read_text("utf-8")))
            except ValueError:
                continue
        return out

    @cached_property
    def covered_isins(self) -> set[str]:
        d = self.data_dir / "scorecards"
        found = {p.stem for p in d.glob("*.json")} if d.exists() else set()
        return found & set(self.companies)  # ignore leftovers (e.g. demo files) not in this dataset
