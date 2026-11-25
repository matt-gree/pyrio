"""What the installed package promises, independent of any one module."""

import pathlib
import shutil
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


def test_imports_from_a_source_tree_without_being_installed(tmp_path: pathlib.Path):
    # How RioVisualizer bundles pyrio: a git submodule put on sys.path, no metadata.
    # A copy of the package alone in a folder, and -S to keep site-packages out.
    shutil.copytree(pathlib.Path(str(files("pyrio"))), tmp_path / "pyrio")
    code = (
        f"import sys; sys.path.insert(0, {str(tmp_path)!r}); import pyrio; print(pyrio.__version__)"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "0+unknown"
