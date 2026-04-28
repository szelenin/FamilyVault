"""Thin wrapper around the Immich REST API for the audit."""
from __future__ import annotations
from typing import Any, Mapping
import requests


class ImmichClient:
    """Minimal Immich REST client. Only methods the audit needs."""

    def __init__(self, server: str, api_key: str, timeout: float = 30.0) -> None:
        self._server = server.rstrip("/")
        self._headers = {"x-api-key": api_key}
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._server}{path}"

    def get_statistics(self) -> Mapping[str, Any]:
        """GET /api/server/statistics — total photo/video counts and per-user breakdown."""
        r = requests.get(self._url("/api/server/statistics"), headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def list_albums(self) -> list[Mapping[str, Any]]:
        """GET /api/albums — list of all albums."""
        r = requests.get(self._url("/api/albums"), headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def search_metadata(self, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        """POST /api/search/metadata — paginate through all matches and return the full items list.

        Immich caps a single response at 1000 items (default 250). We pass size=1000
        and walk pages until a partial page comes back, ensuring the caller sees
        every match — not just the first 250 like a naive single call would.
        """
        items: list[Mapping[str, Any]] = []
        page = 1
        size = 1000
        while True:
            body = {**payload, "size": size, "page": page}
            r = requests.post(self._url("/api/search/metadata"), json=body,
                              headers=self._headers, timeout=self._timeout)
            r.raise_for_status()
            chunk = r.json()["assets"]["items"]
            items.extend(chunk)
            if len(chunk) < size:
                return items
            page += 1

    def search_metadata_count(self, payload: Mapping[str, Any]) -> int:
        """Like search_metadata but returns only the total count.

        Immich v2.6.3's response 'total' field reports the count IN THIS PAGE, not
        across all pages — and there's no separate overall-total field. So we
        paginate (size=1000) and sum up. For 86k HEIC files that's ~86 round-trips
        of ~50ms each = ~4s, which is acceptable for an audit.

        Uses the same pagination contract as search_metadata: walk pages until
        a partial page comes back.
        """
        total = 0
        page = 1
        size = 1000
        while True:
            body = {**payload, "size": size, "page": page}
            r = requests.post(self._url("/api/search/metadata"), json=body,
                              headers=self._headers, timeout=self._timeout)
            r.raise_for_status()
            chunk = r.json()["assets"]["items"]
            total += len(chunk)
            if len(chunk) < size:
                return total
            page += 1
