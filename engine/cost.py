"""Cumulative cost meter (process-wide) behind GET /api/cost. Thread-safe, pure bookkeeping."""
from __future__ import annotations

import threading

from contracts.proof import Cost

_KEYS = ("ms", "tokens_in", "tokens_out", "usd", "llm_calls", "planner_calls")


class CostMeter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total = self._zero()

    @staticmethod
    def _zero() -> dict:
        d = dict.fromkeys(_KEYS, 0)
        d["ms"] = 0.0
        d["usd"] = 0.0
        d["questions"] = 0
        return d

    def reset(self) -> None:
        with self._lock:
            self.total = self._zero()

    def add(self, c: Cost) -> None:
        with self._lock:
            for k in _KEYS:
                self.total[k] += getattr(c, k)
            self.total["questions"] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.total)


METER = CostMeter()
