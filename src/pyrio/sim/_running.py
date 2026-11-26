"""Running the bases: a runner's path and timing, frame by frame from contact.

A port of the frontend's running model (ProjectRio-frontend, Nicholas
Lannutti's ``lib/mssb/RunningSimulation``), itself a single-precision port of
``running_updateRunner`` and the functions it calls in mssb-dtk's
``runner.c``, with ``setRunnerSpeedConstants`` (``roster_init.c``). The tables
are the game's ``gameplay_tables.c``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from .._codes import Hand
from .._float32 import f32 as _f32
from ._spline import make_spline

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .._characters import Character
    from ..geometry import Point

__all__ = ["RunResult", "RunnerAction", "RunnerFrame", "batter_location", "simulate_run"]

_XZ = tuple[float, float]

# baseCoordsForRunning: where runners run to (home, first, second, third). The
# bases themselves sit a little apart (pyrio.geometry.BASE_LOCATIONS).
_RUNNING_BASES: tuple[_XZ, _XZ, _XZ, _XZ] = ((0.4, 0.3), (18.8, 19.4), (0.0, 38.7), (-18.5, 19.3))
# baseRoundingPathPoints[0]: the spline a runner rounding the bases blends onto.
_ROUNDING_PATH: tuple[_XZ, ...] = (
    (0.0, 0.0),
    (12.5, 10.5),
    (18.0, 16.5),
    (18.8, 19.4),
    (18.6, 22.0),
    (3.0, 37.5),
    (0.0, 38.7),
    (-3.0, 38.7),
    (-17.5, 22.0),
    (-18.5, 19.3),
    (-18.5, 17.5),
    (0.4, 0.3),
    (0.0, 0.0),
)
# runnerVelocityLookup: top speed per frame for speed 0, 10, ... 210.
_TOP_SPEEDS = (
    0.132, 0.135, 0.137, 0.139, 0.141, 0.143, 0.145, 0.148, 0.151, 0.154, 0.157,
    0.16, 0.164, 0.168, 0.173, 0.176, 0.179, 0.182, 0.185, 0.188, 0.19, 0.19,
)  # fmt: skip
# runnerSpeedScaling, each (at speed 0, at speed 100): acceleration, the speed a
# full mash meter adds, presses to fill the meter, frames for it to drain.
_ACCELERATION = (0.01, 0.005)
_MAX_MASH_BONUS = (0.02, 0.02)
_PRESSES_TO_FILL_MASH = (5.0, 5.0)
_MASH_DRAIN_FRAMES = (20.0, 20.0)
_SPEED_CAP = 200  # initializeInMemRunner
_BATTER_RUN_DELAY_FRAMES = 30  # batterRunDelayFrames: the batter can't run sooner after contact
_RUNNER_START_FRAME = 5  # running_getDirectionOverride sends every runner forward on this frame
_MASH_HOLD_FRAMES = 6  # runnerTimingConsts.mashHoldFrames
_MAX_STAMINA = 4000  # runnerTimingConsts.maxStamina
_MAX_SPEED_PENALTY = 0.3  # runnerStaminaConsts, at no stamina left
_MAX_ACCELERATION_PENALTY = 0.5
_BASE_REACH_MARGIN = 0.03  # baseReachMargin_forwards: on a base this fraction of the baseline early
_LEADOFF = 0.1  # leadoffDistancePercent: a runner on base leads off this far each pitch
_ROUND_START = 0.5  # running_roundBaseDecision: rounding starts halfway down a baseline
_ROUNDING_PER_FRAME = 0.012  # roundingStrengthPerFrame
_SLIDE_MIN_FRAMES = 16  # runnerCharConsts: the slide window, and the recovery after it
_SLIDE_MAX_FRAMES = 22
_SLIDE_RECOVERY_FRAMES = 25
_OVERRUN_SLOWDOWN_FRAMES = 15  # overrunBaseStageFrames / overrunBaseDistance
_OVERRUN_RETURN_FRAMES = 10
_OVERRUN_DISTANCE = 0.1
_INITIAL_BOX_POSITION: _XZ = (0.0, 0.4)  # initialBoxPosition: where every at-bat starts
_MAX_FRAMES = 4000
_OVERRUN_LIMIT_FRAMES = 300
_HOME = 4


def _lerp_range(v: float, a: float, b: float, c: float, d: float) -> float:
    # LinearInterpolateToNewRange (sub.c), the fraction clamped to 0..1.
    span = _f32(b - a)
    t = 1.0 if span == 0 else _f32(_f32(v - a) / span)
    t = min(max(t, 0.0), 1.0)
    return _f32(_f32(_f32(d - c) * t) + c)


def _over_speed(speed: float, at: tuple[float, float]) -> float:
    return _lerp_range(speed, 0, 100, _f32(at[0]), _f32(at[1]))


@dataclass(frozen=True, slots=True)
class _SpeedConstants:
    top_speed: float
    acceleration: float
    max_mash_bonus: float
    mash_per_press: float
    mash_drain: float


def _speed_constants(speed: int) -> _SpeedConstants:
    # setRunnerSpeedConstants (roster_init.c)
    s = min(speed, _SPEED_CAP)
    lower = s // 10 * 10
    upper = lower + 10
    return _SpeedConstants(
        top_speed=_lerp_range(
            s, lower, upper, _f32(_TOP_SPEEDS[lower // 10]), _f32(_TOP_SPEEDS[upper // 10])
        ),
        acceleration=_over_speed(s, _ACCELERATION),
        max_mash_bonus=_over_speed(s, _MAX_MASH_BONUS),
        mash_per_press=_f32(1 / _over_speed(s, _PRESSES_TO_FILL_MASH)),
        mash_drain=_f32(1 / _over_speed(s, _MASH_DRAIN_FRAMES)),
    )


@cache
def _leg_splines() -> tuple[Callable[[float], _XZ], ...]:
    # running_basePathPosition: one spline per baseline through four of the
    # rounding points (three for third to home).
    return tuple(
        make_spline(_ROUNDING_PATH[start : start + (3 if leg == 3 else 4)])
        for leg, start in enumerate((0, 3, 6, 9))
    )


def _distance(a: _XZ, b: _XZ) -> float:
    return _f32(math.hypot(_f32(a[0] - b[0]), _f32(a[1] - b[1])))


def _lerp(a: _XZ, b: _XZ, t: float) -> _XZ:
    return (
        _f32(a[0] + _f32(_f32(b[0] - a[0]) * t)),
        _f32(a[1] + _f32(_f32(b[1] - a[1]) * t)),
    )


def batter_location(
    character: Character, hand: Hand, box_position: tuple[float, float] | None = None
) -> Point:
    """Where the batter stands, from where they are in the box.

    ``box_position`` is the game's ``g_Batter.boxPosition``, ``(x, z)`` before
    the character's offset and mirroring; it's clamped to the character's box.
    Left out, it's where every at-bat starts. For a left-handed batter the
    location is mirrored across the plate.
    """
    a = character.attributes
    x, z = _INITIAL_BOX_POSITION if box_position is None else box_position
    x = min(max(x, a.horizontal_range_near), a.horizontal_range_far)
    z = min(max(z, a.vertical_range_front), a.vertical_range_back)
    x += a.bat_offset[0]
    z += a.bat_offset[1]
    if hand is Hand.LEFT:
        x = -x
    return (x, 0.0, z)


class RunnerAction(Enum):
    """What a runner is doing besides running."""

    NONE = "none"
    SLIDE = "slide"
    RECOVER = "recover"
    """Getting up from a slide."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RunnerFrame:
    """The runner on one frame after contact."""

    frame: int
    speed: float
    """Field units this frame."""
    bases_run: float
    """How far around the bases: 1.5 is halfway from first to second."""
    location: Point
    mash: float
    """The mash meter, 0 to 1."""
    stamina: int
    is_held: bool
    """Not yet allowed to run (the batter's delay, a runner's start)."""
    action: RunnerAction


@dataclass(frozen=True, slots=True, kw_only=True)
class RunResult:
    """A run from one base to another, from :func:`simulate_run`."""

    frames: int
    """The first frame after contact on which the runner counts as on the end base."""
    top_speed_frame: int | None
    """The first frame at top speed, from which mashing adds speed."""
    base_frames: Mapping[int, int]
    """When the runner first counts as on each base along the way (4 is home)."""
    start: Point
    trace: tuple[RunnerFrame, ...]
    """Every frame from contact to arriving."""
    overrun: tuple[RunnerFrame, ...]
    """A rounding runner who stops at second or third carries on past the base
    and comes back; those frames, after arriving. Empty otherwise."""


def simulate_run(
    character: Character,
    *,
    initial_base: int = 0,
    result_base: int = 1,
    is_superstar: bool = False,
    hand: Hand = Hand.RIGHT,
    box_position: tuple[float, float] | None = None,
    rounding: bool = False,
    mash_every: int | None = 3,
) -> RunResult:
    """Run from ``initial_base`` to ``result_base``, frame by frame from contact.

    Bases are numbered as ``Runner`` numbers them: 0 is the batter (from
    ``batter_location(character, hand, box_position)``), 1 to 3 a runner on
    that base, and 4 home. A runner on base starts from a full lead.

    ``rounding`` is a ball in the outfield: the runner rounds each base and
    keeps their speed. Without it (a ball in the infield) the runner stops on
    first and slides into the other bases. ``mash_every`` is how many frames
    apart the player presses to mash once at top speed (``None`` for no
    mashing); the default, 3, is a quick human's twenty presses a second, and
    1 is a press every frame. Stamina wears down as the game does.
    """
    if not 0 <= initial_base < result_base <= _HOME:
        raise ValueError(
            f"need 0 <= initial_base < result_base <= 4, got {initial_base} and {result_base}"
        )
    if mash_every is not None and mash_every < 1:
        raise ValueError(f"mash_every must be 1 or more (or None), not {mash_every}")
    attributes = character.attributes.with_superstar() if is_superstar else character.attributes
    k = _speed_constants(attributes.speed)
    margin = _f32(_BASE_REACH_MARGIN)
    is_batter = initial_base == 0
    if is_batter:
        x, _, z = batter_location(character, hand, box_position)
        home: _XZ = (x, z)
    else:
        home = _RUNNING_BASES[0]
    splines = _leg_splines()

    def leg_ends(leg: int) -> tuple[_XZ, _XZ]:
        # running_updateDistAndFramesToClosestBases: the batter's first
        # baseline starts where the batter stood.
        start = home if leg == 0 else _RUNNING_BASES[leg % 4]
        return start, _RUNNING_BASES[(leg + 1) % 4]

    pct = _f32(0.0) if is_batter else _f32(_f32(_LEADOFF) + margin)
    bases_run = _f32(0.0) if is_batter else _f32(initial_base + pct)
    position = (
        home
        if is_batter
        else _lerp(_RUNNING_BASES[initial_base], _RUNNING_BASES[(initial_base + 1) % 4], pct)
    )
    start = position

    stamina = _MAX_STAMINA
    speed: float = _f32(0.0)
    prev_speed: float = speed
    mash: float = speed
    mash_hold = 0
    top_speed_frame: int | None = None
    moving = False
    restart_after = _BATTER_RUN_DELAY_FRAMES if is_batter else _RUNNER_START_FRAME
    strength = _f32(0.0)
    batter_overrun_check = is_batter  # baseRoundingState 1, cleared halfway to first
    standing_on = -1
    action = RunnerAction.NONE
    action_frames = 0
    step: float = _f32(0.0)
    left_to_reach: float = _f32(_f32(1 - pct) - margin)
    base_frames: dict[int, int] = {}
    trace: list[RunnerFrame] = []
    overrun: list[RunnerFrame] = []
    arrived_at: int | None = None
    overrun_stage = 0  # overrunBaseStage: 0 none, 1 pending, 2 slowing, 3 returning
    overrun_frames = 0
    overrun_step = _f32(0.0)
    overrun_done = False

    def result(frame: int) -> RunResult:
        return RunResult(
            frames=frame,
            top_speed_frame=top_speed_frame,
            base_frames=MappingProxyType(dict(base_frames)),
            start=(start[0], 0.0, start[1]),
            trace=tuple(trace),
            overrun=tuple(overrun),
        )

    for f in range(1, _MAX_FRAMES):
        # running_updateStamina, from last frame's speed.
        if prev_speed >= _f32(0.1):
            stamina -= 1
        tired = _f32(1 - _f32(stamina / _MAX_STAMINA))
        stamina_mult = _f32(1 - _f32(_f32(_MAX_SPEED_PENALTY) * tired))
        acceleration_mult = _f32(1 - _f32(_f32(_MAX_ACCELERATION_PENALTY) * tired))

        start_of_frame = bases_run
        leg = int(bases_run)
        here, there = leg_ends(leg)
        baseline = _f32(_distance(here, position) + _distance(there, position))
        next_base = (leg + 1) % 4

        # running_roundBaseDecision, then running_overrun1BIndicator for the batter.
        is_rounding = False
        if rounding and action is RunnerAction.NONE and not (batter_overrun_check and leg == 0):
            dont_round = strength == 0 and (pct < _f32(_ROUND_START) or bases_run >= 3)
            is_rounding = not dont_round
            if is_rounding and standing_on >= 0:
                strength = _f32(1.0)
        if batter_overrun_check and bases_run >= _f32(0.5):
            batter_overrun_check = False

        # running_triggerSlideOrBodyCheck: a runner not rounding slides into any base but first.
        if (
            action is RunnerAction.NONE
            and not is_rounding
            and moving
            and step > 0
            and standing_on < 0
            and next_base != 1
        ):
            frames_to_base = int(_f32(left_to_reach / step)) + 1
            if _SLIDE_MIN_FRAMES <= frames_to_base <= _SLIDE_MAX_FRAMES:
                action = RunnerAction.SLIDE
                action_frames = frames_to_base

        # running_calcSpeedVariables
        held = f < restart_after and not moving and action is RunnerAction.NONE
        overrun_stepping = False
        if overrun_stage > 0:
            # running_overrunBaseControl: slow down past the base, then come back to it.
            overrun_stepping = True
            if overrun_stage == 1:
                overrun_stage = 2
                overrun_frames = _OVERRUN_SLOWDOWN_FRAMES
                overrun_step = _f32(
                    _f32(_OVERRUN_DISTANCE) / _f32((overrun_frames + 1) * (overrun_frames // 2))
                )
            if overrun_stage == 2:
                overrun_frames -= 1
                if overrun_frames < 0:
                    overrun_stage = 3
                    overrun_frames = _OVERRUN_RETURN_FRAMES
                    overrun_step = _f32(_f32(margin - pct) / overrun_frames)
                else:
                    step = _f32(overrun_step * overrun_frames)
            if overrun_stage == 3:
                overrun_frames -= 1
                if overrun_frames < 0:
                    overrun_done = True
                    step = _f32(0.0)
                else:
                    step = overrun_step
            bases_run = _f32(bases_run + step)
            pct = _f32(pct + step)
            if overrun_done:
                pct = margin  # running_placeRunnerOnBase
                bases_run = _f32(int(bases_run) + margin)
            speed = _f32(abs(step) * baseline)
        elif action is RunnerAction.SLIDE:
            # Cover the rest of the baseline in equal steps.
            action_frames -= 1
            excess = _f32(_f32(1 - margin) - pct)
            if action_frames <= 0:
                action = RunnerAction.RECOVER
                action_frames = _SLIDE_RECOVERY_FRAMES
                step = _f32(0.0)
                bases_run = _f32(leg + 1)
                pct = _f32(0.0)
            else:
                step = _f32(excess / (action_frames + 1))
        elif action is RunnerAction.RECOVER:
            action_frames -= 1
            speed = step = _f32(0.0)
            if action_frames <= 0:
                action = RunnerAction.NONE
                moving = False
                restart_after = f + 1
                pct = margin
                bases_run = _f32(int(bases_run) + margin)
                here, there = leg_ends(int(bases_run))
        elif not held:
            moving = True
            cap = _f32(k.top_speed * stamina_mult)
            speed = _f32(speed + _f32(k.acceleration * acceleration_mult))
            if speed > cap:
                speed = cap
                if top_speed_frame is None:
                    top_speed_frame = f
                if mash_every is not None and (f - top_speed_frame) % mash_every == 0:
                    mash_hold = _MASH_HOLD_FRAMES
                    mash = min(_f32(mash + k.mash_per_press), 1.0)
                elif mash_hold != 0:
                    mash_hold -= 1
                else:
                    mash = max(_f32(mash - k.mash_drain), 0.0)
                speed = _f32(speed + _f32(mash * k.max_mash_bonus))
            else:
                mash = _f32(0.0)
                mash_hold = 0
            step = _f32(speed * _f32(1 / baseline))
        if step != 0 and not overrun_stepping:
            scaled = int(_f32(_f32(10000) * _f32(bases_run + step)))
            bases_run = _f32(scaled / 10000)
            pct = _f32((scaled % 10000) / 10000)
        prev_speed = speed

        # running_updateBaseArrival: crossing a base.
        if not overrun_stepping and speed > 0 and int(bases_run) > int(start_of_frame):
            crossed = int(bases_run)
            if is_rounding or action is not RunnerAction.NONE:
                bases_run = _f32(crossed)  # keeps speed; the rest of this frame's run is lost
                pct = _f32(0.0)
                if arrived_at is not None:
                    overrun_stage = 1
            else:
                # running_stopRunner + running_placeRunnerOnBase
                speed = prev_speed = step = strength = _f32(0.0)
                moving = False
                restart_after = f + 1
                pct = margin
                bases_run = _f32(crossed + margin)
                here, there = leg_ends(crossed)
        left_to_reach = _f32(_f32(1 - pct) - margin)

        # baseStandingOn: within the margin either side of a base, past half a base.
        reached = -1
        if bases_run > 0.5:
            if bases_run >= _HOME:
                reached = _HOME
            elif pct <= margin:
                reached = int(bases_run)
            elif pct >= _f32(1 - margin):
                reached = int(bases_run) + 1
        standing_on = -1 if reached < 0 else reached % 4
        if reached > initial_base and reached not in base_frames:
            base_frames[reached] = f

        # running_updatePosition: the straight line, blended onto the rounding spline.
        straight = _lerp(here, there, pct)
        if action is RunnerAction.RECOVER:
            position = _RUNNING_BASES[int(bases_run) % 4]
        elif is_rounding:
            if moving:
                strength = _f32(min(1.0, strength + _f32(_ROUNDING_PER_FRAME)))
            curve = splines[min(int(bases_run), 3)](pct)
            position = _lerp(straight, curve, strength)
        else:
            strength = _f32(0.0)
            position = straight

        state = RunnerFrame(
            frame=f,
            speed=speed,
            bases_run=bases_run,
            location=(position[0], 0.0, position[1]),
            mash=mash,
            stamina=stamina,
            is_held=held,
            action=action,
        )
        (trace if arrived_at is None else overrun).append(state)
        if arrived_at is None and reached == result_base:
            if rounding and is_rounding and result_base < _HOME:
                arrived_at = f  # a rounding runner stopping at second or third overruns it
            else:
                return result(f)
        if overrun_done or (arrived_at is not None and f - arrived_at > _OVERRUN_LIMIT_FRAMES):
            return result(arrived_at if arrived_at is not None else f)
    raise RuntimeError(f"the runner never reached base {result_base}")  # pragma: no cover
