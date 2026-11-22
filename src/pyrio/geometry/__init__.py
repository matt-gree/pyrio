"""Stadium geometry: walls, the boundary, collision meshes, hazards and fielders.

Built from the game's own data: the stadium collision meshes, the park sheets
that place each hazard, the boundary outlines and the outfield-wall table
derived from the meshes. Every per-stadium function takes a
:class:`~pyrio.Stadium`. The data loads on first use, never at import::

    >>> from pyrio import Stadium
    >>> from pyrio.geometry import wall_at
    >>> wall_at(Stadium.MARIO_STADIUM, 0.0).height
    4.0

Coordinates are field units with home plate at the origin (see :data:`Point`).
"""

from __future__ import annotations

from ._boundary import area, boundary, boundary_crossing
from ._fielders import FIELDER_LOCKOUT_FRAMES, FIELDER_START_LOCATIONS
from ._mesh import Surface, Triangle, triangles
from ._park import Hazard, HazardKind, StadiumPhysics, hazards, physics
from ._point import Point
from ._walls import WallSegment, clears_wall, wall_at, wall_crossing, walls

__all__ = [
    "FIELDER_LOCKOUT_FRAMES",
    "FIELDER_START_LOCATIONS",
    "Hazard",
    "HazardKind",
    "Point",
    "StadiumPhysics",
    "Surface",
    "Triangle",
    "WallSegment",
    "area",
    "boundary",
    "boundary_crossing",
    "clears_wall",
    "hazards",
    "physics",
    "triangles",
    "wall_at",
    "wall_crossing",
    "walls",
]
