"""The field boundary: the polygon a ball leaves the park through."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from . import _files

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .._codes import Stadium
    from ._point import Point

__all__ = ["area", "boundary", "boundary_crossing"]


def boundary(stadium: Stadium) -> tuple[tuple[float, float], ...]:
    """The stadium's playable boundary as a closed ``(x, z)`` polygon.

    It runs along the outfield fence and back along the foul-line fences
    behind home plate. The last point repeats the first.
    """
    return _files.outline(stadium)


def area(stadium: Stadium) -> float:
    """The playable area inside the boundary, in square field units.

    The shoelace formula over :func:`boundary`, which is a simple polygon at
    every stadium.
    """
    points = boundary(stadium)
    twice = sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in itertools.pairwise(points))
    return abs(twice) / 2


def boundary_crossing(stadium: Stadium, trajectory: Iterable[Sequence[float]]) -> Point | None:
    """Where the flight's ``(x, z)`` path first crosses the boundary, or None.

    That is the ball leaving the park: a home run, off the wall, or foul into
    the netting. The point is interpolated between the last frame inside and
    the first outside, so its height is the flight's at that moment. The
    recorded landing of such a ball is usually a few frames past this, since
    the game logs it where it comes down.
    """
    polygon = boundary(stadium)
    points = [tuple(p) for p in trajectory]
    for a, b in itertools.pairwise(points):
        nearest: float | None = None
        for c, d in itertools.pairwise(polygon):
            t = _crossing(a[0], a[2], b[0], b[2], c, d)
            if t is not None and (nearest is None or t < nearest):
                nearest = t
        if nearest is not None:
            return (
                a[0] + nearest * (b[0] - a[0]),
                a[1] + nearest * (b[1] - a[1]),
                a[2] + nearest * (b[2] - a[2]),
            )
    return None


def _crossing(
    ax: float, az: float, bx: float, bz: float, c: tuple[float, float], d: tuple[float, float]
) -> float | None:
    """How far along ``a -> b`` (0 to 1) it crosses the edge ``c -> d``, or None."""
    cx, cz = c
    dx, dz = d
    rx, rz = bx - ax, bz - az
    sx, sz = dx - cx, dz - cz
    denominator = rx * sz - rz * sx
    if denominator == 0.0:
        return None  # parallel or collinear
    t = ((cx - ax) * sz - (cz - az) * sx) / denominator
    u = ((cx - ax) * rz - (cz - az) * rx) / denominator
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None
