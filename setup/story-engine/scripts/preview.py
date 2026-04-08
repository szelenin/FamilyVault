"""Preview functionality: Immich album creation and thumbnail fetching for Story Engine v2."""
import os
from typing import Optional


def fetch_thumbnail(session, immich_url, asset_id, dest_dir):
    # type: (object, str, str, str) -> str
    """Download asset thumbnail to local file. Returns path to downloaded JPEG."""
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "{}.jpg".format(asset_id))
    resp = session.get(
        "{}/api/assets/{}/thumbnail".format(immich_url, asset_id),
        params={"size": "preview"},
    )
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


def create_preview_album(session, immich_url, asset_ids, title, old_album_id=None):
    # type: (object, str, list, str, Optional[str]) -> dict
    """Create Immich album with selected assets and return album_id + share link.

    If old_album_id is provided, deletes that album first (cleanup).
    """
    # Clean up old preview album if exists
    if old_album_id:
        delete_preview_album(session, immich_url, old_album_id)

    # Create album
    resp = session.post(
        "{}/api/albums".format(immich_url),
        json={"albumName": title, "description": "Story Engine preview"},
    )
    resp.raise_for_status()
    album = resp.json()
    album_id = album["id"]

    # Add assets
    if asset_ids:
        resp = session.put(
            "{}/api/albums/{}/assets".format(immich_url, album_id),
            json={"ids": asset_ids},
        )
        resp.raise_for_status()

    # Create share link
    resp = session.post(
        "{}/api/shared-links".format(immich_url),
        json={
            "type": "ALBUM",
            "albumId": album_id,
            "allowDownload": True,
        },
    )
    resp.raise_for_status()
    share = resp.json()
    share_key = share.get("key", "")

    return {
        "album_id": album_id,
        "share_key": share_key,
        "share_url": "{}/share/{}".format(immich_url, share_key),
    }


def delete_preview_album(session, immich_url, album_id):
    # type: (object, str, str) -> None
    """Delete a temporary preview album."""
    resp = session.delete("{}/api/albums/{}".format(immich_url, album_id))
    resp.raise_for_status()
