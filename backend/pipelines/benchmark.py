"""Measure what judges ask about: is the AI honest, does it fail safely, is it fast?

    python -m pipelines.benchmark            # offline checks only (no API keys used)
    python -m pipelines.benchmark --live     # also time your real AI providers (a few small calls)

Writes DATA_DIR/eval/benchmark.json, which the Methodology page shows.

1. Citation guard   every quote in the scorecards is re-checked against its page (should pass), then
                    tampered three ways (a changed number, a sentence moved to the wrong page, an
                    invented sentence) and checked again (should all be rejected).
2. Fallbacks        fake providers that fail in different ways; the chain must move on, and the
                    chat must still answer from saved findings when every provider is down.
3. Speed            in-process timing of the main API calls (no network), p50 / p95.
4. Live AI (opt.)   time to first word and total time for each configured provider.
5. Coverage         how many companies have scorecards, and how their checks came out.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config import ProviderConfig, settings  # noqa: E402
from app.data_store import DataStore  # noqa: E402
from app.llm import LLMClient, LLMUnavailable  # noqa: E402
from app.redflag.verify import verify_quote  # noqa: E402

INVENTED = [
    "The statutory auditor has resigned with immediate effect citing non-cooperation by management.",
    "Promoters have pledged 78.4% of their shareholding with non-banking lenders as of 31 March.",
    "Related party transactions amounting to Rs 4,812 crore were not approved by the audit committee.",
]


def _pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))], 2)


# --------------------------------------------------------------------- 1
def citation_guard(store: DataStore, seed: int = 7) -> dict:
    rng = random.Random(seed)
    genuine = genuine_ok = 0
    tampered = {"changed_number": [0, 0], "wrong_page": [0, 0], "invented": [0, 0]}  # [tried, rejected]
    for isin in sorted(store.covered_isins):
        card = store.scorecard(isin)
        pages = store.pages(isin)
        if not card or not pages:
            continue
        for chk in card.get("checks", []):
            for ev in chk.get("evidence", []):
                if not ev.get("verified"):
                    continue
                q, pg = ev["quote"], ev["page"]
                genuine += 1
                genuine_ok += verify_quote(q, pg, pages)[0]
                nums = list(re.finditer(r"\d[\d,]*(?:\.\d+)?", q))
                if nums:
                    m = rng.choice(nums)
                    digits = m.group(0)
                    i = next(k for k, ch in enumerate(digits) if ch.isdigit())
                    new = digits[:i] + str((int(digits[i]) + rng.randint(1, 8)) % 10) + digits[i + 1 :]
                    t = tampered["changed_number"]
                    t[0] += 1
                    t[1] += not verify_quote(q[: m.start()] + new + q[m.end() :], pg, pages)[0]
                far = [p for p in pages if abs(p - pg) > 2]
                if far:
                    t = tampered["wrong_page"]
                    t[0] += 1
                    t[1] += not verify_quote(q, rng.choice(far), pages)[0]
                t = tampered["invented"]
                t[0] += 1
                t[1] += not verify_quote(rng.choice(INVENTED), pg, pages)[0]
    tried = sum(v[0] for v in tampered.values())
    rejected = sum(v[1] for v in tampered.values())
    return {
        "genuine_quotes": genuine,
        "genuine_accepted_pct": round(100 * genuine_ok / genuine, 1) if genuine else None,
        "tampered_quotes": tried,
        "tampered_rejected_pct": round(100 * rejected / tried, 1) if tried else None,
        "by_kind": {k: {"tried": v[0], "rejected": v[1]} for k, v in tampered.items()},
    }


# --------------------------------------------------------------------- 2
async def fallbacks() -> list[dict]:
    def chain(*names: str) -> LLMClient:
        provs = [ProviderConfig(n, f"https://{n}.example/v1", "k", "m") for n in names]
        s = settings.__class__(**{**settings.__dict__, "providers": provs, "breaker_failures": 1})

        def handler(req: httpx.Request) -> httpx.Response:
            host = req.url.host.split(".")[0]
            if host == "down":
                return httpx.Response(503)
            if host == "limited":
                return httpx.Response(429)
            if host == "garbage":
                return httpx.Response(200, text="<html>not json</html>")
            if host == "slow":
                raise httpx.ReadTimeout("timed out", request=req)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        return LLMClient(s, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    cases = [
        ("Provider overloaded (503) -> next one answers", ("down", "good"), "good"),
        ("Rate limited (429) -> next one answers", ("limited", "good"), "good"),
        ("Timeout -> next one answers", ("slow", "good"), "good"),
        ("Broken response -> next one answers", ("garbage", "good"), "good"),
        ("Three failures in a row -> fourth answers", ("down", "slow", "limited", "good"), "good"),
        ("Every provider down -> app uses saved findings", ("down", "slow"), None),
    ]
    out = []
    for label, names, expect in cases:
        llm = chain(*names)
        t0 = time.perf_counter()
        try:
            _, used = await llm.complete([{"role": "user", "content": "hi"}], cache=False)
        except LLMUnavailable:
            used = None
        finally:
            await llm.aclose()
        out.append({"case": label, "expected": expect or "fallback", "got": used or "fallback",
                    "ok": used == expect, "ms": round(1000 * (time.perf_counter() - t0), 1)})
    return out


def chat_without_ai() -> dict:
    """With no AI at all, /api/chat must still stream an answer built from saved findings."""
    from fastapi.testclient import TestClient

    import app.main as main

    saved = main.settings
    main.settings = settings.__class__(**{**settings.__dict__, "providers": []})
    try:
        with TestClient(main.app) as c:
            isins = sorted(main.state["store"].covered_isins)[:3]
            r = c.post("/api/chat", json={"question": "What are the warning signs?", "isins": isins})
            body = r.text
    finally:
        main.settings = saved
    return {"status": r.status_code, "streamed_answer": "event: token" in body, "mode_fallback": '"mode": "fallback"' in body}


# --------------------------------------------------------------------- 3
def api_speed(n: int = 100) -> dict:
    from fastapi.testclient import TestClient

    import app.main as main

    out = {}
    main.limiter.enabled = False  # measure the work, not the rate limiter
    with TestClient(main.app) as c:
        funds = main.state["store"].funds[:5]
        manual = {"holdings": [{"scheme_id": f["scheme_id"], "plan": next(iter(f["plans"])), "value": 100000} for f in funds]}
        calls = {
            "sample report (/api/sample)": lambda: c.get("/api/sample?age=30"),
            "5-fund analysis (/api/analyze/manual)": lambda: c.post("/api/analyze/manual", json=manual),
            "fund search (/api/funds/search)": lambda: c.get("/api/funds/search?q=flexi"),
        }
        for name, fn in calls.items():
            fn()  # warm-up
            ts = []
            for _ in range(n):
                t0 = time.perf_counter()
                r = fn()
                ts.append(1000 * (time.perf_counter() - t0))
                if r.status_code != 200:
                    raise RuntimeError(f"{name} returned {r.status_code}")
            out[name] = {"p50_ms": _pct(ts, 0.5), "p95_ms": _pct(ts, 0.95), "n": n}
    return out


# --------------------------------------------------------------------- 4
async def live_ai(runs: int = 3) -> list[dict]:
    out = []
    for p in settings.providers:
        s = settings.__class__(**{**settings.__dict__, "providers": [p]})
        llm = LLMClient(s)
        first, total, errors = [], [], 0
        for i in range(runs):
            t0 = time.perf_counter()
            t_first = None
            try:
                async for tok, _ in llm.stream([{"role": "user", "content": f"In one sentence, what is a mutual fund expense ratio? ({i})"}], max_tokens=120):
                    if t_first is None and tok.strip():
                        t_first = time.perf_counter() - t0
            except Exception:  # noqa: BLE001
                errors += 1
                continue
            first.append(1000 * (t_first or (time.perf_counter() - t0)))
            total.append(1000 * (time.perf_counter() - t0))
        await llm.aclose()
        out.append({"provider": p.name, "model": p.model, "runs": runs, "errors": errors,
                    "first_word_ms": round(statistics.median(first)) if first else None,
                    "total_ms": round(statistics.median(total)) if total else None})
    return out


# --------------------------------------------------------------------- 5
def coverage(store: DataStore) -> dict:
    status: dict[str, int] = {}
    method: dict[str, int] = {}
    ev_total = ev_ok = 0
    for isin in store.covered_isins:
        for chk in (store.scorecard(isin) or {}).get("checks", []):
            status[chk.get("status") or "unknown"] = status.get(chk.get("status") or "unknown", 0) + 1
            method[chk.get("method") or "unknown"] = method.get(chk.get("method") or "unknown", 0) + 1
            for ev in chk.get("evidence", []):
                ev_total += 1
                ev_ok += bool(ev.get("verified"))
    return {"companies_checked": len(store.covered_isins), "companies_held": len(store.companies),
            "checks_by_status": status, "checks_by_method": method,
            "evidence_verified_pct": round(100 * ev_ok / ev_total, 1) if ev_total else None}


def run(live: bool = False, n: int = 100) -> dict:
    import logging

    logging.disable(logging.INFO)  # keep the per-request log lines out of the report
    store = DataStore(settings.data_dir)
    res = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "citation_guard": citation_guard(store),
        "fallbacks": asyncio.run(fallbacks()),
        "chat_without_ai": chat_without_ai(),
        "api_speed": api_speed(n),
        "coverage": coverage(store),
        "live_ai": asyncio.run(live_ai()) if live else None,
    }
    dest = settings.data_dir / "eval" / "benchmark.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=1), "utf-8")
    return res


def _print(res: dict) -> None:
    cg = res["citation_guard"]
    print("\n1. Citation guard")
    print(f"   genuine quotes accepted : {cg['genuine_accepted_pct']}% of {cg['genuine_quotes']}")
    print(f"   tampered quotes rejected: {cg['tampered_rejected_pct']}% of {cg['tampered_quotes']}  {cg['by_kind']}")
    print("\n2. Fallbacks")
    for f in res["fallbacks"]:
        print(f"   {'PASS' if f['ok'] else 'FAIL'}  {f['case']}  ({f['got']}, {f['ms']} ms)")
    c = res["chat_without_ai"]
    print(f"   {'PASS' if c['streamed_answer'] and c['mode_fallback'] else 'FAIL'}  Chat answers with no AI at all")
    print("\n3. API speed (in-process)")
    for k, v in res["api_speed"].items():
        print(f"   {k}: p50 {v['p50_ms']} ms, p95 {v['p95_ms']} ms")
    cov = res["coverage"]
    print(f"\n5. Coverage: {cov['companies_checked']} of {cov['companies_held']} companies checked; {cov['checks_by_status']}; "
          f"evidence verified {cov['evidence_verified_pct']}%")
    if res["live_ai"]:
        print("\n4. Live AI")
        for r in res["live_ai"]:
            print(f"   {r['provider']} ({r['model']}): first word {r['first_word_ms']} ms, full answer {r['total_ms']} ms, errors {r['errors']}/{r['runs']}")
    print(f"\nSaved to {settings.data_dir / 'eval' / 'benchmark.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also time the configured AI providers (makes a few small calls)")
    ap.add_argument("-n", type=int, default=100, help="requests per API timing")
    a = ap.parse_args()
    _print(run(live=a.live, n=a.n))
