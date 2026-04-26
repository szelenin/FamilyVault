"""CLI entry for the Google-vs-iCloud GPS spike. Orchestrates phases A, B+C, D."""
import argparse
import sys
from pathlib import Path

DEFAULT_EXTRACTED = Path("/Volumes/HomeRAID/google-extracted/account1")
DEFAULT_ICLOUD_LIBRARY = Path("/Volumes/HomeRAID/Photos Library.photoslibrary")
DEFAULT_EXPORT_DIR = Path("/Volumes/HomeRAID/icloud-export")
DEFAULT_OUT_DIR = Path("docs/spike")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--extracted", type=Path, default=DEFAULT_EXTRACTED)
    p.add_argument("--library", type=Path, default=DEFAULT_ICLOUD_LIBRARY)
    p.add_argument("--export", type=Path, default=DEFAULT_EXPORT_DIR)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--phase", choices=["A", "BC", "D", "all"], default="all")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"spike: extracted={args.extracted} library={args.library}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
