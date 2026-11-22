"""The outfield wall as a table: one wall position and one height per ``x``.

The table is derived from the collision meshes (``tools/derive_stadium_walls.py``):
wall-type triangles in fair territory, the nearest surface at each ``x``, with
the height of the wall's top there. It is cheap to query, and right everywhere
the wall is a single vertical face. It can't hold a wall whose top slopes, a
tall surface behind a shorter one, or the UNCLIMBABLE_WALL panels the game also
rebounds balls off: Yoshi Park has posts in its fence at 3.5-3.6 where this
says 3.2, and Peach Garden reaches 30.0 where this says 23.0. For those,
``pyrio.sim.play_out`` casts the flight against the mesh itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from . import _files

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .._codes import Stadium
    from ._point import Point

__all__ = ["WallSegment", "clears_wall", "wall_at", "wall_crossing", "walls"]


@dataclass(frozen=True, slots=True)
class WallSegment:
    """A straight stretch of outfield wall, ``start_x <= x < end_x``.

    In plan view the wall runs along ``z = slope * x + intercept``, and it
    stands ``height`` above the field along its whole length.
    """

    start_x: float
    end_x: float
    height: float
    slope: float
    intercept: float

    def z_at(self, x: float) -> float:
        """How deep the wall stands (its ``z``) at ``x``."""
        return self.slope * x + self.intercept


@cache
def walls(stadium: Stadium) -> tuple[WallSegment, ...]:
    """The stadium's outfield wall, foul pole to foul pole, ordered by ``x``."""
    return tuple(
        WallSegment(
            start_x=row["start_x"],
            end_x=row["end_x"],
            height=row["height"],
            slope=row["slope"],
            intercept=row["intercept"],
        )
        for row in _files.wall_table()[stadium.label]
    )


def wall_at(stadium: Stadium, x: float) -> WallSegment | None:
    """The stretch of outfield wall at ``x``, or None beyond the foul poles."""
    for segment in walls(stadium):
        if segment.start_x <= x < segment.end_x:
            return segment
    return None


def clears_wall(stadium: Stadium, trajectory: Iterable[Sequence[float]]) -> bool:
    """Whether the flight passes beyond the outfield wall while above it.

    A quick answer from the wall table: true if any point of ``trajectory`` is
    deeper than the wall at its ``x`` and higher than the wall there. For the
    game's own answer, which also knows the posts, sloped tops and hazards,
    play the hit out with ``pyrio.sim.play_out``.
    """
    for x, y, z in trajectory:
        segment = wall_at(stadium, x)
        if segment is not None and z > segment.z_at(x) and y > segment.height:
            return True
    return False


def wall_crossing(stadium: Stadium, trajectory: Iterable[Sequence[float]]) -> Point | None:
    """Where the flight first reaches the plane of the outfield wall, or None.

    The point is interpolated between the two frames either side of the wall.
    It is where the ball meets the wall whether it clears it or strikes it, so
    it is what a recorded landing should be compared with for a ball that gets
    that far. None if the ball stays in the park or leaves over foul ground,
    where there is no wall.
    """
    points = [tuple(p) for p in trajectory]
    if not points:
        return None
    previous = points[0]
    previous_gap = _gap_to_wall(stadium, previous)
    for current in points[1:]:
        gap = _gap_to_wall(stadium, current)
        if previous_gap is not None and gap is not None and previous_gap < 0.0 <= gap:
            t = previous_gap / (previous_gap - gap)
            return (
                previous[0] + t * (current[0] - previous[0]),
                previous[1] + t * (current[1] - previous[1]),
                previous[2] + t * (current[2] - previous[2]),
            )
        previous, previous_gap = current, gap
    return None


def _gap_to_wall(stadium: Stadium, point: Sequence[float]) -> float | None:
    """Signed distance in ``z`` from the wall (positive past it), or None off the wall."""
    segment = wall_at(stadium, point[0])
    return None if segment is None else point[2] - segment.z_at(point[0])
