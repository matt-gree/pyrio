"""The hit simulation: from a swing's inputs to the ball's contact and flight.

A port of the batting calculator (``index.js``), which follows the game's
``calculateHitVariables``: contact, horizontal angle, vertical angle, power,
velocity, then the flight. Given the three RNG values a stat file records for a
contact, the contact stage reproduces the game exactly. The flight is the
calculator's model, which ends where the ball first comes down; the live ball
(:func:`pyrio.sim.play_out`) carries on from there.

The arithmetic and its order are the game's, so they are kept exactly as
ported: rewriting a formula to taste is how a reproduction stops reproducing.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from .._characters import CaptainStar, Character, StarSwing
from .._codes import (
    ChargeType,
    ContactType,
    Hand,
    InputDirection,
    MoonshotStatus,
    PitchType,
    Side,
    Stadium,
    SwingType,
)
from ..geometry import physics
from . import _tables as tables
from ._physics import GRAVITY_PER_FRAME_SQUARED, VELOCITY_KEPT_PER_FRAME

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .._game import Event
    from ..geometry import Point

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


_NO_STICK: Final = InputDirection(0)


class Mod(Enum):
    """A gecko code that changes how hits behave. The value is Rio's tag for it."""

    FIX_NON_RED_TOAD_REACH = "Fix Non-red Toad Hitboxes and Bat Reach"
    """The blue, yellow, green and purple Toads get the red Toad's bat reach."""

    REMOVE_SLICE = "Remove slice"
    """An earliest- or latest-frame contact goes foul instead of dead up the middle."""


TAG_TO_MOD: Mapping[str, Mod] = MappingProxyType({mod.value: mod for mod in Mod})
"""The mod each Rio web tag turns on, for building ``HitInputs.mods`` from a game's tags."""


@dataclass(frozen=True, slots=True, kw_only=True)
class HitOverrides:
    """Decisions to force instead of letting the game make them.

    Every field defaults to None, which leaves that decision to the game. A
    forced value replaces what the game would have computed at that step; any
    random draw the step makes still happens, so later steps see the same
    random state as in the game.
    """

    vertical_zone: int | None = None
    """Which of the five vertical zones (0-4) the hit takes.

    No effect on a hit whose vertical angle doesn't come from the zones: star
    swings, moonshots, and hit types that force a zone.
    """

    horizontal_angle_raw: int | None = None
    """The final horizontal angle, in raw units (4096 to a turn)."""

    vertical_angle_raw: int | None = None
    """The vertical angle, in raw units, before angles past straight up fold back."""

    power: int | None = None
    """The hit's power."""

    banana_start_frame: int | None = None
    """The frame the DK and Diddy banana curve turns on (the game: a quarter of the hang time)."""

    banana_end_frame: int | None = None
    """The frame the banana curve turns off (the game: 95% of the hang time)."""

    banana_hand: Hand | None = None
    """Which way the banana curves, as for a batter of this hand (the game: the batter's)."""

    garlic_spread_rad: float | None = None
    """How far each Wario and Waluigi garlic ball turns from the hit's heading.

    The game rolls each side separately, between 0.2 and 0.3.
    """

    garlic_real_ball_to_left: bool | None = None
    """Whether the real garlic ball is the one turned toward left field (the game rolls it)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class HitInputs:
    """Everything that decides a batted ball: the players, the pitch, and the swing.

    Positions are in field units. ``batter_x`` and ``ball_x`` are as a stat file
    records them: relative to the batter, mirrored for a left-handed batter.

    **Star swings.** Give what the player controls: ``swing=SwingType.STAR``,
    the team's ``stars``, whether the batter ``is_captain``, and the charge as
    held (``charge_up=1.0`` for a fully charged swing). The library then
    decides the swing the way the game does: a fully charged star swing with
    five stars is a moonshot; a captain's star swing costs one star, a
    captain-class character's two when someone else is captain, and anyone
    else's star swing one. Without the stars it's a plain slap, or a charge
    swing if the batter was charging. A star swing always starts from zero
    charge, as the game resets it.
    """

    batter: Character
    pitcher: Character
    pitch: PitchType
    charge: ChargeType | None = None
    """What a charge pitch was: ``SLIDER``, ``PERFECT`` or ``CAPTAIN_STAR``. None otherwise."""

    swing: SwingType
    """``SLAP``, ``CHARGE`` or ``STAR``. Bunts aren't simulated."""

    hand: Hand
    """The batter's hand."""

    stick: InputDirection = _NO_STICK
    """The stick directions held at contact."""

    batter_x: float
    """The batter's ``x`` in the box at contact (the stat file's ``Bat Contact Pos - X``)."""

    ball_x: float
    """The ball's ``x`` at contact, where the flight starts."""

    ball_z: float = 0.0
    """The ball's ``z`` at contact, where the flight starts."""

    charge_up: float = 0.0
    """How far the swing was charged, 0 to 1."""

    charge_down: float = 0.0
    """How much of a full charge was still held at release, 0 to 1."""

    contact_frame: int = 5
    """The frame of the swing the ball was met on, 2 to 10."""

    chem_links_on_base: int = 0
    """Chemistry links between the batter and runners on base, 0 to 3."""

    stars: int = 0
    """The batting team's stars, 0 to 5."""

    is_captain: bool = False
    """Whether the batter is the team's captain."""

    batter_is_superstar: bool = False
    pitcher_is_superstar: bool = False
    is_easy_batting: bool = False

    stadium: Stadium = Stadium.MARIO_STADIUM
    """Where the hit is played: it decides the ground height and whether the ground bounces."""

    mods: frozenset[Mod] = frozenset()
    seeds: tuple[int, int, int] = tables.DEFAULT_SEEDS
    """The three RNG values a stat file records for the contact (``RNG1``-``RNG3``)."""

    overrides: HitOverrides = HitOverrides()

    @classmethod
    def from_event(
        cls, event: Event, *, stadium: Stadium, mods: frozenset[Mod] = frozenset()
    ) -> HitInputs:
        """The inputs that produced a recorded contact, to simulate it again.

        ``stadium`` is the game's (``game.stadium``); ``mods`` are the gecko mods
        the game was played with, which a stat file doesn't record (see
        ``TAG_TO_MOD``). Raises ``ValueError`` for an event with no contact, a
        bunt, or a file too old to record the swing's RNG.

        A star swing is rebuilt from what the player did: five-star moonshots
        are fully charged. One without the stars to spend it ("Walu tech") was a
        charge swing with no charge held, which is what the game played.
        """
        pitch, contact = event.pitch, event.contact
        if pitch is None or contact is None:
            raise ValueError(f"event {event.number} has no contact to simulate")
        if contact.rng is None or contact.location is None or pitch.bat_location is None:
            raise ValueError(f"event {event.number} is from a client too old to simulate")
        batter, pitcher = event.batter_spot, event.pitcher_spot
        state = event.state
        stars = state.away_stars if state.batting_side is Side.AWAY else state.home_stars
        swing = pitch.swing
        charge_up, charge_down = contact.charge_power_up, contact.charge_power_down
        if swing is SwingType.STAR:
            off_captain = batter.character.attributes.captain_star is not None and not (
                batter.is_captain
            )
            if stars == 0 or (stars == 1 and off_captain):
                swing, charge_down = SwingType.CHARGE, 0.0
            elif contact.moonshot is MoonshotStatus.MOONSHOT:
                charge_up = 1.0
        return cls(
            batter=batter.character,
            pitcher=pitcher.character,
            pitch=pitch.type,
            charge=None if pitch.charge_type is ChargeType.NONE else pitch.charge_type,
            swing=swing,
            hand=batter.batting_hand,
            stick=contact.input_direction,
            batter_x=pitch.bat_location[0],
            ball_x=contact.location[0],
            ball_z=contact.location[1],
            charge_up=charge_up,
            charge_down=charge_down,
            contact_frame=contact.swing_frame,
            chem_links_on_base=state.chemistry_links_on_base,
            stars=stars,
            is_captain=batter.is_captain,
            batter_is_superstar=batter.is_superstar,
            pitcher_is_superstar=pitcher.is_superstar,
            stadium=stadium,
            mods=mods,
            seeds=contact.rng,
        )

    def __post_init__(self) -> None:
        if self.swing not in (SwingType.SLAP, SwingType.CHARGE, SwingType.STAR):
            raise ValueError(f"can't simulate a {self.swing.label} swing: only slap, charge, star")
        charged = self.charge not in (None, ChargeType.NONE)
        if (self.pitch is PitchType.CHARGE) != charged:
            raise ValueError(
                "a charge pitch needs its charge type, and only a charge pitch has one: "
                f"got {self.pitch.label} with {self.charge}"
            )
        if not 0 <= self.stars <= 5:
            raise ValueError(f"stars must be 0 to 5, not {self.stars}")
        if not 0 <= self.chem_links_on_base <= 3:
            raise ValueError(f"chem_links_on_base must be 0 to 3, not {self.chem_links_on_base}")
        if not 0 <= self.contact_frame < len(tables.HORIZONTAL_ANGLE_RANGES[0][0]):
            raise ValueError(f"contact_frame {self.contact_frame} is outside the swing")


@dataclass(frozen=True, slots=True, kw_only=True)
class HitResult:
    """A simulated hit: where it met the bat, how it left, and its flight."""

    contact_type: ContactType
    contact_absolute: float
    """Where on the bat the ball was met, 0 to 200 (the stat file's ``Contact Absolute``)."""

    contact_quality: float
    """How good the contact was within its type, 0 to 1."""

    horizontal_angle_raw: int
    """Raw units, 4096 to a turn; 1024 is straight up the middle."""

    vertical_angle_raw: int
    horizontal_angle_deg: float
    """Degrees from straight up the middle."""

    vertical_angle_deg: float
    power: int
    """The game's hit power (the stat file's ``Ball Power``)."""

    velocity_per_frame: Point
    acceleration_per_frame: Point
    """The steady push the curve and the contact's added gravity give each frame."""

    ball_energy: float
    """How hard the ball plows through fielders (a fully charged clean hit: its power)."""

    star_swing: CaptainStar | StarSwing | None
    """The star swing the batter got, or None for a regular swing or a moonshot."""

    moonshot: MoonshotStatus
    trajectory: tuple[Point, ...] = field(repr=False)
    """The flight, one point per frame from contact to one frame after it first lands."""

    garlic_trajectory: tuple[Point, ...] | None = field(repr=False)
    """The second garlic ball's flight from the split, or None for any other hit."""

    @property
    def landing(self) -> Point:
        """Where the flight ends, one frame after it first comes down."""
        return self.trajectory[-1]

    @property
    def distance(self) -> float:
        """Horizontal distance from home plate to the landing."""
        x, _, z = self.landing
        return math.sqrt(x**2 + z**2)

    @property
    def hang_frames(self) -> int:
        """Frames in the flight, counting the contact point."""
        return len(self.trajectory)

    @property
    def apex_height(self) -> float:
        """The flight's highest point."""
        return max(p[1] for p in self.trajectory)


def simulate_hit(inputs: HitInputs) -> HitResult:
    """Simulate one hit. Raises ValueError if the ball is out of the bat's reach."""
    return _Simulation(inputs).run()


def simulate_trajectory(inputs: HitInputs, frames: int) -> tuple[Point, ...]:
    """The hit's path for a fixed number of frames, bouncing along the ground.

    Where :func:`simulate_hit`'s flight stops when the ball comes down, this
    carries on through ground contacts with the flight model's bounce, which
    is the game's at a stadium with a flat floor and an approximation (a skid)
    at Bowser Castle and Toy Field. Returns ``frames + 1`` points, the first
    at contact. For the game's own play-out, use :func:`pyrio.sim.play_out`.
    """
    simulation = _Simulation(inputs)
    simulation.contact()
    return simulation.fly(max_frames=frames)


def simulate_all_zones(inputs: HitInputs) -> tuple[HitResult, ...]:
    """The hit once per vertical zone (0-4), everything else unchanged.

    Shows how the zone the game rolls moves the hit. A hit whose vertical
    angle doesn't come from the zones gives five identical results.
    """
    return tuple(
        simulate_hit(replace(inputs, overrides=replace(inputs.overrides, vertical_zone=zone)))
        for zone in range(5)
    )


# --- the game's internal codes -------------------------------------------------

# General swing type (hitGeneralType).
_SLAP, _CHARGE, _STAR, _BUNT = 0, 1, 2, 3
# Contact type (ContactType ids).
_SOUR_LEFT, _NICE_LEFT, _PERFECT, _NICE_RIGHT, _SOUR_RIGHT = 0, 1, 2, 3, 4
# Hit types (hit type rows of HIT_TYPE_EFFECTS) that the contact stage builds on.
_SOUR_SLAP, _NICE_SLAP, _PERFECT_SLAP, _SOUR_CHARGE = 0x0, 0x1, 0x2, 0x3
_SOUR_CHANGE_UP_SLAP, _SOUR_CHANGE_UP_CHARGE = 0x6, 0x9
_PERFECT_PITCH_SOUR_SLAP, _PERFECT_PITCH_SOUR_CHARGE = 0xC, 0xF
# Stick direction relative to the batter (PushPull ids).
_NO_PUSH_PULL, _PULL, _PUSH = 0, 1, 2
# Star swing costs (starPowerCosts).
_MOONSHOT_COST, _CAPTAIN_STAR_COST, _OFF_CAPTAIN_STAR_COST, _STAR_COST = 5, 1, 2, 1

_NON_RED_TOADS = frozenset({Character.TOAD_B, Character.TOAD_Y, Character.TOAD_G, Character.TOAD_P})


def _truncate(x: float) -> int:
    """The calculator's ``floor``, which truncates toward zero."""
    return math.trunc(x)


def _to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _f32(x: float) -> float:
    """Narrow to single precision, where the game's ``(float)`` cast changes a result."""
    value: float = struct.unpack("f", struct.pack("f", x))[0]
    return value


def _wrap_angle(a: int) -> int:
    return a % 0x1000


def _raw_to_rad(raw: int) -> float:
    if raw < 0:
        raw += 0x1000
    if raw > 0xFFF:
        raw += -0x1000
    rad = (math.pi * (raw << 1)) / 4096
    if math.pi < rad:
        rad = -(2 * math.pi - rad)
    return rad


def _interpolate(
    value: float, from_low: float, from_high: float, to_low: float, to_high: float
) -> float:
    """``LinearInterpolateToNewRange``, with the fraction clamped to [0, 1]."""
    if (from_high - from_low) == 0:
        fraction = 1.0
    else:
        fraction = 1.0
        calculated = (value - from_low) / (from_high - from_low)
        if calculated <= fraction:
            fraction = calculated
            if calculated < 0.0:
                fraction = 0.0
    return (to_high - to_low) * fraction + to_low


class _Simulation:
    """One hit, worked through the game's steps in order."""

    def __init__(self, inputs: HitInputs) -> None:
        self.inputs = inputs
        overrides = inputs.overrides
        self.overrides = overrides
        batter = inputs.batter.attributes
        boosted = batter.with_superstar() if inputs.batter_is_superstar else batter
        pitcher = inputs.pitcher.attributes
        if inputs.pitcher_is_superstar:
            pitcher = pitcher.with_superstar()

        self.state1, self.state2, self.frames_at_play = inputs.seeds

        self.pitch = inputs.pitch.id
        self.charge_pitch = 0 if inputs.charge is None else inputs.charge.id
        self.cursed_ball = pitcher.cursed_ball

        # The superstar boost the calculator applies is to power alone.
        self.slap_power = boosted.slap_hit_power
        self.charge_power = boosted.charge_hit_power
        self.slap_contact_size = batter.slap_contact_size_multiplier
        self.charge_contact_size = batter.charge_contact_size_multiplier
        self.bunting = batter.bunting
        self.horizontal_trajectory = batter.horizontal_hit_trajectory.id
        self.vertical_trajectory = batter.vertical_hit_trajectory.id
        self.has_super_curve = batter.has_super_curve
        self.pitching_height = batter.pitching_height
        self.trimmed_bat = 1 if batter.has_trimmed_bat else 0
        self.reach_near = batter.horizontal_range_near
        self.reach_far = batter.horizontal_range_far
        if Mod.FIX_NON_RED_TOAD_REACH in inputs.mods and inputs.batter in _NON_RED_TOADS:
            red = Character.TOAD_R.attributes
            self.reach_near, self.reach_far = red.horizontal_range_near, red.horizontal_range_far
        self.removes_slice = Mod.REMOVE_SLICE in inputs.mods

        self.batter_x = inputs.batter_x
        self.ball_x = inputs.ball_x
        self.is_right_handed = inputs.hand is Hand.RIGHT
        self.chem_links = inputs.chem_links_on_base
        self.contact_frame = inputs.contact_frame
        self.easy = 1 if inputs.is_easy_batting else 0
        self.stick_up = InputDirection.UP in inputs.stick
        self.stick_down = InputDirection.DOWN in inputs.stick
        self.stick_left = InputDirection.LEFT in inputs.stick
        self.stick_right = InputDirection.RIGHT in inputs.stick
        self.is_bunting = False

        captain_star = batter.captain_star
        self.captain_star = 0 if captain_star is None else captain_star.id
        self.star_swing_type = batter.star_swing.id
        self.charge_up = inputs.charge_up
        self.charge_down = inputs.charge_down
        self.swing = _CHARGE if inputs.swing is SwingType.CHARGE else _SLAP
        self.star_swing = 0  # the non-captain star swing in play (nonCaptainStarSwingActivated)
        self.captain_star_active = 0  # captainStarSwingActivated
        self.star_swing_connected = False  # didNonCaptainStarSwingConnect
        self.is_moonshot = False
        self.moonshot_attempted = False
        if inputs.swing is SwingType.STAR:
            self._resolve_star_swing()

        self.contact_absolute = 0.0
        self.contact_type = _SOUR_LEFT
        self.contact_quality = 0.0
        self.hit_type = -1
        self.horizontal_angle = 0
        self.vertical_angle = 0
        self.power = 0
        self.added_gravity = 0.0
        self.velocity = [0.0, 0.0, 0.0]
        self.acceleration = [0.0, 0.0, 0.0]
        self.ball_energy = 0.0
        self.garlic_real_ball_to_left = overrides.garlic_real_ball_to_left
        self.landed_at: int | None = None
        self.garlic_trajectory: tuple[Point, ...] | None = None

    # -- calculateHitVariables: what a star swing turns into --------------------

    def _resolve_star_swing(self) -> None:
        """The game's star-swing resolution, from the stars the team has.

        Pressing for a star swing zeroes the charge (``isStarSwing`` resets
        ``chargeUp`` and ``chargeDown``), but a swing that had charged fully
        stays fully charged, and that with five stars is a moonshot.
        """
        stars = self.inputs.stars
        general = _CHARGE if self.charge_up > 0.0 else _SLAP
        fully_charged = self.charge_up >= 1.0
        self.charge_up = 0.0
        self.charge_down = 0.0
        self.swing = general
        if stars == 0:
            return
        if fully_charged and stars >= _MOONSHOT_COST:
            self.swing = _STAR
            self.is_moonshot = self.moonshot_attempted = True
        elif self.captain_star == 0:
            if stars >= _STAR_COST:
                self.star_swing = self.star_swing_type
                if self.star_swing_type in (StarSwing.POP_FLY.id, StarSwing.GROUNDER.id):
                    self.swing = _CHARGE
                    self.star_swing_connected = True
                    self.charge_up = 1.0
                else:
                    self.swing = _SLAP
        elif not self.inputs.is_captain:
            if stars >= _OFF_CAPTAIN_STAR_COST:
                self.swing = _STAR
        elif stars >= _CAPTAIN_STAR_COST:
            self.swing = _STAR
        if self.swing == _STAR or self.star_swing_connected:
            self.captain_star_active = self.captain_star

    # -- the RNG ----------------------------------------------------------------

    def _weighted_random_index(self, weights: list[int]) -> int:
        total = sum(weights)
        magnitude = -total if total < 0 else total
        if magnitude < 2:
            draw = 0
        else:
            self.state1 = (
                (self.state1 - (self.state2 & 0xFF))
                + _truncate(self.state2 / magnitude)
                + self.frames_at_play
            )
            remainder = _to_int32(self.state1 - _truncate(self.state1 / magnitude) * magnitude)
            draw = ((remainder >> 31) ^ remainder) - (remainder >> 31)
            if total < 0:
                draw = -draw
        for index, weight in enumerate(weights):
            if draw < weight:
                return index
            draw -= weight
        return 0

    def _random_int(self, limit: int) -> int:
        """``RandomInt_Game``: a whole number in ``[0, |limit|)`` from the same state."""
        n = -limit if limit < 0 else limit
        if n < 2:
            return 0
        self.state1 = (
            (self.state1 - (self.state2 & 0xFF)) + _truncate(self.state2 / n) + self.frames_at_play
        )
        remainder = _to_int32(self.state1 - _truncate(self.state1 / n) * n)
        result = ((remainder >> 31) ^ remainder) - (remainder >> 31)
        return -result if limit < 0 else result

    def _random_in_range(self, lower: float, upper: float) -> float:
        """``randomInRange``: a value in ``[lower, upper]`` in steps of 0.001."""
        steps = _truncate(_f32(1000.0 * _f32(upper - lower))) + 1
        return _f32(0.001 * self._random_int(steps) + lower)

    # -- the contact stage ------------------------------------------------------

    def contact(self) -> None:
        """Everything up to the flight. Raises ValueError if the bat can't reach."""
        near, far = tables.BAT_REACH[self.trimmed_bat]
        if not near <= self.ball_x - self.batter_x <= far:
            raise ValueError("these inputs don't make contact: the ball is out of the bat's reach")
        self._contact_type()
        self._horizontal_angle()
        self._vertical_angle()
        self._power()
        self._velocity()
        self._star_effects()

    def _contact_type(self) -> None:
        charge_up = self.charge_up
        contact_size: float = self.slap_contact_size
        if self.captain_star_active != 0:
            charge_up = 0.0
            contact_size = 100.0
        if not self.is_bunting:
            if charge_up <= 0.0:
                if self.chem_links != 0:
                    contact_size *= tables.CHEM_CONTACT_SIZE_MULTIPLIERS[self.chem_links]
            else:
                contact_size = self.charge_contact_size
        else:
            contact_size = self.bunting

        offset = self.ball_x - self.batter_x
        if not self.is_right_handed:
            offset = -offset
        if offset >= 0.0:
            absolute = 100.0 * (offset / self.reach_far) + 100.0
        else:
            absolute = -(100.0 * (offset / self.reach_near) - 100.0)
        absolute = max(0.0, min(200.0, absolute))
        self.contact_absolute = absolute

        contact_size = contact_size / 100.0
        row = tables.CONTACT_THRESHOLDS[self.trimmed_bat][self.swing][self.easy]
        b0, b1, b2, b3 = row[0], row[1], row[2], row[3]
        left_nice = contact_size * (row[4] - b0) + b0
        left_perfect = contact_size * (row[5] - b1) + b1
        right_perfect = contact_size * (row[6] - b2) + b2
        right_nice = contact_size * (row[7] - b3) + b3

        kind = _SOUR_LEFT
        if left_nice <= absolute:
            kind = _NICE_LEFT
            if left_perfect <= absolute:
                kind = _PERFECT
                if right_perfect <= absolute:
                    kind = _NICE_RIGHT
                    if right_nice <= absolute:
                        kind = _SOUR_RIGHT
        self.contact_type = kind

        if kind == _PERFECT:
            span = right_perfect - left_perfect
            if absolute >= 100.0:
                self.contact_quality = 1.0 - (absolute - left_perfect) / span
            else:
                self.contact_quality = (absolute - left_perfect) / span
        elif kind < _PERFECT:
            if kind == _SOUR_LEFT:
                self.contact_quality = absolute / left_nice
            else:
                self.contact_quality = (absolute - left_nice) / (left_perfect - left_nice)
        elif kind < _SOUR_RIGHT:
            self.contact_quality = 1.0 - (absolute - right_perfect) / (right_nice - right_perfect)
        else:
            self.contact_quality = 1.0 - (absolute - right_nice) / (200.0 - right_nice)

        # A moonshot resolves at contact: a perfect connect is the dinger and
        # drops the captain star swing (so it takes the charge angles); any
        # other contact turns it into a Texas Leaguer.
        if self.is_moonshot:
            if self.contact_type == _PERFECT:
                self.captain_star_active = 0
            else:
                self.is_moonshot = False

        swing = self.swing
        if swing in (_SLAP, _CHARGE):
            self.hit_type = _SOUR_SLAP
            if self.contact_type == _PERFECT:
                self.hit_type = _PERFECT_SLAP
            elif self.contact_type in (_NICE_LEFT, _NICE_RIGHT):
                self.hit_type = _NICE_SLAP
            if self.charge_pitch == ChargeType.PERFECT.id:
                self.hit_type += (
                    _PERFECT_PITCH_SOUR_SLAP if swing == _SLAP else _PERFECT_PITCH_SOUR_CHARGE
                )
            elif self.pitch == PitchType.CURVE.id:
                if swing != _SLAP:
                    self.hit_type += _SOUR_CHARGE
            else:
                self.hit_type += _SOUR_CHANGE_UP_SLAP if swing == _SLAP else _SOUR_CHANGE_UP_CHARGE

    def _horizontal_angle(self) -> None:
        is_charge = 0 if self.swing == _SLAP else 1
        stick = _NO_PUSH_PULL
        if not self.stick_right:
            if self.stick_left:
                stick = _PULL if self.is_right_handed else _PUSH
        elif self.is_right_handed:
            stick = _PUSH
        else:
            stick = _PULL

        frame = self.contact_frame
        low, high = tables.HORIZONTAL_ANGLE_RANGES[stick][is_charge][frame]
        if self.removes_slice:
            low, high = tables.REMOVE_SLICE_ANGLES.get((stick, is_charge, frame), (low, high))
        span = high - low
        if span < 0:
            low += self.state1 - _truncate(self.state1 / -span) * -span
        elif span > 0:
            low += self.state1 - _truncate(self.state1 / span) * span
        low += 0x400
        if not self.is_right_handed:
            low = (0x800 - low) if low < 0x801 else (0x1800 - low)
        self.horizontal_angle = _wrap_angle(low)
        if self.overrides.horizontal_angle_raw is not None:
            self.horizontal_angle = self.overrides.horizontal_angle_raw

    def _vertical_angle(self) -> None:
        forced_zone = 0
        up_down = 0
        is_charge = 0 if self.swing == _SLAP else 1
        lower = higher = 0

        if self.captain_star_active == 0:
            if self.is_moonshot:
                # A connected moonshot takes the charge column's top zone.
                lower, higher = tables.VERTICAL_ZONE_ANGLES[1][self.contact_type][2]
            elif self.star_swing == 0:
                if not self.stick_up:
                    if self.stick_down:
                        up_down = 2
                else:
                    up_down = 1

                weights = tables.VERTICAL_ZONE_WEIGHTS[self.vertical_trajectory][is_charge][
                    self.easy
                ][self.contact_type]
                w0, w1, w2, w3, w4 = weights

                row = (
                    tables.HIT_TYPE_UNSET_ROW
                    if self.hit_type < 0
                    else tables.HIT_TYPE_EFFECTS[self.hit_type]
                )
                # A hit type can force a zone (a grounder or a pop fly) unless
                # the stick is held against it.
                mask = row[3 - self.easy]
                coarse = mask & 0xF000000
                if coarse == 0:
                    fine = mask & 0xF
                    if fine != 0:
                        forced_zone = 2
                        if (fine == 2 and up_down == 2) or (fine == 3 and up_down == 1):
                            forced_zone = 0
                else:
                    forced_zone = 1
                    if (coarse == 0x2000000 and up_down == 2) or (
                        coarse == 0x3000000 and up_down == 1
                    ):
                        forced_zone = 0

                if forced_zone == 0:
                    if (mask & 0x1E0) == 0:
                        w0 = 0
                    if (mask & 0xF0) == 0:
                        w1 = 0
                    if (mask & 0x78) == 0:
                        w2 = 0
                    if (mask & 0x3C) == 0:
                        w3 = 0
                    if (mask & 0x1E) == 0:
                        w4 = 0
                    if up_down == 2:
                        w4 += w0
                        w0 = 0
                    elif up_down == 1:
                        both = w4 + w0
                        w4 = 0
                        w0 = w3 + both
                        w3 = 0
                    zone = self._weighted_random_index([w0, w1, w2, w3, w4])
                    # Forced only after the draw, so the random state is the game's.
                    if self.overrides.vertical_zone is not None:
                        zone = self.overrides.vertical_zone
                    lower, higher = tables.VERTICAL_ZONE_ANGLES[is_charge][self.contact_type][zone]
                else:
                    lower, higher = tables.FORCED_VERTICAL_ANGLES[forced_zone]
            else:
                lower, higher = tables.STAR_SWING_VERTICAL_ANGLES[self.star_swing - 1][
                    self.contact_type
                ]
        else:
            lower, higher = tables.CAPTAIN_STAR_VERTICAL_ANGLES[self.captain_star_active - 1][
                self.contact_type
            ]

        span = higher - lower
        angle = lower if span == 0 else lower + (self.state1 - _truncate(self.state1 / span) * span)
        self.vertical_angle = angle
        if self.overrides.vertical_angle_raw is not None:
            self.vertical_angle = self.overrides.vertical_angle_raw

        # Angles past straight up fold back, and turn the hit around.
        if self.vertical_angle < 0x401:
            if self.vertical_angle < -0x400:
                self.vertical_angle += 0x1000
                self.horizontal_angle = _wrap_angle(self.horizontal_angle + 0x800)
            elif self.vertical_angle < 0:
                self.vertical_angle += 0x1000
        else:
            self.vertical_angle = 0x800 - self.vertical_angle
            self.horizontal_angle = _wrap_angle(self.horizontal_angle + 0x800)

    def _power(self) -> None:
        contact = self.contact_type
        charged = self.charge_up
        exit_velocity = tables.EXIT_VELOCITIES[self.swing][contact]

        if self.captain_star_active == 0:
            if self.star_swing != 0:
                charged = 0.0
                exit_velocity = tables.STAR_SWING_EXIT_VELOCITIES[self.star_swing - 1][contact]
        else:
            charged = 0.0
            exit_velocity = tables.CAPTAIN_STAR_EXIT_VELOCITIES[self.captain_star_active - 1][
                contact
            ]

        if self.star_swing_connected:
            self.charge_down = 1.0

        if self.is_moonshot:
            exit_velocity = tables.EXIT_VELOCITIES[1][self.contact_type]

        low, high = exit_velocity[0], exit_velocity[1]
        distance = self.contact_quality * (high - low) + low

        if self.captain_star_active == 0:
            if charged <= 0.0:
                power: float = self.slap_power
            else:
                power = self.charge_power - (self.charge_power - self.slap_power) * 0.5 * (
                    1.0 - self.charge_down
                )
        else:
            power = 100.0

        if self.captain_star_active == 0 and self.star_swing == 0:
            if self.contact_type in (_NICE_LEFT, _NICE_RIGHT):
                row = 1
            elif self.contact_type == _PERFECT:
                row = 0
            else:
                row = 2
            scale = tables.CURSED_BALL_POWER_SCALE[row]
            power = power * _interpolate(self.cursed_ball, 0.0, 100.0, scale[0], scale[1])

        if self.chem_links != 0 and charged > 0.0:
            power = power * tables.CHEM_POWER_MULTIPLIERS[self.chem_links]

        if self.hit_type > -1:
            power = (power * tables.HIT_TYPE_EFFECTS[self.hit_type][1 - self.easy]) / 100.0

        result = distance * ((power / 100.0) * (1.0 - 0.8) + 0.8)
        self.added_gravity = 0.00001 * exit_velocity[2]

        if self.captain_star_active == 0:
            angle = self.horizontal_angle
            if angle < 0x200:
                across = 0
            elif angle < 0x601:
                across = angle - 0x200
            else:
                across = 0x400
            if not self.is_right_handed:
                across = 0x400 - across
            if across < 0x100:
                segment = 0
            elif across < 0x200:
                segment = 1
                across -= 0x100
            elif across < 0x300:
                segment = 2
                across -= 0x200
            else:
                segment = 3
                across -= 0x300
            bonus = tables.FIELD_POWER_BONUS[self.horizontal_trajectory]
            result = result * _interpolate(
                across / 256, 0.0, 1.0, bonus[segment], bonus[segment + 1]
            )

        if self.is_moonshot:
            result = result * tables.MOONSHOT_POWER_MULTIPLIER

        self.power = _truncate(result)
        if self.overrides.power is not None:
            self.power = _truncate(self.overrides.power)

    def _velocity(self) -> None:
        half_power = self.power * 0.5
        horizontal = _raw_to_rad(self.horizontal_angle)
        vertical = _raw_to_rad(self.vertical_angle)

        sin_vertical = math.sin(vertical)
        cos_vertical = math.cos(vertical)
        ground_power = half_power * cos_vertical
        cos_horizontal = math.cos(horizontal)
        sin_horizontal = math.sin(horizontal)

        x_ground = cos_horizontal * ground_power
        z_ground = sin_horizontal * ground_power

        self.velocity = [x_ground / 100.0, (half_power * sin_vertical) / 100.0, z_ground / 100.0]
        self.acceleration = [0.0, self.added_gravity, 0.0]

        if not self.is_bunting and (self.horizontal_angle < 0x901 or self.horizontal_angle > 0xEFF):
            curve_row = (
                1 if self.has_super_curve or self.star_swing == StarSwing.LINE_DRIVE.id else 0
            )
            curve = tables.CURVE_FACTORS[curve_row]

            off_centre = self.contact_absolute
            if self.contact_absolute > 100.0:
                off_centre = 200.0 - self.contact_absolute

            factor = 1.0 - (1.0 - off_centre * 0.01) * curve[0]
            if 0x180 < self.vertical_angle < 0x401:
                steep = self.vertical_angle - 0x180
                factor = factor * (1.0 - min(steep, 512.0) * 1.0 / 512.0)

            angle = self.horizontal_angle
            angle = min(angle, 1792) if 255 < angle < 3073 else 256
            if not self.is_right_handed:
                angle = 0x800 - angle
            amount = (0x460 - angle) / 864.0 if angle < 0x460 else (0x460 - angle) / 672.0

            amount = factor * amount
            if amount >= 0.0:
                if amount > 0.0:
                    z_ground = -cos_horizontal
                    x_ground = sin_horizontal
            else:
                amount = -amount
                z_ground = cos_horizontal
                x_ground = -sin_horizontal

            self.acceleration[2] = (z_ground * amount) * curve[2]
            self.acceleration[0] = (x_ground * amount) * curve[1]
            if self.acceleration[2] > 0.0:
                self.acceleration[2] = -self.acceleration[2]
            if not self.is_right_handed:
                self.acceleration[0] = -self.acceleration[0]

    def _star_effects(self) -> None:
        """Ball energy and the garlic roll: the tail of ``calculateHitVariables``.

        Runs after the velocity, so its random draw comes in the game's order.
        """
        captain = self.captain_star_active
        if (
            captain == 0
            and self.contact_type not in (_SOUR_LEFT, _SOUR_RIGHT)
            and self.charge_up >= 1.0
        ):
            self.ball_energy = float(self.power)
        if captain in tables.BULLET_CAPTAIN_STARS:
            self.ball_energy = self.power * tables.BULLET_ENERGY_MULTIPLIER
        if captain in tables.GARLIC_CAPTAIN_STARS and self.garlic_real_ball_to_left is None:
            self.garlic_real_ball_to_left = self._random_int(2) == 1

    # -- the flight -------------------------------------------------------------

    def _straight_hang_frames(self) -> int:
        """Frames to first ground contact with no star curve or split.

        The banana window and the garlic split are both timed from it.
        """
        self.fly(with_star_effects=False)
        return self.landed_at if self.landed_at is not None else 0

    def _banana(self) -> tuple[int, int, bool]:
        """(start frame, end frame, curves as for a right-handed batter)."""
        hand = self.overrides.banana_hand
        is_right = self.is_right_handed if hand is None else hand is Hand.RIGHT
        start = self.overrides.banana_start_frame
        end = self.overrides.banana_end_frame
        if start is None or end is None:
            hang = self._straight_hang_frames()
            if start is None:
                start = math.trunc(hang * tables.BANANA_START_FRACTION)
            if end is None:
                end = math.trunc(hang * tables.BANANA_END_FRACTION)
        return start, end, is_right

    def _garlic(self) -> tuple[int, float, float, bool]:
        """(split frame, left spread, right spread, real ball turns left)."""
        to_left = bool(self.garlic_real_ball_to_left)
        spread = self.overrides.garlic_spread_rad
        if spread is None:
            # The left-turning ball's spread is rolled first, as in warioWaluStarHit.
            left = self._random_in_range(*tables.GARLIC_SPREAD_RAD)
            right = self._random_in_range(*tables.GARLIC_SPREAD_RAD)
        else:
            left = right = spread
        split = self._straight_hang_frames() - tables.GARLIC_SPLIT_FRAMES_BEFORE_GROUND
        return split, left, right, to_left

    def fly(
        self, max_frames: int | None = None, *, with_star_effects: bool = True
    ) -> tuple[Point, ...]:
        """Integrate the flight the way ``liveBallHitPhysics`` does.

        Each frame the velocity loses drag, gains gravity and the steady
        acceleration, and only then moves the ball (semi-implicit Euler). With
        no ``max_frames``, fly to the first ground contact and one frame more,
        the frame the stat file records as the landing. With ``max_frames``,
        integrate exactly that many frames, bouncing (or, where the floor has
        holes, skidding) along the ground.
        """
        stadium = physics(self.inputs.stadium)
        ground = stadium.ground_height
        bounces = stadium.has_flat_floor
        drag = VELOCITY_KEPT_PER_FRAME
        gravity = GRAVITY_PER_FRAME_SQUARED
        # The flight starts at the ball's contact point, mirrored for a lefty:
        # the recorded x is relative to the batter, the flight is the field's.
        start_x = self.ball_x if self.is_right_handed else -self.ball_x
        px, py, pz = start_x, self.pitching_height, self.inputs.ball_z
        vx, vy, vz = self.velocity
        ax, ay, az = self.acceleration

        points: list[Point] = [(px, py, pz)]
        landed_at: int | None = None
        frame = 0
        banana = with_star_effects and self.captain_star_active in tables.BANANA_CAPTAIN_STARS
        banana_start = banana_end = 0
        banana_right = True
        if banana:
            banana_start, banana_end, banana_right = self._banana()
        garlic = with_star_effects and self.captain_star_active in tables.GARLIC_CAPTAIN_STARS
        split_frame = 0
        left_spread = right_spread = 0.0
        real_to_left = False
        if garlic:
            split_frame, left_spread, right_spread, real_to_left = self._garlic()
        split = False
        garlic_points: list[Point] = []
        gx = gy = gz = gvx = gvy = gvz = 0.0
        while True:
            frame += 1
            vx = vx * drag + ax
            vy = (vy - gravity) * drag + ay
            vz = vz * drag + az
            # The banana ball turns its heading a fixed amount each frame,
            # keeping its ground speed.
            if banana and banana_start < frame < banana_end:
                ground_speed = math.hypot(vx, vz)
                heading = math.atan2(vz, vx)
                if banana_right:
                    heading -= tables.BANANA_TURN_RAD_PER_FRAME
                else:
                    heading += tables.BANANA_TURN_RAD_PER_FRAME
                vx = math.cos(heading) * ground_speed
                vz = math.sin(heading) * ground_speed
            px += vx
            py += vy
            pz += vz
            # The garlic ball splits in two, each side turned from the heading;
            # from then on both fly under drag and gravity alone.
            if garlic and not split and frame == split_frame:
                speed = math.hypot(vx, vz)
                heading = math.atan2(vz, vx)
                left = heading + left_spread
                right = heading - right_spread
                real, other = (left, right) if real_to_left else (right, left)
                vx, vz = math.cos(real) * speed, math.sin(real) * speed
                ax = ay = az = 0.0
                gx, gy, gz = px, py, pz
                gvx, gvy, gvz = math.cos(other) * speed, vy, math.sin(other) * speed
                garlic_points = [(gx, gy, gz)]
                split = True
            elif garlic and split:
                gvx = gvx * drag
                gvy = (gvy - gravity) * drag
                gvz = gvz * drag
                gx += gvx
                gy += gvy
                gz += gvz
                if gy < ground:
                    gy = ground
                    if gvy < 0.0:
                        gvy = -gvy if bounces else 0.0
                garlic_points.append((gx, gy, gz))
            if py < ground:
                py = ground
                if vy < 0.0:
                    vy = -vy if bounces else 0.0
                if landed_at is None:
                    landed_at = frame
            points.append((px, py, pz))
            if max_frames is None:
                if landed_at is not None and frame >= landed_at + 1:
                    break
            elif frame >= max_frames:
                break
        self.landed_at = landed_at
        if garlic:
            self.garlic_trajectory = tuple(garlic_points) if split else None
        return tuple(points)

    def run(self) -> HitResult:
        self.contact()
        trajectory = self.fly()
        if self.moonshot_attempted:
            moonshot = MoonshotStatus.MOONSHOT if self.is_moonshot else MoonshotStatus.FAILED
        else:
            moonshot = MoonshotStatus.NONE
        star_swing: CaptainStar | StarSwing | None = None
        if self.star_swing:
            star_swing = StarSwing(self.star_swing)
        elif self.swing == _STAR and not self.moonshot_attempted:
            star_swing = CaptainStar(self.captain_star_active)
        return HitResult(
            contact_type=ContactType(self.contact_type),
            contact_absolute=self.contact_absolute,
            contact_quality=self.contact_quality,
            horizontal_angle_raw=self.horizontal_angle,
            vertical_angle_raw=self.vertical_angle,
            horizontal_angle_deg=(self.horizontal_angle - 0x400) * 360 / 4096,
            vertical_angle_deg=self.vertical_angle * 360 / 4096,
            power=self.power,
            velocity_per_frame=(self.velocity[0], self.velocity[1], self.velocity[2]),
            acceleration_per_frame=(
                self.acceleration[0],
                self.acceleration[1],
                self.acceleration[2],
            ),
            ball_energy=self.ball_energy,
            star_swing=star_swing,
            moonshot=moonshot,
            trajectory=trajectory,
            garlic_trajectory=self.garlic_trajectory,
        )
