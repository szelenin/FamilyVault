"""Unit tests for Immich API-key resolution (env var → key file fallback).

Matches the repo convention (story-engine reads the key from a file). The CLI
should work against the already-provisioned key file without the operator having
to export the raw key.
"""
import index_cli


def test_env_var_takes_precedence_over_file(tmp_path):
    f = tmp_path / "api-key.txt"
    f.write_text("FILEKEY")
    env = {"IMMICH_API_KEY": "ENVKEY", "IMMICH_API_KEY_FILE": str(f)}
    assert index_cli._resolve_api_key(env=env) == "ENVKEY"


def test_falls_back_to_key_file_when_env_unset(tmp_path):
    f = tmp_path / "api-key.txt"
    f.write_text("FILEKEY\n")          # trailing newline must be stripped
    env = {"IMMICH_API_KEY_FILE": str(f)}
    assert index_cli._resolve_api_key(env=env) == "FILEKEY"


def test_empty_string_when_neither_present(tmp_path):
    env = {"IMMICH_API_KEY_FILE": str(tmp_path / "does-not-exist.txt")}
    assert index_cli._resolve_api_key(env=env) == ""


def test_default_key_file_matches_repo_canonical_path():
    # The default must point at the same file the rest of the repo provisions.
    assert index_cli.DEFAULT_API_KEY_FILE == "/Volumes/HomeRAID/immich/api-key.txt"
