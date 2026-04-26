"""Individual audit checks. Each returns a CheckResult."""
from __future__ import annotations
import os
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


def check_album_count(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """Immich's album count must equal the manifest's user_album_count exactly."""
    albums = client.list_albums()
    actual = len(albums)
    expected = manifest.user_album_count
    return CheckResult(
        name="album_count",
        passed=(actual == expected),
        expected=expected,
        actual=actual,
        message=f"Immich albums={actual} manifest expects={expected}",
    )


def check_album_names(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """Every album in the manifest must exist in Immich (extras allowed)."""
    immich_names = {a.get("albumName", "") for a in client.list_albums()}
    missing = [name for name in manifest.user_albums if name not in immich_names]
    return CheckResult(
        name="album_names",
        passed=(len(missing) == 0),
        expected=list(manifest.user_albums),
        actual=sorted(immich_names),
        message=("all manifest albums present" if not missing
                 else f"missing albums: {missing[:5]}"),
    )


def check_year_folders_not_albums(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """No 'Photos from YYYY' folder name should appear as an Immich album."""
    immich_names = [a.get("albumName", "") for a in client.list_albums()]
    leaked = [n for n in immich_names if n.startswith("Photos from ") and n[12:].isdigit()]
    return CheckResult(
        name="year_folders_not_albums",
        passed=(len(leaked) == 0),
        expected=[],
        actual=leaked,
        message=("no year folders leaked as albums" if not leaked
                 else f"year folders found as albums: {leaked}"),
    )


def check_dng_siblings(client: ImmichClient, manifest: Manifest) -> CheckResult:
    """For each DNG in Immich, check if a HEIC/JPG sibling (same basename) exists.

    This check always 'passes' — its purpose is to populate buckets so the user can
    decide what to do with DNG-with-sibling vs DNG-only assets.
    """
    dngs = client.search_metadata({"originalFileName": ".dng"})
    dng_total = len(dngs)
    if dng_total == 0:
        return CheckResult(
            name="dng_siblings",
            passed=True,
            expected={"dng_total": manifest.count_for_extension("dng")},
            actual={"dng_total": 0, "with_sibling": 0, "without_sibling": 0,
                    "with_sibling_files": [], "without_sibling_files": []},
            message="no DNG assets in Immich; nothing to bucket",
        )

    sibling_exts = {"heic", "jpg", "jpeg", "png"}
    with_sibling: list[str] = []
    without_sibling: list[str] = []
    for dng in dngs:
        full = dng.get("originalFileName", "")
        base = os.path.splitext(full)[0]
        # Search by basename — one call covers all sibling extensions
        results = client.search_metadata({"originalFileName": base})
        found = False
        for r in results:
            rname = r.get("originalFileName", "")
            rext = os.path.splitext(rname)[1].lstrip(".").lower()
            if (rname.lower() != full.lower()
                    and rname.lower().startswith(base.lower() + ".")
                    and rext in sibling_exts):
                found = True
                break
        (with_sibling if found else without_sibling).append(full)

    return CheckResult(
        name="dng_siblings",
        passed=True,
        expected={"dng_total": manifest.count_for_extension("dng")},
        actual={
            "dng_total": dng_total,
            "with_sibling": len(with_sibling),
            "without_sibling": len(without_sibling),
            "with_sibling_files": with_sibling[:50],
            "without_sibling_files": without_sibling[:50],
        },
        message=f"DNG buckets — with_sibling={len(with_sibling)} without_sibling={len(without_sibling)}",
    )
