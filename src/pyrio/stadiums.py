"""MSSB stadium outfield-wall geometry and Peach Garden note blocks.

Each outfield wall is a set of line segments in the field X/Z plane: for
segment i the wall runs from x = starting_x[i] to x = ending_x[i] along the
line  z = m[i] * x + c[i]  with height wall_height[i]. STADIUM_WALLS is derived
from the game's own collision models (see tools/derive_stadium_walls.py); the
note blocks and the isHomeRun / hitNoteBlock logic come from the batting
calculator's index.js.

A segment holds one height, so this cannot express a wall whose top slopes, nor
a tall surface standing behind a shorter one. Neither occurs in the seven
stadiums; the generator checks for both. It also leaves out the
UNCLIMBABLE_WALL panels the game bounces balls off, which is a real gap (see
the comment above STADIUM_WALLS).

``live_ball`` has none of those limits: it casts the ball's path against the
actual collision mesh, the way the game does. Use this module for a fast
approximation and that one for an answer -- ``live_ball.is_home_run`` is the
same question asked of the mesh.

Keys match ``StatObj.stadium()`` normalized names (e.g. "Peach Garden", not
the JS's "Peach Gardens").

Note: trajectories produced by ``hit_simulation`` use the calculator's
unverified flight model, so HR/wall checks on simulated paths are
approximations of the game, not ground truth.
"""
from __future__ import annotations

import math
import os
from typing import Iterable, Optional

# Derived from the stadium collision models by tools/derive_stadium_walls.py,
# which reproduces them exactly: wall-typed triangles (BALL_COLLISION_TYPE_WALL,
# fair territory only), nearest surface per x, height taken as the top of the
# wall standing there. Regenerate rather than hand-editing.
#
# This replaces the transcription of the JS `stadiums` constant. The two agree
# on the wall's position everywhere -- the old breakpoints were these values
# rounded to integers -- and on height at Wario Palace, Yoshi Park, Bowser
# Castle, DK Jungle and Peach Garden's middle. Two of the old heights were
# wrong, in opposite directions, so they were transcription slips rather than
# any systematic bias:
#   Mario Stadium        was 3,  is 4.0  (all 8 wall panels measure 4.00)
#   Peach Garden corners were 8, are 7.0 (all 9 corner triangles measure 7.000)
# Toy Field was absent from the JS table and is included here.
#
# Known gap: BALL_COLLISION_TYPE_UNCLIMBABLE_WALL panels are excluded, so at a
# few x this understates the barrier and is_home_run is too generous there.
# The game bounces the ball off them exactly as off a wall
# (ball_physics.c:2783). Yoshi Park has fourteen posts along its outfield fence
# at 3.5-3.6 against the 3.2 recorded here, and Peach Garden reaches 30.0 where
# this table says 23.0. The foul poles are a different surface
# (BALL_COLLISION_TYPE_FOUL_LINE) and a ball off one is a home run, so they are
# not part of this gap. See the KNOWN GAP note in
# tools/derive_stadium_walls.py, and live_ball for the mesh-accurate answer.
STADIUM_WALLS = {
    "Bowser Castle": {
        "starting_x": [-54.4363, -54.0623, -53.4676, -52.217, -45.3188, -36.6322, -26.8103, -21.2497, -20.0654, -18.5346, -17.4522, -15.9191, -8.1376, 8.1376, 15.9191, 17.4522, 18.5346, 20.0654, 21.2497, 26.8103, 36.6322, 45.3188, 52.217, 53.4676, 54.0623],
        "ending_x": [-54.0623, -53.4676, -52.217, -45.3188, -36.6322, -26.8103, -21.2497, -20.0654, -18.5346, -17.4522, -15.9191, -8.1376, 8.1376, 15.9191, 17.4522, 18.5346, 20.0654, 21.2497, 26.8103, 36.6322, 45.3188, 52.217, 53.4676, 54.0623, 54.4363],
        "wall_height": [16.64, 16.64, 12.0, 5.0, 5.0, 5.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 5.0, 5.0, 5.0, 12.0, 16.64, 16.64],
        "m": [-1.000004, 1.0, 1.715334, 1.32012, 0.931046, 0.547168, 0.323751, -1.000002, 0.0, 0.999998, 0.478278, 0.200553, 0.0, -0.200553, -0.478278, -0.999998, 0.0, 1.000002, -0.323749, -0.547168, -0.931046, -1.32012, -1.715334, -1.0, 1.000004],
        "c": [2.7247, 108.0682, 150.5376, 129.9007, 112.2683, 98.206, 92.2161, 64.0868, 84.1522, 102.6868, 95.0398, 90.6187, 88.9866, 90.6187, 95.0398, 102.6868, 84.1522, 64.0868, 92.2161, 98.206, 112.2683, 129.9007, 150.5376, 108.0682, 2.7247],
    },
    "DK Jungle": {
        "starting_x": [-51.2114, -46.0863, -42.8404, -42.7986, -33.1491, -33.1318, -25.9913, -20.4, -9.0226, 9.0603, 20.4, 26.0511, 39.2906, 40.1068, 49.0594],
        "ending_x": [-46.0863, -42.8404, -42.7986, -33.1491, -33.1318, -25.9913, -20.4, -9.0226, 9.0603, 20.4, 26.0511, 39.2906, 40.1068, 49.0594, 51.4519],
        "wall_height": [3.5, 3.5, 6.83, 6.83, 3.5, 3.5, 3.5, 3.68, 4.0, 3.5, 4.0, 4.0, 3.52, 3.5, 3.52],
        "m": [1.685197, 2.813405, 2.813405, 1.796701, 1.796701, 0.678385, 0.348567, 0.348568, 0.011688, -0.383786, -0.383786, -0.80699, -0.806992, -1.741488, -5.237224],
        "c": [137.5126, 189.5075, 189.5075, 145.994, 145.9939, 108.9422, 100.3698, 100.3698, 97.3303, 100.9134, 100.9134, 111.9383, 111.9384, 149.418, 320.9169],
    },
    "Mario Stadium": {
        "starting_x": [-57.4152, -41.5506, -13.3121, 15.7805],
        "ending_x": [-41.5506, -13.3121, 15.7805, 57.461],
        "wall_height": [4.0, 4.0, 4.0, 4.0],
        "m": [1.602718, 0.611196, 0.0, -1.023017],
        "c": [149.3791, 108.1808, 100.0445, 116.1882],
    },
    "Peach Garden": {
        "starting_x": [-58.952, -54.2796, -45.6364, -35.0, -32.4544, -29.9088, -15.0748, -13.4, -11.8, -9.0, -7.0, -5.0, 5.0, 7.0, 9.0, 11.8, 13.4, 15.0748, 29.9088, 32.4544, 35.0, 45.6364, 54.2796, 57.3375],
        "ending_x": [-54.2796, -45.6364, -35.0, -32.4544, -29.9088, -15.0748, -13.4, -11.8, -9.0, -7.0, -5.0, 5.0, 7.0, 9.0, 11.8, 13.4, 15.0748, 29.9088, 32.4544, 35.0, 45.6364, 54.2796, 57.3375, 58.952],
        "wall_height": [7.0, 7.0, 7.0, 18.0, 18.0, 18.0, 18.0, 18.0, 18.0, 18.0, 20.99, 23.0, 20.99, 18.0, 18.0, 18.0, 18.0, 18.0, 18.0, 18.0, 7.0, 7.0, 7.0, 7.0],
        "m": [2.597932, 1.35429, 0.685267, -0.414212, 0.414213, 0.0, -0.827368, 5e-06, 0.137727, -0.699997, 0.0, 0.0, 0.0, 0.699997, -0.137727, -5e-06, 0.827368, 0.0, -0.414213, 0.414212, -0.685268, -1.35429, -2.597928, -2.597946],
        "c": [212.0205, 144.5161, 113.9843, 75.5026, 102.3886, 90.0, 77.5276, 88.6144, 90.2395, 82.7, 87.6, 87.6, 87.6, 82.7, 90.2395, 88.6144, 77.5276, 90.0, 102.3886, 75.5026, 113.9844, 144.5161, 212.0202, 212.0213],
    },
    "Toy Field": {
        "starting_x": [-59.952, -48.8736, -31.9, -11.0787, 11.0788, 31.9, 48.8737],
        "ending_x": [-48.8736, -31.9, -11.0787, 11.0788, 31.9, 48.8737, 59.9522],
        "wall_height": [10.5, 10.5, 10.5, 10.5, 10.5, 10.5, 10.5],
        "m": [1.732452, 0.839099, 0.36397, 0.0, -0.36397, -0.839101, -1.732419],
        "c": [163.8159, 120.1545, 104.9979, 100.9656, 104.9979, 120.1546, 163.8143],
    },
    "Wario Palace": {
        "starting_x": [-51.5685, -48.557, -39.5839, -25.8365, -9.0992, 9.099, 25.8365, 39.5839, 48.5569],
        "ending_x": [-48.557, -39.5839, -25.8365, -9.0992, 9.099, 25.8365, 39.5839, 48.5569, 51.5685],
        "wall_height": [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],
        "m": [4.224211, 1.714382, 0.837241, 0.377298, 3e-06, -0.377295, -0.837241, -1.714382, -4.224211],
        "c": [269.32, 147.4504, 112.7297, 100.8463, 97.4133, 100.8463, 112.7297, 147.4504, 269.32],
    },
    "Yoshi Park": {
        "starting_x": [-58.1086, -52.2813, -40.1169, -25.2185, -8.6016, 8.6016, 25.2185, 40.1169, 52.2813],
        "ending_x": [-52.2813, -40.1169, -25.2185, -8.6016, 8.6016, 25.2185, 40.1169, 52.2813, 58.1086],
        "wall_height": [3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2],
        "m": [1.732051, 0.999999, 0.57735, 0.26795, 0.0, -0.26795, -0.577353, -1.000001, -1.732049],
        "c": [158.6707, 120.3981, 103.4428, 95.6402, 93.3354, 95.6402, 103.4429, 120.3982, 158.6706],
    },
}
# Every stadium, including Toy Field. Toy Field used to be absent, inherited
# from the JS `stadiums` constant: its height looked unrecoverable because the
# wall triangles all report max(y) == 0. They do, because mesh y is inverted
# world height and the wall top IS y = 0 -- its fence is 10.5 high throughout.
STADIUM_NAMES = list(STADIUM_WALLS)


def has_wall_data(stadium: str) -> bool:
    """True if pyrio knows this stadium's outfield wall.

    Every stadium is covered now, so this is True for any name StadiumID can
    produce. It is kept because callers guard on it, and because an unknown or
    misspelled name still has to answer False.
    """
    return stadium in STADIUM_WALLS

# Peach Garden blocks (the JS `noteBlocks`). "Note" blocks are always note
# blocks; "Random" blocks are invisible blocks that may become note blocks;
# "Brick" blocks are plain bricks.
NOTE_BLOCKS = [
    {"x": -51, "y": 9, "z": 65, "type": "Note"},
    {"x": -39, "y": 10, "z": 51, "type": "Note"},
    {"x": 51, "y": 9, "z": 65, "type": "Note"},
    {"x": 39, "y": 10, "z": 52, "type": "Note"},
    {"x": -12, "y": 12, "z": 55, "type": "Random"},
    {"x": 12, "y": 12, "z": 55, "type": "Random"},
    {"x": -20, "y": 9, "z": 73, "type": "Random"},
    {"x": 20, "y": 9, "z": 73, "type": "Random"},
    {"x": -25, "y": 9, "z": 45, "type": "Random"},
    {"x": 25, "y": 9, "z": 45, "type": "Random"},
    {"x": -39, "y": 10, "z": 36, "type": "Brick"},
    {"x": 39, "y": 10, "z": 36, "type": "Brick"},
]

# Effective block-collision radius. The JS hitNoteBlock used 2.0, but validating
# against recorded Peach Garden landings shows deflected balls passing up to ~4.7
# from a block center, so ~5 better matches the real collision volume (estimate).
_NOTE_BLOCK_RADIUS = 5.0

# The note blocks live only in Peach Garden; note_block_hit is a no-op elsewhere.
NOTE_BLOCK_STADIUM = "Peach Garden"


def wall_at(stadium: str, x: float) -> Optional[tuple[float, float]]:
    """(wall_z, wall_height) of the outfield wall at field x, or None if x is
    beyond the foul poles (no wall segment covers it).

    Also None for a stadium with no wall data at all -- currently Toy Field,
    matching how wall_collision_point already documents it. This used to raise
    KeyError, which no caller expected.
    """
    if stadium not in STADIUM_WALLS:
        return None
    w = STADIUM_WALLS[stadium]
    for sx, ex, h, m, c in zip(w["starting_x"], w["ending_x"], w["wall_height"], w["m"], w["c"]):
        if sx <= x < ex:
            return (m * x + c, h)
    return None


def is_home_run(trajectory: Iterable[tuple], stadium: str) -> bool:
    """True if any airborne point of the trajectory is beyond the outfield
    wall and above its height (the JS `isHomeRun` check).

    `trajectory` is an iterable of (x, y, z) points such as
    ``HitResult.trajectory``.

    Raises ValueError for a stadium with no wall data, rather than answering
    False. Toy Field's collision model does have an outfield fence (z 101 at
    centre, tapering to ~84 down the lines), so False would be a claim this
    module cannot support -- it lacks the fence height, not the fence. Guard
    with has_wall_data when the stadium comes from a stat file.
    """
    if not has_wall_data(stadium):
        raise ValueError(
            f"cannot tell whether this was a home run at {stadium!r}: "
            f"no outfield wall data. Known stadiums: {', '.join(STADIUM_NAMES)}. "
            "Check stadiums.has_wall_data() first."
        )
    for x, y, z in trajectory:
        wall = wall_at(stadium, x)
        if wall is None:
            continue
        wall_z, height = wall
        if z > wall_z and y > height:
            return True
    return False


def wall_collision_point(trajectory, stadium) -> Optional[tuple]:
    """Interpolated (x, y, z) where the trajectory first reaches the outfield
    wall plane (z crosses ``wall_at`` for that x), or None if it never does
    (stayed in the park, left over foul territory where there is no wall, or the
    stadium has no walls, e.g. Toy Field).

    This is the point the ball meets the wall whether it clears it (home run --
    see ``is_home_run``) or strikes it (off the wall), so it is what a recorded
    landing should be compared against for balls that reach the wall. It does
    not modify the trajectory; ``HitResult`` stays wall-free.
    """
    if stadium not in STADIUM_WALLS:
        return None
    traj = list(trajectory)
    if not traj:
        return None
    prev = traj[0]
    pw = wall_at(stadium, prev[0])
    prev_d = (prev[2] - pw[0]) if pw else None       # signed dist to wall plane (z - wall_z)
    for cur in traj[1:]:
        cw = wall_at(stadium, cur[0])
        cur_d = (cur[2] - cw[0]) if cw else None
        if prev_d is not None and cur_d is not None and prev_d < 0.0 <= cur_d:
            t = prev_d / (prev_d - cur_d)
            return tuple(prev[k] + t * (cur[k] - prev[k]) for k in range(3))
        prev, prev_d = cur, cur_d
    return None


# --------------------------------------------------------------------------
# Field-boundary polygons (constants/stadiums/*.txt)
# --------------------------------------------------------------------------
# Each file is a closed (x, z) polygon of the whole playable boundary -- the
# outfield fence plus the foul-line fences wrapping back behind home plate. Used
# to detect a ball leaving the park (home run / off the wall / foul into the
# netting) and find where its flight path crosses that boundary plane.

_STADIUMS_DIR = os.path.join(os.path.dirname(__file__), "constants", "stadiums")

# StatObj.stadium() normalized name -> boundary file stem.
_STADIUM_POLY_FILES = {
    "Mario Stadium": "mario_stadium",
    "Bowser Castle": "bowser_castle",
    "Wario Palace": "wario_palace",
    "Yoshi Park": "yoshi_park",
    "Peach Garden": "peach_garden",
    "DK Jungle": "dk_jungle",
    "Toy Field": "toy_field",
}

_poly_cache: dict = {}


def stadium_boundary(stadium: str):
    """Closed (x, z) boundary polygon for a stadium from constants/stadiums, or
    None if there's no file. Cached; the returned list is closed (last == first)."""
    if stadium in _poly_cache:
        return _poly_cache[stadium]
    stem = _STADIUM_POLY_FILES.get(stadium)
    poly = None
    if stem:
        path = os.path.join(_STADIUMS_DIR, stem + ".txt")
        if os.path.exists(path):
            pts = []
            with open(path) as f:
                for line in f:
                    s = line.split()
                    if len(s) == 2:
                        pts.append((float(s[0]), float(s[1])))
            if len(pts) >= 3:
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                poly = pts
    _poly_cache[stadium] = poly
    return poly


def _segment_cross_param(ax, az, bx, bz, c, d) -> Optional[float]:
    """Parameter t in [0, 1] along (ax,az)->(bx,bz) where it crosses edge c->d,
    or None if the segments don't intersect."""
    cx, cz = c
    dx, dz = d
    rx, rz = bx - ax, bz - az
    sx, sz = dx - cx, dz - cz
    denom = rx * sz - rz * sx
    if denom == 0.0:
        return None  # parallel / collinear
    t = ((cx - ax) * sz - (cz - az) * sx) / denom
    u = ((cx - ax) * rz - (cz - az) * rx) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None


def boundary_crossing(trajectory, stadium) -> Optional[tuple]:
    """(frame_index, t) where the trajectory first exits the field boundary: the
    segment from trajectory[frame_index] (last point in play) to
    trajectory[frame_index + 1] (first point past the boundary) crosses the
    boundary polygon at parameter ``t`` in [0, 1] along that segment. None if the
    ball never leaves the park or the stadium has no boundary polygon.

    The trajectory begins inside the boundary, so the first edge crossing is the
    exit. Note the recorded fence-ball landing is usually a few frames *past* this
    crossing (a ball that clears the fence is logged downstream), so for matching
    a recording prefer ``nearest_trajectory_point``; this gives the geometric
    plane crossing itself.
    """
    poly = stadium_boundary(stadium)
    if not poly:
        return None
    traj = list(trajectory)
    for i in range(len(traj) - 1):
        ax, _, az = traj[i]
        bx, _, bz = traj[i + 1]
        best_t = None
        for j in range(len(poly) - 1):
            t = _segment_cross_param(ax, az, bx, bz, poly[j], poly[j + 1])
            if t is not None and (best_t is None or t < best_t):
                best_t = t
        if best_t is not None:
            return i, best_t
    return None


def boundary_intersection(trajectory, stadium) -> Optional[tuple]:
    """Interpolated (x, y, z) where the trajectory's (x, z) path first crosses
    the field-boundary polygon -- the ball leaving the park (home run, off the
    wall, or foul into the netting). None if it never leaves (stayed in play) or
    the stadium has no boundary polygon. The trajectory itself is not modified.
    """
    cross = boundary_crossing(trajectory, stadium)
    if cross is None:
        return None
    traj = list(trajectory)
    i, t = cross
    a, b = traj[i], traj[i + 1]
    return tuple(a[k] + t * (b[k] - a[k]) for k in range(3))


def nearest_trajectory_point(trajectory, point) -> Optional[tuple]:
    """(distance, frame_index, (x, y, z)) of the trajectory point closest in 3D
    to ``point``, or None for an empty trajectory.

    A recorded fence-ball landing (home run / off the wall / foul) is the ball's
    position where it actually struck something, which lies on the wall-free
    flight path -- so its nearest trajectory point reproduces it closely. Walls
    only matter at the moment of contact; up to that instant the real ball and
    the simulated wall-free path coincide.
    """
    best = None
    for idx, p in enumerate(trajectory):
        d = math.dist(point, p)
        if best is None or d < best[0]:
            best = (d, idx, tuple(p))
    return best


def home_run_stadiums(trajectory) -> list[str]:
    """Stadium names where this trajectory clears the outfield wall.

    The JS shows this as "# of stadiums that hit would've been a HR at".
    Pass a list (not a generator) since it is iterated once per stadium.
    """
    trajectory = list(trajectory)
    return [name for name in STADIUM_NAMES if is_home_run(trajectory, name)]


def note_block_hit(trajectory, stadium=None) -> Optional[dict]:
    """First Peach Garden block (note/random/brick) the trajectory passes within
    range of, or None. Only points in the block height band (6 < y < 15) count.

    ``stadium`` (a StatObj.stadium() name) gates the check: the blocks only exist
    in Peach Garden, so any other stadium returns None. Pass None to skip the
    gate (e.g. when the trajectory is already known to be a Peach Garden hit).
    """
    if stadium is not None and stadium != NOTE_BLOCK_STADIUM:
        return None
    for x, y, z in trajectory:
        if not (6 < y < 15):
            continue
        for block in NOTE_BLOCKS:
            d = math.sqrt((block["x"] - x) ** 2 + (block["y"] - y) ** 2 + (block["z"] - z) ** 2)
            if d < _NOTE_BLOCK_RADIUS:
                return block
    return None
