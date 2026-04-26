"""CLI entry for the Phase 1.5 audit. Runs every check, emits JSON report.

Usage:
    python3 -m scripts.phase1_audit \
        --manifest docs/architecture/google-takeout-manifest.json \
        --server http://localhost:2283 \
        --api-key-file /Users/szelenin/immich-data/api-key.txt \
        --report /Users/szelenin/immich-data/phase-1-audit-report.json
"""
from __future__ import annotations
import argparse
import dataclasses
import json
import sys
from pathlib import Path

from .checks import (
    check_album_count,
    check_album_names,
    check_dng_siblings,
    check_extension_count,
    check_total_count,
    check_year_folders_not_albums,
)
from .immich_client import ImmichClient
from .manifest import load_manifest


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--server", default="http://localhost:2283")
    p.add_argument("--api-key-file", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = args.api_key_file.read_text().strip()
    client = ImmichClient(server=args.server, api_key=api_key)
    manifest = load_manifest(args.manifest)

    results = []
    results.append(check_total_count(client, manifest))
    for ext in ("heic", "jpg", "jpeg", "png", "mp4", "mov", "dng", "nef"):
        if manifest.count_for_extension(ext) > 0:
            results.append(check_extension_count(client, manifest, ext))
    results.append(check_album_count(client, manifest))
    results.append(check_album_names(client, manifest))
    results.append(check_year_folders_not_albums(client, manifest))
    results.append(check_dng_siblings(client, manifest))

    report = {
        "manifest_path": str(args.manifest),
        "server": args.server,
        "checks": [dataclasses.asdict(r) for r in results],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
        },
    }
    args.report.write_text(json.dumps(report, indent=2, default=str))

    # Console summary
    for r in results:
        flag = "PASS" if r.passed else "FAIL"
        print(f"  [{flag}] {r.name}: {r.message}")
    print(f"\nSummary: {report['summary']['passed']}/{report['summary']['total']} passed")
    print(f"Full report: {args.report}")

    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
