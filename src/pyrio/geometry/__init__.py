"""Stadium geometry: walls, the boundary, collision meshes, hazards, the bases and fielders.

Built from the game's own data: the stadium collision meshes, the park sheets
that place each hazard, the boundary outlines and the outfield-wall table
derived from the meshes. Every per-stadium function takes a
:class:`~pyrio.Stadium`; the bases and the fielders are the same at every
park. The data loads on first use, never at import::

    >>> from pyrio import Stadium
    >>> from pyrio.geometry import wall_at
    >>> wall_at(Stadium.MARIO_STADIUM, 0.0).height
    4.0

Coordinates are field units with home plate at the origin (see :data:`Point`).
"""

from __future__ import annotations

from ._boundary import area, boundary, boundary_crossing
from ._fielders import (
    BASE_LOCATIONS,
    FIELDER_LOCKOUT_FRAMES,
    FIELDER_START_LOCATIONS,
    MOUND_LOCATION,
    FielderReach,
    fielder_reach,
)
from ._mesh import Surface, Triangle, triangles
from ._park import Hazard, HazardKind, StadiumPhysics, hazards, physics
from ._point import Point
from ._walls import WallSegment, clears_wall, wall_at, wall_crossing, walls

__all__ = [
    "BASE_LOCATIONS",
    "FIELDER_LOCKOUT_FRAMES",
    "FIELDER_START_LOCATIONS",
    "MOUND_LOCATION",
    "FielderReach",
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
    "fielder_reach",
    "hazards",
    "physics",
    "triangles",
    "wall_at",
    "wall_crossing",
    "walls",
]
