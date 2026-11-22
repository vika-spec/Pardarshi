"""LLM access with a fallback chain, circuit breakers, timeouts and a response cache.

Order of attempts = order of providers in config (e.g. Azure OpenAI -> Gemini
-> Groq -> local Ollama). A provider that fails `breaker_failures` times in a
row is skipped for `breaker_cooldown_s`. If every provider fails, callers get
LLMUnavailable and fall back to deterministic templates, so the product never
breaks because an AI API is down.
"""
from __future__ import annotations

import asyncio
import re
import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from .config import ProviderConfig, Settings
from .metrics import metrics

log = logging.getLogger("pardarshi.llm")


class LLMUnavailable(Exception):
    pass


@dataclass
class _Breaker:
    failures: int = 0
    open_until: float = 0.0


class TTLCache:
    def __init__(self, maxsize: int = 512, ttl_s: float = 3600):
        self.maxsize, self.ttl = maxsize, ttl_s
        self._d: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def get(self, key: str):
        item = self._d.get(key)
        if not item:
            return None
        ts, val = item
        if time.monotonic() - ts > self.ttl:
            self._d.pop(key, None)
            return None
        self._d.move_to_end(key)
        return val

    def set(self, key: str, val) -> None:
        self._d[key] = (time.monotonic(), val)
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self._d.popitem(last=False)


class LLMClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.rate_wait_max = 0.0  # seconds to wait on HTTP 429 before giving up on a provider (batch jobs set this)
        self.s = settings
        self.providers = list(settings.providers)
        self._breakers = {p.name: _Breaker() for p in self.providers}
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_timeout_s, connect=5.0), limits=httpx.Limits(max_connections=50))
        self.cache = TTLCache()
        self._pace: dict[str, float] = {}  # provider -> monotonic time before which a batch job should not call it

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------- internals
    def _available(self) -> list[ProviderConfig]:
        now = time.monotonic()
        return [p for p in self.providers if self._breakers[p.name].open_until <= now]

    def _ok(self, p: ProviderConfig) -> None:
        self._breakers[p.name] = _Breaker()

    def _fail(self, p: ProviderConfig, err: Exception) -> None:
        b = self._breakers[p.name]
        b.failures += 1
        metrics.inc(f"llm_fail_{p.name}")
        log.warning("LLM provider %s failed (%s): %s", p.name, b.failures, type(err).__name__)
        if b.failures >= self.s.breaker_failures:
            b.open_until = time.monotonic() + self.s.breaker_cooldown_s
            log.warning("Circuit open for %s for %.0fs", p.name, self.s.breaker_cooldown_s)

    @staticmethod
    def _gemini_body(body: dict) -> dict:
        """OpenAI-style chat body -> Gemini generateContent body."""
        system = "\n\n".join(m["content"] for m in body["messages"] if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in body["messages"] if m["role"] != "system"
        ]
        cfg: dict = {"temperature": body.get("temperature", 0.1), "maxOutputTokens": body.get("max_tokens", 1200)}
        if body.get("response_format", {}).get("type") == "json_object":
            cfg["responseMimeType"] = "application/json"
        out: dict = {"contents": contents, "generationConfig": cfg}
        if system:
            out["systemInstruction"] = {"parts": [{"text": system}]}
        return out

    @staticmethod
    def _gemini_text(data: dict) -> str:
        cands = data.get("candidates") or []
        if not cands:
            raise ValueError(f"Gemini returned no candidates: {str(data.get('promptFeedback', ''))[:200]}")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    @classmethod
    def _request(cls, p: ProviderConfig, body: dict) -> tuple[str, dict, dict]:
        if p.kind == "gemini":
            action = "streamGenerateContent?alt=sse" if body.get("stream") else "generateContent"
            url = f"{p.base_url}/models/{p.model}:{action}"
            return url, {"x-goog-api-key": p.api_key, "Content-Type": "application/json"}, cls._gemini_body(body)
        if p.kind == "azure":
            url = f"{p.base_url}/openai/deployments/{p.model}/chat/completions?api-version={p.api_version}"
            headers = {"api-key": p.api_key, "Content-Type": "application/json"}
            body = {k: v for k, v in body.items() if k != "model"}
        else:
            url = f"{p.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {p.api_key}", "Content-Type": "application/json"}
            body = {**body, "model": p.model}
            if "gpt-oss" in p.model:
                # Reasoning model: keep thinking short so it fits max_tokens and stays fast.
                body["reasoning_effort"] = "low"
                body["max_tokens"] = body.get("max_tokens", 1200) + 1024
        return url, headers, body

    # ------------------------------------------------------------- public API
    async def complete(self, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.1, max_tokens: int = 1200, cache: bool = True,
                       avoid: str | None = None) -> tuple[str, str]:
        """Return (text, provider_name). Raises LLMUnavailable if every provider fails."""
        key = hashlib.sha256(json.dumps([messages, json_mode, temperature, avoid], sort_keys=True).encode()).hexdigest()
        if cache and (hit := self.cache.get(key)):
            metrics.inc("llm_cache_hit")
            return hit  # type: ignore[return-value]
        body: dict = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        order = self._available()
        if avoid:  # e.g. a second opinion should come from a different model when one is available
            order = [p for p in order if p.name != avoid] + [p for p in order if p.name == avoid]
        for p in order:
            url, headers, b = self._request(p, body)
            waited = 0.0
            for attempt in range(6):
                if self.rate_wait_max and (gap := self._pace.get(p.name, 0) - time.monotonic()) > 0:
                    # batch jobs: wait only as long as the provider's own token budget needs, instead of a fixed pause
                    await asyncio.sleep(min(gap, self.rate_wait_max))
                t0 = time.perf_counter()
                try:
                    r = await self._client.post(url, headers=headers, json=b)
                    self._note_budget(p, r)
                    if r.status_code == 429 and self.rate_wait_max > waited:
                        # Free tiers limit tokens per minute: wait as long as the provider asks, then retry.
                        pause = min(_retry_after(r), self.rate_wait_max - waited)
                        waited += pause
                        await asyncio.sleep(pause)
                        continue
                    if r.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                        await asyncio.sleep(0.6)
                        continue
                    r.raise_for_status()
                    data = r.json()
                    text = self._gemini_text(data) if p.kind == "gemini" else (data["choices"][0]["message"]["content"] or "")
                    metrics.observe("llm_latency_ms", (time.perf_counter() - t0) * 1000)
                    metrics.inc(f"llm_ok_{p.name}")
                    self._ok(p)
                    if cache:
                        self.cache.set(key, (text, p.name))
                    return text, p.name
                except Exception as exc:  # noqa: BLE001
                    if attempt == 0 and isinstance(exc, httpx.TransportError) and not isinstance(exc, httpx.TimeoutException):
                        await asyncio.sleep(0.6)
                        continue
                    self._fail(p, exc)
                    break
        raise LLMUnavailable("All AI providers are unavailable right now.")

    def _note_budget(self, p: ProviderConfig, r: httpx.Response) -> None:
        """Read Groq/OpenAI-style rate-limit headers; if few tokens or requests remain, pace the next call."""
        try:
            tok = r.headers.get("x-ratelimit-remaining-tokens")
            req = r.headers.get("x-ratelimit-remaining-requests")
            if (tok is not None and float(tok) < 4000) or (req is not None and float(req) < 1):
                self._pace[p.name] = time.monotonic() + _retry_after(r)
        except ValueError:
            pass

    async def stream(self, messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 900) -> AsyncIterator[tuple[str, str]]:
        """Yield (token, provider_name). Falls through providers until one starts streaming."""
        body = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        for p in self._available():
            url, headers, b = self._request(p, body)
            started = False
            try:
                async with self._client.stream("POST", url, headers=headers, json=b) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            if p.kind == "gemini":
                                delta = self._gemini_text(obj) if obj.get("candidates") else ""
                            else:
                                delta = obj["choices"][0].get("delta", {}).get("content")
                        except (json.JSONDecodeError, KeyError, IndexError, ValueError):
                            continue
                        if delta:
                            started = True
                            yield delta, p.name
                self._ok(p)
                metrics.inc(f"llm_ok_{p.name}")
                return
            except Exception as exc:  # noqa: BLE001
                self._fail(p, exc)
                if started:  # can't splice two providers into one answer
                    yield "\n\n[The answer was cut short. Please ask again.]", p.name
                    return
        raise LLMUnavailable("All AI providers are unavailable right now.")


def _retry_after(r: httpx.Response) -> float:
    """Seconds to wait from Retry-After or Groq's x-ratelimit-reset-* headers (e.g. '7.66s', '1m2.5s')."""
    for h in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        v = r.headers.get(h)
        if not v:
            continue
        try:
            return max(1.0, float(v))
        except ValueError:
            m = re.fullmatch(r"(?:(\d+)m)?([\d.]+)s", v.strip())
            if m:
                return max(1.0, int(m.group(1) or 0) * 60 + float(m.group(2)))
    return 10.0


def parse_json(text: str) -> dict:
    """Tolerant JSON parse: strips code fences and trailing prose."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{") :]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(t[start : end + 1])
