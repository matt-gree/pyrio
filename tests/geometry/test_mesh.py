"""The collision meshes: loading, the manifest check, and the triangles."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter

import pytest

from pyrio import Stadium
from pyrio.geometry import Surface, _files, triangles


def test_every_stadium_has_a_mesh():
    for stadium in Stadium:
        tris = triangles(stadium)
        assert len(tris) > 500, stadium
        surfaces = Counter(t.surface for t in tris)
        assert surfaces[Surface.GRASS], stadium
        assert surfaces[Surface.OUT_OF_PLAY], stadium


def test_triangles_are_in_field_coordinates():
    # The mesh stores height inverted; the ground is near y = 0 and walls stand above it.
    walls = [t for t in triangles(Stadium.MARIO_STADIUM) if t.surface is Surface.WALL]
    assert max(max(t.a[1], t.b[1], t.c[1]) for t in walls) == pytest.approx(4.0, abs=0.01)


def test_foul_territory_is_flagged():
    tris = triangles(Stadium.MARIO_STADIUM)
    assert any(t.is_foul for t in tris)
    assert any(not t.is_foul for t in tris)


def test_a_damaged_mesh_is_refused(monkeypatch: pytest.MonkeyPatch):
    manifest = {k: dict(v) for k, v in _files._manifest().items()}
    manifest["Toy Field.json"]["sha256"] = "0" * 64
    monkeypatch.setattr(_files, "_manifest", lambda: manifest)
    _files.mesh.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="damaged"):
            _files.mesh(Stadium.TOY_FIELD)
    finally:
        _files.mesh.cache_clear()


def test_every_manifest_entry_matches():
    for stadium in Stadium:
        _files.mesh(stadium)  # raises if the sha256 differs
    assert len(_files._manifest()) == len(Stadium)


def test_importing_reads_no_data():
    code = (
        "import pyrio.geometry, pyrio.sim\n"
        "from pyrio.geometry import _files\n"
        "f = _files\n"
        "fns = (f.mesh, f.park_sheet, f.outline, f.wall_table, f._manifest)\n"
        "print(sum(f.cache_info().currsize for f in fns))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "0"
