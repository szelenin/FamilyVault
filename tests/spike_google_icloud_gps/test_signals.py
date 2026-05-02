"""Tests for signal computations + composite confidence."""
from __future__ import annotations
import hashlib
from pathlib import Path

from scripts.spike_google_icloud_gps.signals import (
    name_match,
    date_diff_seconds,
    size_match,
    dim_match,
    is_original,
    hash_db_match,
    sha256_match,
    phash_distance,
    composite_confidence,
)


# -- s1 name_match ----------------------------------------------------------

def test_name_match_exact():
    assert name_match("IMG_2910.HEIC", "IMG_2910.HEIC") is True


def test_name_match_case_insensitive():
    assert name_match("img_2910.heic", "IMG_2910.HEIC") is True


def test_name_match_different():
    assert name_match("IMG_1234.HEIC", "IMG_5678.HEIC") is False


# -- s2 date_diff_seconds ---------------------------------------------------

def test_date_diff_seconds_zero():
    assert date_diff_seconds(1694973809, 1694973809.0) == 0.0


def test_date_diff_seconds_subsecond():
    diff = date_diff_seconds(1694973809, 1694973809.7)
    # Float conversion of unix-second floats has ~1e-7 jitter at this magnitude
    assert abs(diff - 0.7) < 1e-6


def test_date_diff_seconds_minutes():
    assert date_diff_seconds(1694973809, 1694973959.0) == 150.0


# -- s3 size_match ----------------------------------------------------------

def test_size_match_exact():
    assert size_match(2_500_000, 2_500_000) is True


def test_size_match_within_one_percent():
    assert size_match(2_500_000, 2_510_000) is True


def test_size_match_two_percent_off():
    assert size_match(2_500_000, 2_550_000) is False


# -- s4 dim_match -----------------------------------------------------------

def test_dim_match_exact():
    assert dim_match((4032, 3024), (4032, 3024)) is True


def test_dim_match_swapped_returns_false():
    assert dim_match((4032, 3024), (3024, 4032)) is False


def test_dim_match_unknown():
    assert dim_match(None, (4032, 3024)) is None
    assert dim_match((4032, 3024), None) is None


# -- s5 is_original ---------------------------------------------------------

def test_is_original_true_when_size_and_dim_match():
    assert is_original(size_match=True, dim_match=True) == "True"


def test_is_original_false_when_size_mismatch():
    assert is_original(size_match=False, dim_match=False) == "False"


def test_is_original_unknown_when_inputs_unknown():
    assert is_original(size_match=False, dim_match=None) == "Unknown"


# -- s6 hash_db_match -------------------------------------------------------

def test_hash_db_match_skipped_when_compressed():
    assert hash_db_match(google_path=None, icloud_stable_hash="abc", is_original="False") is None


def test_hash_db_match_returns_true_on_equal_hash(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    expected = hashlib.sha1(b"hello world").hexdigest()
    assert hash_db_match(google_path=f, icloud_stable_hash=expected, is_original="True") is True


def test_hash_db_match_returns_false_on_different_hash(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    assert hash_db_match(google_path=f, icloud_stable_hash="deadbeef", is_original="True") is False


# -- s7 sha256_match --------------------------------------------------------

def test_sha256_match_skipped_when_compressed():
    assert sha256_match(google_path=None, icloud_path=None, is_original="False") is None


def test_sha256_match_true_for_identical_bytes(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"identical")
    b.write_bytes(b"identical")
    assert sha256_match(a, b, is_original="True") is True


def test_sha256_match_false_for_different_bytes(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"foo")
    b.write_bytes(b"bar")
    assert sha256_match(a, b, is_original="True") is False


# -- s8 phash_distance ------------------------------------------------------

def test_phash_distance_zero_for_same_file(tmp_path):
    from PIL import Image
    img_path = tmp_path / "img.jpg"
    Image.new("RGB", (64, 64), color=(128, 50, 200)).save(img_path)
    other_path = tmp_path / "img2.jpg"
    Image.new("RGB", (64, 64), color=(128, 50, 200)).save(other_path)
    assert phash_distance(img_path, other_path) == 0


def test_phash_distance_returns_int(tmp_path):
    from PIL import Image
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    Image.new("RGB", (64, 64), color=(0, 0, 0)).save(a)
    Image.new("RGB", (64, 64), color=(255, 255, 255)).save(b)
    d = phash_distance(a, b)
    assert isinstance(d, int)
    assert d > 0


def test_phash_distance_returns_none_for_missing_file(tmp_path):
    assert phash_distance(tmp_path / "nope.jpg", tmp_path / "nope2.jpg") is None


# -- composite confidence ---------------------------------------------------

def test_composite_perfect_match():
    score = composite_confidence(
        s1_name=True, s2_date_sec=0.0, s3_size=True, s4_dim=True,
        s6_hash_db=True, s7_sha256=True, s8_phash=0,
    )
    assert score >= 0.9


def test_composite_no_match():
    score = composite_confidence(
        s1_name=False, s2_date_sec=99999.0, s3_size=False, s4_dim=False,
        s6_hash_db=None, s7_sha256=None, s8_phash=None,
    )
    assert score == 0.0


def test_composite_compressed_original():
    """Name + date match; size + dim mismatch (compressed); pHash close."""
    score = composite_confidence(
        s1_name=True, s2_date_sec=0.5, s3_size=False, s4_dim=False,
        s6_hash_db=None, s7_sha256=None, s8_phash=2,
    )
    # name (0.10) + date (~0.11) + phash close (~0.15) = ~0.36
    assert 0.30 <= score <= 0.55


def test_composite_clamps_to_one():
    score = composite_confidence(
        s1_name=True, s2_date_sec=0.0, s3_size=True, s4_dim=True,
        s6_hash_db=True, s7_sha256=True, s8_phash=0,
    )
    assert score <= 1.0
