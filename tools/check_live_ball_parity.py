"""Check pyrio's live_ball against RioVisualizer's physics.py, its source.

live_ball is a port. RioVisualizer remains the reference implementation, so the
question this answers is not "is the physics right" but "did the port change
anything" -- and the bar is exact: same outcome, same land frame, same
trajectory point for point, same events.

It lives here rather than in tests/ because it needs a RioVisualizer checkout,
which pyrio does not depend on. Run it after touching live_ball, and after
pulling RioVisualizer.

Usage:
    python tools/check_live_ball_parity.py [path/to/RioVisualizer] [--seeds=N]

Defaults to ../RioVisualizer, or set RIO_VISUALIZER.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import math
import os
import pathlib
import random
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def flight(seed: int, frames: int = 90):
    """A synthetic batted ball, spread over the azimuths and launch angles the
    game produces. Not a recorded hit -- the point is to drive both engines
    down the same branches, not to be realistic."""
    rng = random.Random(seed)
    speed = 1.4 + rng.random() * 1.6
    azimuth = math.radians(-50 + rng.random() * 100)
    elevation = math.radians(8 + rng.random() * 45)
    vx = speed * math.sin(azimuth) * math.cos(elevation)
    vy = speed * math.sin(elevation)
    vz = speed * math.cos(azimuth) * math.cos(elevation)
    x, y, z = 0.0, 1.0, 0.0
    points = [(x, y, z)]
    for _ in range(frames):
        vy -= 0.00275
        vx, vy, vz = vx * 0.996, vy * 0.996, vz * 0.996
        x, y, z = x + vx, y + vy, z + vz
        y = max(y, 0.15)
        points.append((x, y, z))
    return points


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    # 40 is the smallest round number that reaches every event type the
    # hazards can raise, capture/release/star included; fewer leaves the port
    # unverified for them, and the run says so when that happens.
    seeds = 40
    for a in argv[1:]:
        if a.startswith("--seeds="):
            seeds = int(a.split("=", 1)[1])
    root = pathlib.Path(args[0] if args else os.environ.get("RIO_VISUALIZER", _HERE.parent.parent / "RioVisualizer"))
    physics = root / "rio_visualizer" / "physics.py"
    data = root / "rio_visualizer" / "data"
    if not physics.is_file():
        print(f"no RioVisualizer physics.py at {physics}\n\n"
              + __doc__.strip().split("Usage:")[1].strip(), file=sys.stderr)
        return 2

    reference = _load(physics, "_rv_physics")
    from pyrio import live_ball

    def reference_stadium(name):
        stadium = json.loads((data / "stadiums" / f"{name}.json").read_text())
        park = data / "extras" / f"{name}.park.json"
        if park.is_file():
            stadium["Park"] = json.loads(park.read_text())
        return stadium

    names = live_ball.list_stadiums()
    total = matched = 0
    failures = []
    outcomes, events = collections.Counter(), collections.Counter()
    for name in names:
        theirs, ours = reference_stadium(name), live_ball.load_stadium(name)
        for seed in range(seeds):
            path = flight(seed)
            for hazards in (True, False):
                a = reference.continue_ball(theirs, path, seed=seed, hazards=hazards)
                b = live_ball.continue_ball(ours, path, seed=seed, hazards=hazards)
                total += 1
                if (a["outcome"] == b["outcome"] and a["land_frame"] == b["land_frame"]
                        and a["points"] == b["points"] and a["events"] == b["events"]):
                    matched += 1
                else:
                    failures.append((name, seed, hazards, a["outcome"], b["outcome"]))
                outcomes[b["outcome"]] += 1
                for e in b["events"]:
                    events[e["type"]] += 1

    print(f"{matched}/{total} runs identical across {len(names)} stadiums "
          f"({seeds} flights, hazards on and off)")
    print(f"  outcomes reached: {dict(outcomes)}")
    print(f"  events reached:   {dict(events)}")
    if failures:
        print("\nDIVERGED:")
        for name, seed, hazards, theirs_out, ours_out in failures[:20]:
            print(f"  {name:15} seed={seed:<3} hazards={hazards!s:<5} "
                  f"reference {theirs_out!r} vs port {ours_out!r}")
        return 1
    missing = {"capture", "release", "hazard", "star", "wall", "land", "bounce"} - set(events)
    if missing:
        print(f"\nNote: these event types were never reached, so the port is "
              f"unverified for them: {sorted(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
