"""Tiny in-process metrics: counters and latency percentiles, served at /api/metrics."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class Metrics:
    def __init__(self, window: int = 2000):
        self._lock = threading.Lock()
        self.counters: dict[str, int] = defaultdict(int)
        self.samples: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self.started = time.time()

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counters[name] += n

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self.samples[name].append(value)

    @staticmethod
    def _pct(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        i = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
        return round(s[i], 1)

    def snapshot(self) -> dict:
        with self._lock:
            lat = {k: {"count": len(v), "p50": self._pct(list(v), 0.5), "p95": self._pct(list(v), 0.95)} for k, v in self.samples.items()}
            counters = dict(self.counters)
        hits, misses = counters.get("llm_cache_hit", 0), sum(v for k, v in counters.items() if k.startswith("llm_ok_"))
        return {
            "uptime_s": round(time.time() - self.started),
            "counters": counters,
            "latency_ms": lat,
            "llm_cache_hit_rate": round(hits / (hits + misses), 3) if hits + misses else None,
        }


metrics = Metrics()
