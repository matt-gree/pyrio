"""``pyrio.geometry`` and ``pyrio.sim`` are imported by name, never by ``import pyrio``."""

from __future__ import annotations

import subprocess
import sys


def test_import_pyrio_loads_neither_submodule():
    code = (
        "import sys, pyrio\n"
        "print(','.join(m for m in ('pyrio.geometry', 'pyrio.sim') if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "", f"`import pyrio` loaded {out}"
