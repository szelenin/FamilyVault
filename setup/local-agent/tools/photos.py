"""search_photos tool — compact Immich search for the agent."""
import os

from tools._engine import (
    search_photos as _search_photos,
    make_session as _make_session,
)

_IMMICH_URL = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
_API_KEY_FILE = os.environ.get(
    "IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt"
)


def _compact(asset: dict) -> dict:
    aid = asset.get("asset_id") or asset.get("id")
    return {
        "asset_id": aid,
        "type": asset.get("type"),
        "taken_at": asset.get("taken_at"),
        "city": asset.get("city"),
        "country": asset.get("country"),
        "description": asset.get("description"),
        "thumbnail_url": f"{_IMMICH_URL}/api/assets/{aid}/thumbnail",
    }


def search_photos(
    query: str = "",
    person: str = "",
    after: str = "",
    before: str = "",
    city: str = "",
    country: str = "",
    media_type: str = "IMAGE",
    limit: int = 30,
) -> list:
    """Search the photo/video library.

    Args:
        query: Free-text semantic query (e.g. "birthday cake").
        person: Person name to filter by.
        after: Start date YYYY-MM-DD.
        before: End date YYYY-MM-DD.
        city: City filter.
        country: Country filter.
        media_type: IMAGE or VIDEO.
        limit: Max results.

    Returns:
        List of compact asset records: asset_id, type, taken_at, city,
        country, description, thumbnail_url.
    """
    session = _make_session(_IMMICH_URL, _API_KEY_FILE)
    try:
        assets = _search_photos(
            immich_url=_IMMICH_URL,
            session=session,
            query=query or None,
            person_name=person or None,
            after=after or None,
            before=before or None,
            city=city or None,
            country=country or None,
            media_type=media_type,
            limit=limit,
        )
    except SystemExit as e:  # underlying script calls sys.exit(3) on errors
        raise RuntimeError(f"search failed (exit {e.code})")
    return [_compact(a) for a in assets]
