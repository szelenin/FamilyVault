"""Stratified sampling for manual review."""
from __future__ import annotations
import random
from typing import Iterable, Mapping


def stratified_sample(
    rows: Iterable[Mapping],
    high_n: int = 30, med_n: int = 30, low_n: int = 30, unmatched_n: int = 30,
) -> list:
    """Pick up to N rows from each confidence bucket."""
    buckets: dict = {"high": [], "medium": [], "low": [], "unmatched": []}
    for r in rows:
        c = r.get("composite_confidence") or 0
        if c >= 0.85:
            buckets["high"].append(r)
        elif c >= 0.50:
            buckets["medium"].append(r)
        elif c > 0:
            buckets["low"].append(r)
        else:
            buckets["unmatched"].append(r)
    out: list = []
    for name, n in (("high", high_n), ("medium", med_n), ("low", low_n), ("unmatched", unmatched_n)):
        b = buckets[name]
        out.extend(random.sample(b, min(n, len(b))))
    return out
