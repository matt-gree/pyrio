"""What the installed package promises, independent of any one module."""

import subprocess
import sys
from importlib.metadata import version
from importlib.resources import files

import pyrio

# Optional dependencies (and the ones the plan drops). Only the module that
# owns an extra may import it, so a bare `import pyrio` must load none of them.
HEAVY = ("httpx", "pandas", "numpy", "matplotlib", "scipy")


def test_version_comes_from_the_distribution():
    assert pyrio.__version__ == version("projectrio")


def test_ships_py_typed():
    assert files("pyrio").joinpath("py.typed").is_file()


def test_import_loads_no_optional_dependency():
    # A fresh interpreter: this one already has whatever other tests imported.
    code = f"import sys, pyrio\nprint(','.join(m for m in {HEAVY!r} if m in sys.modules))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "", f"`import pyrio` loaded {out}"
