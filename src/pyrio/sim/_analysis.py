"""Game-level hit analysis: each contact's simulated flight, and the game's highlights.

Re-simulating a contact from its recorded RNG values gives what the stat file
can't: the full flight, where a caught ball would have come down, and whether
it would have cleared the wall. The contact stage is exact; the flight is the
hit simulation's model, so landings and wall checks are close approximations,
not the game's record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._codes import AtBatResult, PrimaryContactResult, SecondaryContactResult
from ..geometry import clears_wall

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .._characters import Character
    from .._codes import Side, Stadium, SwingType
    from ..geometry import Point
    from ._hit import HitResult

__all__ = ["ContactRecord", "Highlights", "best", "find_highlights", "format_highlights"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ContactRecord:
    """One ball in play: its place in the game and its simulated flight."""

    event_number: int
    inning: int
    batting_side: Side
    player: str
    """The person controlling the batting team."""

    batter: Character
    swing: SwingType
    result: AtBatResult
    primary_result: PrimaryContactResult
    secondary_result: SecondaryContactResult
    rbi: int
    simulation: HitResult

    @property
    def power(self) -> int:
        return self.simulation.power

    @property
    def distance(self) -> float:
        """How far from home plate the simulated flight comes down."""
        return self.simulation.distance

    @property
    def hang_frames(self) -> int:
        return self.simulation.hang_frames

    @property
    def landing(self) -> Point:
        return self.simulation.landing

    @property
    def trajectory(self) -> tuple[Point, ...]:
        return self.simulation.trajectory

    @property
    def apex_height(self) -> float:
        return self.simulation.apex_height

    @property
    def is_foul(self) -> bool:
        return self.primary_result is PrimaryContactResult.FOUL

    @property
    def is_fair(self) -> bool:
        return not self.is_foul

    @property
    def caught(self) -> bool:
        """Whether a fielder caught it on the fly."""
        return self.secondary_result is SecondaryContactResult.OUT_CAUGHT

    @property
    def is_hit(self) -> bool:
        return self.result.is_hit


@dataclass(frozen=True, slots=True, kw_only=True)
class Highlights:
    """A game's standout contacts. Each is None when no fair ball qualifies."""

    hardest_hit: ContactRecord | None
    longest_flight: ContactRecord | None
    highest_apex: ContactRecord | None
    deepest_robbery: ContactRecord | None
    """The caught ball whose flight would have come down deepest."""

    robbed_home_runs: tuple[ContactRecord, ...]
    """Caught balls whose flight clears the wall. Empty unless a stadium was given."""


def best(
    contacts: Iterable[ContactRecord], key: Callable[[ContactRecord], float]
) -> ContactRecord | None:
    """The contact with the highest ``key``, or None if there are none.

    ``best(contacts, key=lambda c: c.power)`` is the hardest hit. Ties go to
    the earliest contact.
    """
    return max(contacts, key=key, default=None)


def find_highlights(
    contacts: Iterable[ContactRecord], *, stadium: Stadium | None = None
) -> Highlights:
    """The game's highlights, among fair balls.

    With a ``stadium``, also the home runs fielders took away: caught balls
    whose flight clears that stadium's wall (by ``pyrio.geometry.clears_wall``).
    """
    fair = [c for c in contacts if c.is_fair]
    caught = [c for c in fair if c.caught]
    return Highlights(
        hardest_hit=best(fair, key=lambda c: c.power),
        longest_flight=best(fair, key=lambda c: c.distance),
        highest_apex=best(fair, key=lambda c: c.apex_height),
        deepest_robbery=best(caught, key=lambda c: c.distance),
        robbed_home_runs=()
        if stadium is None
        else tuple(c for c in caught if clears_wall(stadium, c.trajectory)),
    )


def format_highlights(highlights: Highlights) -> list[str]:
    """The highlights as one line each, for a report or a chat message."""
    lines: list[str] = []
    if c := highlights.hardest_hit:
        lines.append(
            f"HARDEST HIT: {c.batter} ({c.player}) - {c.power} power {c.result}, inning {c.inning}"
        )
    if c := highlights.longest_flight:
        lines.append(
            f"LONGEST FLIGHT: {c.batter} ({c.player}) - "
            f"{c.distance:.1f} units, {c.result}, inning {c.inning}"
        )
    if c := highlights.highest_apex:
        lines.append(
            f"HIGHEST APEX: {c.batter} ({c.player}) - "
            f"apex {c.apex_height:.1f}, {c.hang_frames} frame hang time"
        )
    if c := highlights.deepest_robbery:
        lines.append(
            f"ROBBERY OF THE GAME: {c.batter} ({c.player}) - caught ball would have "
            f"landed {c.distance:.1f} units deep (inning {c.inning})"
        )
    for c in highlights.robbed_home_runs:
        lines.append(
            f"ROBBED HOME RUN: {c.batter} ({c.player}) - "
            f"inning {c.inning}, trajectory cleared the wall"
        )
    return lines
