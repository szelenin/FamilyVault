"""The 8 matching signals + composite confidence. Pure functions; no I/O.

Each signal compares one Google sidecar against one iCloud row and returns
either a bool, a number, or None. None means "could not compute" (e.g., a
required input was missing, or the signal was skipped because it's known
to fail — e.g., sha256 on a compressed file).
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional, Tuple


# -- s1 ---------------------------------------------------------------------

def name_match(google_title: str, icloud_filename: str) -> bool:
    """Lowercased filename equality."""
    return google_title.lower() == icloud_filename.lower()


# -- s2 ---------------------------------------------------------------------

def date_diff_seconds(google_unix: int, icloud_unix: float) -> float:
    """Absolute difference between Google's photoTakenTime and iCloud's ZDATECREATED."""
    return abs(float(google_unix) - icloud_unix)


# -- s3 ---------------------------------------------------------------------

def size_match(google_bytes: int, icloud_bytes: int) -> bool:
    """True if file sizes match within 1%."""
    if icloud_bytes == 0:
        return False
    return abs(google_bytes - icloud_bytes) / icloud_bytes <= 0.01


# -- s4 ---------------------------------------------------------------------

def dim_match(
    google_wh: Optional[Tuple[int, int]],
    icloud_wh: Optional[Tuple[int, int]],
) -> Optional[bool]:
    """Width × height equality. None when either side is unknown."""
    if google_wh is None or icloud_wh is None:
        return None
    return google_wh == icloud_wh


# -- s5 ---------------------------------------------------------------------

def is_original(size_match: bool, dim_match: Optional[bool]) -> str:
    """Classify Google's copy as 'True' (original), 'False' (compressed), or 'Unknown'.

    True when both size and dimensions match the iCloud original.
    False when sizes mismatch (compressed copy is smaller).
    Unknown when dimensions can't be read.
    """
    if dim_match is None:
        return "Unknown"
    if size_match and dim_match:
        return "True"
    return "False"


# -- s6 ---------------------------------------------------------------------

def hash_db_match(
    google_path: Optional[Path],
    icloud_stable_hash: str,
    is_original: str,
) -> Optional[bool]:
    """SHA-1 of Google's bytes vs iCloud's ZORIGINALSTABLEHASH.

    Returns None when is_original='False' (skip — recorded as N/A in output).
    Returns True/False otherwise.
    """
    if is_original == "False":
        return None
    if google_path is None or not google_path.exists():
        return False
    h = hashlib.sha1()
    with google_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest() == icloud_stable_hash


# -- s7 ---------------------------------------------------------------------

def sha256_match(
    google_path: Optional[Path],
    icloud_path: Optional[Path],
    is_original: str,
) -> Optional[bool]:
    """SHA-256 of both files compared.

    Returns None when is_original='False' (skip — recorded as N/A).
    """
    if is_original == "False":
        return None
    if google_path is None or icloud_path is None:
        return False
    if not google_path.exists() or not icloud_path.exists():
        return False
    g = hashlib.sha256()
    with google_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            g.update(chunk)
    i = hashlib.sha256()
    with icloud_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            i.update(chunk)
    return g.hexdigest() == i.hexdigest()


# -- s8 ---------------------------------------------------------------------

def phash_distance(
    google_path: Optional[Path],
    icloud_path: Optional[Path],
) -> Optional[int]:
    """Perceptual-hash Hamming distance between two images. None on missing files."""
    if google_path is None or icloud_path is None:
        return None
    if not google_path.exists() or not icloud_path.exists():
        return None
    from PIL import Image
    import imagehash
    g = imagehash.phash(Image.open(google_path))
    i = imagehash.phash(Image.open(icloud_path))
    return g - i  # imagehash supports `-` as Hamming distance


# -- composite ---------------------------------------------------------------

def composite_confidence(
    s1_name: bool,
    s2_date_sec: float,
    s3_size: bool,
    s4_dim: Optional[bool],
    s6_hash_db: Optional[bool],
    s7_sha256: Optional[bool],
    s8_phash: Optional[int],
) -> float:
    """Weighted sum across all signals; clamped to [0, 1].

    Weights chosen to give byte-equality (s6/s7) the most weight, then phash, then
    name+date+size+dim. This formula is provisional and refined after manual review.
    """
    score = 0.0
    if s1_name:
        score += 0.10
    if s2_date_sec is not None:
        # Saturates to full credit at exact match; 0 credit at 2s away
        score += 0.15 * max(0.0, 1.0 - min(1.0, s2_date_sec / 2.0))
    if s3_size:
        score += 0.10
    if s4_dim is True:
        score += 0.10
    if s6_hash_db is True:
        score += 0.30
    if s7_sha256 is True:
        score += 0.30
    if s8_phash is not None:
        # Distance ≤ 8 is "same image perceptually"; saturates to full credit
        score += 0.20 * max(0.0, 1.0 - min(1.0, s8_phash / 8.0))
    return max(0.0, min(1.0, score))
