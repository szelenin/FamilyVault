"""Shared pytest fixtures + path setup for understanding-layer tests.

Mirrors tests/story-engine/conftest.py: adds setup/understanding to sys.path so
tests import the package modules directly. Also registers the opt-in `integration`
and `e2e` markers (scoped to this suite; the repo has no central pytest config).
"""
import os
import sys

# Add setup/understanding to path so tests can import the package modules.
_PKG_PARENT = os.path.join(
    os.path.dirname(__file__), "..", "..", "setup", "understanding"
)
sys.path.insert(0, os.path.abspath(_PKG_PARENT))


def pytest_configure(config):
    """Register opt-in markers for the integration and e2e layers."""
    config.addinivalue_line(
        "markers",
        "integration: live Immich/Ollama/ffmpeg/MLX checks (opt-in; deselected by default)",
    )
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end index→search flows on tiny fixtures (opt-in)",
    )
