"""Make pyrio importable from its own test suite.

Two entries, because the modules disagree about what they need. `package_dir`
maps the repo root to the `pyrio` package, so a module with relative imports
(`stat_file_parser` does `from .lookup import ...`) is only importable AS
`pyrio.*` — which needs the root's PARENT on the path. Flat modules like
`web_caching` import fine from the root itself, and those tests already do.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(ROOT))
