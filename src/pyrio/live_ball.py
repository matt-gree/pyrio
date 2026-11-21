"""Live-ball physics after contact: bounces, walls, and stadium hazards.

``hit_simulation`` ends where the ball first reaches the ground. This module
carries on from there the way the game does, following the Mario Superstar
Baseball decompilation (mssb-dtk):

  liveBallHitPhysics   ball_physics.c:1666   the per-frame step
  ballCollisionLogic   ball_physics.c:2490   what a surface does to the ball
  checkForBallDead     ball_physics.c:2995   home run / foul over out-of-play ground
  checkCollision       collision_primitives.c (asm)   hazards first, then the park
  sta_c1..sta_c6.c     the hazards themselves

The ball is tested against the park's collision triangles and against each
hazard's own triangles. Collision meshes are stored Y-down, as the game stores
them; ball space is Y-up. Functions here take and return ball-space points and
flip Y at the mesh boundary.

Ported from RioVisualizer's ``rio_visualizer/physics.py``, which is the
original work and remains the reference implementation. The physics is carried
over unchanged -- the constants and the order of operations come from the
decomp, and rewriting them to taste is how subtle divergence gets introduced.
What is new here is the data loading (``load_stadium``) and the typed entry
points.

Standard library only, so importing this costs nothing that the rest of pyrio
does not already pay for.

Why this exists alongside ``stadiums.STADIUM_WALLS``
---------------------------------------------------
``stadiums`` answers wall questions from a one-dimensional table: one wall
position and one height per x. That is cheap and good enough for a quick
"would this clear the fence", but it cannot express a wall whose top slopes, a
tall surface standing behind a shorter one, or the UNCLIMBABLE_WALL panels the
game also bounces balls off (see the KNOWN GAP note in
tools/derive_stadium_walls.py). This module has none of those limits, because
it does what the game does: cast the ball's path against the actual mesh. Use
``stadiums`` for a fast approximation and this for an answer.

What is exact and what is not
-----------------------------
Exact (constants and order from the decomp): gravity, drag, ground bounce and
roll, wall rebounds, the surface outcomes, the hazard rebound multipliers, the
Thwomp slam cycle, the tornado orbit, the plant's spit.

The game rolls its own dice for hazards (stadium rng(), reseeded every frame
between pitches), and a stat file does not record them. Wherever a hazard
needs a roll -- which way a tornado spins, where a plant spits, what a "?"
block turns out to be -- this module draws from a generator seeded by the hit,
and marks the event ``assumed``. The same hit always replays the same way; it
is one of the outcomes the game could have produced, not a recording of it.

Approximations, marked ``approx`` on their events: a Piranha Plant's catch
uses its lunge envelope instead of its animated mouth joint, and a Chain
Chomp's lunge is a straight hop along its launch heading.
"""
from __future__ import annotations

import functools
import gzip
import json
import math
import pathlib
import random
from typing import Any, Iterator, Optional, Sequence

_CONSTANTS = pathlib.Path(__file__).resolve().parent / "constants"
COLLISION_DIR = _CONSTANTS / "collision"
PARK_DIR = _CONSTANTS / "parks"

GRAVITY = 0.00275          # lbl_3_data_45FC
DRAG = 0.996               # 1 - lbl_3_data_4600 / 10000
ROLL_VY = 0.08             # lbl_3_data_4604: below this the ball starts rolling
ROLL_MIN_CONTACTS = 2      # lbl_3_data_4608
SURFACE_OFFSET = 0.005     # the ball rests this far (plus groundY) off a surface
MIN_HAZARD_SPEED = 0.03    # horizontal speed floor after a hazard hit
OVER_WALL_FRAMES = 5       # airborne frames over out-of-play ground before a home run
FIRST_BASE_Z = 19.4

# BALL_COLLISION_TYPE (collision_primitives.h); bit 0x80 marks foul territory.
# BACK_WALL is the decomp's BALL_COLLISION_TYPE_UNCLIMBABLE_WALL and HR_MARKER
# its BALL_COLLISION_TYPE_FOUL_LINE; the names here are RioVisualizer's and are
# kept so the two files read alike.
GRASS, WALL, STRUCTURE, HR_MARKER, BACK_WALL, DIRT, PIT_WALL, PIT, ROUGH, WATER, CHOMP_AREA = range(1, 12)
SURFACE_NAMES = {
    GRASS: "grass", WALL: "wall", STRUCTURE: "out of play", HR_MARKER: "foul pole", BACK_WALL: "back wall",
    DIRT: "dirt", PIT_WALL: "pit wall", PIT: "pit", ROUGH: "rough", WATER: "water", CHOMP_AREA: "chomp pen",
    0x20: "hazard wall", 0x22: "star pad", 0x23: "hazard", 0x30: "chain chomp", 0x32: "sand star",
    0x10: "brick block", 0x11: "used block", 0x12: "note block", 0x13: "brick block",
    0x14: "used block", 0x15: "note block", 0x60: "barrel", 0x61: "klaptrap", 0x64: "piranha plant",
}
GROUND_KINDS = {GRASS, DIRT, ROUGH, WATER, 0x22, 0x32}
# lbl_3_data_610C: speed kept off hazard kinds 0x10..0x15
KNOCK_KEEP = {0x10: 0.1, 0x11: 0.4, 0x12: 0.7, 0x13: 0.2, 0x14: 0.5, 0x15: 1.0}
HALF_KEEP = {0x21, 0x30, 0x40, 0x60, 0x61}

IN_AIR, LANDED = 0, 1

# Outcomes LiveBall.run can settle on.
OUTCOMES = ("home_run", "foul", "ground_rule_double", "fielded", "stopped", "in_play")


# --------------------------------------------------------------------- data

def list_stadiums() -> list[str]:
    """Stadium names with a bundled collision mesh."""
    return sorted(p.name[: -len(".json.gz")] for p in COLLISION_DIR.glob("*.json.gz"))


@functools.lru_cache(maxsize=None)
def _load_mesh(name: str) -> dict:
    path = COLLISION_DIR / f"{name}.json.gz"
    if not path.is_file():
        raise ValueError(
            f"{name!r} has no collision mesh. Known stadiums: "
            f"{', '.join(list_stadiums())}."
        )
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


@functools.lru_cache(maxsize=None)
def _load_park(name: str) -> Optional[dict]:
    path = PARK_DIR / f"{name}.park.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_stadium(name: str) -> dict:
    """A stadium payload for ``continue_ball``: collision triangles plus hazards.

    The mesh and the hazard sheet are both cached and shared, so repeated calls
    are cheap -- but the returned dict is the cached object. ``LiveBall`` only
    reads it; do not mutate it.

    Raises ValueError for an unknown stadium rather than returning None, since
    every caller would otherwise have to check.
    """
    stadium = dict(_load_mesh(name))
    park = _load_park(name)
    if park is not None:
        stadium["Park"] = park
    return stadium


def _meshes(park: dict) -> dict:
    """The park's named hazard meshes as a dict.

    A park with no meshes stores them as an empty JSON array, so normalize
    before the hazards index into it. RioVisualizer never trips over this
    because the parks that lack meshes also have no hazard kind it implements.
    """
    meshes = park.get("meshes") or {}
    return meshes if isinstance(meshes, dict) else {}


# ------------------------------------------------------------------ vectors
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _to_mesh(p, lift=0.0):
    """Ball space -> mesh space (Y down), optionally lowered by the ball radius."""
    return (p[0], -(p[1] - lift), p[2])


# ------------------------------------------------------------------- meshes
class TriangleSet:
    """Triangles in mesh space with a coarse XZ grid, and the game's segment test.

    checkTriangleCollisions is one-sided: a triangle only stops a segment that
    comes at its front, the side N = (v1 - v0) x (v2 - v0) points to.
    """

    CELL = 10.0

    def __init__(self, triangles):
        self.tris = []      # (v0, v1, v2, normal, tag)
        self.grid = {}
        for v0, v1, v2, tag in triangles:
            n = _cross(_sub(v1, v0), _sub(v2, v0))
            if _dot(n, n) < 1e-18:
                continue
            idx = len(self.tris)
            self.tris.append((v0, v1, v2, n, tag))
            x0, x1 = min(v0[0], v1[0], v2[0]), max(v0[0], v1[0], v2[0])
            z0, z1 = min(v0[2], v1[2], v2[2]), max(v0[2], v1[2], v2[2])
            for ix in range(int(math.floor(x0 / self.CELL)), int(math.floor(x1 / self.CELL)) + 1):
                for iz in range(int(math.floor(z0 / self.CELL)), int(math.floor(z1 / self.CELL)) + 1):
                    self.grid.setdefault((ix, iz), []).append(idx)

    def cast(self, src, dst, best=1.0):
        """Nearest front-facing hit along src -> dst (mesh space) as
        (fraction, point, unit normal, tag), or None."""
        d = _sub(dst, src)
        x0, x1 = min(src[0], dst[0]), max(src[0], dst[0])
        z0, z1 = min(src[2], dst[2]), max(src[2], dst[2])
        seen = set()
        found = None
        for ix in range(int(math.floor(x0 / self.CELL)), int(math.floor(x1 / self.CELL)) + 1):
            for iz in range(int(math.floor(z0 / self.CELL)), int(math.floor(z1 / self.CELL)) + 1):
                for idx in self.grid.get((ix, iz), ()):
                    if idx in seen:
                        continue
                    seen.add(idx)
                    v0, v1, v2, n, tag = self.tris[idx]
                    denom = _dot(n, d)
                    if denom >= 0.0:
                        continue                      # back face, or parallel
                    t = _dot(n, _sub(v0, src)) / denom
                    if t < 0.0 or t >= best:
                        continue
                    p = (src[0] + d[0] * t, src[1] + d[1] * t, src[2] + d[2] * t)
                    # inside test: the three edge functions all agree with the normal
                    eps = -1e-7 * _dot(n, n)
                    if (_dot(_cross(_sub(v1, v0), _sub(p, v0)), n) < eps
                            or _dot(_cross(_sub(v2, v1), _sub(p, v1)), n) < eps
                            or _dot(_cross(_sub(v0, v2), _sub(p, v2)), n) < eps):
                        continue
                    best = t
                    ln = math.sqrt(_dot(n, n))
                    found = (t, p, (n[0] / ln, n[1] / ln, n[2] / ln), tag)
        return found


def stadium_triangles(stadium: dict) -> Iterator[tuple]:
    """The park's collision triangles in mesh space, strips unrolled with the
    alternating winding the game gives them."""
    for box in stadium["Triangle Collections"]:
        for coll in box["Triangles"]:
            pts = coll["Points"]
            strip = coll["CollectionType"] != 0
            for k, i in enumerate(range(0, len(pts) - 2, 1 if strip else 3)):
                a, b, c = (tuple(p["Point"][ax] for ax in "XYZ") for p in pts[i:i + 3])
                tag = pts[i + 2]["CollisionType"]
                yield (c, b, a, tag) if strip and k % 2 else (a, b, c, tag)


def placed_triangles(mesh, pos, yaw_deg, tag_override=None):
    """A hazard's local triangles placed in mesh space at ball-space `pos`,
    turned `yaw_deg` about Y (PSMTXRotRad 'Y': x' = x cos + z sin, z' = -x sin + z cos)."""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    ox, oy, oz = pos[0], -pos[1], pos[2]
    out = []
    for tri, tag in zip(mesh["tris"], mesh["tags"]):
        out.append(tuple((x * c + z * s + ox, y + oy, -x * s + z * c + oz) for x, y, z in tri)
                   + (tag if tag_override is None else tag_override,))
    return out


# ------------------------------------------------------------------ hazards
class Hazard:
    """One object from the park sheet. Subclasses add behaviour."""

    def __init__(self, spec, park, sim):
        self.spec = spec
        self.id = spec["id"]
        self.kind = spec["kind"]
        self.pos = list(spec["pos"])
        self.sim = sim
        self.mesh = _meshes(park).get(spec.get("mesh") or "")
        self.tris = None
        self.spent = False
        self.rebuild()

    def rebuild(self):
        self.tris = TriangleSet(placed_triangles(self.mesh, self.pos, self.spec.get("yaw", 0))) if self.mesh else None

    def update(self, ball):
        """Called once per frame before the ball's collision step."""

    def on_hit(self, ball, kind):
        """The ball struck this hazard's triangles (surface kind `kind`)."""
        self.sim.event("hazard", hazard=self.id, what=self.kind, surface=SURFACE_NAMES.get(kind, hex(kind)))


class StarPad(Hazard):
    """Bowser Castle's star panels and Wario Palace's sand stars: the first ball
    to touch one earns the batting team a star, and the pad is used up."""

    def on_hit(self, ball, kind):
        if not self.spent:
            self.spent = True
            self.sim.event("star", hazard=self.id, what="starPad")


class Block(Hazard):
    """Peach Garden's floating blocks (sta_c4.c). A "?" block or a brick is
    secretly a brick, a used block or a note block (rand() % 3 at stadium load)."""

    def __init__(self, spec, park, sim):
        self.variant = spec["type"]
        if spec.get("hidden"):
            forced = sim.options.get("mystery_blocks")
            self.variant = forced if forced in ("brick", "used", "note") else sim.rng.choice(["brick", "used", "note"])
        super().__init__(spec, park, sim)
        self.mesh = _meshes(park)[self.variant]
        self.rebuild()

    def on_hit(self, ball, kind):
        hidden = bool(self.spec.get("hidden"))
        if self.variant == "brick":
            self.spent = True     # breaks; gone for the rest of the game, and pays a star
            self.sim.event("hazard", hazard=self.id, what="block", result="break", variant="brick", assumed=hidden)
            self.sim.event("star", hazard=self.id, what="block")
        else:
            self.sim.event("hazard", hazard=self.id, what="block", result="bounce", variant=self.variant, assumed=hidden)


class Thwomp(Hazard):
    """thwomp_slamControl (sta_c1.c:1984). Perched over the wall until a batted
    ball comes its way, then: rise, drop, sit, climb back."""

    def __init__(self, spec, park, sim):
        super().__init__(spec, park, sim)
        self.home_y = self.pos[1]
        self.state = "perched"
        self.timer = 0
        self.fall = 0.0

    def update(self, ball):
        s = self.spec["slam"]
        if self.state == "perched":
            v = ball.vel
            if v[2] <= 0 or ball.pos[1] >= s["triggerHeight"]:
                return
            reach = ball.pos[0] + v[0] * (self.pos[2] - ball.pos[2]) / v[2]
            if abs(reach - self.pos[0]) > s["triggerHalfWidth"]:
                return
            if math.dist(ball.pos, self.pos) >= s["triggerDist"]:
                return
            self.state, self.timer = "rise", s["riseFrames"]
            self.fall = self.sim.rng.choice(s["fallSpeeds"])
            self.sim.event("hazard", hazard=self.id, what="thwomp", result="slam", fall=self.fall, assumed=True)
        elif self.state == "rise":
            self.pos[1] += s["rise"] / s["riseFrames"]
            self.timer -= 1
            if self.timer <= 0:
                self.state = "fall"
        elif self.state == "fall":
            self.pos[1] = max(s["floorY"], self.pos[1] - self.fall)
            if self.pos[1] <= s["floorY"]:
                self.state, self.timer = "hold", s["holdFrames"]
                self.sim.event("hazard", hazard=self.id, what="thwomp", result="land")
        elif self.state == "hold":
            self.timer -= 1
            if self.timer <= 0:
                self.state = "return"
        elif self.state == "return":
            self.pos[1] = min(self.home_y, self.pos[1] + s["returnSpeed"])
            if self.pos[1] >= self.home_y:
                self.state = "done"
        if self.state in ("rise", "fall", "return"):
            self.rebuild()


class Tornado(Hazard):
    """palaceNadoLogic (sta_c2.c:2300). Fixed in place. A ball passing through
    its column is carried round at radius 5 for at least one turn, then thrown
    out along a heading the game rolls."""

    def __init__(self, spec, park, sim):
        super().__init__(spec, park, sim)
        self.state = "idle"
        self.dir = 1
        self.swept = 0.0
        self.exit = (0.0, 1.0)

    def _offset(self, ball):
        return ball.pos[0] - self.pos[0], ball.pos[2] - self.pos[2]

    def update(self, ball):
        s = self.spec
        ex, ez = self._offset(ball)
        dist = math.hypot(ex, ez)
        if self.state == "idle":
            if dist < s["radius"] and s["minY"] < ball.pos[1] < s["maxY"] and not ball.held:
                self.state = "spinup"
                self.dir = self.sim.rng.choice([1, -1])
        elif self.state == "spinup":
            if dist < s["radius"]:
                scale = s["radius"] / dist if dist > 1e-6 else 0.0
                ball.pos[0], ball.pos[2] = self.pos[0] + ex * scale, self.pos[2] + ez * scale
                base, span = s["exitCW"] if self.dir > 0 else s["exitCCW"]
                heading = math.radians((base + span * self.sim.rng.random()) % 360)
                self.exit = (math.sin(heading), math.cos(heading))   # 0 = toward centre field
                self.state, self.swept = "hold", 0.0
                ball.capture(self)
                self.sim.event("capture", hazard=self.id, what="tornado", spin=self.dir, assumed=True)
            else:
                self.state = "idle"
        elif self.state == "hold":
            step = math.radians(self.dir * s["spin"])
            c, sn = math.cos(step), math.sin(step)
            nx, nz = ex * c + ez * sn, -ex * sn + ez * c
            tangent = lambda x, z: (z, -x) if self.dir > 0 else (-z, x)
            a, b = tangent(ex, ez), tangent(nx, nz)
            self.swept += s["spin"]

            def angle(u, v):
                return math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v) or 1))))
            if self.swept >= 360 and angle(a, self.exit) <= angle(a, b):
                chord = math.hypot(nx - ex, nz - ez)                # 2 * 5 * sin(2 deg) = 0.349 m/frame
                ball.release((self.exit[0] * chord, 0.0, self.exit[1] * chord))
                self.state = "spent"
                self.sim.event("release", hazard=self.id, what="tornado")
            else:
                ball.pos[0], ball.pos[2] = self.pos[0] + nx, self.pos[2] + nz


class Piranha(Hazard):
    """controlYoshiParkPlants (sta_c3.c:700). Pops up once per play when the
    ball comes near, catches it, turns, and spits it out along the ground."""

    def __init__(self, spec, park, sim):
        super().__init__(spec, park, sim)
        self.state = "idle"
        self.timer = 0
        self.scale = 0.2
        self.heading = 0.0
        self.star = False

    def update(self, ball):
        s = self.spec
        dx, dz = ball.pos[0] - self.pos[0], ball.pos[2] - self.pos[2]
        dist = math.hypot(dx, dz)
        if self.state == "idle":
            if dist <= s["popDist"] and ball.pos[1] <= s["popMaxY"] and not ball.held:
                self.state, self.timer = "pop", s["popFrames"]
                forced = self.sim.options.get("star_plants")
                self.star = forced if isinstance(forced, bool) else self.sim.rng.random() < s["starChance"]
                self.sim.event("hazard", hazard=self.id, what="piranha", result="pop", star=self.star, assumed=True)
        elif self.state in ("pop", "up"):
            if self.state == "pop":
                self.scale = min(s["scale"], self.scale + (s["scale"] - 0.2) / s["popFrames"])
                self.timer -= 1
                if self.timer <= 0:
                    self.state = "up"
            if self.star or ball.held:
                return
            # The plant lunges at a moving ball inside this envelope (fn_3_E29B4)
            # and snaps at a stopped one within 2.5 (fn_3_E28DC); the catch itself
            # is its mouth joint coming within 2.2 * scale of the ball.
            moving = math.hypot(*ball.vel) > 1e-6
            reach = 5.5 * self.scale if moving else 2.5
            if dist < reach and (not moving or 1.5 * self.scale <= ball.pos[1] <= 8.5 * self.scale):
                base, span = s["spitBase"], s["spitRange"]
                self.heading = math.radians((base + self.sim.rng.randrange(int(10 * span)) / 10.0) % 360)
                self.state, self.timer = "hold", s["turnFrames"] + s["spitFrame"]
                ball.capture(self)
                ball.vel = [0.0, 0.0, 0.0]
                self.sim.event("capture", hazard=self.id, what="piranha", heading=math.degrees(self.heading),
                               assumed=True, approx=True)
        elif self.state == "hold":
            ball.pos[:] = [self.pos[0], 4.5 * self.scale, self.pos[2]]   # in its mouth
            self.timer -= 1
            if self.timer <= 0:
                sx, sz = math.sin(self.heading), -math.cos(self.heading)  # heading h -> (sin h, 0, -cos h)
                ball.pos[:] = [self.pos[0] + self.scale * 5 * sx, 2.0 * self.scale, self.pos[2] + self.scale * 5 * sz]
                ball.release((s["spitSpeed"] * sx, 0.0, s["spitSpeed"] * sz))
                self.state = "spent"
                self.sim.event("release", hazard=self.id, what="piranha")


class Chomp(Hazard):
    """palaceChainChompControl (sta_c2.c:1399). Lunges once per play at a ball
    that comes close, and bats it away with its bite."""

    def __init__(self, spec, park, sim):
        super().__init__(spec, park, sim)
        self.state = "awake"
        self.dirv = (0.0, 0.0)
        self.vy = 0.0
        self.bitten = False

    def update(self, ball):
        s = self.spec
        lunge, bite = s["lunge"], s["bite"]
        dx, dz = ball.pos[0] - self.pos[0], ball.pos[2] - self.pos[2]
        if self.state == "awake":
            if math.hypot(dx, dz) <= lunge["near"] and not ball.held:
                h = math.atan2(dz, dx)
                self.dirv = (math.cos(h), math.sin(h))
                self.vy = lunge["hopVy"]
                self.state = "lunge"
                self.sim.event("hazard", hazard=self.id, what="chomp", result="lunge", assumed=True, approx=True)
        elif self.state == "lunge":
            nx = self.pos[0] + self.dirv[0] * lunge["speed"]
            nz = self.pos[2] + self.dirv[1] * lunge["speed"]
            stake = s["stake"]
            if math.hypot(nx - stake[0], nz - stake[2]) > lunge["maxChain"]:
                self.state = "spent"      # chain pulled taut: the attack is over
            else:
                self.pos[0], self.pos[2] = nx, nz
                self.pos[1] = max(0.0, self.pos[1] + self.vy)
                self.vy -= lunge["gravity"]
                if self.pos[1] <= 0.0 and self.vy < 0:
                    self.vy = 0.2         # each landing re-hops along the same line
            self.rebuild()
            if not self.bitten:
                c = (self.pos[0], self.pos[1] + bite["centerY"], self.pos[2])
                off = _sub(tuple(ball.pos), c)
                d = math.sqrt(_dot(off, off))
                if d < bite["radius"]:
                    u = tuple(v / d for v in off) if d > 1e-6 else (0.0, 1.0, 0.0)
                    ball.pos[:] = [c[i] + u[i] * bite["radius"] for i in range(3)]
                    ball.vel[:] = [u[i] * bite["push"] for i in range(3)]
                    ball.accel[:] = [0.0, 0.0, 0.0]
                    self.bitten = True
                    self.sim.event("hazard", hazard=self.id, what="chomp", result="bite")


class Panel(Hazard):
    """Toy Field's floor panels: what the ball first touches decides the play.
    The eight on the grass are round (`radius`); the seven at the foot of the
    outfield wall are wedges turned by `yaw`: `wedge` is the half width at the
    wall edge, the half width at the near edge and the half depth of the
    tinted centre, and `rim` the metal border around it."""

    def contains(self, x, z):
        dx, dz = x - self.pos[0], z - self.pos[2]
        wedge = self.spec.get("wedge")
        if not wedge:
            return math.hypot(dx, dz) <= self.spec["radius"]
        far, near, depth = wedge
        rim = self.spec.get("rim", 0.0)
        a = math.radians(self.spec.get("yaw", 0.0))
        # into the plate's own frame (the inverse of placed_triangles' turn);
        # its +z is toward the wall
        lx = dx * math.cos(a) - dz * math.sin(a)
        lz = dx * math.sin(a) + dz * math.cos(a)
        half = (far + near) / 2 + (far - near) / (2 * depth) * lz + rim
        return abs(lz) <= depth + rim and abs(lx) <= half


HAZARD_CLASSES = {"starPad": StarPad, "block": Block, "thwomp": Thwomp, "tornado": Tornado,
                  "piranha": Piranha, "chomp": Chomp, "klaptrap": Hazard, "panel": Panel,
                  "wallPanel": Hazard, "windmill": Hazard}


# --------------------------------------------------------------------- ball
class Ball:
    def __init__(self, pos):
        self.pos = list(pos)
        self.prev = list(pos)
        self.vel = [0.0, 0.0, 0.0]
        self.accel = [0.0, 0.0, 0.0]
        self.state = IN_AIR
        self.rolling = False
        self.ground_frames = 0      # framesOnGroundUntilPickedUp
        self.held = None            # the hazard holding the ball (plant, tornado)
        self.past = []              # recent positions, newest first (pastCoordinates)

    def capture(self, hazard):
        self.held = hazard
        self.accel[:] = [0.0, 0.0, 0.0]

    def release(self, vel):
        self.held = None
        self.vel[:] = list(vel)


class LiveBall:
    """Carry a batted ball from contact until the play is settled.

    stadium   a payload from load_stadium(): collision triangles, plus "Park"
              (the hazard sheet) when the park has one
    options   seed (int)            the dice for hazard rolls
              hazards (bool)        False plays the park with its hazards removed
              mystery_blocks        'brick' | 'used' | 'note' forces Peach's "?" blocks
              star_plants (bool)    force Yoshi's plants to be (or not be) star plants
              max_frames            hard stop (default 1500)
              roll_frames           how long to follow the ball after it lands (default 420)
              stop_at ([x, z])      end the play when the landed ball reaches this
                                    point (a recorded fielder's pick-up)
    """

    def __init__(self, stadium: dict, options: Optional[dict] = None):
        self.options = dict(options or {})
        self.rng = random.Random(self.options.get("seed", 0))
        park = stadium.get("Park") or {}
        phys = park.get("physics") or {}
        self.bounce = phys.get("bounce", [0.44, 0.90, 0.66, 0.85, 0.999])
        self.wall_keep = phys.get("wall", 0.3)
        self.ground_y = phys.get("groundY", 0.15)
        self.floor_clamp = phys.get("floorClamp", True)
        self.stadium_id = park.get("id", 0)
        self.static = TriangleSet(stadium_triangles(stadium))
        self.hazards = []
        if self.options.get("hazards", True):
            for spec in park.get("hazards", []):
                cls = HAZARD_CLASSES.get(spec["kind"])
                if cls:
                    self.hazards.append(cls(spec, park, self))
        self.events = []
        self.frame = 0
        self.outcome = None
        self.terrain = 0
        self.prev_terrain = 0
        self.over_wall = 0
        self.land_frame = None
        self.ball = None

    # -- bookkeeping
    def event(self, type_, **extra):
        e = {"frame": self.frame, "type": type_, "pos": [round(v, 4) for v in self.ball.pos]}
        e.update(extra)
        self.events.append(e)

    def _settle(self, outcome):
        if self.outcome is None:
            self.outcome = outcome
            self.event(outcome)

    # -- collision queries
    def _cast(self, src, dst, hazards=True, hazard_src=None):
        """checkCollision: a hazard hit wins outright; the park is only tested
        when no hazard was hit. Returns (hit, hazard or None)."""
        if hazards:
            best, owner = None, None
            hs = hazard_src if hazard_src is not None else (src, dst)
            for h in self.hazards:
                if h.tris is None or h.spent or isinstance(h, Panel):
                    continue
                hit = h.tris.cast(hs[0], hs[1], best[0] if best else 1.0)
                if hit:
                    best, owner = hit, h
            if best:
                return best, owner
        return self.static.cast(src, dst), None

    def _is_foul(self, x, z, tag=0):
        return bool(tag & 0x80) or abs(x) > z

    # -- ballCollisionLogic
    def _collide(self):
        b = self.ball
        gy = self.ground_y
        # Probe A: what kind of ground is under the ball
        under = self.static.cast((b.pos[0], min(-b.pos[1], -0.1), b.pos[2]), (b.pos[0], 10.0, b.pos[2]))
        self.prev_terrain = self.terrain
        if under:
            self.terrain = under[3]
        # Probe B: this frame's movement. Wario Palace, Yoshi Park and DK Jungle
        # sweep their hazards over the last five frames instead, with no radius.
        src, dst = _to_mesh(b.prev, gy), _to_mesh(b.pos, gy)
        hazard_seg = None
        if self.stadium_id in (2, 3, 5) and len(b.past) >= 5:
            hazard_seg = (_to_mesh(b.past[4]), _to_mesh(b.pos))
        hit, hazard = self._cast(src, dst, hazard_src=hazard_seg)
        if not hit:
            self._check_dead()
            return
        t, point, n, tag = hit
        kind = tag & 0x7F
        was_air = b.state == IN_AIR
        if hazard:
            hazard.on_hit(b, kind)

        # where the ball sits, and its mirrored velocity (built the game's way)
        frac = 1.0 if src[1] == dst[1] else 1.0 - (src[1] - point[1]) / (src[1] - dst[1])
        off = gy + SURFACE_OFFSET
        b.pos[:] = [point[0] + n[0] * off, -(point[1] + n[1] * off), point[2] + n[2] * off]
        vm = (b.vel[0], -b.vel[1], b.vel[2])
        axis = (1.0, 0.0, 0.0) if abs(n[0]) < 0.5 else (0.0, 1.0, 0.0)
        p1 = _cross(n, axis)
        p2 = _cross(n, p1)
        vn, v1, v2 = -_dot(vm, n), _dot(vm, p1), _dot(vm, p2)
        b.vel[:] = [n[0] * vn + p1[0] * v1 + p2[0] * v2,
                    -(n[1] * vn + p1[1] * v1 + p2[1] * v2),
                    n[2] * vn + p1[2] * v1 + p2[2] * v2]

        if kind in GROUND_KINDS:
            count = 0 if was_air else b.ground_frames
            b.vel[1] *= self.bounce[0] if count == 0 else self.bounce[1]
            if not b.rolling and b.vel[1] < ROLL_VY and count >= ROLL_MIN_CONTACTS:
                b.rolling = True
            if b.rolling:
                b.vel[1] = 0.0
            b.accel[0] *= 0.5
            b.accel[2] *= 0.5
            if was_air:
                keep = self.bounce[2]
                b.state = LANDED
                self.land_frame = self.frame if self.land_frame is None else self.land_frame
                self.event("land", surface=SURFACE_NAMES.get(kind, hex(kind)))
                if self._is_foul(b.pos[0], b.pos[2], tag):
                    self._settle("foul")
                self._panel_under()
            else:
                keep = self.bounce[4] if b.rolling else self.bounce[3]
                if not b.rolling:
                    self.event("bounce", surface=SURFACE_NAMES.get(kind, hex(kind)))
            b.vel[0] *= keep
            b.vel[2] *= keep
            # finish the frame along the new velocity, unless something is in the way
            end = [b.pos[i] + b.vel[i] * frac for i in range(3)]
            if not self._cast(_to_mesh(b.pos, gy), _to_mesh(end, gy))[0]:
                b.pos[:] = end
            b.ground_frames = min(b.ground_frames + 1, 255)
        else:
            b.pos[1] += gy
            b.accel[:] = [0.0, 0.0, 0.0]
            foul = bool(tag & 0x80)
            name = SURFACE_NAMES.get(kind, hex(kind))
            floor = False
            if kind == HR_MARKER:
                keep = 0.3
                self._settle("home_run" if was_air and self.outcome != "foul" else "ground_rule_double")
            elif kind in (WALL, BACK_WALL, 0x20):
                keep = self.wall_keep
                if was_air and foul:
                    self._settle("foul")
                else:
                    b.state = LANDED
                    self.event("wall", surface=name)
            elif kind == CHOMP_AREA:
                keep = 0.3
                self.event("wall", surface=name)
            elif kind in (STRUCTURE, PIT_WALL, PIT, 0x23) and was_air:
                keep = 0.3
                self._settle("foul" if foul else "home_run")
            elif kind in KNOCK_KEEP:
                keep, floor = KNOCK_KEEP[kind], True
            elif kind in HALF_KEEP:
                keep, floor = 0.5, True
            else:
                keep = 0.3
                if kind in (PIT_WALL, PIT):
                    self._settle("foul" if foul or self.outcome == "foul" else "ground_rule_double")
                else:
                    self.event("wall", surface=name)
            b.vel[:] = [v * keep for v in b.vel]
            if floor and math.hypot(b.vel[0], b.vel[2]) < MIN_HAZARD_SPEED:
                speed = math.hypot(b.vel[0], b.vel[2])
                if speed > 0:
                    b.vel[0] *= MIN_HAZARD_SPEED / speed
                    b.vel[2] *= MIN_HAZARD_SPEED / speed
                else:
                    r = math.hypot(b.pos[0], b.pos[2]) or 1.0
                    b.vel[0], b.vel[2] = MIN_HAZARD_SPEED * b.pos[0] / r, MIN_HAZARD_SPEED * b.pos[2] / r
            if self.floor_clamp:
                if b.pos[1] < gy + SURFACE_OFFSET:
                    b.pos[1] = gy + SURFACE_OFFSET
                    if b.vel[1] < 0:
                        b.vel[1] = -b.vel[1]
            if b.rolling and b.vel[1] < 0:
                b.vel[1] = -b.vel[1]
            b.ground_frames = min(b.ground_frames + 1, 255)
        if math.hypot(b.vel[0], b.vel[2]) < 0.0001:
            b.vel[0] = b.vel[2] = 0.0

    def _panel_under(self):
        """Toy Field: the panel the ball lands on calls the play."""
        for h in self.hazards:
            if isinstance(h, Panel) and h.contains(self.ball.pos[0], self.ball.pos[2]):
                self.event("panel", hazard=h.id, what="panel", label=h.spec["label"].replace("\n", " "))
                return

    def _check_dead(self):
        """No contact this frame: a ball in the air over out-of-play ground for
        five frames is gone."""
        b = self.ball
        if self.over_wall:
            self.over_wall += 1
        if (self.terrain & 0x7F) != STRUCTURE or self.outcome:
            return
        foul = self._is_foul(b.pos[0], b.pos[2], self.terrain)
        if b.state == IN_AIR and self.over_wall >= OVER_WALL_FRAMES:
            self._settle("foul" if foul else "home_run")
        elif b.state == LANDED and (self.prev_terrain & 0x7F) == STRUCTURE:
            self._settle("ground_rule_double")
        if not self.over_wall:
            self.over_wall = 1

    # -- the frame loop
    def run(self, trajectory: Sequence[Sequence[float]],
            acceleration: Sequence[float] = (0.0, 0.0, 0.0)) -> dict:
        """Follow `trajectory` (the flight, one point per frame) until the ball
        first touches anything, then integrate freely.

        Returns {points, events, outcome, land_frame}. `points` has one
        ball-space position per frame from contact to the end of the play.
        """
        traj = [tuple(p) for p in trajectory]
        if not traj:
            raise ValueError("trajectory is empty; need at least the contact point")
        self.ball = b = Ball(traj[0])
        self.land_frame = None
        self.events = []
        points = [list(traj[0])]
        max_frames = int(self.options.get("max_frames", 1500))
        roll_frames = int(self.options.get("roll_frames", 420))
        stop_at = self.options.get("stop_at")
        on_rails = True
        b.accel[:] = [float(a) for a in acceleration]   # unused on rails; contacts damp or clear it
        slow = 0

        while self.frame < max_frames and self.outcome is None:
            self.frame += 1
            f = self.frame
            b.past.insert(0, tuple(b.pos))
            del b.past[8:]
            b.prev[:] = b.pos
            if b.held:
                b.held.update(b)             # the hazard moves the ball
                for h in self.hazards:
                    if h is not b.held and isinstance(h, (Thwomp, Chomp)):
                        h.update(b)
                points.append([round(v, 4) for v in b.pos])
                continue
            # the hit simulation pins the landing frame to the ground plane, so
            # its last usable frame is the one before the flight ends.
            if on_rails and f < len(traj) - 2:
                b.vel[:] = [traj[f][i] - traj[f - 1][i] for i in range(3)]
                b.pos[:] = traj[f]
            else:
                on_rails = False
                b.vel[1] -= GRAVITY
                b.vel[:] = [v * DRAG + a for v, a in zip(b.vel, b.accel)]
                b.pos[:] = [p + v for p, v in zip(b.pos, b.vel)]
            for h in self.hazards:
                h.update(b)
            if b.held:
                on_rails = False
                points.append([round(v, 4) for v in b.pos])
                continue
            before = (tuple(b.vel), b.state)
            self._collide()
            if on_rails and (tuple(b.vel), b.state) != before:
                on_rails = False             # something was hit in flight
            elif on_rails and any(abs(b.pos[i] - traj[f][i]) > 1e-9 for i in range(3)):
                on_rails = False             # a hazard moved the ball
            if self.floor_clamp and b.pos[1] < self.ground_y:
                b.pos[1] = self.ground_y
                if b.vel[1] < 0:
                    b.vel[1] = -b.vel[1]
            points.append([round(v, 4) for v in b.pos])

            if b.state == LANDED and self.outcome is None:
                speed = math.hypot(b.vel[0], b.vel[2])
                slow = slow + 1 if (speed < 0.005 and abs(b.vel[1]) < 0.01) else 0
                if slow >= 3:
                    self._settle("stopped")
                elif stop_at and self.land_frame is not None and \
                        math.hypot(b.pos[0] - stop_at[0], b.pos[2] - stop_at[1]) < 1.5:
                    self._settle("fielded")
                elif self.land_frame is not None and f - self.land_frame >= roll_frames:
                    self._settle("in_play")
        if self.outcome is None:
            self._settle("in_play")
        return {"points": points, "events": self.events, "outcome": self.outcome, "land_frame": self.land_frame}


def continue_ball(stadium: dict, trajectory: Sequence[Sequence[float]],
                  acceleration: Sequence[float] = (0.0, 0.0, 0.0), **options: Any) -> dict:
    """Play a flight out in `stadium` (a load_stadium() payload)."""
    return LiveBall(stadium, options).run(trajectory, acceleration)


def play_out(trajectory: Sequence[Sequence[float]], stadium: str,
             acceleration: Sequence[float] = (0.0, 0.0, 0.0), **options: Any) -> dict:
    """Play a flight out in a stadium named as ``StatObj.stadium()`` names it.

    The convenience form of ``continue_ball``: it loads the park for you.
    Prefer ``continue_ball`` with a payload held across calls when playing out
    many hits in one park, so the mesh is only indexed once.
    """
    return continue_ball(load_stadium(stadium), trajectory, acceleration, **options)


def is_home_run(trajectory: Sequence[Sequence[float]], stadium: str, **options: Any) -> bool:
    """Would this flight leave the park, judged against the collision mesh?

    The mesh-accurate counterpart of ``stadiums.is_home_run``, which answers
    from a one-dimensional table instead. This costs a full play-out, so it is
    much slower, and it resolves cases the table cannot -- a sloped wall top, a
    tall surface behind a shorter one, the UNCLIMBABLE_WALL panels.

    Hazards are left ON, because the game leaves them on: a ball a Thwomp
    swats down is not a home run. Pass ``hazards=False`` for the park's bare
    geometry.
    """
    return continue_ball(load_stadium(stadium), trajectory, **options)["outcome"] == "home_run"
