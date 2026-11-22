"""Spending guards for a deployment on limited (student) credits.

Three layers, all in memory and all configurable by environment variable:

1. Per-IP keys that can't be spoofed with a fake X-Forwarded-For header.
2. Daily AI budgets: a cap per visitor and a cap for the whole site. When either is used up,
   chat keeps working in its no-AI mode (verified findings + report passages), so a flood of
   requests can never turn into a bill.
3. Concurrency caps for the expensive endpoints, so one small replica is enough and the
   platform never has to scale out (more replicas = more cost).

Counters reset at midnight IST. Run one worker per replica (WEB_CONCURRENCY=1) so the counts are exact.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
from collections import defaultdict

from starlette.requests import Request

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def client_ip(request: Request) -> str:
    """The visitor's address as seen by OUR ingress.

    Cloud ingresses (Azure Container Apps, Vercel, nginx) append the real client to the RIGHT end of
    X-Forwarded-For; anything to the left was written by the client and can be faked. So the rightmost
    entry is the one to trust. Falls back to the socket address when there is no proxy.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        last = xff.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


class DailyBudget:
    def __init__(self) -> None:
        self.site_limit = _int("AI_DAILY_CALLS", 300)  # whole site, per day
        self.ip_limit = _int("AI_DAILY_CALLS_PER_IP", 25)  # one visitor, per day
        self._day = self._today()
        self._site = 0
        self._ip: dict[str, int] = defaultdict(int)

    @staticmethod
    def _today() -> dt.date:
        return dt.datetime.now(IST).date()

    def _roll(self) -> None:
        if (d := self._today()) != self._day:
            self._day, self._site = d, 0
            self._ip.clear()

    def take(self, ip: str) -> str | None:
        """Reserve one AI call. Returns None if allowed, else the reason it isn't."""
        self._roll()
        if self._site >= self.site_limit:
            return "site_budget"
        if self._ip[ip] >= self.ip_limit:
            return "ip_budget"
        self._site += 1
        self._ip[ip] += 1
        return None

    def refund(self, ip: str) -> None:
        """Give the call back when no model was actually used (cache hit, guardrail, provider down)."""
        self._roll()
        self._site = max(0, self._site - 1)
        self._ip[ip] = max(0, self._ip[ip] - 1)

    def snapshot(self) -> dict:
        self._roll()
        return {"day": self._day.isoformat(), "ai_calls_today": self._site, "ai_daily_limit": self.site_limit,
                "per_visitor_limit": self.ip_limit, "visitors_today": len(self._ip)}


budget = DailyBudget()
# How many chats may stream, and how many statements may be parsed, at the same moment on one replica.
chat_slots = asyncio.Semaphore(_int("MAX_CONCURRENT_CHATS", 6))
parse_slots = asyncio.Semaphore(_int("MAX_CONCURRENT_PARSES", 2))
