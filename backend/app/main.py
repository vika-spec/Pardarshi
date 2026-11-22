"""Pardarshi API.

Run locally:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import datetime as _dt
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .budget import budget, chat_slots, client_ip, parse_slots
from .cas import CASError, parse_cas, positions_from_raw
from .chat import answer_stream
from .config import settings
from .data_store import DataStore
from .llm import LLMClient
from .metrics import metrics
from .portfolio import Position, analyse
from .redflag.checks import CAVEATS, CHECKS, LEVEL_POINTS, finding_level, fy_end, is_old_report
from .redflag.verify import printed_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pardarshi.api")

limiter = Limiter(key_func=client_ip, default_limits=[settings.rate_limit])
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["store"] = DataStore(settings.data_dir)
    state["llm"] = LLMClient(settings)
    log.info("AI providers: %s", [p.name for p in settings.providers] or "none (template mode)")
    from .chat import prewarm

    t = asyncio.get_running_loop().run_in_executor(None, prewarm, state["store"])  # search indexes, in the background
    yield
    t.cancel()
    await state["llm"].aclose()


app = FastAPI(title="Pardarshi API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        metrics.inc("http_500")
        log.exception("Unhandled error rid=%s path=%s", rid, request.url.path)
        return JSONResponse({"error": "Something went wrong on our side. Please try again.", "request_id": rid}, status_code=500)
    ms = (time.perf_counter() - t0) * 1000
    route = request.scope.get("route")
    name = getattr(route, "path", request.url.path)
    metrics.observe(f"http {request.method} {name}", ms)
    response.headers["x-request-id"] = rid
    response.headers["server-timing"] = f"app;dur={ms:.1f}"
    # Never log query strings or bodies: they may contain personal data.
    log.info("%s %s %d %.1fms rid=%s", request.method, name, response.status_code, ms, rid)
    return response


def store() -> DataStore:
    return state["store"]


# ------------------------------------------------------------------ helpers
def _years(age: int | None, years: float | None) -> float:
    if years:
        return max(1.0, min(50.0, years))
    if age:
        return float(max(1, min(50, settings.default_retire_age - age)))
    return 20.0


def _with_risk(result: dict, direct_stocks: list[dict] | None = None) -> dict:
    s = store()
    tops = result["exposure"]["top_stocks"]
    covered = [t for t in tops if t["has_scorecard"]]
    cards = {t["isin"]: _enrich(t["isin"], s.scorecard(t["isin"])) for t in covered if s.scorecard(t["isin"])}

    def flags_of(card: dict) -> list[dict]:
        return [
            {"id": c["id"], "title": c["title"], "severity": c["severity"], "level": c.get("level") or "moderate",
             "summary": c["summary"], "pages": sorted({e["page"] for e in c["evidence"] if e.get("verified")})}
            for c in card["checks"] if c["status"] == "flagged"
        ]

    companies = []
    for t in covered:
        card = cards.get(t["isin"])
        if not card:
            continue
        companies.append({
            "isin": t["isin"],
            "name": card["name"],
            "fy": card.get("fy", ""),
            "report_date": card.get("report_date", ""),
            "old_report": card.get("old_report", False),
            "pct_of_portfolio": t["pct_of_portfolio"],
            "rupees": t["rupees"],
            "counts": card["counts"],
            "via": [v["fund"] for v in sorted(t["via"], key=lambda v: -v["rupees"])],
            "event": s.companies.get(t["isin"], {}).get("event"),
            "flags": flags_of(card),
            "score": company_score(card),
        })
    companies.sort(key=lambda c: (-len(c["flags"]), -c["pct_of_portfolio"]))

    # Exposure to companies with at least one quote-verified warning sign, and which funds bring it in.
    total = result["total_value"] or 1.0
    flagged = [c for c in companies if c["flags"]]
    flagged_isins = {c["isin"] for c in flagged}
    by_fund: dict[str, float] = {}
    for t in tops:
        if t["isin"] in flagged_isins:
            for v in t["via"]:
                by_fund[v["fund"]] = by_fund.get(v["fund"], 0.0) + v["rupees"]
    fund_value = {f["name"]: f["value"] for f in result["funds"]}
    money_flagged = sum(c["rupees"] for c in flagged)

    result["risk"] = {
        "companies": companies[:12],
        "n_checked": len(companies),
        "n_with_flags": len(flagged),
        "n_flags": sum(len(c["flags"]) for c in companies),
        "n_not_covered": len(tops) - len(covered),
        "n_checks_each": len(CHECKS),
        "money_flagged": round(money_flagged, 2),
        "pct_flagged": round(money_flagged / total * 100, 1),
        "coverage_pct": round(sum(t["pct_of_portfolio"] for t in covered), 1),
        "top_flagged": [
            {"isin": c["isin"], "name": c["name"], "rupees": c["rupees"], "pct_of_portfolio": c["pct_of_portfolio"],
             "n_flags": len(c["flags"]), "worst": max((f["level"] for f in c["flags"]), key=lambda x: LEVEL_POINTS.get(x, 0))}
            for c in sorted(flagged, key=lambda c: -c["rupees"])[:5]
        ],
        "by_fund": sorted(
            [{"fund": f, "rupees": round(r, 2), "pct_of_fund": round(r / fund_value[f] * 100, 1) if fund_value.get(f) else None}
             for f, r in by_fund.items()],
            key=lambda x: -x["rupees"]),
        "score": portfolio_score(companies, total),
        "trust": _trust(),
    }
    result["direct_stocks"] = direct_stocks or []
    result["dataset"] = s.meta
    result["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


def company_score(card: dict) -> dict:
    """Each company starts at 100; every quote-verified warning sign subtracts 30 / 15 / 5 points
    for High / Moderate / Low. Checks that are not applicable, not found or unverified subtract nothing,
    so we also report how many checks actually had data."""
    lost = sum(LEVEL_POINTS.get(c.get("level") or "moderate", 15) for c in card["checks"] if c["status"] == "flagged")
    with_data = sum(1 for c in card["checks"] if c["status"] in ("flagged", "passed"))
    applicable = sum(1 for c in card["checks"] if c["status"] != "not_applicable")
    return {"value": max(0, 100 - lost), "checks_with_data": with_data, "checks_applicable": applicable}


def portfolio_score(companies: list[dict], total: float) -> dict | None:
    if not companies:
        return None
    weight = sum(c["rupees"] for c in companies)
    value = sum(c["score"]["value"] * c["rupees"] for c in companies) / weight if weight else 0.0
    band = "few" if value >= 85 else "some" if value >= 60 else "many"
    data = sum(c["score"]["checks_with_data"] for c in companies)
    applicable = sum(c["score"]["checks_applicable"] for c in companies)
    return {
        "value": round(value),
        "band": band,
        "coverage_pct": round(weight / (total or 1) * 100, 1),
        "n_companies": len(companies),
        "data_pct": round(data / applicable * 100) if applicable else 0,
        "lowest": [{"name": c["name"], "score": c["score"]["value"], "rupees": c["rupees"]}
                   for c in sorted(companies, key=lambda c: (c["score"]["value"], -c["rupees"]))[:3]],
        "formula": "score = Σ (company score × rupees in company) ÷ Σ rupees, over the companies we have read; "
                   "company score = 100 − 30 per High − 15 per Moderate − 5 per Low quote-verified warning sign",
        "points": LEVEL_POINTS,
    }


def _run(positions: list[Position], *, years: float, gross_return: float, unmatched=None, direct_stocks=None) -> dict:
    t0 = time.perf_counter()
    try:
        res = analyse(store(), positions, years=years, gross_return=gross_return)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    res = _with_risk(res, direct_stocks)
    res["unmatched"] = unmatched or []
    metrics.observe("analysis_ms", (time.perf_counter() - t0) * 1000)
    return res


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return {"ok": True, "schemes": len(store().funds), "scorecards": len(store().covered_isins)}


@app.get("/api/meta")
def meta():
    return {
        "dataset": store().meta,
        "ai_enabled": settings.ai_enabled,
        "ai_providers": [p.name for p in settings.providers],
        "n_schemes": len(store().funds),
        "n_companies_checked": len(store().covered_isins),
        "max_upload_mb": settings.max_upload_mb,
    }


@app.get("/api/sample")
def sample(age: int | None = None, years: float | None = None, gross_return: float | None = None):
    s = store()
    sp = json.loads((s.data_dir / "sample_portfolio.json").read_text("utf-8"))
    positions = []
    for h in sp.get("holdings", []):
        idx = s.scheme_by_id(h["scheme_id"])
        if idx is not None:
            plan = h["plan"] if h["plan"] in s.funds[idx]["plans"] else next(iter(s.funds[idx]["plans"]))
            positions.append(Position(idx, plan, float(h["value"]), "sample"))
    if not positions:  # sample file missing or stale: never fail the demo, use the first funds
        log.warning("sample_portfolio.json has no usable holdings; using the first funds in the dataset")
        for i, amount in zip(range(min(6, len(s.funds))), [180000, 150000, 90000, 120000, 75000, 60000]):
            plans = s.funds[i]["plans"]
            positions.append(Position(i, "regular" if "regular" in plans else next(iter(plans)), float(amount), "sample"))
    res = _run(positions, years=_years(age, years), gross_return=gross_return or settings.default_return)
    res["label"] = sp.get("label", "Sample portfolio")
    return res


class ManualHolding(BaseModel):
    scheme_id: str | None = None
    name: str | None = None
    plan: Literal["direct", "regular"] | None = None
    value: float = Field(gt=0, lt=1e11)


class ManualRequest(BaseModel):
    holdings: list[ManualHolding] = Field(min_length=1, max_length=60)
    age: int | None = Field(default=None, ge=16, le=90)
    years: float | None = Field(default=None, ge=1, le=50)
    gross_return: float | None = Field(default=None, ge=0.0, le=0.3)


@app.post("/api/analyze/manual")
@limiter.limit(settings.rate_limit_analyze)
def analyze_manual(request: Request, body: ManualRequest):
    s = store()
    positions: list[Position] = []
    raw: list[dict] = []
    for h in body.holdings:
        if h.scheme_id:
            idx = s.scheme_by_id(h.scheme_id)
            if idx is None:
                raw.append({"name": h.name or h.scheme_id, "value": h.value})
                continue
            plan = h.plan or "regular"
            if plan not in s.funds[idx]["plans"]:
                plan = next(iter(s.funds[idx]["plans"]))
            positions.append(Position(idx, plan, h.value, "manual"))
        else:
            raw.append({"name": h.name or "", "value": h.value})
    more, unmatched = positions_from_raw(s, raw)
    return _run(positions + more, years=_years(body.age, body.years), gross_return=body.gross_return or settings.default_return, unmatched=unmatched)


@app.post("/api/analyze/cas")
@limiter.limit(settings.rate_limit_cas)
async def analyze_cas(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(""),
    age: int | None = Form(None),
    years: float | None = Form(None),
):
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Please upload the CAS as a PDF file.")
    if parse_slots.locked():
        raise HTTPException(503, "Many statements are being read right now. Please try again in a few seconds.", headers={"Retry-After": "5"})
    try:
        async with parse_slots:  # parsing is CPU work: run it off the event loop, a couple at a time
            parsed = await asyncio.to_thread(parse_cas, store(), data, password)
    except CASError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        del data  # drop the statement bytes as soon as we can
    if not parsed.positions:
        raise HTTPException(422, "We found shares but no mutual funds we recognise. You can add your funds by name instead.")
    res = _run(parsed.positions, years=_years(age, years), gross_return=settings.default_return, unmatched=parsed.unmatched, direct_stocks=parsed.direct_stocks)
    res["statement"] = {"type": parsed.statement_type, "as_of": parsed.as_of}
    return res


@app.get("/api/funds/search")
def funds_search(q: str = Query(..., min_length=2, max_length=80)):
    return {"results": store().search_funds(q)}


@app.get("/api/companies/{isin}/scorecard")
def scorecard(isin: str):
    s = store()
    card = s.scorecard(isin)
    if not card:
        raise HTTPException(404, "We have not checked this company's annual report yet.")
    return _enrich(isin, card)


def _enrich(isin: str, card: dict) -> dict:
    """Add what older scorecards lack: printed page numbers, caveats, and where the report came from."""
    if card.get("_enriched"):
        return card
    pages = store().pages(isin)
    comp = store().companies.get(isin, {})
    card["old_report"] = is_old_report(card.get("fy", ""))
    for chk in card["checks"]:
        chk.update({k: v for k, v in CAVEATS.get(chk["id"], {}).items()})
        if chk["status"] == "flagged" and not chk.get("level"):
            chk["level"] = finding_level(chk["id"], chk.get("severity", "medium"), chk.get("derived"))
        for e in chk.get("evidence", []):
            if e.get("printed_page") is None and pages:
                e["printed_page"] = printed_page(pages, e["page"])
    card["source_url"] = comp.get("source_url", "")
    card["sector"] = comp.get("sector", "")
    card["_enriched"] = True
    return card


@app.get("/api/companies/{isin}/timeline")
def timeline(isin: str):
    """The seven checks across financial years, oldest first, with a trend per check."""
    s = store()
    cur = s.scorecard(isin)
    if not cur:
        raise HTTPException(404, "We have not checked this company's annual report yet.")
    cards = {c.get("fy") or "?": c for c in s.history(isin)}
    cards[cur.get("fy") or "latest"] = cur
    years = sorted(cards, key=lambda fy: fy_end(fy) or _dt.date.max)
    rank = {"passed": 0, "flagged": 1}
    rows, worse, better = [], 0, 0
    for chk in CHECKS:
        cells = []
        for fy in years:
            c = next((x for x in cards[fy]["checks"] if x["id"] == chk.id), None)
            st = c["status"] if c else "not_found"
            lvl = (c.get("level") or finding_level(chk.id, chk.severity, c.get("derived"))) if c and st == "flagged" else None
            cells.append({"fy": fy, "status": st, "level": lvl})
        known = [x for x in cells if x["status"] in rank]
        trend = "same"
        if len(known) >= 2:
            a, b = known[-2], known[-1]
            if rank[b["status"]] > rank[a["status"]] or (b["status"] == a["status"] == "flagged"
                                                          and LEVEL_POINTS.get(b["level"] or "", 0) > LEVEL_POINTS.get(a["level"] or "", 0)):
                trend = "worse"
            elif rank[b["status"]] < rank[a["status"]] or (b["status"] == a["status"] == "flagged"
                                                            and LEVEL_POINTS.get(b["level"] or "", 0) < LEVEL_POINTS.get(a["level"] or "", 0)):
                trend = "better"
        else:
            trend = "unknown"
        worse += trend == "worse"
        better += trend == "better"
        rows.append({"id": chk.id, "title": chk.title, "cells": cells, "trend": trend})
    return {"isin": isin, "name": cur["name"], "years": years, "checks": rows,
            "summary": {"worse": worse, "better": better, "years": len(years)},
            "scores": [{"fy": fy, "score": company_score(cards[fy])["value"]} for fy in years]}


@app.get("/api/companies/{isin}/pages/{page}")
def page_text(isin: str, page: int):
    pages = store().pages(isin)
    if page not in pages:
        raise HTTPException(404, "Page not found.")
    return {"isin": isin, "page": page, "printed_page": printed_page(pages, page), "n_pages": len(pages), "text": pages[page]}


@app.get("/api/reports/{isin}.pdf")
def report_pdf(isin: str):
    if not isin.replace("_", "").isalnum():
        raise HTTPException(400, "Bad identifier.")
    p = store().data_dir / "reports" / f"{isin}.pdf"
    if p.exists():
        return FileResponse(p, media_type="application/pdf")
    src = store().companies.get(isin, {}).get("source_url", "")
    if src.startswith(("https://", "http://")):
        return RedirectResponse(src, status_code=307)  # big real PDFs aren't shipped; send users to the official copy
    raise HTTPException(404, "Report not available.")


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    isins: list[str] = Field(default_factory=list, max_length=20)
    portfolio: dict | None = None
    lang: Literal["en", "hi"] = "en"


@app.post("/api/chat")
@limiter.limit(settings.rate_limit_chat)
async def chat(request: Request, body: ChatRequest):
    if chat_slots.locked():
        raise HTTPException(503, "The assistant is busy right now. Please try again in a few seconds.", headers={"Retry-After": "5"})
    ip = client_ip(request)

    async def gen():
        async with chat_slots:
            async for chunk in answer_stream(store(), state["llm"], body.question, isins=body.isins,
                                             portfolio=body.portfolio, lang=body.lang, ip=ip):
                yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/methodology")
def methodology():
    return {
        "checks": [{"id": c.id, "kind": c.kind, "severity": c.severity, "title": c.title, "what": c.what, "rule": c.rule} for c in CHECKS],
        "formulas": {
            "exposure": "exposure(stock) = Σ over funds of (your value in fund × fund's weight in stock)",
            "overlap": "overlap(A,B) = Σ over stocks of min(wA, wB), weights normalised to each fund's equity book",
            "effective_funds": "1 / (vᵀ O v), v = share of your money in each fund, O = overlap matrix with 1 on the diagonal",
            "cost": "loss = V(1 + r − TER_direct)^n − V(1 + r − TER_regular)^n",
        },
        "principles": [
            "Numbers are calculated by code. The AI only explains and reads text.",
            "A red flag is shown only if its quote was found on the cited page.",
            "A red flag is a reason to look closer, not proof of wrongdoing.",
            "For banks, lenders and insurers, the cash-vs-profit, receivables and contingent-liability checks are marked Not applicable: they are built for ordinary businesses and would give false alarms.",
            "Your statement is read in memory and never stored. Personal details are removed before anything else sees the data.",
            "This is an educational tool, not investment advice.",
        ],
        "dataset": store().meta,
        "ai_providers": [p.name for p in settings.providers],
        "ai_pipeline": [
            {"step": "Read", "who": "code", "text": "Every page is read and kept with its PDF and printed page number. Tables are also rebuilt row by row from word positions, so each label stays next to its figures (plain PDF text splits them apart)."},
            {"step": "Find", "who": "code", "text": "For each of the 7 checks, a search (BM25, optional dense embeddings and a reranker) picks the 6–10 most relevant passages out of 300–700 pages."},
            {"step": "Extract", "who": "AI", "text": "An LLM (Groq gpt-oss-120b, or Gemini Flash-Lite as fallback) reads only those passages with check-specific guidance and returns figures or a verdict, each with an exact quote and page, as JSON."},
            {"step": "Decide", "who": "code", "text": "Code applies the published rule and threshold to the figures (e.g. more than 10% of promoter shares pledged). The AI never decides a warning on its own."},
            {"step": "Prove", "who": "code", "text": "Every quote is matched against the cited page (and its neighbours), with every number identical. A warning with no provable quote becomes 'Unverified' and is never shown."},
            {"step": "Second opinion", "who": "AI", "text": "A different AI model re-reads the full cited pages and must agree. If it disagrees, the finding becomes 'Models disagree' and is not shown or scored as a warning."},
            {"step": "Backup", "who": "code", "text": "If the AI is rate-limited or down, a rule-based reader fills in only what it can prove with a verified quote; results say which method was used."},
            {"step": "Explain", "who": "AI", "text": "The chat answers only from these passages and code-calculated numbers, cites [Company, p. N], and code then checks each citation and figure against the page."},
            {"step": "Measure", "who": "code", "text": "Measured stage by stage against hand labels (retrieval, cited page, final verdict), plus a fake-quote test and failure drills, published on this page."},
        ],
        "limitations": [
            "Only Indian company shares inside funds are checked. Debt, gold, overseas and fund-of-funds holdings are not.",
            "Annual reports come once a year, so a warning reflects the latest report, not this week's news.",
            "Only companies whose reports have been processed are checked; the report says how much of your money that covers.",
            "The AI can miss information that is worded unusually or buried in images. Misses show as 'Not found', never as a pass.",
            "Fund holdings are from the latest monthly disclosure and change every month.",
            "Thresholds (for example 10% pledged) are simple published rules, not a full credit analysis.",
        ],
        "accuracy": _accuracy(),
        "figures": _eval_file("figures.json"),
        "benchmark": _eval_file("benchmark.json"),
    }


@app.get("/api/cases")
def cases():
    """'Before the fall': companies with a recorded later event (collapse, fraud, default)
    and what our checks found in a report filed BEFORE that event."""
    s = store()
    out = []
    for isin, c in s.companies.items():
        ev = c.get("event")
        card = s.scorecard(isin) if ev else None
        if not card:
            continue
        flagged = [k for k in card["checks"] if k["status"] == "flagged"]
        published = c.get("published") or card.get("report_date") or ""
        out.append({
            "isin": isin, "name": card["name"], "fy": card.get("fy", ""), "event": ev,
            "published": published, "lead_months": _months_between(published, ev.get("date", "")),
            "others": [{"id": k["id"], "title": k["title"], "status": k["status"]} for k in card["checks"] if k["status"] != "flagged"],
            "counts": card["counts"], "n_checks": len(card["checks"]),
            "flags": [{"id": k["id"], "title": k["title"], "summary": k["summary"],
                       "pages": sorted({e["page"] for e in k["evidence"] if e.get("verified")})} for k in flagged],
        })
    out.sort(key=lambda x: -len(x["flags"]))
    return {"cases": out}


def _months_between(a: str, b: str) -> int | None:
    """Whole months from the report's publication to the event: how early the warning was public."""
    try:
        d1, d2 = dt.date.fromisoformat(a[:10]), dt.date.fromisoformat(b[:10])
    except ValueError:
        return None
    m = (d2.year - d1.year) * 12 + d2.month - d1.month - (d2.day < d1.day)
    return m if m >= 0 else None


def _trust() -> dict | None:
    """Headline proof numbers for the report page, from the latest benchmark/evaluation runs."""
    b, a = _eval_file("benchmark.json"), _eval_file("results.json")
    cg = (b or {}).get("citation_guard", {})
    agreed = total = 0
    for isin in store().covered_isins:
        for c in (store().scorecard(isin) or {}).get("checks", []):
            if c.get("review"):
                total += 1
                agreed += bool(c["review"].get("agree"))
    return {
        "review_agreed": agreed,
        "review_total": total,
        "fakes_tried": cg.get("tampered_quotes"),
        "fakes_rejected_pct": cg.get("tampered_rejected_pct"),
        "precision": (a or {}).get("flag_precision"),
        "recall": (a or {}).get("flag_recall"),
        "labelled": (a or {}).get("labelled_checks"),
    }


def _accuracy() -> dict | None:
    return _eval_file("results.json")


def _eval_file(name: str) -> dict | None:
    p = store().data_dir / "eval" / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except ValueError:
        return None


@app.get("/api/metrics")
def get_metrics():
    return {**metrics.snapshot(), "budget": budget.snapshot()}
