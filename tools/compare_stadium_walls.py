"""Compare pyrio's hand-typed STADIUM_WALLS against the game's collision models.

STADIUM_WALLS is transcribed from the JS `stadiums` constant: piecewise-linear
segments in field x, each with a slope/intercept for the wall's z and a wall
height. The authoritative geometry is the stadium collision model, where the
outfield wall is the set of triangles whose CollisionType low nibble is 0x02.

This reads those triangles and reports, per stadium, how far the hand-typed
wall sits from the modelled one. It changes nothing -- `is_home_run` and
`wall_collision_point` still use the table. Run it before touching those
numbers, because they decide home runs.

Usage:
    python tools/compare_stadium_walls.py [path/to/stadium/models]

The models are the per-stadium JSON collision files (one per stadium, named
after it, each containing "Triangle Collections"). RioVisualizer keeps a set
under rio_visualizer/data/stadiums/; pass that directory, or set
PYRIO_STADIUM_MODELS.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from pyrio.stadiums import STADIUM_WALLS  # noqa: E402

# Low nibble of CollisionType that marks a wall surface.
WALL_COLLISION = 0x02
# Triangles nearer than this to home are the backstop and dugout walls, not the
# outfield fence.
MIN_WALL_DISTANCE = 40.0
# Half-width in x used to collect the modelled wall near a sample point.
SAMPLE_TOLERANCE = 2.5


def wall_triangles(doc):
    """Yield (centroid_x, centroid_z, max_y) for each outfield-wall triangle.

    A collection is a triangle list (CollectionType 0, read in threes) or a
    strip (read one at a time). The collision type lives on the third point.
    """
    for box in doc["Triangle Collections"]:
        for collection in box["Triangles"]:
            points = collection["Points"]
            step = 3 if collection["CollectionType"] == 0 else 1
            for i in range(0, len(points) - 2, step):
                tri = points[i:i + 3]
                if (tri[2]["CollisionType"] & 0x0F) != WALL_COLLISION:
                    continue
                xs = [p["Point"]["X"] for p in tri]
                ys = [p["Point"]["Y"] for p in tri]
                zs = [p["Point"]["Z"] for p in tri]
                cx, cz = sum(xs) / 3, sum(zs) / 3
                if math.hypot(cx, cz) < MIN_WALL_DISTANCE:
                    continue
                yield cx, cz, max(ys)


def table_wall_at(stadium: str, x: float):
    """(wall_z, height) from STADIUM_WALLS, or None if no segment covers x."""
    spec = STADIUM_WALLS.get(stadium)
    if spec is None:
        return None
    for sx, ex, h, m, c in zip(spec["starting_x"], spec["ending_x"],
                               spec["wall_height"], spec["m"], spec["c"]):
        if sx <= x < ex:
            return m * x + c, h
    return None


def compare(stadium: str, triangles):
    """Per-sample (x, modelled_z, table_z, delta) across fair territory."""
    rows = []
    for x in range(-50, 51, 5):
        near = [t for t in triangles if abs(t[0] - x) <= SAMPLE_TOLERANCE]
        table = table_wall_at(stadium, x)
        if not near or table is None:
            continue
        modelled_z = min(t[1] for t in near)
        rows.append((x, modelled_z, table[0], modelled_z - table[0]))
    return rows


def main(argv):
    models = pathlib.Path(
        argv[1] if len(argv) > 1
        else os.environ.get("PYRIO_STADIUM_MODELS", "")
    )
    if not models.is_dir():
        print(__doc__.strip().split("Usage:")[1].strip(), file=sys.stderr)
        return 2

    print(f"{'stadium':16} {'tris':>5} {'in table':>8} {'max |dz|':>9} "
          f"{'mean dz':>8}  worst sample")
    for path in sorted(models.glob("*.json")):
        stadium = path.stem
        triangles = list(wall_triangles(json.load(path.open())))
        in_table = stadium in STADIUM_WALLS
        if not triangles:
            print(f"{stadium:16} {0:>5} {str(in_table):>8} "
                  f"{'-':>9} {'-':>8}  no wall-typed triangles")
            continue
        if not in_table:
            xs = [t[0] for t in triangles]
            print(f"{stadium:16} {len(triangles):>5} {'False':>8} "
                  f"{'-':>9} {'-':>8}  NO TABLE ENTRY "
                  f"(model spans x {min(xs):+.1f}..{max(xs):+.1f})")
            continue
        rows = compare(stadium, triangles)
        if not rows:
            print(f"{stadium:16} {len(triangles):>5} {'True':>8} "
                  f"{'-':>9} {'-':>8}  no overlapping samples")
            continue
        deltas = [r[3] for r in rows]
        worst = max(rows, key=lambda r: abs(r[3]))
        print(f"{stadium:16} {len(triangles):>5} {'True':>8} "
              f"{max(abs(d) for d in deltas):>9.2f} "
              f"{statistics.fmean(deltas):>8.2f}  "
              f"x={worst[0]:+3.0f}: model {worst[1]:.1f} vs table "
              f"{worst[2]:.1f} ({worst[3]:+.2f})")

    print("\nA negative delta means the modelled wall is CLOSER to home than "
          "the table says,\nso is_home_run is currently too generous there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
