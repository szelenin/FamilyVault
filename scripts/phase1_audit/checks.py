"""Individual audit checks. Each returns a CheckResult."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .immich_client import ImmichClient
from .manifest import Manifest


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: str = ""


def _within_tolerance(actual: int, expected: int, tolerance: float) -> bool:
    """Return True if actual is within (expected * tolerance) of expected, with a min slack of 1."""
    if expected == 0:
        return actual == 0
    slack = max(1, int(expected * tolerance))
    return abs(actual - expected) <= slack


def check_total_count(client: ImmichClient, manifest: Manifest, tolerance: float = 0.01) -> CheckResult:
    """Verify Immich's photos+videos count matches manifest's expected media count within tolerance."""
    stats = client.get_statistics()
    actual = int(stats.get("photos", 0)) + int(stats.get("videos", 0))
    expected = manifest.expected_media_count()
    passed = _within_tolerance(actual, expected, tolerance)
    return CheckResult(
        name="total_count",
        passed=passed,
        expected=expected,
        actual=actual,
        message=f"Immich={actual} expected={expected} (tolerance ±{tolerance:.0%})",
    )


def check_extension_count(client: ImmichClient, manifest: Manifest,
                          ext: str, tolerance: float = 0.01) -> CheckResult:
    """Verify Immich's count of assets ending in .<ext> matches manifest within tolerance."""
    expected = manifest.count_for_extension(ext)
    items = client.search_metadata({"originalFileName": f".{ext.lower()}"})
    actual = len(items)
    passed = _within_tolerance(actual, expected, tolerance)
    return CheckResult(
        name=f"extension_count_{ext.lower()}",
        passed=passed,
        expected=expected,
        actual=actual,
        message=f".{ext} Immich={actual} expected={expected}",
    )
