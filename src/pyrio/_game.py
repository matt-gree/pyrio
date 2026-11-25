"""The game model: one stat file, decoded into typed, immutable objects.

Everything here is a frozen, slotted dataclass, built by the decoder in
``_decode.py``. Coded values are enums, a section the file may not have is
``X | None``, and nothing in the model knows which client version wrote the
file: the decoder has already applied every per-version rule.

Units: locations are the game's world coordinates (x across the field, y up,
z from home plate toward center field), velocities are world units per frame,
and angles are the game's raw angle units, 4096 to a full turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ._codes import (
    AtBatResult,
    Bases,
    ChargeType,
    ContactType,
    DeadBallReason,
    FielderAction,
    FielderBobble,
    Hand,
    InputDirection,
    ManualSelect,
    MoonshotStatus,
    OutType,
    PitchType,
    Position,
    PrimaryContactResult,
    PushPull,
    SecondaryContactResult,
    Side,
    Stadium,
    StealType,
    SwingType,
)
from ._stats import BattingLine, PitchingLine

if TYPE_CHECKING:
    from datetime import datetime

    from ._characters import Character
    from ._team_names import TeamName

__all__ = [
    "AtBat",
    "Contact",
    "Event",
    "Fielding",
    "Game",
    "GameResult",
    "GameState",
    "HUDSnapshot",
    "HalfInning",
    "Pitch",
    "RosterSpot",
    "Runner",
    "Team",
    "Version",
]

_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?(?:\.?([A-Za-z]+))?")

_HOME_PLATE = 4  # Runner.end_base for a runner who scored
_MERCY_LEAD = 10  # the mercy rule ends a game on a lead this size
_OUTS_PER_HALF = 3


@dataclass(frozen=True, slots=True, order=True)
class Version:
    """A Project Rio client version, which compares in release order.

    ``Version(2, 3, 0) > Version(2, 2, 0)``, and a lettered build sorts after
    its release: ``Version(0, 1, 7) < Version(0, 1, 7, "a") < Version(0, 1, 8)``.
    """

    major: int
    minor: int
    patch: int = 0
    suffix: str = ""

    @classmethod
    def parse(cls, text: str) -> Version:
        """A version from the string a client writes: ``"2.2.0"``, ``"0.1.7.a"``, ``"0.1.7a"``.

        Raises ``ValueError`` for anything else.
        """
        match = _VERSION.fullmatch(text.strip())
        if match is None:
            raise ValueError(f"{text!r} is not a Project Rio version")
        major, minor, patch, suffix = match.groups()
        return cls(int(major), int(minor), int(patch or 0), (suffix or "").lower())

    def __str__(self) -> str:
        text = f"{self.major}.{self.minor}.{self.patch}"
        return f"{text}.{self.suffix}" if self.suffix else text


@dataclass(frozen=True, slots=True, kw_only=True)
class RosterSpot:
    """One of a team's nine roster spots and the character's game in it.

    Hashable, so spots work as dict keys (``Counter(e.batter_spot for e in
    game.events)``). The per-position counts are left out of equality and the
    hash, since dicts aren't hashable; the rest of the spot identifies it.
    """

    side: Side
    index: int
    """The spot's place in the roster, 0 to 8 (also the batting order)."""
    character: Character
    is_superstar: bool
    is_captain: bool
    fielding_hand: Hand
    batting_hand: Hand
    batting: BattingLine
    pitching: PitchingLine
    was_pitcher: bool
    stamina: int
    """Pitching stamina at the end of the game."""
    big_plays: int
    batters_per_position: dict[Position, int] | None = field(default=None, compare=False)
    """Batters faced while fielding each position, from Rio 1.9.2 on (``None`` before)."""
    pitches_per_position: dict[Position, int] | None = field(default=None, compare=False)
    """Pitches thrown while fielding each position, written only before Rio 1.9.2.

    Rio 1.9.2 replaced this with ``batters_per_position``, a different count.
    """
    batter_outs_per_position: dict[Position, int] = field(
        default_factory=dict[Position, int], compare=False
    )
    """Outs made by the batting team while this character fielded each position."""
    outs_per_position: dict[Position, int] = field(
        default_factory=dict[Position, int], compare=False
    )
    """Outs this character recorded at each position."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Team:
    """One side of a game: the player, the final score and the nine-spot roster."""

    side: Side
    player: str
    score: int
    roster: tuple[RosterSpot, ...]
    """The nine spots; ``roster[i].index == i``."""

    @property
    def captain(self) -> RosterSpot:
        """The captain's spot. The decoder guarantees exactly one."""
        for spot in self.roster:
            if spot.is_captain:
                return spot
        raise ValueError(f"the {self.side} team has no captain")

    @property
    def batting(self) -> BattingLine:
        """The team's batting line: every spot's, summed."""
        return sum((spot.batting for spot in self.roster), BattingLine())

    @property
    def pitching(self) -> PitchingLine:
        """The team's pitching line: every spot's, summed."""
        return sum((spot.pitching for spot in self.roster), PitchingLine())


@dataclass(frozen=True, slots=True, kw_only=True)
class GameState:
    """The situation when a pitch was thrown: inning, count, score and bases."""

    inning: int
    batting_side: Side
    """``Side.AWAY`` in the top of the inning, ``Side.HOME`` in the bottom."""
    balls: int
    strikes: int
    outs: int
    away_score: int
    home_score: int
    away_stars: int | None
    """``None`` when the client didn't record the count."""
    home_stars: int | None
    is_star_chance: bool
    pitcher_stamina: int
    chemistry_links_on_base: int
    bases: Bases
    """The occupied bases."""

    def score(self, side: Side) -> int:
        """One side's runs so far."""
        return self.away_score if side is Side.AWAY else self.home_score

    def stars(self, side: Side) -> int | None:
        """One side's star count, or ``None`` if the client didn't record it."""
        return self.away_stars if side is Side.AWAY else self.home_stars

    @property
    def leader(self) -> Side | None:
        """The side ahead, or ``None`` when the score is level."""
        if self.away_score == self.home_score:
            return None
        return Side.AWAY if self.away_score > self.home_score else Side.HOME


@dataclass(frozen=True, slots=True, kw_only=True)
class Pitch:
    """The pitch thrown in an event, and the batter's swing at it."""

    type: PitchType
    charge_type: ChargeType
    is_star: bool
    is_dickball: bool
    """A straight pitch down the middle: thrown from the center of the mound with
    no curve input. The stat file's ``"DB"``."""
    speed: int
    swing: SwingType
    strike_zone_location: float | None
    """Where the ball crossed the plate relative to the strike zone (from Rio 1.9.2)."""
    is_in_strike_zone: bool | None
    """From Rio 1.9.2; ``None`` before."""
    bat_location: tuple[float, float] | None
    """Where the batter held the bat, ``(x, z)`` (from Rio 1.9.2)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Contact:
    """The ball meeting the bat, and where it went.

    Fields Rio added in 1.9.2 are ``None`` in older files.
    """

    type: ContactType
    swing_frame: int
    """The frame of the swing on which the ball was hit."""
    charge_power_up: float
    charge_power_down: float
    moonshot: MoonshotStatus
    """Before Rio 2.3.0 only a hit moonshot was recorded, so a failed one reads ``NONE``."""
    push_pull: PushPull
    input_direction: InputDirection
    power: int | None
    vertical_angle: int | None
    horizontal_angle: int | None
    absolute: float | None
    """Rio's "Contact Absolute": where along the bat the ball met it, 0 to 200."""
    quality: float | None
    """Rio's "Contact Quality", 0 to 1."""
    rng: tuple[int, int, int] | None
    """The three random numbers the game drew for the hit."""
    velocity: tuple[float, float, float]
    location: tuple[float, float] | None
    """Where the ball was when it met the bat, ``(x, z)``."""
    landing_location: tuple[float, float, float]
    max_height: float
    hang_time_frames: int | None
    primary_result: PrimaryContactResult
    secondary_result: SecondaryContactResult


@dataclass(frozen=True, slots=True, kw_only=True)
class Fielding:
    """The first fielder to touch a batted ball."""

    spot: RosterSpot
    position: Position | None
    """The position the fielder was playing, or ``None`` if Rio recorded none
    (as for a fielder who bobbled the ball, before Rio 0.1.9)."""
    action: FielderAction | None
    """``None`` before Rio 0.1.9, which could write uninitialised memory here."""
    jumped: bool | None
    """``None`` before Rio 0.1.9, as ``action``."""
    manual_select: ManualSelect | None
    """Which fielder the player had selected. ``None`` before Rio 1.9.2, which
    recorded a different value under the same key."""
    location: tuple[float, float, float]
    bobble: FielderBobble


@dataclass(frozen=True, slots=True, kw_only=True)
class Runner:
    """A runner in an event, the batter included: where they started and finished.

    Rio writes the end base when the result is logged, which can be before the
    play finishes; a game-ending play often has none at all. ``Event.runs`` is
    counted from the score instead, so it's always right.
    """

    spot: RosterSpot
    start_base: int
    """0 for the batter, else the base the runner started on."""
    end_base: int | None
    """The base reached, 4 for home; ``None`` when the runner was put out."""
    out_type: OutType
    out_base: int | None
    """The base the runner was put out at, or ``None`` if they weren't."""
    steal: StealType

    @property
    def is_out(self) -> bool:
        return self.out_type is not OutType.NONE

    @property
    def scored(self) -> bool:
        return self.end_base == _HOME_PLATE

    @property
    def bases_advanced(self) -> int:
        """Bases gained on the play: 0 for a runner who was put out or held."""
        return 0 if self.end_base is None else self.end_base - self.start_base


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """One pitch (or pickoff) and what came of it."""

    game_id: int
    """The game this event belongs to, so events from many games can be pooled."""
    number: int
    """Rio's event number. Older clients wrapped it past 255; ``Game.events`` is in order."""
    state: GameState
    batter_spot: RosterSpot
    pitcher_spot: RosterSpot
    catcher_spot: RosterSpot
    result: AtBatResult
    """How the at-bat ended, or ``AtBatResult.NONE`` if it goes on."""
    rbi: int
    runs: int
    """Runs scored on the event, from the change in score."""
    outs_during_play: int | None
    """Outs made on the play. ``None`` before Rio 1.9.2, and when the game ended mid-play."""
    dead_ball_reason: DeadBallReason | None
    """From Rio 2.2.0; ``None`` before."""
    runners: tuple[Runner, ...]
    """The batter (``start_base == 0``) first, then the runners on base."""
    pitch: Pitch | None
    contact: Contact | None
    fielding: Fielding | None

    @property
    def batter(self) -> Character:
        return self.batter_spot.character

    @property
    def pitcher(self) -> Character:
        return self.pitcher_spot.character

    @property
    def catcher(self) -> Character:
        return self.catcher_spot.character

    @property
    def is_first_pitch(self) -> bool:
        """The first pitch of an at-bat: a pitch on an 0-0 count."""
        return self.pitch is not None and self.state.balls == 0 and self.state.strikes == 0

    @property
    def is_last_pitch(self) -> bool:
        """The pitch that ended an at-bat."""
        return self.pitch is not None and self.result is not AtBatResult.NONE

    @property
    def is_hit(self) -> bool:
        """The at-bat ended in a single, double, triple or home run."""
        return self.result.is_hit

    @property
    def is_lead_change(self) -> bool:
        """The event put the batting side ahead when it wasn't before (behind or level)."""
        side = self.state.batting_side
        before = self.state.score(side)
        other = self.state.score(side.other)
        return before <= other < before + self.runs

    @property
    def is_star_pitch(self) -> bool:
        """The pitcher threw a star pitch."""
        return self.pitch is not None and self.pitch.is_star

    @property
    def is_star_swing(self) -> bool:
        """The batter took a star swing, whether or not it made contact."""
        return self.pitch is not None and self.pitch.swing is SwingType.STAR

    @property
    def is_moonshot(self) -> bool:
        """A star swing hit as a moonshot (the community's "five-star dinger")."""
        return self.contact is not None and self.contact.moonshot is MoonshotStatus.MOONSHOT

    @property
    def has_bobble(self) -> bool:
        """The first fielder to touch the ball failed to hold it, in any way."""
        return self.fielding is not None and self.fielding.bobble is not FielderBobble.NONE

    @property
    def has_wall_jump(self) -> bool:
        """The first fielder to touch the ball wall-jumped for it."""
        return self.fielding is not None and self.fielding.action is FielderAction.WALL_JUMP


@dataclass(frozen=True, slots=True, kw_only=True)
class AtBat:
    """One batter's turn at the plate: the events from the first pitch to the result.

    An at-bat that never finished (the third out made on the bases, or a game
    that ended mid-count) has ``result`` ``AtBatResult.NONE``.
    """

    events: tuple[Event, ...]
    """Never empty."""

    @property
    def final(self) -> Event:
        """The last event: the one with the result, if the at-bat finished."""
        return self.events[-1]

    @property
    def batter_spot(self) -> RosterSpot:
        return self.events[0].batter_spot

    @property
    def batter(self) -> Character:
        return self.events[0].batter_spot.character

    @property
    def inning(self) -> int:
        return self.events[0].state.inning

    @property
    def batting_side(self) -> Side:
        return self.events[0].state.batting_side

    @property
    def state(self) -> GameState:
        """The situation when the at-bat began."""
        return self.events[0].state

    @property
    def result(self) -> AtBatResult:
        """How the at-bat ended, or ``AtBatResult.NONE`` if it never finished."""
        return self.final.result

    @property
    def is_complete(self) -> bool:
        return self.final.result is not AtBatResult.NONE

    @property
    def is_star_chance(self) -> bool:
        """The at-bat was a star chance. The game sets this as an at-bat begins
        and holds it to the end."""
        return self.events[0].state.is_star_chance

    @property
    def pitches(self) -> int:
        """Pitches thrown to the batter (events with no pitch, like pickoffs, aren't counted)."""
        return sum(1 for event in self.events if event.pitch is not None)

    @property
    def runs(self) -> int:
        """Runs scored during the at-bat, on the result or before it."""
        return sum(event.runs for event in self.events)

    @property
    def rbi(self) -> int:
        return sum(event.rbi for event in self.events)


def _at_bats(events: tuple[Event, ...]) -> tuple[AtBat, ...]:
    # An at-bat ends on a result, and also, with none, when the next event has
    # a new batter or half inning: a third out made on the bases ends the half
    # without finishing the at-bat.
    groups: list[list[Event]] = []
    for event in events:
        if groups:
            last = groups[-1][-1]
            if (
                last.result is AtBatResult.NONE
                and last.batter_spot == event.batter_spot
                and last.state.inning == event.state.inning
                and last.state.batting_side is event.state.batting_side
            ):
                groups[-1].append(event)
                continue
        groups.append([event])
    return tuple(AtBat(events=tuple(group)) for group in groups)


@dataclass(frozen=True, slots=True, kw_only=True)
class HalfInning:
    """One side's turn at bat."""

    inning: int
    batting_side: Side
    events: tuple[Event, ...]

    @property
    def is_top(self) -> bool:
        return self.batting_side is Side.AWAY

    @property
    def runs(self) -> int:
        return sum(event.runs for event in self.events)

    @property
    def at_bats(self) -> tuple[AtBat, ...]:
        """The half's events grouped into at-bats, in order."""
        return _at_bats(self.events)


@dataclass(frozen=True, slots=True, kw_only=True)
class GameResult:
    """How a game ended."""

    winner: Side | None
    """The side with more runs, however the game ended; ``None`` when level."""
    is_mercy: bool
    """Ended early on the mercy rule: a lead of 10 or more before the last
    inning, with nobody quitting. A trailing home team always bats its half of
    the inning first, so an away mercy win ends in the bottom of an inning."""
    quit_by: Side | None
    """The side whose player quit, if one did."""
    crashed: bool
    """The game was cut off by a crash or a disconnect, not finished."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Game:
    """A whole game, decoded from one stat file by :func:`pyrio.read_game`."""

    id: int
    version: Version
    """The client version that wrote the file."""
    start_time: datetime
    """When the game started. Aware (UTC) from an encoded file; from a decoded
    file it's the naive wall-clock time of the machine that wrote it, since
    decoded files don't record its time zone."""
    end_time: datetime
    """When the game ended; aware or naive as ``start_time``."""
    stadium: Stadium
    tag_set_id: int | None
    """The tag set the game was played under (what the client and site currently
    call a game mode), or ``None`` for none."""
    is_netplay: bool
    loaded_from_hud: bool
    """The game was resumed from a HUD file (Rio 2.2.0 on)."""
    innings_selected: int
    innings_played: int
    average_ping_ms: int
    lag_spikes: int
    away: Team
    home: Team
    events: tuple[Event, ...]
    result: GameResult

    def team(self, side: Side) -> Team:
        """The team on one side."""
        return self.away if side is Side.AWAY else self.home

    @property
    def half_innings(self) -> tuple[HalfInning, ...]:
        """The events grouped into half innings, in order."""
        groups: list[HalfInning] = []
        for event in self.events:
            key = (event.state.inning, event.state.batting_side)
            if groups and (groups[-1].inning, groups[-1].batting_side) == key:
                last = groups[-1]
                groups[-1] = HalfInning(
                    inning=last.inning, batting_side=last.batting_side, events=(*last.events, event)
                )
            else:
                groups.append(HalfInning(inning=key[0], batting_side=key[1], events=(event,)))
        return tuple(groups)

    @property
    def at_bats(self) -> tuple[AtBat, ...]:
        """The events grouped into at-bats, in order; every event is in exactly one.

        Unfinished at-bats are kept (see :class:`AtBat`), so filter on
        ``is_complete`` to count plate appearances.
        """
        return _at_bats(self.events)

    def inning_runs(self, side: Side) -> tuple[int | None, ...]:
        """One side's runs in each inning, for a line score.

        One entry per inning played; ``None`` for a half the side never batted
        (a home team ahead after the top of the last inning).
        """
        last = max(self.innings_played, max((e.state.inning for e in self.events), default=0))
        runs = {h.inning: h.runs for h in self.half_innings if h.batting_side is side}
        return tuple(runs.get(inning) for inning in range(1, last + 1))

    @property
    def lead_changes(self) -> tuple[Event, ...]:
        """The events that put the batting side ahead when it wasn't before."""
        return tuple(event for event in self.events if event.is_lead_change)

    @property
    def walkoff(self) -> Event | None:
        """The game's last event, if the home side won the game on it.

        That is: the home side, batting in the last scheduled inning or later,
        went from behind or level to ahead, and nobody quit or crashed.
        """
        if not self.events or self.result.quit_by is not None or self.result.crashed:
            return None
        last = self.events[-1]
        if (
            last.state.batting_side is Side.HOME
            and last.state.inning >= self.innings_selected
            and last.is_lead_change
            and self.result.winner is Side.HOME
        ):
            return last
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class HUDSnapshot:
    """A HUD file: the live state of a game in progress, read by :func:`pyrio.read_hud`.

    Rio rewrites its HUD file twice an event: once the pitch or pickoff is
    thrown, and again when the play is over. The second (``is_play_over``)
    carries the whole event as :attr:`play`. Clients before 2.2.0 wrote no
    header, so the fields marked as from 2.2.0 are ``None`` for them.
    """

    version: Version
    """The client version that wrote the file, as the caller supplied it."""
    game_id: int | None
    """From Rio 2.2.0."""
    tag_set_id: int | None
    stadium: Stadium | None
    """From Rio 2.2.0."""
    innings_selected: int | None
    """From Rio 2.2.0."""
    away_logo: TeamName | None
    """From Rio 2.2.0."""
    home_logo: TeamName | None
    """From Rio 2.2.0."""
    away_port: int | None
    """The away player's controller port, counted from 0: 0 is port 1 (from Rio 2.2.0)."""
    home_port: int | None
    star_skills: bool | None
    """Superstar skills are on (from Rio 2.2.0)."""
    mercy_rule: bool | None
    """The mercy rule is on (from Rio 2.2.0)."""
    event_number: int
    is_play_over: bool
    """Written when the play ended (Rio's ``"120b"``), not as the pitch was thrown (``"120"``)."""
    away: Team
    home: Team
    """The teams. ``score`` and the stat lines count every play so far, the
    one in :attr:`play` included."""
    away_inning_runs: tuple[int, ...] | None
    """Runs per inning so far, :attr:`play` included (from Rio 2.2.0)."""
    home_inning_runs: tuple[int, ...] | None
    state: GameState
    """The situation as the pitch was thrown: before :attr:`play`, on a play-over file."""
    batter_spot: RosterSpot
    pitcher_spot: RosterSpot
    runners: tuple[Runner, ...]
    """The batter and the runners on base; on a play-over file, with where the play left them."""
    play: Event | None
    """The play that just ended, on a play-over file from Rio 2.2.0 on; ``None``
    otherwise. Its ``state`` is :attr:`state`, the situation before it."""
    fielding_positions: dict[RosterSpot, Position] = field(
        default_factory=dict[RosterSpot, Position], compare=False
    )
    """Where each character is fielding now (from Rio 2.2.0; empty before)."""

    def team(self, side: Side) -> Team:
        """The team on one side."""
        return self.away if side is Side.AWAY else self.home

    def port(self, side: Side) -> int | None:
        """The controller port one side's player is on, or ``None`` before Rio 2.2.0."""
        return self.away_port if side is Side.AWAY else self.home_port

    def fielder(self, position: Position, side: Side | None = None) -> RosterSpot | None:
        """Who is fielding a position, on ``side`` or else the fielding side.

        ``None`` if nobody is recorded there (files before Rio 2.2.0 record no positions).
        """
        side = self.state.batting_side.other if side is None else side
        for spot, at in self.fielding_positions.items():
            if at is position and spot.side is side:
                return spot
        return None

    @property
    def is_game_over(self) -> bool:
        """The play in this file ended the game.

        Rio writes no file after the last play, so this is the only sign a
        game finished rather than paused. A game ends on a walk-off, when a
        half inning ends with the game decided (in the last scheduled inning
        or later, or on the mercy rule's 10-run lead), or after the top half
        when the home side is already ahead. Quits and crashes don't show in
        a HUD file. Needs the 2.2.0 header; ``False`` without it.
        """
        play, innings = self.play, self.innings_selected
        if play is None or innings is None:
            return False
        lead = self.home.score - self.away.score
        regulation = self.state.inning >= innings
        mercy = self.mercy_rule is not False and abs(lead) >= _MERCY_LEAD
        half_over = self.state.outs + (play.outs_during_play or 0) >= _OUTS_PER_HALF
        if self.state.batting_side is Side.HOME:
            if regulation and lead > 0:
                return True
            return half_over and ((regulation and lead != 0) or mercy)
        return half_over and lead > 0 and (regulation or mercy)
