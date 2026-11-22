"""Each stadium's hazards and surface physics, from its park sheet.

The park sheets come from RioVisualizer, which built them from the decomp's
``sta_c1.c`` .. ``sta_c6.c``. ``.park.json`` is an internal file format: outside
``pyrio.geometry`` only the live ball reads it, for the hazards' behaviour.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from . import _files

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .._codes import Stadium
    from ._point import Point

__all__ = ["Hazard", "HazardKind", "StadiumPhysics", "hazards", "physics"]


class HazardKind(Enum):
    """The kinds of hazard and set piece a stadium can have.

    The value is the park sheet's spelling.
    """

    STAR_PAD = "starPad"  # Bowser Castle's star panels, Wario Palace's sand stars
    THWOMP = "thwomp"
    FIRE_GRATE = "fireGrate"
    LAVA_POOL = "lavaPool"
    VINE = "vine"
    CANNON = "cannon"
    KLAPTRAP = "klaptrap"
    PALM = "palm"
    BLOCK = "block"  # Peach Garden's floating blocks
    FOUNTAIN = "fountain"
    HEDGE = "hedge"
    PANEL = "panel"  # Toy Field's floor panels
    WALL_PANEL = "wallPanel"
    CHOMP = "chomp"
    TORNADO = "tornado"
    PIRANHA = "piranha"
    WINDMILL = "windmill"


@dataclass(frozen=True, slots=True)
class Hazard:
    """One hazard or set piece, as the park sheet places it.

    ``parameters`` is the sheet's whole entry for it: the behaviour constants
    (a Thwomp's slam cycle, a tornado's spin, a panel's label) that the live
    ball reads. A lava pool is a patch of ground with no single location, so
    its ``location`` is None.
    """

    id: str
    kind: HazardKind
    location: Point | None
    yaw_deg: float
    parameters: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StadiumPhysics:
    """How a stadium's ground and walls treat a ball.

    The ``*_keep`` values are the fraction of a velocity component the ball
    keeps through a contact: vertical on its first bounce and on later ones,
    horizontal on landing, on later bounces, and while rolling, and all of it
    off a wall.
    """

    ground_height: float
    """The height of the ground plane the ball bounces on."""

    first_bounce_vertical_keep: float
    bounce_vertical_keep: float
    landing_horizontal_keep: float
    bounce_horizontal_keep: float
    rolling_horizontal_keep: float
    wall_keep: float

    has_flat_floor: bool
    """Whether the ground has no holes, so a ball below it is lifted back onto it.

    False at Bowser Castle and Toy Field, whose ground has pits; there only the
    mesh can say where the floor is.
    """


@cache
def physics(stadium: Stadium) -> StadiumPhysics:
    """The stadium's ground and wall physics."""
    sheet = _files.park_sheet(stadium)["physics"]
    first, later, landing, bounce, rolling = sheet["bounce"]
    return StadiumPhysics(
        ground_height=sheet["groundY"],
        first_bounce_vertical_keep=first,
        bounce_vertical_keep=later,
        landing_horizontal_keep=landing,
        bounce_horizontal_keep=bounce,
        rolling_horizontal_keep=rolling,
        wall_keep=sheet["wall"],
        has_flat_floor=sheet["floorClamp"],
    )


@cache
def hazards(stadium: Stadium) -> tuple[Hazard, ...]:
    """The stadium's hazards and set pieces, in the park sheet's order."""
    out: list[Hazard] = []
    for entry in _files.park_sheet(stadium)["hazards"]:
        location = entry.get("pos")
        out.append(
            Hazard(
                id=entry["id"],
                kind=HazardKind(entry["kind"]),
                location=None if location is None else (location[0], location[1], location[2]),
                yaw_deg=float(entry.get("yaw", 0.0)),
                parameters=MappingProxyType(copy.deepcopy(entry)),
            )
        )
    return tuple(out)
