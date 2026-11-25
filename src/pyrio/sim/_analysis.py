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

from .._codes import (
    AtBatResult,
    DeadBallReason,
    PrimaryContactResult,
    SecondaryContactResult,
    SwingType,
)
from ..geometry import clears_wall
from ._hit import HitInputs, simulate_hit
from ._live_ball import LiveBallOutcome, hazard_seed, play_out

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .._characters import Character
    from .._codes import Side, Stadium
    from .._game import Contact, Event, Game
    from ..geometry import Point
    from ._hit import HitResult, Mod
    from ._live_ball import LiveBallResult

__all__ = [
    "ContactRecord",
    "Highlights",
    "best",
    "find_highlights",
    "format_highlights",
    "simulate_contacts",
]

_SIMULATED_SWINGS = (SwingType.SLAP, SwingType.CHARGE, SwingType.STAR)


@dataclass(frozen=True, slots=True, kw_only=True)
class ContactRecord:
    """One ball in play: the event that recorded it and its simulated hit."""

    event: Event
    player: str
    """The person controlling the batting team."""

    hit: HitResult
    """The contact simulated again from the event's recorded RNG values."""

    @property
    def event_number(self) -> int:
        return self.event.number

    @property
    def inning(self) -> int:
        return self.event.state.inning

    @property
    def batting_side(self) -> Side:
        return self.event.state.batting_side

    @property
    def batter(self) -> Character:
        return self.event.batter

    @property
    def swing(self) -> SwingType:
        assert self.event.pitch is not None  # simulate_contacts keeps only swings
        return self.event.pitch.swing

    @property
    def result(self) -> AtBatResult:
        return self.event.result

    @property
    def contact(self) -> Contact:
        assert self.event.contact is not None  # simulate_contacts keeps only contacts
        return self.event.contact

    @property
    def rbi(self) -> int:
        return self.event.rbi

    @property
    def power(self) -> int:
        return self.hit.power

    @property
    def distance(self) -> float:
        """How far from home plate the simulated flight comes down."""
        return self.hit.distance

    @property
    def hang_frames(self) -> int:
        return self.hit.hang_frames

    @property
    def landing(self) -> Point:
        return self.hit.landing

    @property
    def trajectory(self) -> tuple[Point, ...]:
        return self.hit.trajectory

    @property
    def apex_height(self) -> float:
        return self.hit.apex_height

    @property
    def is_foul(self) -> bool:
        return self.contact.primary_result is PrimaryContactResult.FOUL

    @property
    def is_fair(self) -> bool:
        return not self.is_foul

    @property
    def caught(self) -> bool:
        """Whether a fielder caught it on the fly."""
        return self.contact.secondary_result is SecondaryContactResult.OUT_CAUGHT

    @property
    def is_hit(self) -> bool:
        return self.result.is_hit

    def play_out(
        self,
        *,
        hazards: bool = True,
        seed: int | None = None,
        max_frames: int = 1500,
        roll_frames: int = 420,
    ) -> LiveBallResult:
        """The ball played out in the park, ending where the stat file says the play did.

        A ball caught on the fly stops in the glove, at the recorded catch. Any
        other ball plays out (:func:`pyrio.sim.play_out`) until it comes down
        and reaches the first fielder who touched it, or stops, or leaves the
        park.

        The game rolls dice for its hazards (how fast a Thwomp falls, which way
        a tornado spins) that no stat file records. Without a ``seed``, this
        tries the hit's default dice and then others, and keeps the first play
        that ends the way the record says: a home run, a foul, a ground-rule
        double, or a ball that stayed in play. If none does (the flight is the
        simulation's, so a ball that barely cleared the wall may not), it
        returns the default dice's play.
        """
        contact, fielding = self.contact, self.event.fielding
        if self.caught:
            return play_out(self.hit, caught_at=contact.landing_location)
        stop_at = None if fielding is None else (fielding.location[0], fielding.location[2])

        def attempt(dice: int | None) -> LiveBallResult:
            return play_out(
                self.hit,
                seed=dice,
                hazards=hazards,
                max_frames=max_frames,
                roll_frames=roll_frames,
                stop_at=stop_at,
            )

        first = attempt(seed)
        if seed is not None or not hazards or self._agrees(first.outcome):
            return first
        base = hazard_seed(self.hit.inputs.seeds)
        for offset in range(1, _DICE_TRIES):
            played = attempt(base + offset)
            if self._agrees(played.outcome):
                return played
        return first

    def _agrees(self, outcome: LiveBallOutcome) -> bool:
        """Whether a played-out ball ends the way the stat file recorded."""
        reason = self.event.dead_ball_reason
        if self.result is AtBatResult.HOME_RUN or reason is DeadBallReason.HOME_RUN:
            return outcome is LiveBallOutcome.HOME_RUN
        if self.is_foul or reason is DeadBallReason.FOUL_BALL:
            return outcome is LiveBallOutcome.FOUL
        if reason is DeadBallReason.GROUND_RULE_DOUBLE:
            return outcome is LiveBallOutcome.GROUND_RULE_DOUBLE
        return outcome not in _DEAD_BALLS


_DICE_TRIES = 16
_DEAD_BALLS = frozenset(
    {LiveBallOutcome.HOME_RUN, LiveBallOutcome.FOUL, LiveBallOutcome.GROUND_RULE_DOUBLE}
)


def simulate_contacts(
    game: Game, *, mods: frozenset[Mod] = frozenset()
) -> tuple[ContactRecord, ...]:
    """Every slap, charge and star swing the batter connected on, simulated again.

    Each contact is rebuilt with :meth:`HitInputs.from_event` from the RNG
    values the stat file records, at the game's stadium, in event order.
    Bunts aren't simulated, and a file from a client too old to record the
    RNG gives an empty tuple. ``mods`` are the gecko codes the game was
    played with.
    """
    records: list[ContactRecord] = []
    for event in game.events:
        pitch, contact = event.pitch, event.contact
        if pitch is None or contact is None or contact.rng is None:
            continue
        if pitch.swing not in _SIMULATED_SWINGS:
            continue
        inputs = HitInputs.from_event(event, stadium=game.stadium, mods=mods)
        records.append(
            ContactRecord(
                event=event,
                player=game.team(event.state.batting_side).player,
                hit=simulate_hit(inputs),
            )
        )
    return tuple(records)


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
