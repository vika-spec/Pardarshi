"""API tests, including the fallback paths (no AI keys, failing provider)."""
from __future__ import annotations

import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import ProviderConfig, settings
from app.llm import LLMClient, LLMUnavailable
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"]


def test_sample_report_shape(client):
    r = client.get("/api/sample?age=30")
    assert r.status_code == 200
    d = r.json()
    assert d["overlap"]["n_funds"] == 6
    assert 1 <= d["overlap"]["effective_funds"] <= 6
    assert d["cost"]["years"] == 30
    assert d["risk"]["n_checked"] >= 1
    assert any(c["name"] == "Sample Co. Ltd" and c["flags"] for c in d["risk"]["companies"])
    assert "server-timing" in r.headers


def test_manual_by_name_and_id(client):
    r = client.post("/api/analyze/manual", json={"holdings": [
        {"scheme_id": "DEMO-LCA", "plan": "regular", "value": 50000},
        {"name": "Demo Flexi Cap Fund B Direct Growth", "value": 25000},
        {"name": "Totally Unknown Fund", "value": 1000},
    ]})
    assert r.status_code == 200
    d = r.json()
    assert d["overlap"]["n_funds"] == 2
    assert d["unmatched"][0]["name"] == "Totally Unknown Fund"


def test_manual_validation(client):
    assert client.post("/api/analyze/manual", json={"holdings": []}).status_code == 422
    assert client.post("/api/analyze/manual", json={"holdings": [{"name": "x", "value": -5}]}).status_code == 422


def test_cas_rejects_non_pdf(client):
    r = client.post("/api/analyze/cas", files={"file": ("x.pdf", io.BytesIO(b"hello"), "application/pdf")}, data={"password": "x"})
    assert r.status_code == 415


def test_cas_bad_pdf_gives_friendly_error(client):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "not a CAS")
    buf = doc.tobytes()
    r = client.post("/api/analyze/cas", files={"file": ("cas.pdf", io.BytesIO(buf), "application/pdf")}, data={"password": "ABCDE1234F"})
    assert r.status_code == 422
    assert "ABCDE1234F" not in r.text  # never echo the password/PAN


def test_scorecard_and_page(client):
    card = client.get("/api/companies/ZZDEMO000005/scorecard").json()
    flagged = [c for c in card["checks"] if c["status"] == "flagged"]
    ev = flagged[0]["evidence"][0]
    page = client.get(f"/api/companies/ZZDEMO000005/pages/{ev['page']}").json()
    assert ev["quote"].split()[0] in page["text"]
    assert client.get("/api/companies/NOPE/scorecard").status_code == 404


def test_report_pdf_served(client):
    r = client.get("/api/reports/ZZDEMO000005.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.get("/api/reports/..%2Fsecret.pdf").status_code in (400, 404)


def test_search(client):
    res = client.get("/api/funds/search?q=bluechip").json()["results"]
    assert res and res[0]["scheme_id"] == "DEMO-BCC"


def test_chat_fallback_without_ai(client):
    r = client.post("/api/chat", json={"question": "why is cash flow low?", "isins": ["ZZDEMO000005"]})
    assert r.status_code == 200
    body = r.text
    assert "event: meta" in body and '"mode": "fallback"' in body and "event: done" in body
    assert "p. " in body


def test_methodology_lists_all_rules(client):
    d = client.get("/api/methodology").json()
    assert len(d["checks"]) == 7 and all(c["rule"] for c in d["checks"])


# ---------------------------------------------------------------- LLM chain
@pytest.mark.asyncio
async def test_llm_falls_through_to_second_provider_and_opens_breaker():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.host)
        if request.url.host == "bad.example":
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    s = settings.__class__(**{**settings.__dict__, "providers": [
        ProviderConfig("bad", "https://bad.example/v1", "k", "m"),
        ProviderConfig("good", "https://good.example/v1", "k", "m"),
    ], "breaker_failures": 1})
    llm = LLMClient(s, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    text, provider = await llm.complete([{"role": "user", "content": "hi"}], cache=False)
    assert (text, provider) == ("hello", "good")
    calls.clear()
    await llm.complete([{"role": "user", "content": "again"}], cache=False)
    assert calls == ["good.example"]  # breaker skipped the failing provider
    await llm.aclose()


@pytest.mark.asyncio
async def test_llm_all_fail_raises():
    s = settings.__class__(**{**settings.__dict__, "providers": [ProviderConfig("bad", "https://bad.example/v1", "k", "m")]})
    llm = LLMClient(s, client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    with pytest.raises(LLMUnavailable):
        await llm.complete([{"role": "user", "content": "hi"}], cache=False)
    await llm.aclose()


def test_chat_fallback_leads_with_named_company_findings(client):
    r = client.post("/api/chat", json={"question": "Why is Sample Co. Ltd flagged?", "isins": ["ZZDEMO000005", "ZZDEMO000007"]})
    body = r.text
    first_token = body.split("event: token", 2)[2]
    assert "Sample Co. Ltd" in first_token and "Monsoon" not in first_token
    assert "Profit rose" in body or "Large deals" in body


def test_report_redirects_to_source_when_pdf_not_shipped(client):
    from app.main import state

    s = state["store"]
    s.companies["ZZDEMO000001"]["source_url"] = "https://example.com/northwind-ar.pdf"
    try:
        r = client.get("/api/reports/ZZDEMO000001.pdf", follow_redirects=False)
        assert r.status_code == 307 and r.headers["location"] == "https://example.com/northwind-ar.pdf"
    finally:
        s.companies["ZZDEMO000001"].pop("source_url")


@pytest.mark.asyncio
async def test_gemini_native_request_and_parse():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": "OK"}]}}]})

    s = settings.__class__(**{**settings.__dict__, "providers": [ProviderConfig("gemini", "https://generativelanguage.googleapis.com/v1beta", "AQ.test", "gemini-flash-latest", kind="gemini")]})
    llm = LLMClient(s, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    text, prov = await llm.complete([{"role": "system", "content": "be brief"}, {"role": "user", "content": "Say OK"}], json_mode=True, cache=False)
    assert (text, prov) == ("OK", "gemini")
    assert seen["url"].endswith("/models/gemini-flash-latest:generateContent") and seen["key"] == "AQ.test"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    await llm.aclose()


@pytest.mark.asyncio
async def test_gemini_native_stream():
    sse = 'data: {"candidates":[{"content":{"parts":[{"text":"Hel"}]}}]}\n\ndata: {"candidates":[{"content":{"parts":[{"text":"lo"}]}}]}\n\n'
    s = settings.__class__(**{**settings.__dict__, "providers": [ProviderConfig("gemini", "https://g/v1beta", "k", "m", kind="gemini")]})
    llm = LLMClient(s, client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=sse))))
    out = "".join([t async for t, _ in llm.stream([{"role": "user", "content": "hi"}])])
    assert out == "Hello"
    await llm.aclose()


def test_sample_survives_empty_sample_file(client):
    from app.main import state

    p = state["store"].data_dir / "sample_portfolio.json"
    original = p.read_text()
    try:
        p.write_text('{"label": "x", "holdings": []}')
        r = client.get("/api/sample")
        assert r.status_code == 200 and r.json()["overlap"]["n_funds"] >= 1
    finally:
        p.write_text(original)


def test_cases_and_lookthrough(client):
    cases = client.get("/api/cases").json()["cases"]
    assert cases and cases[0]["name"] == "Monsoon Foods Ltd" and cases[0]["event"]["date"]
    assert all(p for f in cases[0]["flags"] for p in f["pages"])
    risk = client.get("/api/sample").json()["risk"]["companies"]
    flagged = next(c for c in risk if c["flags"])
    assert flagged["via"], "flagged company should list the funds it is held through"


def test_methodology_accuracy_absent_then_present(client):
    from app.main import state

    p = state["store"].data_dir / "eval" / "results.json"
    assert client.get("/api/methodology").json()["accuracy"] is None or p.exists()
    p.parent.mkdir(exist_ok=True)
    p.write_text('{"flag_precision": 0.8, "flag_recall": 0.75, "labelled_checks": 40}')
    try:
        assert client.get("/api/methodology").json()["accuracy"]["flag_precision"] == 0.8
    finally:
        p.unlink()


def test_risk_money_coverage_and_by_fund(client):
    k = client.get("/api/sample").json()["risk"]
    assert k["money_flagged"] > 0 and 0 < k["pct_flagged"] <= 100
    assert 0 < k["coverage_pct"] <= 100 and k["pct_flagged"] <= k["coverage_pct"]
    assert k["by_fund"] and all(f["rupees"] > 0 for f in k["by_fund"])
    assert abs(sum(f["rupees"] for f in k["by_fund"]) - k["money_flagged"]) < 1.0
    m = client.get("/api/methodology").json()
    assert m["limitations"] and any("bank" in p for p in m["principles"])


def test_score_levels_and_top_flagged(client):
    k = client.get("/api/sample").json()["risk"]
    sc = k["score"]
    assert 0 <= sc["value"] <= 100 and sc["band"] in ("few", "some", "many") and "Σ" in sc["formula"]
    for c in k["companies"]:
        lost = sum(sc["points"][f["level"]] for f in c["flags"])
        assert c["score"]["value"] == max(0, 100 - lost)
        assert all(f["level"] in ("high", "moderate", "low") for f in c["flags"])
    weights = sum(c["rupees"] for c in k["companies"])
    expected = sum(c["score"]["value"] * c["rupees"] for c in k["companies"]) / weights
    assert abs(sc["value"] - expected) <= 0.5
    tf = k["top_flagged"]
    assert 1 <= len(tf) <= 5 and tf == sorted(tf, key=lambda x: -x["rupees"])


def test_timeline_and_enriched_scorecard(client):
    t = client.get("/api/companies/ZZDEMO000007/timeline").json()
    assert t["years"] == ["FY2024-25", "FY2025-26"]
    assert all(len(r["cells"]) == 2 for r in t["checks"])
    assert t["summary"]["worse"] >= 1 and t["scores"][0]["score"] > t["scores"][1]["score"]
    one = client.get("/api/companies/ZZDEMO000005/timeline").json()
    assert one["summary"]["years"] == 1 and all(r["trend"] == "unknown" for r in one["checks"])
    card = client.get("/api/companies/ZZDEMO000005/scorecard").json()
    assert "old_report" in card and all(c["level"] for c in card["checks"] if c["status"] == "flagged")
    assert all(c.get("caveat") for c in card["checks"])


@pytest.mark.asyncio
async def test_rate_limited_provider_is_waited_for_not_skipped():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"x-ratelimit-reset-tokens": "0.01s"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    s = settings.__class__(**{**settings.__dict__, "providers": [ProviderConfig("groq", "https://g.example/v1", "k", "m")]})
    llm = LLMClient(s, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    llm.rate_wait_max = 5
    import time as _t
    t0 = _t.perf_counter()
    text, prov = await llm.complete([{"role": "user", "content": "hi"}], cache=False)
    assert (text, prov) == ("ok", "groq") and len(calls) == 2 and _t.perf_counter() - t0 < 3
    await llm.aclose()


def test_chat_citations_are_checked_against_pages():
    from app.chat import check_citations
    from app.main import state

    store = state["store"] if state.get("store") else None
    if store is None:
        from app.config import settings
        from app.data_store import DataStore
        store = DataStore(settings.data_dir)
    isin = "ZZDEMO000007"
    page_text = store.pages(isin)[10]
    name = store.companies[isin]["name"]
    good = f"Promoters pledged 38.0% of their shares [{name}, p. 10]."
    bad = f"Promoters pledged 77.5% of their shares [{name}, p. 10]. Revenue fell [{name}, p. 999]."
    assert "38.0" in page_text
    r = check_citations(store, good, [isin])
    assert r == {"citations": r["citations"], "ok": 1, "total": 1}
    r = check_citations(store, bad, [isin])
    assert r["total"] == 2 and r["ok"] == 0
    assert r["citations"][0]["figures_missing"] == ["77.5"] and r["citations"][1]["page_ok"] is False


def test_chat_streams_stages_and_timing(client):
    r = client.post("/api/chat", json={"question": "What did the auditor say?", "isins": ["ZZDEMO000005"], "lang": "en"})
    assert r.status_code == 200
    assert "event: stage" in r.text and "event: timing" in r.text and '"retrieval_ms"' in r.text


def test_chat_refuses_advice_without_calling_a_model(client):
    r = client.post("/api/chat", json={"question": "Should I buy this stock?", "isins": ["ZZDEMO000005"], "lang": "en"})
    assert "event: guard" in r.text and '"mode": "guard"' in r.text and "SEBI-registered" in r.text
