"""Derive STADIUM_WALLS from the game's stadium collision models.

The outfield wall is the set of collision triangles of type
BALL_COLLISION_TYPE_WALL. Collision semantics are taken from the decomp
(include/game/ball/collision_primitives.h, src/game/ball/ball_physics.c):

  * The game masks the type as ``collType & 0x7F`` (ball_physics.c:2295), so
    0x80 is a FOUL flag rather than part of the type. Wall panels in foul
    territory are 0x82 and do not belong in a fair-territory table -- at Mario
    Stadium they are the 2.0-high wall out past the pole, and including them
    corrupted both the segmentation and the height.
  * BALL_COLLISION_TYPE_UNCLIMBABLE_WALL (5) is also treated as a wall for
    bouncing (ball_physics.c:2783), but in these models its panels are
    0.3-1.6m kerbs sitting at the same z as the fence, not the fence itself.
    Including them makes the nearest-surface pick lose the real wall height.
  * Mesh y is inverted world height: the game probes with
    ``-(ball.y - groundYForBounces)`` (ball_physics.c:2750), so a panel spans
    y=-height to y=0 and the wall top IS y=0. A naive max(y) therefore reads
    0.0 at every stadium; the triangle's y-SPAN is the height.

Each wall panel is a quad split into two triangles; the edge at maximum y gives
the panel's (x, z) line.

Caveat on provenance: the game never does a geometric "did it clear the wall"
test. It integrates the trajectory and probes the collision mesh each frame
(checkCollision), and a home run is a ball that never struck a wall or
foul-line triangle. A one-dimensional wall_at(x) is therefore an approximation
of a 3-D mesh by construction, which is why overlapping corner panels cannot be
represented exactly. The models themselves come from RioVisualizer's
extraction; ZZZZ.dat is not in the decomp checkout, so they have not been
re-extracted from the disc independently.

Corners project onto overlapping x ranges, which a one-dimensional
``wall_at(x)`` cannot represent, so at each x this keeps the NEAREST wall
(minimum z) and that panel's height -- the surface the ball meets first.

Fine samples are merged back into linear runs, and the result is re-sampled
against the model to prove the segments reproduce it. Emits a STADIUM_WALLS
block for src/pyrio/stadiums.py.

Usage:
    python tools/derive_stadium_walls.py <models-dir> [--validate-only]

<models-dir> holds one JSON collision file per stadium, named after it, each
containing "Triangle Collections".
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

WALL_COLLISION = 0x02        # BALL_COLLISION_TYPE_WALL
FOUL_FLAG = 0x80             # BALL_COLLISION_TYPE_FOUL, a flag not a type
TYPE_MASK = 0x7F             # what the game masks with (ball_physics.c:2295)
MIN_WALL_DISTANCE = 40.0   # nearer than this is backstop / dugout
SAMPLE_STEP = 0.25         # x resolution when flattening corners
SLOPE_TOLERANCE = 2e-2     # when to start a new linear run


def wall_panels(doc):
    """(x0, x1, z0, z1, height) per wall triangle, from its top edge."""
    out = []
    for box in doc["Triangle Collections"]:
        for collection in box["Triangles"]:
            points = collection["Points"]
            step = 3 if collection["CollectionType"] == 0 else 1
            for i in range(0, len(points) - 2, step):
                tri = points[i:i + 3]
                coll_type = tri[2]["CollisionType"]
                if coll_type & FOUL_FLAG:
                    continue        # wall, but in foul territory
                if (coll_type & TYPE_MASK) != WALL_COLLISION:
                    continue
                pts = [(p["Point"]["X"], p["Point"]["Y"], p["Point"]["Z"]) for p in tri]
                cx = sum(p[0] for p in pts) / 3
                cz = sum(p[2] for p in pts) / 3
                if math.hypot(cx, cz) < MIN_WALL_DISTANCE:
                    continue
                y_max = max(p[1] for p in pts)
                y_min = min(p[1] for p in pts)
                top = [p for p in pts if abs(p[1] - y_max) < 1e-6]
                if len(top) != 2 or y_max - y_min <= 0:
                    continue
                (x0, _, z0), (x1, _, z1) = sorted(top)
                if abs(x1 - x0) < 1e-6:
                    continue        # edge-on, no x extent
                out.append((x0, x1, z0, z1, round(y_max - y_min, 2)))
    return out


def nearest_wall(panels, x):
    """(z, height) of the closest wall at x, or None if x has no wall."""
    best = None
    for x0, x1, z0, z1, height in panels:
        if x0 <= x <= x1:
            z = z0 + (z1 - z0) * ((x - x0) / (x1 - x0))
            if best is None or z < best[0]:
                best = (z, height)
    return best


def segments(panels):
    """Merge fine samples into (start_x, end_x, height, m, c) runs."""
    lo = min(p[0] for p in panels)
    hi = max(p[1] for p in panels)
    samples, x = [], lo
    while x <= hi + 1e-9:
        samples.append((round(x, 3), nearest_wall(panels, x)))
        x += SAMPLE_STEP

    runs, run, run_m = [], [], None
    for x, s in samples:
        if s is None:
            if len(run) > 1:
                runs.append(run)
            run, run_m = [], None
            continue
        if run:
            px, (pz, ph) = run[-1]
            slope = (s[0] - pz) / (x - px)
            new_height = abs(s[1] - ph) > 1e-6
            new_slope = run_m is not None and abs(slope - run_m) > SLOPE_TOLERANCE
            if new_height or new_slope:
                runs.append(run)
                run, run_m = [], None
        run.append((x, s))
        if len(run) == 2:
            run_m = (run[1][1][0] - run[0][1][0]) / (run[1][0] - run[0][0])
    if len(run) > 1:
        runs.append(run)

    out = []
    for r in runs:
        (x0, (z0, height)), (x1, (z1, _)) = r[0], r[-1]
        m = (z1 - z0) / (x1 - x0) if x1 != x0 else 0.0
        out.append((round(x0, 2), round(x1, 2), height, round(m, 4), round(z0 - m * x0, 2)))
    return out


def degenerate(segs):
    """Segments a one-dimensional wall_at cannot honestly represent.

    Corner panels overlap in x, and flattening them can leave zero-width or
    near-vertical runs. wall_at matches `sx <= x < ex`, so a zero-width segment
    is simply dead, and a 0.25m-wide run with a slope of -11 is noise rather
    than wall. These must be resolved before the table is used.
    """
    return [s for s in segs if (s[1] - s[0]) < 0.5 or abs(s[3]) > 5.0]


def validate(panels, segs):
    """Worst (distance, height) error of the segments against the model.

    NOTE: this samples on a grid and matches `sx <= x < ex`, so it cannot see
    inside segments narrower than the step -- exactly where the corner
    degeneracy lives. Read it together with degenerate().
    """
    worst_z = worst_h = 0.0
    n = 0
    xs = []
    x = min(p[0] for p in panels)
    hi = max(p[1] for p in panels)
    while x <= hi:
        xs.append(x)
        x += SAMPLE_STEP * 2
    # Also sample just inside each segment, so narrow runs are not skipped.
    xs.extend(s[0] + min(1e-3, max(0.0, (s[1] - s[0]) / 2)) for s in segs)
    for x in sorted(xs):
        truth = nearest_wall(panels, x)
        if truth is None:
            continue
        for sx, ex, height, m, c in segs:
            if sx <= x < ex:
                worst_z = max(worst_z, abs(m * x + c - truth[0]))
                worst_h = max(worst_h, abs(height - truth[1]))
                n += 1
                break
    return worst_z, worst_h, n


def emit(name, segs) -> str:
    sx = ", ".join(f"{s[0]}" for s in segs)
    ex = ", ".join(f"{s[1]}" for s in segs)
    h = ", ".join(f"{s[2]}" for s in segs)
    m = ", ".join(f"{s[3]}" for s in segs)
    c = ", ".join(f"{s[4]}" for s in segs)
    return (f'    "{name}": {{\n'
            f'        "starting_x": [{sx}],\n'
            f'        "ending_x": [{ex}],\n'
            f'        "wall_height": [{h}],\n'
            f'        "m": [{m}],\n'
            f'        "c": [{c}],\n'
            f'    }},\n')


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().split("Usage:")[1].strip(), file=sys.stderr)
        return 2
    models = pathlib.Path(argv[1])
    validate_only = "--validate-only" in argv

    blocks, report = [], []
    for path in sorted(models.glob("*.json")):
        panels = wall_panels(json.load(path.open()))
        if not panels:
            report.append(f"{path.stem:16} no wall-typed triangles")
            continue
        segs = segments(panels)
        dz, dh, n = validate(panels, segs)
        bad = degenerate(segs)
        note = f"   NOT USABLE: {len(bad)} degenerate segment(s)" if bad else ""
        report.append(f"{path.stem:16} {len(panels):>3} panels -> {len(segs):>3} segments"
                      f"   max dz={dz:.3f}m  max dh={dh:.3f}  ({n} samples){note}")
        blocks.append(emit(path.stem, segs))

    print("\n".join(report), file=sys.stderr)
    if not validate_only:
        print("STADIUM_WALLS = {")
        print("".join(blocks), end="")
        print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
