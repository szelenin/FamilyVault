"""Immich fetch utilities for the FamilyVault understanding layer.

Provides three public functions:

  list_photo_assets(session, *, base_url=...) -> list[dict]
      Paginate POST /api/search/metadata (type=IMAGE) and return all raw asset
      dicts as delivered by Immich.

  download_preview(session, asset_id, dest_path, *, base_url=...) -> str | None
      GET the preview thumbnail for *asset_id*, write bytes to *dest_path*, and
      return the path string.  Returns None if the response is non-200 or the
      body is empty (no usable preview).

  asset_filter_fields(immich_asset_json) -> dict
      Map one Immich asset dict to the cached index columns consumed by
      index.db.upsert_asset.  Person names are intentionally omitted (FR-007):
      only person UUIDs are stored so that identity remains Immich's concern.

Design for injection: `session` is a `requests.Session`-like object (real or
mock).  No global session is held; callers supply it.
"""
import json
import os
from pathlib import Path
from typing import Union

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = os.environ.get("IMMICH_URL", "http://localhost:2283")
_DEFAULT_PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# list_photo_assets
# ---------------------------------------------------------------------------


def list_photo_assets(
    session,
    *,
    base_url: str = _DEFAULT_BASE_URL,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> list:
    """Return all IMAGE assets from Immich, paginating until exhausted.

    Args:
        session: A requests.Session-like object with a .post() method.
        base_url: Immich base URL (without trailing slash).
        page_size: Number of assets to request per page.

    Returns:
        A flat list of raw Immich asset dicts (one per asset).
    """
    url = f"{base_url}/api/search/metadata"
    assets: list = []
    page = 1

    while True:
        body = {
            "type": "IMAGE",
            "page": page,
            "size": page_size,
        }
        response = session.post(url, json=body)
        data = response.json()
        page_assets = data["assets"]["items"]
        assets.extend(page_assets)

        next_page = data["assets"].get("nextPage")
        if not next_page:
            break
        page = next_page

    return assets


# ---------------------------------------------------------------------------
# download_preview
# ---------------------------------------------------------------------------


def download_preview(
    session,
    asset_id: str,
    dest_path: Union[str, Path],
    *,
    base_url: str = _DEFAULT_BASE_URL,
) -> Union[str, None]:
    """Download the preview thumbnail for *asset_id* to *dest_path*.

    Args:
        session: A requests.Session-like object with a .get() method.
        asset_id: The Immich asset UUID.
        dest_path: Filesystem path where the preview image will be written.
        base_url: Immich base URL (without trailing slash).

    Returns:
        The absolute path string of the written file on success, or None if
        the response is non-200 or the body is empty (no usable preview).
    """
    url = f"{base_url}/api/assets/{asset_id}/thumbnail"
    response = session.get(url, params={"size": "preview"})

    if response.status_code != 200:
        return None

    content = response.content
    if not content:
        return None

    dest = Path(dest_path)
    dest.write_bytes(content)
    return str(dest)


# ---------------------------------------------------------------------------
# asset_filter_fields
# ---------------------------------------------------------------------------


def asset_filter_fields(immich_asset_json: dict) -> dict:
    """Map one raw Immich asset dict to the cached index columns.

    Column mapping:
        asset_id    ← id
        type        ← type
        taken_at    ← localDateTime (preferred) or fileCreatedAt
        lat         ← exifInfo.latitude  (None when absent)
        lon         ← exifInfo.longitude (None when absent)
        city        ← exifInfo.city      (None when absent)
        country     ← exifInfo.country   (None when absent)
        person_ids  ← JSON-encoded list of people[].id ONLY (names excluded, FR-007)
        is_favorite ← isFavorite → 1 or 0
        duration    ← parsed seconds float from "H:MM:SS.ffffff" (None for photos at 0)
        source_hash ← checksum

    Args:
        immich_asset_json: A single asset dict as returned by the Immich API.

    Returns:
        A dict keyed by index column names.
    """
    a = immich_asset_json
    exif = a.get("exifInfo") or {}
    people = a.get("people") or []

    # taken_at: prefer localDateTime, fall back to fileCreatedAt
    taken_at = a.get("localDateTime") or a.get("fileCreatedAt")

    # is_favorite: bool → 0/1 integer
    is_favorite = 1 if a.get("isFavorite") else 0

    # person_ids: JSON list of UUIDs only — never include names (FR-007)
    person_ids = json.dumps([p["id"] for p in people])

    # duration: parse "H:MM:SS.ffffff" → total seconds float, or None for photos
    duration = _parse_duration(a.get("duration"))

    return {
        "asset_id": a.get("id"),
        "type": a.get("type"),
        "taken_at": taken_at,
        "lat": exif.get("latitude"),
        "lon": exif.get("longitude"),
        "city": exif.get("city"),
        "country": exif.get("country"),
        "person_ids": person_ids,
        "is_favorite": is_favorite,
        "duration": duration,
        "source_hash": a.get("checksum"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_duration(duration_str: Union[str, None]) -> Union[float, None]:
    """Convert Immich duration string "H:MM:SS.ffffff" to total seconds.

    Returns None if the value is absent, unparseable, or zero (photos).
    Returns a positive float for actual video durations.
    """
    if not duration_str:
        return None

    try:
        # Format: "0:00:00.00000" or "1:23:45.678900"
        parts = duration_str.split(":")
        if len(parts) != 3:
            return None
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        total = hours * 3600 + minutes * 60 + seconds
        # Zero duration (photos) → None
        return total if total > 0.0 else None
    except (ValueError, IndexError):
        return None
