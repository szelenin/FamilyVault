from unittest.mock import patch
import tools.photos as photos


def test_search_returns_compact_records():
    fake_assets = [
        {"id": "a1", "asset_id": "a1", "type": "IMAGE", "filename": "x.jpg",
         "mime_type": "image/jpeg", "taken_at": "2025-03-15T14:30:00Z",
         "city": "Miami", "country": "US", "description": "cake"},
    ]
    with patch.object(photos, "_search_photos", return_value=fake_assets), \
         patch.object(photos, "_make_session", return_value=object()):
        out = photos.search_photos(query="birthday", limit=5)
    assert isinstance(out, list)
    rec = out[0]
    assert rec["asset_id"] == "a1"
    assert rec["taken_at"] == "2025-03-15T14:30:00Z"
    assert rec["city"] == "Miami"
    assert rec["thumbnail_url"].endswith("/api/assets/a1/thumbnail")
    # compact: no raw mime/filename noise
    assert set(rec.keys()) == {
        "asset_id", "type", "taken_at", "city", "country", "description", "thumbnail_url"
    }


def test_search_traps_systemexit():
    def boom(*a, **k):
        raise SystemExit(3)
    with patch.object(photos, "_search_photos", side_effect=boom), \
         patch.object(photos, "_make_session", return_value=object()):
        try:
            photos.search_photos(query="x")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "search failed" in str(e).lower()
