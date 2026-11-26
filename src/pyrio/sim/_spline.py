"""The game's 2D splines (mssb-dtk ``src/game/math/spline.c``), in single precision.

``spline2D_build`` parameterises the points by normalised chord length and
solves a natural cubic spline per axis; ``spline_evaluate`` reads it back.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .._float32 import f32 as _f32

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["make_spline"]


def _second_derivatives(t: list[float], v: list[float], n: int) -> list[float]:
    # spline_computeSecondDerivatives
    c = [0.0] * n
    h = [0.0] * n
    s = [0.0] * (n + 1)
    for i in range(n - 1):
        h[i] = _f32(t[i + 1] - t[i])
        s[i + 1] = _f32(_f32(v[i + 1] - v[i]) / h[i])
    c[1] = _f32(_f32(s[2] - s[1]) - _f32(h[0] * c[0]))
    s[1] = _f32(2 * _f32(t[2] - t[0]))
    for i in range(1, n - 2):
        f = _f32(h[i] / s[i])
        c[i + 1] = _f32(_f32(s[i + 2] - s[i + 1]) - _f32(f * c[i]))
        s[i + 1] = _f32(_f32(2 * _f32(t[i + 2] - t[i])) - _f32(f * h[i]))
    c[n - 2] = _f32(c[n - 2] - _f32(h[n - 2] * c[n - 1]))
    for i in range(n - 2, 0, -1):
        c[i] = _f32(_f32(c[i] - _f32(h[i] * c[i + 1])) / s[i])
    return c


def _evaluate(d: float, t: list[float], v: list[float], c: list[float], n: int) -> float:
    # spline_evaluate
    seg, end = 0, n - 1
    while seg < end:
        half = (seg + end) >> 1
        if t[half] < d:
            seg = half + 1
        else:
            end = half
    if seg > 0:
        seg -= 1
    lt = _f32(d - t[seg])
    length = _f32(t[seg + 1] - t[seg])
    slope = (v[seg + 1] - v[seg]) / length - length * (2 * c[seg] + c[seg + 1])
    curve = lt * (3 * c[seg] + (lt * (c[seg + 1] - c[seg])) / length)
    return _f32(v[seg] + lt * (curve + slope))


def make_spline(points: Sequence[tuple[float, float]]) -> Callable[[float], tuple[float, float]]:
    """``spline2D_build``: the spline through ``points``, read at ``t`` from 0 to 1 by chord."""
    n = len(points)
    xs = [_f32(p[0]) for p in points]
    zs = [_f32(p[1]) for p in points]
    ts = [0.0] * n
    for i in range(1, n):
        ts[i] = _f32(ts[i - 1] + _f32(math.hypot(xs[i] - xs[i - 1], zs[i] - zs[i - 1])))
    for i in range(1, n):
        ts[i] = _f32(ts[i] / ts[n - 1])
    cx = _second_derivatives(ts, xs, n)
    cz = _second_derivatives(ts, zs, n)

    def point(t: float) -> tuple[float, float]:
        return (_evaluate(t, ts, xs, cx, n), _evaluate(t, ts, zs, cz, n))

    return point
