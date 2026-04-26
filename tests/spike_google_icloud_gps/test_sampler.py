"""Tests for sampler.stratified_sample."""
from __future__ import annotations
import random

from scripts.spike_google_icloud_gps.sampler import stratified_sample


def _row(conf: float) -> dict:
    return {"composite_confidence": conf, "icloud_uuid": "x" if conf > 0 else None}


def test_stratified_sample_selects_buckets():
    random.seed(0)
    rows = (
        [_row(0.95) for _ in range(100)]
        + [_row(0.65) for _ in range(50)]
        + [_row(0.20) for _ in range(40)]
        + [_row(0.0) for _ in range(60)]
    )
    sampled = stratified_sample(rows, high_n=30, med_n=30, low_n=30, unmatched_n=30)
    bucket_counts = {"high": 0, "medium": 0, "low": 0, "unmatched": 0}
    for r in sampled:
        c = r["composite_confidence"]
        if c >= 0.85:
            bucket_counts["high"] += 1
        elif c >= 0.50:
            bucket_counts["medium"] += 1
        elif c > 0:
            bucket_counts["low"] += 1
        else:
            bucket_counts["unmatched"] += 1
    assert bucket_counts == {"high": 30, "medium": 30, "low": 30, "unmatched": 30}


def test_stratified_sample_respects_small_buckets():
    rows = [_row(0.95)] * 5 + [_row(0.0)] * 5
    sampled = stratified_sample(rows, high_n=30, med_n=30, low_n=30, unmatched_n=30)
    assert len(sampled) == 10
