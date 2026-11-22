"""The live ball: a batted ball's bounces, walls and hazards, until the play settles.

The hit simulation ends where the ball first comes down. This carries a flight
on from contact the way the game does, following the decompilation (mssb-dtk):

  liveBallHitPhysics   ball_physics.c:1666   the per-frame step
  ballCollisionLogic   ball_physics.c:2490   what a surface does to the ball
  checkForBallDead     ball_physics.c:2995   home run or foul over out-of-play ground
  checkCollision       collision_primitives.c (asm)   hazards first, then the park
  sta_c1..sta_c6.c     the hazards themselves

The ball is cast against the stadium's collision mesh and each hazard's own
triangles. Meshes are stored Y-down, as the game stores them, and the ball is
Y-up, so Y flips at the mesh boundary.

Ported from RioVisualizer's ``physics.py``, the original work, and held to it
exactly by ``tools/check_live_ball_parity.py``. The constants and the order of
operations are the decomp's; rewriting them to taste is how a port drifts.

Exact: gravity, drag, ground bounce and roll, wall rebounds, the surface
outcomes, the hazard rebounds, the Thwomp's slam, the tornado's orbit, the
plant's spit. The game rolls its own dice for hazards, and a stat file doesn't
record them, so wherever a hazard needs a roll (which way a tornado spins,
where a plant spits, what a "?" block is) this draws from a generator seeded
by ``seed`` and marks the event ``is_assumed``. The same flight and seed
always play out the same way: one of the outcomes the game could have
produced, not a recording of it. Approximations, marked ``is_approximate``: a
Piranha Plant's catch uses its lunge envelope rather than its animated mouth,
and a Chain Chomp's lunge is a straight hop along its launch heading.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast

from .._codes import Stadium
from ..geometry import HazardKind, physics
from ..geometry._files import park_sheet
from ..geometry._mesh import FOUL_BIT, MeshTriangle, mesh_triangles
from ._physics import GRAVITY_PER_FRAME_SQUARED, VELOCITY_KEPT_PER_FRAME

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..geometry import Point

__all__ = ["LiveBallEvent", "LiveBallEventKind", "LiveBallOutcome", "LiveBallResult", "play_out"]


class LiveBallOutcome(Enum):
    """How a played-out ball settled."""

    HOME_RUN = "home_run"
    FOUL = "foul"
    GROUND_RULE_DOUBLE = "ground_rule_double"
    FIELDED = "fielded"
    """It reached the ``stop_at`` point after landing."""

    STOPPED = "stopped"
    """It came to rest."""

    IN_PLAY = "in_play"
    """Still rolling when the play-out stopped following it."""


class LiveBallEventKind(Enum):
    """What happened to the ball on a frame."""

    LAND = "land"
    BOUNCE = "bounce"
    WALL = "wall"
    HAZARD = "hazard"
    STAR = "star"
    """The batting team earned a star (a star pad, or a brick block broken)."""

    CAPTURE = "capture"
    """A hazard took hold of the ball (a tornado, a Piranha Plant)."""

    RELEASE = "release"
    PANEL = "panel"
    """A Toy Field panel called the play."""

    OUTCOME = "outcome"
    """The play settled; see ``LiveBallEvent.outcome``."""


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveBallEvent:
    """One thing that happened to the ball, and where.

    Fields that don't apply to the kind of event are None.
    """

    frame: int
    kind: LiveBallEventKind
    location: Point
    """Where the ball was, rounded to 4 decimal places."""

    outcome: LiveBallOutcome | None = None
    surface: str | None = None
    """The surface touched, by name (a ``Surface`` label, or a hazard's)."""

    hazard: str | None = None
    """The hazard's id in ``pyrio.geometry.hazards``."""

    hazard_kind: HazardKind | None = None
    result: str | None = None
    """What the hazard did: ``"slam"``, ``"land"``, ``"pop"``, ``"lunge"``, ``"bite"``,
    ``"break"`` or ``"bounce"``."""

    block: str | None = None
    """What a Peach Garden block turned out to be: ``"brick"``, ``"used"`` or ``"note"``."""

    label: str | None = None
    """The Toy Field panel's label."""

    fall_speed: float | None = None
    """How fast the Thwomp drops."""

    heading_deg: float | None = None
    """Where the Piranha Plant will spit the ball."""

    spin: int | None = None
    """Which way the tornado turns: 1 or -1."""

    is_star_plant: bool | None = None
    is_assumed: bool = False
    """The event rests on a roll the game made and the stat file doesn't record."""

    is_approximate: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveBallResult:
    """A flight played out to the end of the play."""

    trajectory: tuple[Point, ...]
    """One point per frame, from contact to the end of the play."""

    events: tuple[LiveBallEvent, ...]
    outcome: LiveBallOutcome
    land_frame: int | None
    """The frame the ball first came down, or None if it never did."""


def play_out(
    stadium: Stadium,
    trajectory: Iterable[Sequence[float]],
    *,
    acceleration: Sequence[float] = (0.0, 0.0, 0.0),
    seed: int = 0,
    hazards: bool = True,
    mystery_blocks: Literal["brick", "used", "note"] | None = None,
    star_plants: bool | None = None,
    max_frames: int = 1500,
    roll_frames: int = 420,
    stop_at: tuple[float, float] | None = None,
) -> LiveBallResult:
    """Carry a flight on from contact until the play is settled.

    The ball follows ``trajectory`` (one point per frame, from the contact
    point) until it first touches anything, then the game's physics takes
    over. Pass a hit's ``trajectory`` and ``acceleration_per_frame``.

    ``seed`` rolls the hazards' dice. ``hazards=False`` plays the bare park.
    ``mystery_blocks`` forces what Peach Garden's "?" blocks are, and
    ``star_plants`` whether Yoshi Park's plants are star plants. The play ends
    after ``max_frames``, or ``roll_frames`` after the ball lands, or when the
    landed ball reaches ``stop_at`` (an ``(x, z)`` point, such as where a
    fielder picked it up).

    The ball leaves the park as the game decides it: off a foul pole, over
    the out-of-play structure, or past the wall at whatever height the mesh
    says, and a hazard may stop it first (a ball a Thwomp swats down is not a
    home run).
    """
    options = _Options(
        seed=seed,
        hazards=hazards,
        mystery_blocks=mystery_blocks,
        star_plants=star_plants,
        max_frames=max_frames,
        roll_frames=roll_frames,
        stop_at=stop_at,
    )
    return _LiveBall(stadium, options).run(trajectory, acceleration)


@dataclass(frozen=True, slots=True)
class _Options:
    seed: int
    hazards: bool
    mystery_blocks: str | None
    star_plants: bool | None
    max_frames: int
    roll_frames: int
    stop_at: tuple[float, float] | None


# BALL_COLLISION_TYPE (collision_primitives.h), as ``Surface`` ids.
_GRASS, _WALL, _OUT_OF_PLAY, _FOUL_POLE, _UNCLIMBABLE_WALL, _DIRT = 1, 2, 3, 4, 5, 6
_PIT_WALL, _PIT, _ROUGH, _WATER, _CHOMP_PEN = 7, 8, 9, 10, 11
# Hazard surfaces.
_HAZARD_WALL, _STAR_PAD, _HAZARD_STRUCTURE, _SAND_STAR = 0x20, 0x22, 0x23, 0x32
_SURFACE_NAMES = {
    _GRASS: "grass",
    _WALL: "wall",
    _OUT_OF_PLAY: "out of play",
    _FOUL_POLE: "foul pole",
    _UNCLIMBABLE_WALL: "back wall",
    _DIRT: "dirt",
    _PIT_WALL: "pit wall",
    _PIT: "pit",
    _ROUGH: "rough",
    _WATER: "water",
    _CHOMP_PEN: "chomp pen",
    _HAZARD_WALL: "hazard wall",
    _STAR_PAD: "star pad",
    _HAZARD_STRUCTURE: "hazard",
    0x30: "chain chomp",
    _SAND_STAR: "sand star",
    0x10: "brick block",
    0x11: "used block",
    0x12: "note block",
    0x13: "brick block",
    0x14: "used block",
    0x15: "note block",
    0x60: "barrel",
    0x61: "klaptrap",
    0x64: "piranha plant",
}
_GROUND = frozenset({_GRASS, _DIRT, _ROUGH, _WATER, _STAR_PAD, _SAND_STAR})
# Speed kept off the block surfaces 0x10..0x15 (lbl_3_data_610C).
_BLOCK_KEEP = {0x10: 0.1, 0x11: 0.4, 0x12: 0.7, 0x13: 0.2, 0x14: 0.5, 0x15: 1.0}
_HALF_KEEP = frozenset({0x21, 0x30, 0x40, 0x60, 0x61})

_ROLL_VERTICAL_SPEED = 0.08  # lbl_3_data_4604: below this the ball starts rolling
_ROLL_MIN_CONTACTS = 2  # lbl_3_data_4608
_SURFACE_OFFSET = 0.005  # the ball rests this far (plus the ground height) off a surface
_MIN_HAZARD_SPEED = 0.03  # ground speed floor after a hazard hit
_OVER_WALL_FRAMES = 5  # airborne frames over out-of-play ground before a home run
# Parks that sweep their hazards over the last five frames instead of this one.
_SWEEPING_STADIUMS = frozenset({Stadium.WARIO_PALACE, Stadium.YOSHI_PARK, Stadium.DK_JUNGLE})

_IN_AIR, _LANDED = 0, 1

_Vec: TypeAlias = tuple[float, float, float]
_Hit: TypeAlias = tuple[float, _Vec, _Vec, int]
"""A ray-cast hit: (fraction along the ray, point, unit normal, collision tag)."""


def _name(kind: int) -> str:
    return _SURFACE_NAMES.get(kind, hex(kind))


# --- vectors -------------------------------------------------------------------


def _sub(a: Sequence[float], b: Sequence[float]) -> _Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> _Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _to_mesh(p: Sequence[float], lift: float = 0.0) -> _Vec:
    """Field space to mesh space (Y down), optionally lowered by the ball's radius."""
    return (p[0], -(p[1] - lift), p[2])


# --- meshes --------------------------------------------------------------------


class _TriangleSet:
    """Triangles in mesh space on a coarse XZ grid, with the game's segment test.

    ``checkTriangleCollisions`` is one-sided: a triangle only stops a segment
    coming at its front, the side ``(v1 - v0) x (v2 - v0)`` points to.
    """

    CELL = 10.0

    def __init__(self, triangles: Iterable[MeshTriangle]) -> None:
        self.triangles: list[tuple[_Vec, _Vec, _Vec, _Vec, int]] = []
        self.grid: dict[tuple[int, int], list[int]] = {}
        for v0, v1, v2, tag in triangles:
            n = _cross(_sub(v1, v0), _sub(v2, v0))
            if _dot(n, n) < 1e-18:
                continue
            index = len(self.triangles)
            self.triangles.append((v0, v1, v2, n, tag))
            x0, x1 = min(v0[0], v1[0], v2[0]), max(v0[0], v1[0], v2[0])
            z0, z1 = min(v0[2], v1[2], v2[2]), max(v0[2], v1[2], v2[2])
            for ix in range(math.floor(x0 / self.CELL), math.floor(x1 / self.CELL) + 1):
                for iz in range(math.floor(z0 / self.CELL), math.floor(z1 / self.CELL) + 1):
                    self.grid.setdefault((ix, iz), []).append(index)

    def ray_cast(self, src: _Vec, dst: _Vec, best: float = 1.0) -> _Hit | None:
        """The nearest front-facing hit along ``src -> dst`` (mesh space), or None."""
        d = _sub(dst, src)
        x0, x1 = min(src[0], dst[0]), max(src[0], dst[0])
        z0, z1 = min(src[2], dst[2]), max(src[2], dst[2])
        seen: set[int] = set()
        found: _Hit | None = None
        for ix in range(math.floor(x0 / self.CELL), math.floor(x1 / self.CELL) + 1):
            for iz in range(math.floor(z0 / self.CELL), math.floor(z1 / self.CELL) + 1):
                for index in self.grid.get((ix, iz), ()):
                    if index in seen:
                        continue
                    seen.add(index)
                    v0, v1, v2, n, tag = self.triangles[index]
                    denominator = _dot(n, d)
                    if denominator >= 0.0:
                        continue  # a back face, or parallel
                    t = _dot(n, _sub(v0, src)) / denominator
                    if t < 0.0 or t >= best:
                        continue
                    p = (src[0] + d[0] * t, src[1] + d[1] * t, src[2] + d[2] * t)
                    # inside: the three edge functions all agree with the normal
                    eps = -1e-7 * _dot(n, n)
                    if (
                        _dot(_cross(_sub(v1, v0), _sub(p, v0)), n) < eps
                        or _dot(_cross(_sub(v2, v1), _sub(p, v1)), n) < eps
                        or _dot(_cross(_sub(v0, v2), _sub(p, v2)), n) < eps
                    ):
                        continue
                    best = t
                    length = math.sqrt(_dot(n, n))
                    found = (t, p, (n[0] / length, n[1] / length, n[2] / length), tag)
        return found


@cache
def _park_triangles(stadium: Stadium) -> _TriangleSet:
    """The stadium's own collision mesh, indexed once and shared (read-only)."""
    return _TriangleSet(mesh_triangles(stadium))


def _placed_triangles(
    mesh: dict[str, Any], location: Sequence[float], yaw_deg: float
) -> list[MeshTriangle]:
    """A hazard's local triangles placed in mesh space at a field-space location.

    Turned ``yaw_deg`` about Y (PSMTXRotRad 'Y': x' = x cos + z sin, z' = -x sin + z cos).
    """
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    ox, oy, oz = location[0], -location[1], location[2]
    out: list[MeshTriangle] = []
    for (a, b, d), tag in zip(mesh["tris"], mesh["tags"], strict=False):
        placed = tuple((x * c + z * s + ox, y + oy, -x * s + z * c + oz) for x, y, z in (a, b, d))
        out.append((placed[0], placed[1], placed[2], tag))
    return out


def _hazard_meshes(sheet: dict[str, Any]) -> dict[str, Any]:
    """The park's named hazard meshes. A park with none stores an empty JSON array."""
    meshes: Any = sheet.get("meshes") or {}
    return cast("dict[str, Any]", meshes) if isinstance(meshes, dict) else {}


# --- hazards -------------------------------------------------------------------


class _Hazard:
    """One object from the park sheet. Subclasses add behaviour."""

    def __init__(self, spec: dict[str, Any], sheet: dict[str, Any], play: _LiveBall) -> None:
        self.spec = spec
        self.id: str = spec["id"]
        self.kind = HazardKind(spec["kind"])
        self.location: list[float] = list(spec["pos"])
        self.play = play
        self.mesh: dict[str, Any] | None = _hazard_meshes(sheet).get(spec.get("mesh") or "")
        self.triangles: _TriangleSet | None = None
        self.spent = False
        self.rebuild()

    def rebuild(self) -> None:
        self.triangles = (
            _TriangleSet(_placed_triangles(self.mesh, self.location, self.spec.get("yaw", 0)))
            if self.mesh
            else None
        )

    def update(self, ball: _Ball) -> None:
        """Called once a frame, before the ball's collision step."""

    def on_hit(self, ball: _Ball, kind: int) -> None:
        """The ball struck this hazard's triangles (surface ``kind``)."""
        self.play.record(
            LiveBallEventKind.HAZARD, hazard=self.id, hazard_kind=self.kind, surface=_name(kind)
        )


class _StarPad(_Hazard):
    """Bowser Castle's star panels and Wario Palace's sand stars: the first ball
    to touch one earns the batting team a star, and the pad is used up."""

    def on_hit(self, ball: _Ball, kind: int) -> None:
        if not self.spent:
            self.spent = True
            self.play.record(
                LiveBallEventKind.STAR, hazard=self.id, hazard_kind=HazardKind.STAR_PAD
            )


class _Block(_Hazard):
    """Peach Garden's floating blocks (sta_c4.c). A "?" block or a brick is
    secretly a brick, a used block or a note block (rand() % 3 at stadium load)."""

    def __init__(self, spec: dict[str, Any], sheet: dict[str, Any], play: _LiveBall) -> None:
        self.variant: str = spec["type"]
        if spec.get("hidden"):
            forced = play.options.mystery_blocks
            self.variant = (
                forced
                if forced in ("brick", "used", "note")
                else play.rng.choice(["brick", "used", "note"])
            )
        super().__init__(spec, sheet, play)
        self.mesh = _hazard_meshes(sheet)[self.variant]
        self.rebuild()

    def on_hit(self, ball: _Ball, kind: int) -> None:
        hidden = bool(self.spec.get("hidden"))
        if self.variant == "brick":
            self.spent = True  # breaks for the rest of the game, and pays a star
            self.play.record(
                LiveBallEventKind.HAZARD,
                hazard=self.id,
                hazard_kind=HazardKind.BLOCK,
                result="break",
                block="brick",
                is_assumed=hidden,
            )
            self.play.record(LiveBallEventKind.STAR, hazard=self.id, hazard_kind=HazardKind.BLOCK)
        else:
            self.play.record(
                LiveBallEventKind.HAZARD,
                hazard=self.id,
                hazard_kind=HazardKind.BLOCK,
                result="bounce",
                block=self.variant,
                is_assumed=hidden,
            )


class _Thwomp(_Hazard):
    """thwomp_slamControl (sta_c1.c:1984). Perched over the wall until a batted
    ball comes its way, then: rise, drop, sit, climb back."""

    def __init__(self, spec: dict[str, Any], sheet: dict[str, Any], play: _LiveBall) -> None:
        super().__init__(spec, sheet, play)
        self.home_y = self.location[1]
        self.state = "perched"
        self.timer = 0
        self.fall = 0.0

    def update(self, ball: _Ball) -> None:
        s = self.spec["slam"]
        if self.state == "perched":
            v = ball.velocity
            if v[2] <= 0 or ball.location[1] >= s["triggerHeight"]:
                return
            reach = ball.location[0] + v[0] * (self.location[2] - ball.location[2]) / v[2]
            if abs(reach - self.location[0]) > s["triggerHalfWidth"]:
                return
            if math.dist(ball.location, self.location) >= s["triggerDist"]:
                return
            self.state, self.timer = "rise", s["riseFrames"]
            self.fall = self.play.rng.choice(s["fallSpeeds"])
            self.play.record(
                LiveBallEventKind.HAZARD,
                hazard=self.id,
                hazard_kind=HazardKind.THWOMP,
                result="slam",
                fall_speed=self.fall,
                is_assumed=True,
            )
        elif self.state == "rise":
            self.location[1] += s["rise"] / s["riseFrames"]
            self.timer -= 1
            if self.timer <= 0:
                self.state = "fall"
        elif self.state == "fall":
            self.location[1] = max(s["floorY"], self.location[1] - self.fall)
            if self.location[1] <= s["floorY"]:
                self.state, self.timer = "hold", s["holdFrames"]
                self.play.record(
                    LiveBallEventKind.HAZARD,
                    hazard=self.id,
                    hazard_kind=HazardKind.THWOMP,
                    result="land",
                )
        elif self.state == "hold":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "return"
        elif self.state == "return":
            self.location[1] = min(self.home_y, self.location[1] + s["returnSpeed"])
            if self.location[1] >= self.home_y:
                self.state = "done"
        if self.state in ("rise", "fall", "return"):
            self.rebuild()


class _Tornado(_Hazard):
    """palaceNadoLogic (sta_c2.c:2300). Fixed in place. A ball passing through
    its column is carried round at radius 5 for at least one turn, then thrown
    out along a heading the game rolls."""

    def __init__(self, spec: dict[str, Any], sheet: dict[str, Any], play: _LiveBall) -> None:
        super().__init__(spec, sheet, play)
        self.state = "idle"
        self.direction = 1
        self.swept = 0.0
        self.exit = (0.0, 1.0)

    def _offset(self, ball: _Ball) -> tuple[float, float]:
        return ball.location[0] - self.location[0], ball.location[2] - self.location[2]

    def update(self, ball: _Ball) -> None:
        s = self.spec
        ex, ez = self._offset(ball)
        dist = math.hypot(ex, ez)
        if self.state == "idle":
            if dist < s["radius"] and s["minY"] < ball.location[1] < s["maxY"] and not ball.holder:
                self.state = "spinup"
                self.direction = self.play.rng.choice([1, -1])
        elif self.state == "spinup":
            if dist < s["radius"]:
                scale = s["radius"] / dist if dist > 1e-6 else 0.0
                ball.location[0] = self.location[0] + ex * scale
                ball.location[2] = self.location[2] + ez * scale
                base, span = s["exitCW"] if self.direction > 0 else s["exitCCW"]
                heading = math.radians((base + span * self.play.rng.random()) % 360)
                self.exit = (math.sin(heading), math.cos(heading))  # 0 = toward centre field
                self.state, self.swept = "hold", 0.0
                ball.capture(self)
                self.play.record(
                    LiveBallEventKind.CAPTURE,
                    hazard=self.id,
                    hazard_kind=HazardKind.TORNADO,
                    spin=self.direction,
                    is_assumed=True,
                )
            else:
                self.state = "idle"
        elif self.state == "hold":
            step = math.radians(self.direction * s["spin"])
            c, sn = math.cos(step), math.sin(step)
            nx, nz = ex * c + ez * sn, -ex * sn + ez * c

            def tangent(x: float, z: float) -> tuple[float, float]:
                return (z, -x) if self.direction > 0 else (-z, x)

            a, b = tangent(ex, ez), tangent(nx, nz)
            self.swept += s["spin"]

            def angle(u: tuple[float, float], v: tuple[float, float]) -> float:
                cosine = (u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v) or 1)
                return math.acos(max(-1.0, min(1.0, cosine)))

            if self.swept >= 360 and angle(a, self.exit) <= angle(a, b):
                chord = math.hypot(nx - ex, nz - ez)  # 2 * 5 * sin(2 deg) = 0.349 a frame
                ball.release((self.exit[0] * chord, 0.0, self.exit[1] * chord))
                self.state = "spent"
                self.play.record(
                    LiveBallEventKind.RELEASE, hazard=self.id, hazard_kind=HazardKind.TORNADO
                )
            else:
                ball.location[0] = self.location[0] + nx
                ball.location[2] = self.location[2] + nz


class _Piranha(_Hazard):
    """controlYoshiParkPlants (sta_c3.c:700). Pops up once a play when the ball
    comes near, catches it, turns, and spits it out along the ground."""

    def __init__(self, spec: dict[str, Any], sheet: dict[str, Any], play: _LiveBall) -> None:
        super().__init__(spec, sheet, play)
        self.state = "idle"
        self.timer = 0
        self.scale = 0.2
        self.heading = 0.0
        self.star = False

    def update(self, ball: _Ball) -> None:
        s = self.spec
        dx, dz = ball.location[0] - self.location[0], ball.location[2] - self.location[2]
        dist = math.hypot(dx, dz)
        if self.state == "idle":
            if dist <= s["popDist"] and ball.location[1] <= s["popMaxY"] and not ball.holder:
                self.state, self.timer = "pop", s["popFrames"]
                forced = self.play.options.star_plants
                self.star = (
                    forced if forced is not None else self.play.rng.random() < s["starChance"]
                )
                self.play.record(
                    LiveBallEventKind.HAZARD,
                    hazard=self.id,
                    hazard_kind=HazardKind.PIRANHA,
                    result="pop",
                    is_star_plant=self.star,
                    is_assumed=True,
                )
        elif self.state in ("pop", "up"):
            if self.state == "pop":
                self.scale = min(s["scale"], self.scale + (s["scale"] - 0.2) / s["popFrames"])
                self.timer -= 1
                if self.timer <= 0:
                    self.state = "up"
            if self.star or ball.holder:
                return
            # The plant lunges at a moving ball inside this envelope (fn_3_E29B4)
            # and snaps at a stopped one within 2.5 (fn_3_E28DC); the catch itself
            # is its mouth joint coming within 2.2 * scale of the ball.
            moving = math.hypot(*ball.velocity) > 1e-6
            reach = 5.5 * self.scale if moving else 2.5
            if dist < reach and (
                not moving or 1.5 * self.scale <= ball.location[1] <= 8.5 * self.scale
            ):
                base, span = s["spitBase"], s["spitRange"]
                self.heading = math.radians(
                    (base + self.play.rng.randrange(int(10 * span)) / 10.0) % 360
                )
                self.state, self.timer = "hold", s["turnFrames"] + s["spitFrame"]
                ball.capture(self)
                ball.velocity = [0.0, 0.0, 0.0]
                self.play.record(
                    LiveBallEventKind.CAPTURE,
                    hazard=self.id,
                    hazard_kind=HazardKind.PIRANHA,
                    heading_deg=math.degrees(self.heading),
                    is_assumed=True,
                    is_approximate=True,
                )
        elif self.state == "hold":
            ball.location[:] = [
                self.location[0],
                4.5 * self.scale,
                self.location[2],
            ]  # in its mouth
            self.timer -= 1
            if self.timer <= 0:
                sx, sz = math.sin(self.heading), -math.cos(self.heading)  # h -> (sin h, 0, -cos h)
                ball.location[:] = [
                    self.location[0] + self.scale * 5 * sx,
                    2.0 * self.scale,
                    self.location[2] + self.scale * 5 * sz,
                ]
                ball.release((s["spitSpeed"] * sx, 0.0, s["spitSpeed"] * sz))
                self.state = "spent"
                self.play.record(
                    LiveBallEventKind.RELEASE, hazard=self.id, hazard_kind=HazardKind.PIRANHA
                )


class _Chomp(_Hazard):
    """palaceChainChompControl (sta_c2.c:1399). Lunges once a play at a ball that
    comes close, and bats it away with its bite."""

    def __init__(self, spec: dict[str, Any], sheet: dict[str, Any], play: _LiveBall) -> None:
        super().__init__(spec, sheet, play)
        self.state = "awake"
        self.heading = (0.0, 0.0)
        self.vertical_speed = 0.0
        self.bitten = False

    def update(self, ball: _Ball) -> None:
        s = self.spec
        lunge, bite = s["lunge"], s["bite"]
        dx, dz = ball.location[0] - self.location[0], ball.location[2] - self.location[2]
        if self.state == "awake":
            if math.hypot(dx, dz) <= lunge["near"] and not ball.holder:
                h = math.atan2(dz, dx)
                self.heading = (math.cos(h), math.sin(h))
                self.vertical_speed = lunge["hopVy"]
                self.state = "lunge"
                self.play.record(
                    LiveBallEventKind.HAZARD,
                    hazard=self.id,
                    hazard_kind=HazardKind.CHOMP,
                    result="lunge",
                    is_assumed=True,
                    is_approximate=True,
                )
        elif self.state == "lunge":
            nx = self.location[0] + self.heading[0] * lunge["speed"]
            nz = self.location[2] + self.heading[1] * lunge["speed"]
            stake = s["stake"]
            if math.hypot(nx - stake[0], nz - stake[2]) > lunge["maxChain"]:
                self.state = "spent"  # chain pulled taut: the attack is over
            else:
                self.location[0], self.location[2] = nx, nz
                self.location[1] = max(0.0, self.location[1] + self.vertical_speed)
                self.vertical_speed -= lunge["gravity"]
                if self.location[1] <= 0.0 and self.vertical_speed < 0:
                    self.vertical_speed = 0.2  # each landing re-hops along the same line
            self.rebuild()
            if not self.bitten:
                c = (self.location[0], self.location[1] + bite["centerY"], self.location[2])
                off = _sub(ball.location, c)
                d = math.sqrt(_dot(off, off))
                if d < bite["radius"]:
                    u = (off[0] / d, off[1] / d, off[2] / d) if d > 1e-6 else (0.0, 1.0, 0.0)
                    ball.location[:] = [c[i] + u[i] * bite["radius"] for i in range(3)]
                    ball.velocity[:] = [u[i] * bite["push"] for i in range(3)]
                    ball.acceleration[:] = [0.0, 0.0, 0.0]
                    self.bitten = True
                    self.play.record(
                        LiveBallEventKind.HAZARD,
                        hazard=self.id,
                        hazard_kind=HazardKind.CHOMP,
                        result="bite",
                    )


class _Panel(_Hazard):
    """Toy Field's floor panels: what the ball first touches decides the play.
    The eight on the grass are round (``radius``); the seven at the foot of the
    outfield wall are wedges turned by ``yaw``: ``wedge`` is the half width at
    the wall edge, the half width at the near edge and the half depth of the
    tinted centre, and ``rim`` the metal border around it."""

    def contains(self, x: float, z: float) -> bool:
        dx, dz = x - self.location[0], z - self.location[2]
        wedge = self.spec.get("wedge")
        if not wedge:
            return math.hypot(dx, dz) <= self.spec["radius"]
        far, near, depth = wedge
        rim = self.spec.get("rim", 0.0)
        a = math.radians(self.spec.get("yaw", 0.0))
        # into the plate's own frame (the inverse of the placement turn); its +z
        # is toward the wall
        lx = dx * math.cos(a) - dz * math.sin(a)
        lz = dx * math.sin(a) + dz * math.cos(a)
        half = (far + near) / 2 + (far - near) / (2 * depth) * lz + rim
        return abs(lz) <= depth + rim and abs(lx) <= half


_HAZARD_CLASSES: dict[HazardKind, type[_Hazard]] = {
    HazardKind.STAR_PAD: _StarPad,
    HazardKind.BLOCK: _Block,
    HazardKind.THWOMP: _Thwomp,
    HazardKind.TORNADO: _Tornado,
    HazardKind.PIRANHA: _Piranha,
    HazardKind.CHOMP: _Chomp,
    HazardKind.KLAPTRAP: _Hazard,
    HazardKind.PANEL: _Panel,
    HazardKind.WALL_PANEL: _Hazard,
    HazardKind.WINDMILL: _Hazard,
}


# --- the ball ------------------------------------------------------------------


class _Ball:
    def __init__(self, location: Sequence[float]) -> None:
        self.location = list(location)
        self.previous = list(location)
        self.velocity = [0.0, 0.0, 0.0]
        self.acceleration = [0.0, 0.0, 0.0]
        self.state = _IN_AIR
        self.rolling = False
        self.ground_frames = 0  # framesOnGroundUntilPickedUp
        self.holder: _Hazard | None = None  # the hazard holding the ball (plant, tornado)
        self.recent: list[_Vec] = []  # recent locations, newest first (pastCoordinates)

    def capture(self, hazard: _Hazard) -> None:
        self.holder = hazard
        self.acceleration[:] = [0.0, 0.0, 0.0]

    def release(self, velocity: Sequence[float]) -> None:
        self.holder = None
        self.velocity[:] = list(velocity)


class _LiveBall:
    """One play, frame by frame."""

    def __init__(self, stadium: Stadium, options: _Options) -> None:
        self.options = options
        self.rng = random.Random(options.seed)
        sheet = park_sheet(stadium)
        surface = physics(stadium)
        self.bounce = (
            surface.first_bounce_vertical_keep,
            surface.bounce_vertical_keep,
            surface.landing_horizontal_keep,
            surface.bounce_horizontal_keep,
            surface.rolling_horizontal_keep,
        )
        self.wall_keep = surface.wall_keep
        self.ground_y = surface.ground_height
        self.floor_clamp = surface.has_flat_floor
        self.stadium = stadium
        self.park = _park_triangles(stadium)
        self.hazards: list[_Hazard] = []
        if options.hazards:
            for spec in sheet["hazards"]:
                cls = _HAZARD_CLASSES.get(HazardKind(spec["kind"]))
                if cls:
                    self.hazards.append(cls(spec, sheet, self))
        self.events: list[LiveBallEvent] = []
        self.frame = 0
        self.outcome: LiveBallOutcome | None = None
        self.terrain = 0
        self.previous_terrain = 0
        self.over_wall = 0
        self.land_frame: int | None = None
        self.ball = _Ball((0.0, 0.0, 0.0))

    # -- bookkeeping

    def record(self, kind: LiveBallEventKind, **details: Any) -> None:
        location = self.ball.location
        self.events.append(
            LiveBallEvent(
                frame=self.frame,
                kind=kind,
                location=(round(location[0], 4), round(location[1], 4), round(location[2], 4)),
                **details,
            )
        )

    def _settle(self, outcome: LiveBallOutcome) -> None:
        if self.outcome is None:
            self.outcome = outcome
            self.record(LiveBallEventKind.OUTCOME, outcome=outcome)

    # -- collision queries

    def _cast(
        self,
        src: _Vec,
        dst: _Vec,
        hazard_segment: tuple[_Vec, _Vec] | None = None,
    ) -> tuple[_Hit | None, _Hazard | None]:
        """checkCollision: a hazard hit wins outright; the park is only tested
        when no hazard was hit."""
        best: _Hit | None = None
        owner: _Hazard | None = None
        segment = hazard_segment if hazard_segment is not None else (src, dst)
        for hazard in self.hazards:
            if hazard.triangles is None or hazard.spent or isinstance(hazard, _Panel):
                continue
            hit = hazard.triangles.ray_cast(segment[0], segment[1], best[0] if best else 1.0)
            if hit:
                best, owner = hit, hazard
        if best:
            return best, owner
        return self.park.ray_cast(src, dst), None

    @staticmethod
    def _is_foul(x: float, z: float, tag: int = 0) -> bool:
        return bool(tag & FOUL_BIT) or abs(x) > z

    # -- ballCollisionLogic

    def _collide(self) -> None:
        b = self.ball
        gy = self.ground_y
        # Probe A: what kind of ground is under the ball
        under = self.park.ray_cast(
            (b.location[0], min(-b.location[1], -0.1), b.location[2]),
            (b.location[0], 10.0, b.location[2]),
        )
        self.previous_terrain = self.terrain
        if under:
            self.terrain = under[3]
        # Probe B: this frame's movement. Wario Palace, Yoshi Park and DK Jungle
        # sweep their hazards over the last five frames instead, with no radius.
        src, dst = _to_mesh(b.previous, gy), _to_mesh(b.location, gy)
        hazard_segment = None
        if self.stadium in _SWEEPING_STADIUMS and len(b.recent) >= 5:
            hazard_segment = (_to_mesh(b.recent[4]), _to_mesh(b.location))
        hit, hazard = self._cast(src, dst, hazard_segment)
        if not hit:
            self._check_dead()
            return
        _, point, n, tag = hit
        kind = tag & 0x7F
        was_in_air = b.state == _IN_AIR
        if hazard:
            hazard.on_hit(b, kind)

        # where the ball sits, and its mirrored velocity (built the game's way)
        fraction = 1.0 if src[1] == dst[1] else 1.0 - (src[1] - point[1]) / (src[1] - dst[1])
        off = gy + _SURFACE_OFFSET
        b.location[:] = [point[0] + n[0] * off, -(point[1] + n[1] * off), point[2] + n[2] * off]
        mirrored = (b.velocity[0], -b.velocity[1], b.velocity[2])
        axis = (1.0, 0.0, 0.0) if abs(n[0]) < 0.5 else (0.0, 1.0, 0.0)
        p1 = _cross(n, axis)
        p2 = _cross(n, p1)
        vn, v1, v2 = -_dot(mirrored, n), _dot(mirrored, p1), _dot(mirrored, p2)
        b.velocity[:] = [
            n[0] * vn + p1[0] * v1 + p2[0] * v2,
            -(n[1] * vn + p1[1] * v1 + p2[1] * v2),
            n[2] * vn + p1[2] * v1 + p2[2] * v2,
        ]

        if kind in _GROUND:
            count = 0 if was_in_air else b.ground_frames
            b.velocity[1] *= self.bounce[0] if count == 0 else self.bounce[1]
            if (
                not b.rolling
                and b.velocity[1] < _ROLL_VERTICAL_SPEED
                and count >= _ROLL_MIN_CONTACTS
            ):
                b.rolling = True
            if b.rolling:
                b.velocity[1] = 0.0
            b.acceleration[0] *= 0.5
            b.acceleration[2] *= 0.5
            if was_in_air:
                keep = self.bounce[2]
                b.state = _LANDED
                self.land_frame = self.frame if self.land_frame is None else self.land_frame
                self.record(LiveBallEventKind.LAND, surface=_name(kind))
                if self._is_foul(b.location[0], b.location[2], tag):
                    self._settle(LiveBallOutcome.FOUL)
                self._panel_under()
            else:
                keep = self.bounce[4] if b.rolling else self.bounce[3]
                if not b.rolling:
                    self.record(LiveBallEventKind.BOUNCE, surface=_name(kind))
            b.velocity[0] *= keep
            b.velocity[2] *= keep
            # finish the frame along the new velocity, unless something is in the way
            end = [b.location[i] + b.velocity[i] * fraction for i in range(3)]
            if not self._cast(_to_mesh(b.location, gy), _to_mesh(end, gy))[0]:
                b.location[:] = end
            b.ground_frames = min(b.ground_frames + 1, 255)
        else:
            b.location[1] += gy
            b.acceleration[:] = [0.0, 0.0, 0.0]
            foul = bool(tag & FOUL_BIT)
            name = _name(kind)
            floor = False
            if kind == _FOUL_POLE:
                keep = 0.3
                self._settle(
                    LiveBallOutcome.HOME_RUN
                    if was_in_air and self.outcome is not LiveBallOutcome.FOUL
                    else LiveBallOutcome.GROUND_RULE_DOUBLE
                )
            elif kind in (_WALL, _UNCLIMBABLE_WALL, _HAZARD_WALL):
                keep = self.wall_keep
                if was_in_air and foul:
                    self._settle(LiveBallOutcome.FOUL)
                else:
                    b.state = _LANDED
                    self.record(LiveBallEventKind.WALL, surface=name)
            elif kind == _CHOMP_PEN:
                keep = 0.3
                self.record(LiveBallEventKind.WALL, surface=name)
            elif kind in (_OUT_OF_PLAY, _PIT_WALL, _PIT, _HAZARD_STRUCTURE) and was_in_air:
                keep = 0.3
                self._settle(LiveBallOutcome.FOUL if foul else LiveBallOutcome.HOME_RUN)
            elif kind in _BLOCK_KEEP:
                keep, floor = _BLOCK_KEEP[kind], True
            elif kind in _HALF_KEEP:
                keep, floor = 0.5, True
            else:
                keep = 0.3
                if kind in (_PIT_WALL, _PIT):
                    self._settle(
                        LiveBallOutcome.FOUL
                        if foul or self.outcome is LiveBallOutcome.FOUL
                        else LiveBallOutcome.GROUND_RULE_DOUBLE
                    )
                else:
                    self.record(LiveBallEventKind.WALL, surface=name)
            b.velocity[:] = [v * keep for v in b.velocity]
            if floor and math.hypot(b.velocity[0], b.velocity[2]) < _MIN_HAZARD_SPEED:
                speed = math.hypot(b.velocity[0], b.velocity[2])
                if speed > 0:
                    b.velocity[0] *= _MIN_HAZARD_SPEED / speed
                    b.velocity[2] *= _MIN_HAZARD_SPEED / speed
                else:
                    r = math.hypot(b.location[0], b.location[2]) or 1.0
                    b.velocity[0] = _MIN_HAZARD_SPEED * b.location[0] / r
                    b.velocity[2] = _MIN_HAZARD_SPEED * b.location[2] / r
            if self.floor_clamp and b.location[1] < gy + _SURFACE_OFFSET:
                b.location[1] = gy + _SURFACE_OFFSET
                if b.velocity[1] < 0:
                    b.velocity[1] = -b.velocity[1]
            if b.rolling and b.velocity[1] < 0:
                b.velocity[1] = -b.velocity[1]
            b.ground_frames = min(b.ground_frames + 1, 255)
        if math.hypot(b.velocity[0], b.velocity[2]) < 0.0001:
            b.velocity[0] = b.velocity[2] = 0.0

    def _panel_under(self) -> None:
        """Toy Field: the panel the ball lands on calls the play."""
        for hazard in self.hazards:
            if isinstance(hazard, _Panel) and hazard.contains(
                self.ball.location[0], self.ball.location[2]
            ):
                self.record(
                    LiveBallEventKind.PANEL,
                    hazard=hazard.id,
                    hazard_kind=HazardKind.PANEL,
                    label=hazard.spec["label"].replace("\n", " "),
                )
                return

    def _check_dead(self) -> None:
        """No contact this frame: a ball in the air over out-of-play ground for
        five frames is gone."""
        b = self.ball
        if self.over_wall:
            self.over_wall += 1
        if (self.terrain & 0x7F) != _OUT_OF_PLAY or self.outcome:
            return
        foul = self._is_foul(b.location[0], b.location[2], self.terrain)
        if b.state == _IN_AIR and self.over_wall >= _OVER_WALL_FRAMES:
            self._settle(LiveBallOutcome.FOUL if foul else LiveBallOutcome.HOME_RUN)
        elif b.state == _LANDED and (self.previous_terrain & 0x7F) == _OUT_OF_PLAY:
            self._settle(LiveBallOutcome.GROUND_RULE_DOUBLE)
        if not self.over_wall:
            self.over_wall = 1

    # -- the frame loop

    def run(
        self, trajectory: Iterable[Sequence[float]], acceleration: Sequence[float]
    ) -> LiveBallResult:
        """Follow ``trajectory`` until the ball first touches anything, then integrate freely."""
        flight = [(p[0], p[1], p[2]) for p in trajectory]
        if not flight:
            raise ValueError("trajectory is empty; need at least the contact point")
        self.ball = b = _Ball(flight[0])
        self.land_frame = None
        self.events = []
        points: list[Point] = [flight[0]]
        max_frames = self.options.max_frames
        roll_frames = self.options.roll_frames
        stop_at = self.options.stop_at
        on_rails = True
        b.acceleration[:] = [float(a) for a in acceleration]  # contacts damp or clear it
        slow = 0

        def rounded() -> Point:
            return (round(b.location[0], 4), round(b.location[1], 4), round(b.location[2], 4))

        while self.frame < max_frames and self.outcome is None:
            self.frame += 1
            f = self.frame
            b.recent.insert(0, (b.location[0], b.location[1], b.location[2]))
            del b.recent[8:]
            b.previous[:] = b.location
            if b.holder:
                b.holder.update(b)  # the hazard moves the ball
                for hazard in self.hazards:
                    if hazard is not b.holder and isinstance(hazard, (_Thwomp, _Chomp)):
                        hazard.update(b)
                points.append(rounded())
                continue
            # The hit simulation pins its landing frame to the ground plane, so
            # its last usable frame is the one before the flight ends.
            if on_rails and f < len(flight) - 2:
                b.velocity[:] = [flight[f][i] - flight[f - 1][i] for i in range(3)]
                b.location[:] = flight[f]
            else:
                on_rails = False
                b.velocity[1] -= GRAVITY_PER_FRAME_SQUARED
                b.velocity[:] = [
                    v * VELOCITY_KEPT_PER_FRAME + a
                    for v, a in zip(b.velocity, b.acceleration, strict=True)
                ]
                b.location[:] = [p + v for p, v in zip(b.location, b.velocity, strict=True)]
            for hazard in self.hazards:
                hazard.update(b)
            if b.holder:
                on_rails = False
                points.append(rounded())
                continue
            before = (tuple(b.velocity), b.state)
            self._collide()
            if on_rails and (tuple(b.velocity), b.state) != before:
                on_rails = False  # something was hit in flight
            elif on_rails and any(abs(b.location[i] - flight[f][i]) > 1e-9 for i in range(3)):
                on_rails = False  # a hazard moved the ball
            if self.floor_clamp and b.location[1] < self.ground_y:
                b.location[1] = self.ground_y
                if b.velocity[1] < 0:
                    b.velocity[1] = -b.velocity[1]
            points.append(rounded())

            if b.state == _LANDED and self.outcome is None:
                speed = math.hypot(b.velocity[0], b.velocity[2])
                slow = slow + 1 if (speed < 0.005 and abs(b.velocity[1]) < 0.01) else 0
                if slow >= 3:
                    self._settle(LiveBallOutcome.STOPPED)
                elif (
                    stop_at
                    and self.land_frame is not None
                    and math.hypot(b.location[0] - stop_at[0], b.location[2] - stop_at[1]) < 1.5
                ):
                    self._settle(LiveBallOutcome.FIELDED)
                elif self.land_frame is not None and f - self.land_frame >= roll_frames:
                    self._settle(LiveBallOutcome.IN_PLAY)
        if self.outcome is None:
            self._settle(LiveBallOutcome.IN_PLAY)
        assert self.outcome is not None
        return LiveBallResult(
            trajectory=tuple(points),
            events=tuple(self.events),
            outcome=self.outcome,
            land_frame=self.land_frame,
        )
