"""Parse a Consolidated Account Statement (CAS) into anonymous positions.

Privacy contract (tested in tests/test_cas.py):
  * The PDF is parsed from memory and never written to disk or logged.
  * Investor name, PAN, email, mobile, folio numbers and addresses are dropped
    here, before anything else in the app sees the data. Only scheme names,
    ISINs/AMFI codes and rupee values leave this module.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field

from .data_store import DataStore
from .portfolio import Position

log = logging.getLogger("pardarshi.cas")


class CASError(Exception):
    """User-facing parse problem. The message is safe to show."""


@dataclass
class ParsedCAS:
    positions: list[Position]
    unmatched: list[dict] = field(default_factory=list)
    direct_stocks: list[dict] = field(default_factory=list)
    statement_type: str = ""
    as_of: str = ""


def _plan_from_name(name: str) -> str:
    return "direct" if re.search(r"\bdirect\b", name or "", re.I) else "regular"


def _num(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def positions_from_raw(store: DataStore, raw_schemes: list[dict]) -> tuple[list[Position], list[dict]]:
    """raw_schemes: [{name, isin?, amfi?, value}] -> matched positions + unmatched list."""
    merged: dict[tuple[int, str], Position] = {}
    unmatched: list[dict] = []
    for s in raw_schemes:
        value = _num(s.get("value"))
        if value <= 0:
            continue
        ref, how = store.match_scheme(s.get("name", ""), s.get("isin"), s.get("amfi"))
        if ref is None:
            unmatched.append({"name": s.get("name", "Unknown scheme"), "value": round(value, 2)})
            continue
        plan = ref.plan
        # A name match can't see the plan reliably; trust the statement's wording.
        if how == "name":
            plan = _plan_from_name(s.get("name", ""))
            if plan not in store.funds[ref.scheme_idx].get("plans", {}):
                plan = ref.plan
        key = (ref.scheme_idx, plan)
        if key in merged:
            merged[key].value += value
        else:
            merged[key] = Position(ref.scheme_idx, plan, value, how)
    return list(merged.values()), unmatched


def parse_cas(store: DataStore, pdf_bytes: bytes, password: str) -> ParsedCAS:
    try:
        import casparser
        from casparser.exceptions import IncorrectPasswordError, ParserException
    except ImportError as exc:  # pragma: no cover
        raise CASError("Statement parsing is not available on this server.") from exc

    try:
        data = casparser.read_cas_pdf(io.BytesIO(pdf_bytes), password, output="dict")
    except IncorrectPasswordError as exc:
        raise CASError("That password didn't open the file. For CAMS/KFintech statements it is the password you chose when requesting it; for NSDL/CDSL it is usually your PAN in capitals.") from exc
    except ParserException as exc:
        raise CASError("We couldn't read this file as a CAS statement. Try the detailed statement from CAMS or KFintech, or add your funds by name instead.") from exc
    except Exception as exc:  # noqa: BLE001 - never leak parser internals
        log.warning("CAS parse failed: %s", type(exc).__name__)
        raise CASError("We couldn't read this file. You can add your funds by name instead.") from exc

    raw: list[dict] = []
    stocks: list[dict] = []
    period = data.get("statement_period") or {}
    as_of = str(period.get("to", "") or "")

    if "folios" in data:  # CAMS / KFintech
        stype = "CAMS/KFintech"
        for folio in data.get("folios", []):
            for sch in folio.get("schemes", []):
                val = (sch.get("valuation") or {}).get("value")
                raw.append({"name": sch.get("scheme", ""), "isin": sch.get("isin"), "amfi": sch.get("amfi"), "value": val})
    else:  # NSDL / CDSL depository CAS
        stype = "NSDL/CDSL"
        for acc in data.get("accounts", []):
            for mf in acc.get("mutual_funds", []) or []:
                raw.append({"name": mf.get("name", ""), "isin": mf.get("isin"), "amfi": mf.get("amfi"), "value": mf.get("value")})
            for eq in acc.get("equities", []) or []:
                if _num(eq.get("value")) > 0:
                    stocks.append({"isin": eq.get("isin"), "name": eq.get("name", ""), "value": round(_num(eq.get("value")), 2)})

    # `data` (with investor_info, PAN, folio numbers) goes out of scope here.
    positions, unmatched = positions_from_raw(store, raw)
    if not positions and not stocks:
        raise CASError("We found no mutual fund holdings we recognise in this statement. You can add your funds by name instead.")
    for s in stocks:
        s["has_scorecard"] = bool(s.get("isin")) and s["isin"] in store.covered_isins
    return ParsedCAS(positions, unmatched, stocks, stype, as_of)
