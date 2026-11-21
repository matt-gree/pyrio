"""Derive STADIUM_WALLS from the game's stadium collision models.

The outfield wall is the set of collision triangles of type
BALL_COLLISION_TYPE_WALL. Collision semantics are taken from the decomp
(include/game/ball/collision_primitives.h, src/game/ball/ball_physics.c):

  * The game masks the type as ``collType & 0x7F`` (ball_physics.c:2295), so
    0x80 is a FOUL flag rather than part of the type. Wall panels in foul
    territory are 0x82 and do not belong in a fair-territory table -- at Mario
    Stadium they are the 2.0-high wall out past the pole.
  * BALL_COLLISION_TYPE_UNCLIMBABLE_WALL (5) is also treated as a wall for
    bouncing (ball_physics.c:2783), but in these models its panels are
    0.3-1.6m kerbs sitting at the same z as the fence, not the fence itself.
  * Mesh y is inverted world height: the game probes with
    ``-(ball.y - groundYForBounces)`` (ball_physics.c:2750), so the wall top is
    y=0 and a point's height above the field is -y. A naive max(y) reads 0.0 at
    every stadium.

Two things vary between stadiums, and both have to be handled:

  * Most walls are planar vertical faces, so a triangle's corners project onto
    one line in (x, z). DK Jungle's do not -- its wall is a curved tri-strip
    whose triangles span up to 3.3m off any plan line.
  * Height is the UPPER ENVELOPE of the triangles at an x, not a triangle's
    y-span and not its y-max edge. A y-span measures one course's thickness; a
    y-max edge misses a triangle with only one corner at its top. Peach
    Garden's centre wall is a triangulated silhouette, and both readings got it
    wrong there -- see wall_height_at.

So geometry comes from the top edges (the wall's rim in plan view) and height
is resolved separately, per x, from whichever triangles stand on that line at
that x. Segments are then built from the panel lines exactly, never sampled:
the nearest panel can only change at a panel edge or where two panels cross, so
taking those plus every triangle corner as breakpoints yields intervals on
which one panel is nearest and the height is constant.

Caveat on provenance: the game never does a geometric "did it clear the wall"
test. It integrates the trajectory and probes the collision mesh each frame
(checkCollision), and a home run is a ball that never struck a wall or
foul-line triangle. A one-dimensional wall_at(x) is therefore an approximation
of a 3-D mesh by construction: it holds one surface per x, so it would hide a
tall far panel behind a short near one. That case does not arise here -- only
Bowser Castle has overlapping panels, and its nearer corner panel is also its
taller one -- but the table cannot express it if a future model set has it.

The models come from RioVisualizer's extraction; ZZZZ.dat is not in the decomp
checkout, so they have not been re-extracted from the disc independently.

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
MIN_WALL_DISTANCE = 40.0     # nearer than this is backstop / dugout
MERGE_TOLERANCE = 1e-3       # when two adjacent intervals are the same line
MIN_SEGMENT_WIDTH = 1e-3     # narrower than this is a numerical sliver
COINCIDENT_Z = 1e-3          # panels this close in z are the same surface
ON_WALL_Z = 0.05             # a triangle this close in z stands on that wall


# ---------------------------------------------------------------- extraction

def wall_triangles(doc):
    """Every fair-territory outfield wall triangle, as 3 (x, y, z) corners."""
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
                out.append(pts)
    return out


def wall_lines(tris):
    """(x0, x1, z0, z1) per wall line, from each triangle's top edge.

    The edge at maximum y is the wall's rim, which is its line in plan view.
    This is geometry only -- height is resolved by wall_height_at, because an
    edge-based height is wrong wherever a triangle has a single corner at its
    top.
    """
    out = []
    for pts in tris:
        y_max = max(p[1] for p in pts)
        top = [p for p in pts if abs(p[1] - y_max) < 1e-6]
        if len(top) != 2:
            continue
        (x0, _, z0), (x1, _, z1) = sorted(top)
        if abs(x1 - x0) < 1e-6:
            continue        # edge-on, no x extent
        out.append((x0, x1, z0, z1))
    return out


# ------------------------------------------------------------------- height

def _covers(tri, x):
    xs = [p[0] for p in tri]
    return min(xs) - 1e-9 <= x <= max(xs) + 1e-9


def _peak(tri):
    """The triangle's highest point in world height (-y, mesh y is inverted)."""
    return -min(p[1] for p in tri)


def _stands_on(tri, m, c):
    """Does this triangle stand on the wall line z = m*x + c?

    At least two corners must lie on the line. Two, not three: DK Jungle's
    wall is a curved strip whose triangles straddle the kinks, so a triangle
    can have two corners on one line segment and its third up to 3.3m away.
    Requiring all three discarded nearly all of them. Bracketing the line's z
    by the triangle's slice instead is too loose, for the same reason -- those
    wide slices bracket lines the triangle does not stand on.
    """
    on = sum(1 for px, _, pz in tri if abs(m * px + c - pz) <= ON_WALL_Z)
    return on >= 2


def wall_height_at(tris, x, m, c):
    """Top of the wall standing at (x, z) -- the upper envelope there.

    Height is neither a triangle's y-span nor its y-max edge:

      * A y-span measures one course's THICKNESS, which equals the wall height
        only for a one-course wall on the ground, where y_max is 0.
      * A y-max edge misses any triangle with a single corner at its top.

    Peach Garden's centre wall is a triangulated silhouette where both fail.
    The triangle carrying the 20.99 top across x -7..-5 is (-7, 18),
    (-7, 20.99), (-5, 20.99) in (x, height): one corner at its y-max, so an
    edge reading discards it, and a span reading calls it 2.99 thick. Taking
    the tallest triangle standing on the line gives 20.99 there and 23.0
    across x -5..5, which are the 21 and 23 of the hand-typed table -- it was
    right here and the first derivations were not.

    A triangle's peak is used rather than its top interpolated at x, because
    the triangulation is not consistent between stadiums: several of DK
    Jungle's wall triangles have a diagonal top edge, so an interpolated top
    ramps down to the ground inside the panel and reported heights swinging
    0.00 to 4.00 on a wall that is 3.5 high. The peak of whatever wall
    triangle stands here is what a ball has to clear.
    """
    best = None
    for tri in tris:
        if _stands_on(tri, m, c) and _covers(tri, x):
            peak = _peak(tri)
            best = peak if best is None else max(best, peak)
    return best


# ------------------------------------------------------------------ segments

def _z_at(line, x):
    x0, x1, z0, z1 = line
    return z0 + (z1 - z0) * ((x - x0) / (x1 - x0))


def _coeffs(line):
    """(m, c) of a wall line in the z = m*x + c form."""
    x0, x1, z0, z1 = line
    m = (z1 - z0) / (x1 - x0)
    return m, z0 - m * x0


def nearest_wall(lines, tris, x):
    """(z, height) of the wall at x, or None if x has no wall.

    Nearest in z wins -- the surface the ball meets first -- and coincident
    lines tie-break on the greater height, since a ball at this x has to clear
    every surface here. This is the single definition of "the wall at x", so
    segments() builds from it and validate() checks against it and the two
    cannot drift apart.
    """
    best = None
    for line in lines:
        if line[0] <= x <= line[1]:
            z = _z_at(line, x)
            m, c = _coeffs(line)
            height = wall_height_at(tris, x, m, c)
            if height is None:
                continue
            height = round(height, 4)
            if best is None or z < best[0] - COINCIDENT_Z:
                best = (z, height)
            elif z < best[0] + COINCIDENT_Z and height > best[1]:
                best = (z, height)
    return best


def _breakpoints(lines, tris):
    """Every x where the nearest wall or its height can change.

    Lines are exact segments, so the nearest one changes only at a line's own
    end or where two lines cross. Height changes only at a triangle corner.
    Collecting all three gives intervals on which one line is nearest and the
    height is constant, which is what makes the output exact rather than
    sampled.
    """
    marks = set()
    for x0, x1, _, _ in lines:
        marks.update((x0, x1))
    for tri in tris:
        marks.update(p[0] for p in tri)
    for i, a in enumerate(lines):
        for b in lines[i + 1:]:
            lo, hi = max(a[0], b[0]), min(a[1], b[1])
            if hi - lo <= MIN_SEGMENT_WIDTH:
                continue
            ma, ca = _coeffs(a)
            mb, cb = _coeffs(b)
            if abs(ma - mb) < 1e-12:
                continue
            x = (cb - ca) / (ma - mb)
            if lo < x < hi:
                marks.add(x)

    # Collapse breakpoints that coincide to within a sliver. A line's end and
    # a triangle corner at the same place can differ by ~5e-5 in the model's
    # floats, which would otherwise leave an interval too narrow to emit and
    # so a gap in a table that must be contiguous for wall_at to work.
    collapsed = []
    for x in sorted(marks):
        if not collapsed or x - collapsed[-1] > MIN_SEGMENT_WIDTH:
            collapsed.append(x)
    return collapsed


def segments(lines, tris):
    """Exact (start_x, end_x, height, m, c) runs for the nearest wall."""
    marks = _breakpoints(lines, tris)
    runs = []
    for lo, hi in zip(marks, marks[1:]):
        if hi - lo <= MIN_SEGMENT_WIDTH:
            continue
        mid = 0.5 * (lo + hi)
        chosen = nearest_wall(lines, tris, mid)
        if chosen is None:
            continue
        z_mid, height = chosen
        best = None
        for line in lines:
            if line[0] <= mid <= line[1] and abs(_z_at(line, mid) - z_mid) < COINCIDENT_Z:
                if best is None or _z_at(line, mid) < _z_at(best, mid):
                    best = line
        if best is None:
            continue
        m, c = _coeffs(best)
        if runs:
            px0, px1, ph, pm, pc = runs[-1]
            if (abs(pm - m) < MERGE_TOLERANCE and abs(pc - c) < MERGE_TOLERANCE
                    and ph == height and abs(px1 - lo) < MIN_SEGMENT_WIDTH):
                runs[-1] = (px0, hi, ph, pm, pc)
                continue
        runs.append((lo, hi, height, m, c))

    # x is kept to 4dp, not 2dp. Breakpoints are panel edges, and at Bowser
    # Castle's corner a 0.59m tower panel abuts the fence: 2dp moves a boundary
    # by up to 5mm, enough to hand a slice of one segment the neighbouring
    # surface's z (2.6m away) and height. 4dp bounds that at 50um.
    return [(round(x0, 4), round(x1, 4), round(h, 2), round(m, 6), round(c, 4))
            for x0, x1, h, m, c in runs]


def degenerate(segs):
    """Segments a one-dimensional wall_at cannot honestly represent.

    Only true slivers qualify. A steep slope does not: DK Jungle's wall really
    does taper into the foul pole at m=-5.2, and wall_at reproduces that
    exactly. An earlier version flagged steepness and so condemned a faithful
    segment while passing sampled-chord artifacts that were the real fault.
    """
    return [s for s in segs if (s[1] - s[0]) < MIN_SEGMENT_WIDTH]


def validate(lines, tris, segs, per_segment=40):
    """Worst (distance, height) error of the segments against the model.

    Samples strictly inside every segment, so narrow runs are checked as
    closely as wide ones, and steps in by the rounding slop so a boundary that
    moved in the last decimal is not scored as a segment-wide error.
    """
    worst_z = worst_h = 0.0
    n = 0
    for sx, ex, height, m, c in segs:
        margin = min(1e-3, 0.25 * (ex - sx))
        lo, hi = sx + margin, ex - margin
        for k in range(per_segment + 1):
            x = lo + (hi - lo) * k / per_segment
            truth = nearest_wall(lines, tris, x)
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
        tris = wall_triangles(json.load(path.open()))
        lines = wall_lines(tris)
        if not lines:
            report.append(f"{path.stem:16} no wall-typed triangles")
            continue
        segs = segments(lines, tris)
        dz, dh, n = validate(lines, tris, segs)
        bad = degenerate(segs)
        note = f"   NOT USABLE: {len(bad)} degenerate segment(s)" if bad else ""
        report.append(f"{path.stem:16} {len(lines):>3} lines -> {len(segs):>3} segments"
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
