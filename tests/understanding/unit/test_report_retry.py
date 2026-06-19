"""US4 — report (no_preview remediation) + retry (re-queue) + doctor gate on run."""
import pytest
from index.db import open_db, upsert_asset, counts
import index_cli


def _seed(conn):
    upsert_asset(conn, {"asset_id": "np1", "type": "IMAGE", "status": "no_preview", "schema_ver": 1})
    upsert_asset(conn, {"asset_id": "np2", "type": "IMAGE", "status": "no_preview", "schema_ver": 1})
    upsert_asset(conn, {"asset_id": "er1", "type": "IMAGE", "status": "error", "error": "boom", "schema_ver": 1})
    upsert_asset(conn, {"asset_id": "ok1", "type": "IMAGE", "status": "done", "schema_ver": 1})


def test_report_lists_no_preview_ids(tmp_path, capsys):
    conn = open_db(str(tmp_path / "i.db"))
    _seed(conn)
    ids = index_cli.report(conn)
    assert sorted(ids) == ["np1", "np2"]            # only no_preview
    out = capsys.readouterr().out
    assert "np1" in out and "np2" in out            # printed for the operator


def test_report_empty_returns_empty(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    assert index_cli.report(conn) == []


def test_retry_requeues_no_preview_and_error(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed(conn)
    n = index_cli.retry(conn, ["no_preview", "error"])
    assert n == 3                                    # 2 no_preview + 1 error
    c = counts(conn)
    assert c["pending"] == 3 and c["no_preview"] == 0 and c["error"] == 0 and c["done"] == 1


def test_retry_single_status(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed(conn)
    n = index_cli.retry(conn, ["no_preview"])
    assert n == 2
    c = counts(conn)
    assert c["pending"] == 2 and c["no_preview"] == 0 and c["error"] == 1


def test_retry_clears_error_text(tmp_path):
    conn = open_db(str(tmp_path / "i.db"))
    _seed(conn)
    index_cli.retry(conn, ["error"])
    row = conn.execute("SELECT status, error FROM assets WHERE asset_id='er1'").fetchone()
    assert row["status"] == "pending" and row["error"] is None


def test_run_blocks_when_doctor_fails(tmp_path, monkeypatch):
    from preflight import Check
    monkeypatch.setattr(index_cli, "run_doctor", lambda asset_type, **kw: [Check("ollama", False, "ollama serve")])
    with pytest.raises(SystemExit) as exc:
        index_cli.main(["--db", str(tmp_path / "i.db"), "run", "--type", "photo"])
    assert exc.value.code == 3                        # fail-fast before heavy work


def test_report_auto_regenerate_triggers_immich_job(tmp_path):
    from unittest.mock import MagicMock
    conn = open_db(str(tmp_path / "i.db"))
    upsert_asset(conn, {"asset_id": "np1", "type": "IMAGE", "status": "no_preview", "schema_ver": 1})
    s = MagicMock()
    ids = index_cli.report(conn, auto_regenerate=True, session=s, base_url="http://x:2283")
    assert ids == ["np1"]
    s.put.assert_called_once()
    url, = s.put.call_args[0]
    assert url == "http://x:2283/api/jobs/thumbnailGeneration"
    assert s.put.call_args.kwargs["json"]["command"] == "start"

def test_report_no_autoregen_makes_no_network_call(tmp_path):
    from unittest.mock import MagicMock
    conn = open_db(str(tmp_path / "i.db"))
    upsert_asset(conn, {"asset_id": "np1", "type": "IMAGE", "status": "no_preview", "schema_ver": 1})
    s = MagicMock()
    index_cli.report(conn, auto_regenerate=False, session=s)
    s.put.assert_not_called()

def test_report_autoregen_skipped_when_no_missing(tmp_path):
    from unittest.mock import MagicMock
    conn = open_db(str(tmp_path / "i.db"))
    s = MagicMock()
    assert index_cli.report(conn, auto_regenerate=True, session=s) == []
    s.put.assert_not_called()    # nothing to regenerate
