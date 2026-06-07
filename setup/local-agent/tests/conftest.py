"""Put the local-agent package root on sys.path so `import tools...` works."""
import os
import sys

_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _PKG_ROOT)
