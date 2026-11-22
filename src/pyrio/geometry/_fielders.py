"""Where fielders stand when the pitch is thrown, and how long they're locked out."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from .._codes import Position

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ._point import Point

__all__ = ["FIELDER_LOCKOUT_FRAMES", "FIELDER_START_LOCATIONS"]

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
