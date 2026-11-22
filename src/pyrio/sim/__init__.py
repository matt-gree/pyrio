"""Hit simulation: from a swing to the ball's contact, flight and play-out.

:func:`simulate_hit` reproduces the game's contact stage exactly from the
three RNG values a stat file records, then flies the ball to where it first
comes down. :func:`play_out` carries a flight on from there, against the
stadium's collision mesh and hazards, until the play is settled::

    >>> from pyrio import Character, Hand, PitchType, SwingType
    >>> from pyrio.sim import HitInputs, simulate_hit
    >>> hit = simulate_hit(HitInputs(
    ...     batter=Character.MARIO, pitcher=Character.LUIGI, pitch=PitchType.CURVE,
    ...     swing=SwingType.CHARGE, hand=Hand.RIGHT, batter_x=0.0, ball_x=0.0,
    ... ))
    >>> hit.contact_type
    <ContactType.PERFECT: 2>
"""

from __future__ import annotations

from ._hit import (
    TAG_TO_MOD,
    HitInputs,
    HitOverrides,
    HitResult,
    Mod,
    simulate_all_zones,
    simulate_hit,
    simulate_trajectory,
)

__all__ = [
    "TAG_TO_MOD",
    "HitInputs",
    "HitOverrides",
    "HitResult",
    "Mod",
    "simulate_all_zones",
    "simulate_hit",
    "simulate_trajectory",
]
