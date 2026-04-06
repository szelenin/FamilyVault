#!/usr/bin/env python3
"""
search-photos.py — Search Immich for assets matching criteria.

Usage:
  python3 search-photos.py [--query QUERY] [--person NAME]
                           [--after YYYY-MM-DD] [--before YYYY-MM-DD]
                           [--city CITY] [--country COUNTRY]
                           [--type IMAGE|VIDEO] [--limit N]
                           [--format json|ids]

Exit codes:
  0 — results found, JSON array printed to stdout
  2 — no results found, empty array printed to stdout
  3 — error (missing dependency, API unreachable), message on stderr
"""
import argparse
import json
import os
import sys
from typing import Optional
import requests


def get_api_key(api_key_file: str) -> str:
    """Read API key from file."""
    try:
        with open(api_key_file) as f:
            return f.read().strip()
    except OSError as e:
        print(f"ERROR: Cannot read API key from {api_key_file}: {e}", file=sys.stderr)
        sys.exit(3)


def make_session(immich_url: str, api_key_file: str) -> requests.Session:
    """Create authenticated requests session."""
    session = requests.Session()
    api_key = get_api_key(api_key_file)
    session.headers.update({
        "x-api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    return session


def person_name_to_id(session: requests.Session, name: str, immich_url: str) -> Optional[str]:
    """Look up person ID by name (case-insensitive)."""
    try:
        resp = session.get(f"{immich_url}/api/people", params={"withHidden": "false"})
        resp.raise_for_status()
        data = resp.json()
        name_lower = name.lower()
        for person in data.get("people", []):
            if person.get("name", "").lower() == name_lower:
                return person["id"]
        return None
    except requests.RequestException as e:
        print(f"ERROR: Cannot reach Immich at {immich_url}: {e}", file=sys.stderr)
        sys.exit(3)


def build_smart_search_request(
    query: str,
    person_id: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    media_type: str = "IMAGE",
    limit: int = 30,
) -> dict:
    """Build request body for POST /api/search/smart."""
    body: dict = {
        "query": query,
        "type": media_type,
        "size": limit,
    }
    if person_id:
        body["personIds"] = [person_id]
    if after:
        body["takenAfter"] = f"{after}T00:00:00.000Z"
    if before:
        body["takenBefore"] = f"{before}T23:59:59.999Z"
    return body


def build_metadata_search_request(
    after: Optional[str] = None,
    before: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    person_id: Optional[str] = None,
    media_type: str = "IMAGE",
    limit: int = 30,
) -> dict:
    """Build request body for POST /api/search/metadata."""
    body: dict = {
        "type": media_type,
        "size": limit,
    }
    if after:
        body["takenAfter"] = f"{after}T00:00:00.000Z"
    if before:
        body["takenBefore"] = f"{before}T23:59:59.999Z"
    if city:
        body["city"] = city
    if country:
        body["country"] = country
    if person_id:
        body["personIds"] = [person_id]
    return body


def parse_asset_response(data: dict, city_hint: Optional[str] = None,
                         country_hint: Optional[str] = None) -> list:
    """Parse Immich search response into list of asset dicts.

    Note: /api/search/smart does not return exifInfo. City/country will be
    null for smart search results unless city_hint/country_hint are supplied
    (from the search filter used).
    """
    items = data.get("assets", {}).get("items", [])
    result = []
    for item in items:
        exif = item.get("exifInfo") or {}
        result.append({
            "id": item.get("id"),
            "type": item.get("type"),
            "filename": item.get("originalFileName"),
            "mime_type": item.get("originalMimeType"),
            "taken_at": item.get("localDateTime") or item.get("fileCreatedAt"),
            "city": exif.get("city") or city_hint,
            "country": exif.get("country") or country_hint,
            "description": exif.get("description"),
        })
    return result


def search_photos(
    immich_url: str,
    session: requests.Session,
    query: Optional[str] = None,
    person_name: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    media_type: str = "IMAGE",
    limit: int = 30,
) -> list:
    """Search Immich and return list of matching assets.

    Strategy:
    - If city/country filters given: use metadata search (supports location filters).
      If query also given: run smart search in parallel and intersect by asset ID.
    - If only query: use smart search.
    """
    person_id = None
    if person_name:
        person_id = person_name_to_id(session, person_name, immich_url)

    has_location_filter = bool(city or country)

    try:
        if has_location_filter:
            # Metadata search respects city/country filters
            body = build_metadata_search_request(
                after=after,
                before=before,
                city=city,
                country=country,
                person_id=person_id,
                media_type=media_type,
                limit=limit,
            )
            resp = session.post(f"{immich_url}/api/search/metadata", json=body)
            resp.raise_for_status()
            assets = parse_asset_response(resp.json())

            # If query also provided, re-rank by running smart search and
            # boosting assets that appear in both result sets
            if query and assets:
                smart_body = build_smart_search_request(
                    query=query,
                    person_id=person_id,
                    after=after,
                    before=before,
                    media_type=media_type,
                    limit=limit * 2,
                )
                smart_resp = session.post(f"{immich_url}/api/search/smart", json=smart_body)
                smart_resp.raise_for_status()
                smart_ids = {a["id"] for a in parse_asset_response(smart_resp.json())}
                # Put assets that appear in smart results first
                assets.sort(key=lambda a: (0 if a["id"] in smart_ids else 1, a.get("taken_at") or ""))

        elif query:
            body = build_smart_search_request(
                query=query,
                person_id=person_id,
                after=after,
                before=before,
                media_type=media_type,
                limit=limit,
            )
            resp = session.post(f"{immich_url}/api/search/smart", json=body)
            resp.raise_for_status()
            assets = parse_asset_response(resp.json())

        else:
            # No query and no location — metadata search with whatever filters we have
            body = build_metadata_search_request(
                after=after,
                before=before,
                person_id=person_id,
                media_type=media_type,
                limit=limit,
            )
            resp = session.post(f"{immich_url}/api/search/metadata", json=body)
            resp.raise_for_status()
            assets = parse_asset_response(resp.json())

    except requests.RequestException as e:
        print(f"ERROR: Search failed: {e}", file=sys.stderr)
        sys.exit(3)

    return assets


def main():
    parser = argparse.ArgumentParser(description="Search Immich for photos/videos")
    parser.add_argument("--query", help="Semantic search query")
    parser.add_argument("--person", help="Person name to filter by")
    parser.add_argument("--after", help="Start date YYYY-MM-DD")
    parser.add_argument("--before", help="End date YYYY-MM-DD")
    parser.add_argument("--city", help="City filter")
    parser.add_argument("--country", help="Country filter")
    parser.add_argument("--type", choices=["IMAGE", "VIDEO"], default="IMAGE",
                        dest="media_type", help="Asset type")
    parser.add_argument("--limit", type=int, default=30, help="Max results")
    parser.add_argument("--format", choices=["json", "ids"], default="json",
                        dest="output_format", help="Output format")
    args = parser.parse_args()

    immich_url = os.environ.get("IMMICH_URL", "http://immich-immich-server-1.orb.local")
    api_key_file = os.environ.get("IMMICH_API_KEY_FILE", "/Volumes/HomeRAID/immich/api-key.txt")

    session = make_session(immich_url, api_key_file)
    assets = search_photos(
        immich_url=immich_url,
        session=session,
        query=args.query,
        person_name=args.person,
        after=args.after,
        before=args.before,
        city=args.city,
        country=args.country,
        media_type=args.media_type,
        limit=args.limit,
    )

    if not assets:
        print("[]")
        sys.exit(2)

    if args.output_format == "ids":
        print(json.dumps([a["id"] for a in assets], indent=2))
    else:
        print(json.dumps(assets, indent=2))


if __name__ == "__main__":
    main()
