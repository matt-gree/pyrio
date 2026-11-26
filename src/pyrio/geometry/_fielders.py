"""The bases, where fielders stand when the pitch is thrown, and how far they can get.

All from the game's tables (mssb-dtk ``gameplay_tables.c``) and the same at
every stadium.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from .._characters import Ability
from .._codes import Position

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .._characters import Character
    from ._point import Point

__all__ = [
    "BASE_LOCATIONS",
    "FIELDER_LOCKOUT_FRAMES",
    "FIELDER_START_LOCATIONS",
    "MOUND_LOCATION",
    "FielderReach",
    "fielder_reach",
]

BASE_LOCATIONS: tuple[Point, Point, Point, Point] = (
    (0.05, 0.0, 0.25),
    (18.95, 0.0, 19.4),
    (0.1, 0.0, 39.0),
    (-18.95, 0.0, 19.4),
)
"""Home plate, first, second and third base, indexed as ``Runner`` numbers them.

``BASE_LOCATIONS[0]`` is home (a runner who scores reaches base 4, home again).
The game's ``base_MoundCoordinates``. Runners run to slightly different points
(``baseCoordsForRunning``: first base at ``(18.8, 19.4)``), so a runner's path
isn't measured from these.
"""

MOUND_LOCATION: Point = (0.0, 0.0, 18.5)
"""The middle of the pitcher's mound (``base_MoundCoordinates[4]``)."""

FIELDER_START_LOCATIONS: Mapping[Position, Point] = MappingProxyType(
    {
        Position.PITCHER: (0.0, 0.22299999, 18.3999996),
        Position.CATCHER: (0.0, 0.0, -3.7999995),
        Position.FIRST_BASE: (18.5, 0.0, 22.0),
        Position.SECOND_BASE: (11.0, 0.0, 36.0),
        Position.THIRD_BASE: (-18.5, 0.0, 22.0),
        Position.SHORTSTOP: (-11.0, 0.0, 36.0),
        Position.LEFT_FIELD: (-34.0, 0.0, 60.0),
        Position.CENTER_FIELD: (0.0, 0.0, 76.0),
        Position.RIGHT_FIELD: (34.0, 0.0, 60.0),
    }
)
"""Each fielder's starting location, the same at every stadium.

The ``x`` and ``z`` match the game's ``fieldingStartingCoords_regular``, except
the pitcher's: that table has ``z`` 18.6, where this has the 18.4 (and the
height of the mound) that pyrio has always used. Which one fielding data
should be measured from is not yet settled.
"""

FIELDER_LOCKOUT_FRAMES: Mapping[Position, int] = MappingProxyType(
    {
        Position.PITCHER: 25,
        Position.CATCHER: 40,
        Position.FIRST_BASE: 16,
        Position.SECOND_BASE: 15,
        Position.THIRD_BASE: 18,
        Position.SHORTSTOP: 17,
        Position.LEFT_FIELD: 50,
        Position.CENTER_FIELD: 50,
        Position.RIGHT_FIELD: 50,
    }
)
"""Frames after contact before a human-controlled fielder can move.

The human row of the game's ``fielderLockout`` table. The computer's fielders
are locked out longer at some positions, plus a random delay.
"""


# setFielderVelocity_someSituation and roster_init.c: a fielder speeds up by a
# fifteenth of their jogging speed each frame until they reach it.
_ACCELERATION_FRAMES = 15
# updateSprintPointers: each sprint press adds 10 charge, up to 50, and a
# sprinting fielder runs at 1 + 0.4 * charge / 50 times jogging speed, set
# directly rather than accelerated to.
_SPRINT_CHARGE_PER_PRESS = 10
_SPRINT_FULL_CHARGE = 50
_SPRINT_BONUS = 0.4
_SPRINT_PRESS_FRAMES = 3  # a quick human's mashing, as the frontend's runner model takes it
# divingCatch, for a ball in the air: a dive starts once the ball is this many
# frames from coming down (slidingCatchArray), never fewer than 6 out, and the
# running the dive covers counts this much more (slidingCatchMultipliers).
_DIVE_WINDOW_FRAMES = 45
_SLIDING_CATCH_DIVE_WINDOW_FRAMES = 60
_MIN_DIVE_FRAMES = 6
_SLIDING_CATCH_DIVE_RUN = 1.2


@dataclass(frozen=True, slots=True, kw_only=True)
class FielderReach:
    """How far a fielder can get from their starting spot by a frame after contact.

    Distances are along the ground (``x`` and ``z``), in field units.
    """

    character: Character
    position: Position
    start: Point
    frames: int
    """Frames after contact, the lockout included."""
    running: float
    """How far the fielder can run."""
    diving: float
    """How far a diving catch reaches; ``running`` when the ball comes down too
    soon after the lockout for a dive."""

    def distance_to(self, point: Point) -> float:
        """How far ``point`` is from the fielder's starting spot, along the ground."""
        return math.hypot(point[0] - self.start[0], point[2] - self.start[2])

    def reaches(self, point: Point, *, dive: bool = True) -> bool:
        """Whether the fielder can get to ``point`` in time, diving if ``dive``."""
        return self.distance_to(point) <= (self.diving if dive else self.running)


def fielder_reach(
    character: Character,
    position: Position,
    frames: int,
    *,
    is_superstar: bool = False,
    sprint: bool = True,
) -> FielderReach:
    """How far a human-controlled fielder can get ``frames`` frames after contact.

    The game's movement: the fielder is locked out for
    ``FIELDER_LOCKOUT_FRAMES[position]``, starts from ``FIELDER_START_LOCATIONS``,
    accelerates to their jogging speed over 15 frames and, with ``sprint``,
    mashes the sprint button every third frame, reaching the full 1.4 times
    jogging speed after five presses. They run straight at the ball.

    ``diving`` is the game's diving-catch reach for a fly ball that comes down
    at ``frames`` (one whose apex is at least 5 high): a dive starts 45 frames
    before the ball lands (60 with Sliding Catch), covers the running left
    until then (1.2 times as far with Sliding Catch) plus the character's
    ``dive_range``. Computer fielders are locked out longer, so this is the
    most any fielder at the position can reach.
    """
    if frames < 0:
        raise ValueError(f"frames must be 0 or more, not {frames}")
    attributes = character.attributes.with_superstar() if is_superstar else character.attributes
    jogging = attributes.jogging_speed
    control = max(frames - FIELDER_LOCKOUT_FRAMES[position], 0)

    covered = [0.0]  # covered[t]: distance run in the first t frames of control
    speed = 0.0
    for t in range(control):
        presses = -(-t // _SPRINT_PRESS_FRAMES) if sprint else 0  # presses before frame t
        charge = min(presses * _SPRINT_CHARGE_PER_PRESS, _SPRINT_FULL_CHARGE)
        if charge:
            speed = jogging * (1 + _SPRINT_BONUS * charge / _SPRINT_FULL_CHARGE)
        else:
            speed = min(speed + jogging / _ACCELERATION_FRAMES, jogging)
        covered.append(covered[-1] + speed)
    running = covered[control]

    sliding = Ability.SLIDING_CATCH in attributes.abilities
    window = _SLIDING_CATCH_DIVE_WINDOW_FRAMES if sliding else _DIVE_WINDOW_FRAMES
    until_landing = min(control, window)
    dive_frame = until_landing - 1
    diving = running
    if dive_frame >= _MIN_DIVE_FRAMES:
        before = covered[control - until_landing]
        during = covered[control - until_landing + dive_frame] - before
        scale = _SLIDING_CATCH_DIVE_RUN if sliding else 1.0
        diving = max(running, before + during * scale + attributes.dive_range)

    return FielderReach(
        character=character,
        position=position,
        start=FIELDER_START_LOCATIONS[position],
        frames=frames,
        running=running,
        diving=diving,
    )
