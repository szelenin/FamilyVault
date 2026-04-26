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
        """POST /api/search/metadata — returns the assets.items list directly."""
        r = requests.post(self._url("/api/search/metadata"), json=payload,
                          headers=self._headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()["assets"]["items"]
