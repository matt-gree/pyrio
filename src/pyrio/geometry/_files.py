"""Reading the bundled stadium data, lazily and once per stadium.

Every file in ``_data/`` is named after its stadium's label. Nothing here runs at
import: each reader is behind ``functools.cache``, so the first call per stadium
reads the file and later calls share the parsed result. Callers must not mutate
what they get back.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .._codes import Stadium

_DATA = files("pyrio.geometry").joinpath("_data")


def _read_text(*parts: str) -> str:
    return _DATA.joinpath(*parts).read_text(encoding="utf-8")


@cache
def _manifest() -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = json.loads(_read_text("collision", "MANIFEST.json"))
    return manifest


@cache
def mesh(stadium: Stadium) -> dict[str, Any]:
    """The stadium's collision mesh, checked against ``MANIFEST.json``.

    The meshes are copied from RioVisualizer's extraction of the game files.
    The manifest records each one's sha256, so a damaged or edited copy raises
    here instead of quietly changing every answer built on it.
    """
    name = f"{stadium.label}.json"
    raw = gzip.decompress(_DATA.joinpath("collision", f"{name}.gz").read_bytes())
    want = _manifest()[name]["sha256"]
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        raise RuntimeError(
            f"the bundled collision mesh for {stadium.label} is damaged: "
            f"sha256 {got}, MANIFEST.json says {want}"
        )
    data: dict[str, Any] = json.loads(raw)
    return data


@cache
def park_sheet(stadium: Stadium) -> dict[str, Any]:
    """The stadium's park sheet: surface physics, hazards and the hazards' meshes."""
    sheet: dict[str, Any] = json.loads(_read_text("parks", f"{stadium.label}.park.json"))
    return sheet


@cache
def outline(stadium: Stadium) -> tuple[tuple[float, float], ...]:
    """The stadium's boundary polygon as ``(x, z)`` points, closed (last == first)."""
    points: list[tuple[float, float]] = []
    for line in _read_text("outlines", f"{stadium.label}.txt").splitlines():
        fields = line.split()
        if len(fields) == 2:
            points.append((float(fields[0]), float(fields[1])))
    if points[0] != points[-1]:
        points.append(points[0])
    return tuple(points)


@cache
def wall_table() -> dict[str, list[dict[str, float]]]:
    """The outfield-wall table for every stadium, keyed by label."""
    table: dict[str, list[dict[str, float]]] = json.loads(_read_text("walls.json"))
    return table
