"""MSSB stadium outfield-wall geometry and Peach Garden note blocks.

Ported from the batting calculator's index.js (`stadiums`, `noteBlocks`,
`isHomeRun`, `hitNoteBlock`). Each outfield wall is a set of line segments in
the field X/Z plane: for segment i the wall runs from x = starting_x[i] to
x = ending_x[i] along the line  z = m[i] * x + c[i]  with height wall_height[i].

Keys match ``StatObj.stadium()`` normalized names (e.g. "Peach Garden", not
the JS's "Peach Gardens").

Note: trajectories produced by ``hit_simulation`` use the calculator's
unverified flight model, so HR/wall checks on simulated paths are
approximations of the game, not ground truth.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

# Each stadium: parallel arrays exactly as in the JS `stadiums` constant.
STADIUM_WALLS = {
    "Mario Stadium": {
        "starting_x": [-57, -44, -14, 16],
        "ending_x": [-44, -14, 16, 57],
        "wall_height": [3, 3, 3, 3],
        "m": [1.65, 0.69, 0, -1.05],
        "c": [151.3, 110.7, 100, 116.8],
    },
    "Peach Garden": {
        "starting_x": [-59, -53, -45, -35, -32, -30, -14.3, -7, -5, 5, 7, 14.3, 30, 32, 35, 45, 53],
        "ending_x": [-53, -45, -35, -32, -30, -14.3, -7, -5, 5, 7, 14.3, 30, 32, 35, 45, 53, 59],
        "wall_height": [8, 8, 8, 18, 18, 18, 18, 21, 23, 21, 18, 18, 18, 18, 8, 8, 8],
        "m": [2, 1.5, 0.7, -1 / 3, 0.5, -0.064, -0.205, -0.1, 0, 0.1, 0.205, 0.064, -0.5, 1 / 3, -0.7, -1.5, -2],
        "c": [177, 150.5, 114.5, 78.33, 105, 88.08, 86.07, 86.8, 87.3, 86.8, 86.07, 88.08, 105, 78.33, 114.5, 150.5, 177],
    },
    "Wario Palace": {
        "starting_x": [-51, -49, -39, -26, -9, 9, 26, 39, 49],
        "ending_x": [-49, -39, -26, -9, 9, 26, 39, 49, 51],
        "wall_height": [5, 5, 5, 5, 5, 5, 5, 5, 5],
        "m": [6.25, 1.55, 0.923, 0.412, 0, -0.412, -0.923, -1.55, -6.25],
        "c": [369.75, 139.75, 115, 101.712, 98, 101.712, 115, 139.75, 369.75],
    },
    "Yoshi Park": {
        "starting_x": [-58, -52, -40, -25, -9, 9, 25, 40, 52],
        "ending_x": [-52, -40, -25, -9, 9, 25, 40, 52, 58],
        "wall_height": [3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2],
        "m": [5 / 3, 1, 0.6, 0.25, 0, -0.25, -0.6, -1, -5 / 3],
        "c": [154.66666, 120, 104, 95.25, 93, 95.25, 104, 120, 154.66666],
    },
    "DK Jungle": {
        "starting_x": [-50, -43, -33, -26, -10, 10, 26, 40, 49],
        "ending_x": [-43, -33, -26, -10, 10, 26, 40, 49, 50],
        "wall_height": [3.5, 6.9, 3.5, 3.7, 3.8, 3.8, 3.8, 3.7, 3.7],
        "m": [19 / 7, 17 / 10, 5 / 7, 3 / 8, 0, -3 / 8, -6 / 7, -17 / 9, -12],
        "c": [185.7, 142.1, 109.6, 100.75, 97, 100.75, 113.3, 154.6, 650],
    },
    "Bowser Castle": {
        "starting_x": [-54, -53.5, -52, -45, -36, -27, -21.5, -20, -19, -17.5, -17, -8, 8, 17, 17.5, 19, 20, 21.5, 27, 36, 45, 52, 53.5],
        "ending_x": [-53.5, -52, -45, -36, -27, -21.5, -20, -19, -17.5, -17, -8, 8, 17, 17.5, 19, 20, 21.5, 27, 36, 45, 52, 53.5, 54],
        "wall_height": [16.7, 12, 5, 5, 5, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 5, 5, 5, 12, 16.7],
        "m": [6, 2.3333, 1.43, 0.888, 0.5, 0.3636, -0.6667, -0.5, 1, 4, 0.22222, 0, -0.22222, -4, -1, 0.5, 0.6667, -0.3636, -0.5, -0.888, -1.43, -2.3333, -6],
        "c": [378, 181.8, 134.86, 110.5, 96.5, 92.82, 70.67, 74, 102.5, 155, 90.78, 89, 90.78, 155, 102.5, 74, 70.67, 92.82, 96.5, 110.5, 134.86, 181.8, 378],
    },
}

STADIUM_NAMES = list(STADIUM_WALLS)

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

_NOTE_BLOCK_RADIUS = 2.0  # JS hitNoteBlock: blockBallDist < 2


def wall_at(stadium: str, x: float) -> Optional[tuple[float, float]]:
    """(wall_z, wall_height) of the outfield wall at field x, or None if x is
    beyond the foul poles (no wall segment covers it)."""
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
    """
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


def home_run_stadiums(trajectory) -> list[str]:
    """Stadium names where this trajectory clears the outfield wall.

    The JS shows this as "# of stadiums that hit would've been a HR at".
    Pass a list (not a generator) since it is iterated once per stadium.
    """
    trajectory = list(trajectory)
    return [name for name in STADIUM_NAMES if is_home_run(trajectory, name)]


def note_block_hit(trajectory) -> Optional[dict]:
    """First Peach Garden block (note/random/brick) the trajectory passes
    within range of, or None. Port of the JS `hitNoteBlock` (which only
    checks points with 6 < y < 15).
    """
    for x, y, z in trajectory:
        if not (6 < y < 15):
            continue
        for block in NOTE_BLOCKS:
            d = math.sqrt((block["x"] - x) ** 2 + (block["y"] - y) ** 2 + (block["z"] - z) ** 2)
            if d < _NOTE_BLOCK_RADIUS:
                return block
    return None
