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

Corners project onto overlapping x ranges, so at each x this keeps the NEAREST
wall (minimum z) and that panel's height -- the surface the ball meets first.

Segments are built from the panel lines directly, never sampled. The nearest
panel can only change at a panel edge or where two panels cross, so taking
both as breakpoints yields intervals on which one panel is nearest throughout,
and its exact (m, c, height) is emitted. All seven stadiums then reproduce the
model to 0.000m in distance and height. An earlier version flattened on a
0.25m grid and fitted lines through consecutive samples; where panels are
under a metre wide a run could hold only two samples drawn from *different*
panels, and the chord between them became the segment -- that is where Bowser
Castle's m=-11.1 slivers and its reported 2.774m error came from, not from the
geometry.

Caveat on provenance: the game never does a geometric "did it clear the wall"
test. It integrates the trajectory and probes the collision mesh each frame
(checkCollision), and a home run is a ball that never struck a wall or
foul-line triangle. A one-dimensional wall_at(x) is therefore an approximation
of a 3-D mesh by construction: it holds one surface per x, so it would hide a
tall far panel behind a short near one. That case does not arise here -- only
Bowser Castle has overlaps, and its nearer corner panel is also its taller
one -- but the table cannot express it if a future model set has it.

The models themselves come from RioVisualizer's extraction; ZZZZ.dat is not in
the decomp checkout, so they have not been re-extracted from the disc
independently. Emits a STADIUM_WALLS block for src/pyrio/stadiums.py.

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
MERGE_TOLERANCE = 1e-3     # when two adjacent intervals are the same line
MIN_SEGMENT_WIDTH = 1e-3   # narrower than this is a numerical sliver


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


def _z_at(panel, x):
    x0, x1, z0, z1, _ = panel
    return z0 + (z1 - z0) * ((x - x0) / (x1 - x0))


def _line(panel):
    """(m, c) of a panel's top edge in the z = m*x + c form."""
    x0, x1, z0, z1, _ = panel
    m = (z1 - z0) / (x1 - x0)
    return m, z0 - m * x0


def _breakpoints(panels):
    """Every x where the nearest panel can change.

    Panels are exact line segments, so the nearest one changes only at a
    panel's own edge or where two panels cross. Collecting both gives
    intervals on which a single panel is nearest throughout, which is what
    makes the output exact rather than sampled.
    """
    marks = set()
    for x0, x1, *_ in panels:
        marks.add(x0)
        marks.add(x1)
    for i, a in enumerate(panels):
        for b in panels[i + 1:]:
            lo, hi = max(a[0], b[0]), min(a[1], b[1])
            if hi - lo <= MIN_SEGMENT_WIDTH:
                continue
            ma, ca = _line(a)
            mb, cb = _line(b)
            if abs(ma - mb) < 1e-12:
                continue
            x = (cb - ca) / (ma - mb)
            if lo < x < hi:
                marks.add(x)
    return sorted(marks)


def segments(panels):
    """Exact (start_x, end_x, height, m, c) runs for the nearest wall surface.

    Where panels overlap in x the nearest (minimum z) one wins: that is the
    surface the ball meets first. In this model set only Bowser Castle has
    overlaps, and there the nearer panel is also the taller one (the 16.64
    corner tower in front of the 5.0 fence), so nearest-wins does not hide a
    tall wall behind a short one. A one-dimensional table could not express
    that case if it arose.
    """
    marks = _breakpoints(panels)
    runs = []
    for lo, hi in zip(marks, marks[1:]):
        if hi - lo <= MIN_SEGMENT_WIDTH:
            continue
        mid = 0.5 * (lo + hi)
        best = None
        for panel in panels:
            if panel[0] <= mid <= panel[1]:
                z = _z_at(panel, mid)
                if best is None or z < best[0]:
                    best = (z, panel)
        if best is None:
            continue
        m, c = _line(best[1])
        height = best[1][4]
        if runs:
            px0, px1, ph, pm, pc = runs[-1]
            same = (abs(pm - m) < MERGE_TOLERANCE
                    and abs(pc - c) < MERGE_TOLERANCE
                    and ph == height
                    and abs(px1 - lo) < MIN_SEGMENT_WIDTH)
            if same:
                runs[-1] = (px0, hi, ph, pm, pc)
                continue
        runs.append((lo, hi, height, m, c))

    # x is rounded to 4dp, not 2dp. The breakpoints are panel edges, and at
    # Bowser Castle's corner a 0.59m tower panel abuts the fence: 2dp moves a
    # boundary by up to 5mm, enough to hand a slice of one segment the
    # neighbouring surface's z (2.6m away) and height. 4dp bounds that at 50um.
    return [(round(x0, 4), round(x1, 4), h, round(m, 6), round(c, 4))
            for x0, x1, h, m, c in runs]


def degenerate(segs):
    """Segments a one-dimensional wall_at cannot honestly represent.

    Only true slivers qualify. A steep slope does not: DK Jungle's wall really
    does taper into the foul pole at m=-5.2, and wall_at reproduces that
    exactly. An earlier version flagged steepness and so condemned a faithful
    segment while passing the sampled-chord artifacts that were the real fault.
    """
    return [s for s in segs if (s[1] - s[0]) < MIN_SEGMENT_WIDTH]


def validate(panels, segs, per_segment=40):
    """Worst (distance, height) error of the segments against the model.

    Samples strictly inside every segment, so narrow runs are checked as
    closely as wide ones. The grid-based version this replaces stepped at a
    fixed 0.25m and could not see inside a segment narrower than the step --
    exactly where the corner artifacts lived.
    """
    worst_z = worst_h = 0.0
    n = 0
    for sx, ex, height, m, c in segs:
        # Step inside by the rounding slop, so a boundary that moved by half a
        # unit in the last decimal is not scored as a segment-wide error.
        margin = min(1e-3, 0.25 * (ex - sx))
        lo, hi = sx + margin, ex - margin
        for k in range(per_segment + 1):
            x = lo + (hi - lo) * k / per_segment
            truth = nearest_wall(panels, x)
            if truth is None:
                continue
            worst_z = max(worst_z, abs(m * x + c - truth[0]))
            worst_h = max(worst_h, abs(height - truth[1]))
            n += 1
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
