"""Stadium drawings on matplotlib axes, with the ``plot`` extra.

The matplotlib counterparts of :mod:`pyrio.svg`. Each function draws onto the
``ax`` it's given, or onto a new figure's axes, and returns the axes so the
caller can keep drawing::

    >>> import pyrio, pyrio.plot
    >>> game = pyrio.read_game("game.json")                      # doctest: +SKIP
    >>> ax = pyrio.plot.spray_chart(game.events, stadium=game.stadium)  # doctest: +SKIP
    >>> ax.figure.savefig("spray.png")                           # doctest: +SKIP

Install it with ``pip install 'projectrio[plot]'``. Coordinates are field
units, so ``ax.plot(x, z)`` adds anything else in the same frame.
"""

# matplotlib types every Axes method's **kwargs as Unknown, so strict mode would
# flag each call; everything pyrio passes is typed.
# pyright: reportUnknownMemberType=false

from __future__ import annotations

from typing import TYPE_CHECKING

from .geometry import FIELDER_START_LOCATIONS, boundary
from .svg import (
    _FIELD_EDGE,  # pyright: ignore[reportPrivateUsage]
    _FIELD_FILL,  # pyright: ignore[reportPrivateUsage]
    _FIELDER,  # pyright: ignore[reportPrivateUsage]
    _foul_line_end,  # pyright: ignore[reportPrivateUsage]
    _spray_mark,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from matplotlib.axes import Axes

    from ._codes import Stadium
    from ._game import Event

__all__ = ["spray_chart", "stadium"]

_MARKERS = {
    "circle": "o",
    "square": "s",
    "diamond": "D",
    "triangle": "^",
    "star": "*",
    "cross": "x",
}


def stadium(
    stadium: Stadium,
    *,
    ax: Axes | None = None,
    fielders: bool = False,
    foul_lines: bool = True,
) -> Axes:
    """The stadium's field from above, with equal scales on both axes.

    ``fielders`` adds each fielder's starting spot, labelled by position.
    """
    return _field(stadium, ax=ax, fielders=fielders, foul_lines=foul_lines)


def _field(stadium: Stadium, *, ax: Axes | None, fielders: bool, foul_lines: bool) -> Axes:
    if ax is None:
        import matplotlib.pyplot as plt

        _, ax = plt.subplots()
    outline = boundary(stadium)
    ax.fill(
        [x for x, _ in outline],
        [z for _, z in outline],
        facecolor=_FIELD_FILL,
        edgecolor=_FIELD_EDGE,
        linewidth=1.2,
        zorder=0,
    )
    if foul_lines:
        for side in (-1.0, 1.0):
            end = _foul_line_end(outline, side)
            if end is not None:
                ax.plot([0, end[0]], [0, end[1]], color="white", linewidth=1.2, zorder=1)
    if fielders:
        for position, (x, _, z) in FIELDER_START_LOCATIONS.items():
            ax.scatter([x], [z], color=_FIELDER, marker="s", s=18, zorder=2)
            ax.annotate(
                position.label,
                (x, z),
                textcoords="offset points",
                xytext=(0, -9),
                ha="center",
                fontsize=7,
                color=_FIELDER,
            )
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("z")
    return ax


def spray_chart(
    events: Iterable[Event],
    *,
    stadium: Stadium,
    ax: Axes | None = None,
    fouls: bool = False,
) -> Axes:
    """Where each ball in play came down, styled as :func:`pyrio.svg.spray_chart`."""
    marks = [m for e in events if (m := _spray_mark(e, fouls=fouls)) is not None]
    ax = _field(stadium, ax=ax, fielders=False, foul_lines=True)
    for m in marks:
        marker = _MARKERS[m.shape]
        ax.scatter(
            [m.x],
            [m.z],
            color=m.color,
            marker=marker,
            s=(m.size * 6) ** 2,
            edgecolors="black" if marker != "x" else None,
            linewidths=0.5 if marker != "x" else 1.2,
            zorder=3,
        )
    return ax
