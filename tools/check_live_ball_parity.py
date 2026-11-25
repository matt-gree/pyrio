"""Check pyrio.sim's live ball against RioVisualizer's physics.py, its source.

The live ball is a port. RioVisualizer's implementation is the reference, so
the question here is not "is the physics right" but "did the port change
anything", and the bar is exact: same outcome, land frame, trajectory point
for point, and events, run on RioVisualizer's own copy of the stadium data.

RioVisualizer now imports its physics from pyrio, so its current physics.py
is a shim. The reference is then the last revision of that file that still
held the implementation, read from RioVisualizer's git history; ``--ref=REV``
names one instead.

It lives in tools/ rather than tests/ because it needs a RioVisualizer
checkout, which pyrio does not depend on. Run it after touching the live
ball, and after pulling RioVisualizer.

Where the port deliberately leaves the reference to follow the decomp, the
runs that touch it are counted as departures, listed, and not failed:

  thwomp   thwomp_slamControl's disarm, re-slam and still frame at the top
           (pyrio.sim._live_ball._Thwomp)

Usage:
    python tools/check_live_ball_parity.py [path/to/RioVisualizer] [--seeds=N] [--ref=REV]

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
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING, Any

from pyrio import Stadium
from pyrio.sim import LiveBallEvent, LiveBallResult, play_out_flight

if TYPE_CHECKING:
    from types import ModuleType

_HERE = pathlib.Path(__file__).resolve().parent
_PHYSICS = "rio_visualizer/physics.py"
_SHIM_MARKER = "from pyrio"


def _git(root: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout


def reference_source(root: pathlib.Path, ref: str | None) -> tuple[str, str]:
    """(where it came from, source) of RioVisualizer's own live-ball implementation."""
    if ref is not None:
        return f"{_PHYSICS} at {ref}", _git(root, "show", f"{ref}:{_PHYSICS}")
    current = (root / _PHYSICS).read_text(encoding="utf-8")
    if _SHIM_MARKER not in current:
        return f"{_PHYSICS} (working tree)", current
    for rev in _git(root, "log", "--format=%h", "--", _PHYSICS).split():
        source = _git(root, "show", f"{rev}:{_PHYSICS}")
        if _SHIM_MARKER not in source:
            return f"{_PHYSICS} at {rev}", source
    raise SystemExit(f"no revision of {_PHYSICS} holds the implementation; pass --ref")


def load_module(source: str, name: str) -> ModuleType:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(source)
    spec = importlib.util.spec_from_file_location(name, f.name)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def launch(speed: float, azimuth_deg: float, elevation_deg: float, frames: int) -> list[Any]:
    """A batted ball under drag and gravity, as the hit simulation flies it."""
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    vx = speed * math.sin(a) * math.cos(e)
    vy = speed * math.sin(e)
    vz = speed * math.cos(a) * math.cos(e)
    x, y, z = 0.0, 1.0, 0.0
    points = [(x, y, z)]
    for _ in range(frames):
        vy -= 0.00275
        vx, vy, vz = vx * 0.996, vy * 0.996, vz * 0.996
        x, y, z = x + vx, y + vy, z + vz
        y = max(y, 0.15)
        points.append((x, y, z))
    return points


def flight(seed: int) -> list[Any]:
    """A synthetic flight, spread over the azimuths and launch angles the game produces.

    Not a recorded hit: the point is to drive both engines down the same branches.
    """
    rng = random.Random(seed)
    speed = 1.4 + rng.random() * 1.6
    return launch(speed, -50 + rng.random() * 100, 8 + rng.random() * 45, 90)


_FIELDS = {
    "surface": "surface",
    "hazard": "hazard",
    "result": "result",
    "block": "variant",
    "label": "label",
    "fall_speed": "fall",
    "heading_deg": "heading",
    "spin": "spin",
    "is_star_plant": "star",
}


def as_reference(result: LiveBallResult) -> dict[str, Any]:
    """A result in physics.py's dict form."""

    def event(e: LiveBallEvent) -> dict[str, Any]:
        out: dict[str, Any] = {
            "frame": e.frame,
            "type": e.outcome.value if e.outcome else e.kind.value,
            "pos": list(e.location),
        }
        for name, key in _FIELDS.items():
            if (value := getattr(e, name)) is not None:
                out[key] = value
        if e.hazard_kind is not None:
            out["what"] = e.hazard_kind.value
        if e.is_assumed:
            out["assumed"] = True
        if e.is_approximate:
            out["approx"] = True
        return out

    return {
        "outcome": result.outcome.value,
        "land_frame": result.land_frame,
        "points": [list(p) for p in result.trajectory],
        "events": [event(e) for e in result.events],
    }


def normalised(result: dict[str, Any]) -> dict[str, Any]:
    """physics.py's result with ``assumed: False`` dropped (the port leaves it unsaid)."""
    events = [
        {k: v for k, v in e.items() if not (k == "assumed" and v is False)}
        for e in result["events"]
    ]
    keys = ("outcome", "land_frame", "points")
    return {**{k: result[k] for k in keys}, "events": events}


# Hazard kinds whose behaviour the port changed on purpose (see the docstring).
_DEPARTURES = frozenset({"thwomp"})


def departs(*results: dict[str, Any]) -> bool:
    """Whether a run involves a hazard the port deliberately departs on."""
    return any(e.get("what") in _DEPARTURES for r in results for e in r["events"])


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    # 40 is the smallest round number that reaches every event type the
    # hazards raise, capture, release and star included.
    seeds = 40
    ref: str | None = None
    for a in argv[1:]:
        if a.startswith("--seeds="):
            seeds = int(a.split("=", 1)[1])
        elif a.startswith("--ref="):
            ref = a.split("=", 1)[1]
    default = os.environ.get("RIO_VISUALIZER", str(_HERE.parent.parent / "RioVisualizer"))
    root = pathlib.Path(args[0] if args else default)
    data = root / "rio_visualizer" / "data"
    if not (root / _PHYSICS).is_file():
        usage = (__doc__ or "").split("Usage:")[1].strip()
        print(f"no RioVisualizer at {root}\n\n{usage}", file=sys.stderr)
        return 2

    where, source = reference_source(root, ref)
    reference = load_module(source, "_rv_physics")
    print(f"reference: {where}")

    def reference_stadium(name: str) -> dict[str, Any]:
        stadium = json.loads((data / "stadiums" / f"{name}.json").read_text(encoding="utf-8"))
        park = data / "extras" / f"{name}.park.json"
        if park.is_file():
            stadium["Park"] = json.loads(park.read_text(encoding="utf-8"))
        return stadium

    runs: list[tuple[Stadium, str, list[Any], int, bool]] = []
    for stadium in Stadium:
        for seed in range(seeds):
            for hazards in (True, False):
                runs.append((stadium, f"seed {seed}", flight(seed), seed, hazards))
    # The seeded flights never land on a Toy Field panel; these do.
    for speed in (0.6, 0.8, 1.0, 1.2, 1.4, 1.6):
        for azimuth in (-30.0, 0.0, 25.0):
            path = launch(speed, azimuth, 25.0, 150)
            runs.append((Stadium.TOY_FIELD, f"panel {speed}/{azimuth}", path, 0, True))

    theirs = {stadium: reference_stadium(stadium.label) for stadium in Stadium}
    matched = 0
    failures: list[tuple[Stadium, str, bool, str, str]] = []
    departed: list[tuple[Stadium, str, bool, str, str]] = []
    outcomes: collections.Counter[str] = collections.Counter()
    events: collections.Counter[str] = collections.Counter()
    for stadium, label, path, seed, hazards in runs:
        a = normalised(reference.continue_ball(theirs[stadium], path, seed=seed, hazards=hazards))
        b = as_reference(play_out_flight(stadium, path, seed=seed, hazards=hazards))
        if a == b:
            matched += 1
        elif departs(a, b):
            departed.append((stadium, label, hazards, a["outcome"], b["outcome"]))
        else:
            failures.append((stadium, label, hazards, a["outcome"], b["outcome"]))
        outcomes[b["outcome"]] += 1
        events.update(e["type"] for e in b["events"])

    print(
        f"{matched}/{len(runs)} runs identical across {len(Stadium)} stadiums "
        f"({seeds} seeded flights, hazards on and off, plus Toy Field's panels)"
    )
    print(f"  outcomes reached: {dict(outcomes)}")
    print(f"  events reached:   {dict(events)}")
    if departed:
        print(f"\nDEPARTED on purpose ({', '.join(sorted(_DEPARTURES))}): {len(departed)} runs")
        for stadium, label, hazards, theirs_out, ours_out in departed[:20]:
            print(
                f"  {stadium.label:15} {label:14} hazards={hazards!s:<5} "
                f"reference {theirs_out!r} vs port {ours_out!r}"
            )
    if failures:
        print("\nDIVERGED:")
        for stadium, label, hazards, theirs_out, ours_out in failures[:20]:
            print(
                f"  {stadium.label:15} {label:14} hazards={hazards!s:<5} "
                f"reference {theirs_out!r} vs port {ours_out!r}"
            )
        return 1
    wanted = {"capture", "release", "hazard", "star", "wall", "land", "bounce", "panel"}
    if missing := wanted - set(events):
        print(
            "\nNote: these event types were never reached, so the port is unverified "
            f"for them: {sorted(missing)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
