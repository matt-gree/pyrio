"""Stadium drawings as SVG strings, with no dependencies.

Like ``chess.svg``, every function returns the SVG source as a ``str``, ready
to write to a file, embed in a page or display in a notebook::

    >>> from pyrio import Stadium
    >>> import pyrio.svg
    >>> pyrio.svg.stadium(Stadium.MARIO_STADIUM).startswith("<svg")
    True

:func:`stadium` draws the field with any :class:`Mark` and :class:`Flight`
you give it; :func:`spray_chart` marks where each ball in play came down.
Coordinates are field units (see ``pyrio.geometry.Point``): ``x`` toward
right field, ``z`` toward centre field, home plate at the origin.
"""

from __future__ import annotations

import html
import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ._codes import AtBatResult, PrimaryContactResult
from .geometry import FIELDER_START_LOCATIONS, boundary

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ._codes import Stadium
    from ._game import Event

__all__ = ["Flight", "Mark", "MarkShape", "spray_chart", "stadium"]

MarkShape = Literal["circle", "square", "diamond", "triangle", "star", "cross"]

_FIELD_FILL = "#e9f2e1"
_FIELD_EDGE = "#4a6b45"
_FOUL_LINE = "#ffffff"
_FIELDER = "#7a7a7a"
_PAD = 4.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Mark:
    """A point to draw on the field, such as where a ball landed."""

    x: float
    z: float
    color: str = "#333333"
    shape: MarkShape = "circle"
    size: float = 1.2
    """The mark's radius, in field units."""
    title: str | None = None
    """Shown as a tooltip when the SVG is viewed in a browser."""
    label: str | None = None
    """Text drawn beside the mark."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Flight:
    """A ball's path seen from above, such as a ``HitResult.trajectory``."""

    points: Sequence[Sequence[float]]
    """``(x, y, z)`` points; the height ``y`` is ignored."""
    color: str = "#333333"
    width: float = 0.35
    opacity: float = 0.6


def stadium(
    stadium: Stadium,
    *,
    marks: Iterable[Mark] = (),
    flights: Iterable[Flight] = (),
    fielders: bool = False,
    foul_lines: bool = True,
    size: int | None = 400,
    title: str | None = None,
) -> str:
    """The stadium's field from above, with flights drawn under marks.

    ``fielders`` adds each fielder's starting spot. ``size`` is the width in
    pixels, with the height following the field's shape; ``None`` leaves the
    SVG to fill its container. ``title`` is the document's accessible name.
    """
    return _draw(
        stadium,
        marks=marks,
        flights=flights,
        fielders=fielders,
        foul_lines=foul_lines,
        size=size,
        title=title,
    )


def _draw(
    stadium: Stadium,
    *,
    marks: Iterable[Mark],
    flights: Iterable[Flight],
    fielders: bool,
    foul_lines: bool,
    size: int | None,
    title: str | None,
) -> str:
    outline = boundary(stadium)
    xs = [x for x, _ in outline]
    zs = [z for _, z in outline]
    left, right = min(xs) - _PAD, max(xs) + _PAD
    near, far = min(zs) - _PAD, max(zs) + _PAD
    width, height = right - left, far - near

    out: list[str] = []
    dims = "" if size is None else f' width="{size}" height="{round(size * height / width)}"'
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"{dims} '
        f'viewBox="{_n(left)} {_n(-far)} {_n(width)} {_n(height)}">'
    )
    if title is not None:
        out.append(f"<title>{html.escape(title)}</title>")
    points = " ".join(f"{_n(x)},{_n(-z)}" for x, z in outline)
    out.append(
        f'<polygon points="{points}" fill="{_FIELD_FILL}" stroke="{_FIELD_EDGE}" '
        'stroke-width="0.6" stroke-linejoin="round"/>'
    )
    if foul_lines:
        for side in (-1.0, 1.0):
            end = _foul_line_end(outline, side)
            if end is not None:
                out.append(
                    f'<line x1="0" y1="0" x2="{_n(end[0])}" y2="{_n(-end[1])}" '
                    f'stroke="{_FOUL_LINE}" stroke-width="0.5"/>'
                )
    if fielders:
        for position, (x, _, z) in FIELDER_START_LOCATIONS.items():
            out.append(_mark(Mark(x=x, z=z, color=_FIELDER, shape="square", size=0.9)))
            out.append(_text(x, z - 3.2, position.label, _FIELDER, anchor="middle"))
    for flight in flights:
        path = " ".join(f"{_n(p[0])},{_n(-p[-1])}" for p in flight.points)
        out.append(
            f'<polyline points="{path}" fill="none" stroke="{html.escape(flight.color)}" '
            f'stroke-width="{_n(flight.width)}" stroke-opacity="{_n(flight.opacity)}" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )
    for mark in marks:
        out.append(_mark(mark))
        if mark.label is not None:
            out.append(_text(mark.x + mark.size + 0.8, mark.z, mark.label, "#222222"))
    out.append("</svg>")
    return "\n".join(out)


def spray_chart(
    events: Iterable[Event],
    *,
    stadium: Stadium,
    fouls: bool = False,
    size: int | None = 400,
    title: str | None = None,
) -> str:
    """Where each ball in play came down, coloured by the at-bat's result.

    Uses the landing the stat file records. Hits are coloured by bases (home
    runs largest), outs are grey crosses, and fouls are left off unless
    ``fouls`` is set. Each mark's tooltip names the batter and the result.
    """
    marks = [m for e in events if (m := _spray_mark(e, fouls=fouls)) is not None]
    return _draw(
        stadium, marks=marks, flights=(), fielders=False, foul_lines=True, size=size, title=title
    )


# --- spray-chart style, shared with pyrio.plot --------------------------------

_HIT_STYLE: dict[AtBatResult, tuple[str, MarkShape, float]] = {
    AtBatResult.SINGLE: ("#2e8b3a", "circle", 1.2),
    AtBatResult.DOUBLE: ("#2a62b8", "diamond", 1.5),
    AtBatResult.TRIPLE: ("#7b4bb3", "triangle", 1.7),
    AtBatResult.HOME_RUN: ("#e08a00", "star", 2.4),
}
_OUT_STYLE: tuple[str, MarkShape, float] = ("#6b6b6b", "cross", 1.0)
_FOUL_STYLE: tuple[str, MarkShape, float] = ("#b5b5b5", "circle", 0.6)


def _spray_mark(event: Event, *, fouls: bool) -> Mark | None:
    contact = event.contact
    if contact is None:
        return None
    is_foul = contact.primary_result is PrimaryContactResult.FOUL
    if is_foul and not fouls:
        return None
    color, shape, size = _FOUL_STYLE if is_foul else _HIT_STYLE.get(event.result, _OUT_STYLE)
    x, _, z = contact.landing_location
    tip = f"{event.batter_spot.character.label}: {'Foul' if is_foul else event.result.label}"
    return Mark(x=x, z=z, color=color, shape=shape, size=size, title=tip)


# --- drawing primitives ------------------------------------------------------


def _foul_line_end(
    outline: Sequence[tuple[float, float]], side: float
) -> tuple[float, float] | None:
    """Where the foul line from home plate along ``x = side * z`` meets the boundary."""
    dx, dz = side * math.sqrt(0.5), math.sqrt(0.5)
    nearest: float | None = None
    for (x0, z0), (x1, z1) in itertools.pairwise(outline):
        ex, ez = x1 - x0, z1 - z0
        denom = dx * ez - dz * ex
        if denom == 0:
            continue
        t = (x0 * ez - z0 * ex) / denom  # distance along the ray
        u = (x0 * dz - z0 * dx) / denom  # fraction along the edge
        if t > 0 and 0 <= u <= 1 and (nearest is None or t < nearest):
            nearest = t
    return None if nearest is None else (dx * nearest, dz * nearest)


def _mark(mark: Mark) -> str:
    x, y, r = mark.x, -mark.z, mark.size
    color = html.escape(mark.color)
    paint = f'fill="{color}" stroke="#000000" stroke-width="0.15"'
    if mark.shape == "circle":
        tag, attrs = "circle", f'cx="{_n(x)}" cy="{_n(y)}" r="{_n(r)}" {paint}'
    elif mark.shape == "square":
        tag = "rect"
        attrs = f'x="{_n(x - r)}" y="{_n(y - r)}" width="{_n(2 * r)}" height="{_n(2 * r)}" {paint}'
    elif mark.shape == "cross":
        d = (
            f"M{_n(x - r)},{_n(y - r)}L{_n(x + r)},{_n(y + r)}"
            f"M{_n(x - r)},{_n(y + r)}L{_n(x + r)},{_n(y - r)}"
        )
        tag, attrs = "path", f'd="{d}" fill="none" stroke="{color}" stroke-width="{_n(r * 0.45)}"'
    else:
        corners = _POLYGONS[mark.shape]
        points = " ".join(f"{_n(x + r * cx)},{_n(y + r * cy)}" for cx, cy in corners)
        tag, attrs = "polygon", f'points="{points}" {paint}'
    if mark.title is None:
        return f"<{tag} {attrs}/>"
    return f"<{tag} {attrs}><title>{html.escape(mark.title)}</title></{tag}>"


def _star() -> tuple[tuple[float, float], ...]:
    corners: list[tuple[float, float]] = []
    for i in range(10):
        radius = 1.0 if i % 2 == 0 else 0.45
        angle = math.pi / 2 + i * math.pi / 5
        corners.append((radius * math.cos(angle), -radius * math.sin(angle)))
    return tuple(corners)


_POLYGONS: dict[str, tuple[tuple[float, float], ...]] = {
    "diamond": ((0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)),
    "triangle": ((0.0, -1.0), (0.95, 0.75), (-0.95, 0.75)),
    "star": _star(),
}


def _text(x: float, z: float, text: str, color: str, *, anchor: str = "start") -> str:
    return (
        f'<text x="{_n(x)}" y="{_n(-z)}" font-size="2.6" font-family="sans-serif" '
        f'fill="{color}" text-anchor="{anchor}" dominant-baseline="middle">'
        f"{html.escape(text)}</text>"
    )


def _n(value: float) -> str:
    """A coordinate to two decimals, without trailing zeros."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text
