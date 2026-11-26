"""Check pyrio.sim's running model against the frontend's, its source.

``pyrio.sim.simulate_run`` is a port of ProjectRio-frontend's
``lib/mssb/RunningSimulation/runningModel.ts`` (Nicholas Lannutti's running
analysis). This runs that TypeScript over a spread of characters, superstar,
mashing, rounding, legs and batting hands, and checks the port gives the same
frames and the same final position exactly.

It lives in tools/ because it needs a frontend checkout with its node modules
installed (it runs the model with the checkout's ``tsx``). ``--write`` also
replaces ``tests/fixtures/running_goldens.json.gz``, the frozen record
``tests/sim/test_running.py`` holds the port to.

Usage:
    python tools/check_running_parity.py [path/to/ProjectRio-frontend] [--write]

Defaults to ../ProjectRio-frontend, or set PROJECTRIO_FRONTEND.
"""

from __future__ import annotations

import gzip
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

from pyrio import Character, Hand
from pyrio.sim import simulate_run

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLDENS = ROOT / "tests" / "fixtures" / "running_goldens.json.gz"
MODEL = "lib/mssb/RunningSimulation"

SCRIPT = """
import { simulateRun, batterPosition } from '%(model)s/runningModel';
import { CHARACTER_SPEED } from '%(model)s/runningConstants';
const out: any[] = [];
const mashes = { tas: 1, human: 3, none: null } as const;
for (const id of [0, 1, 6, 9, 15, 22, 30, 41]) {
  for (const sup of [false, true]) {
    const speed = CHARACTER_SPEED[id] + (sup ? 50 : 0);
    for (const [mash, every] of Object.entries(mashes)) {
      for (const path of ['straight', 'round'] as const) {
        for (const [s, e] of [[0, 1], [0, 2], [0, 4], [1, 2], [1, 3], [2, 4], [3, 4], [1, 4]]) {
          for (const side of ['R', 'L'] as const) {
            if (s !== 0 && side === 'L') continue;
            const pos = batterPosition(id, side, 'def');
            const r = simulateRun({ speed, mash: mash as any, path, startBase: s, endBase: e,
                                    batterPos: pos });
            const last = r.trace[r.trace.length - 1];
            out.push({ id, sup, every, path, s, e, side, frames: r.frame, top: r.topFrame,
                       bases: r.bases, x: last.x, z: last.z, overrun: r.overrun.length });
          }
        }
      }
    }
  }
}
console.log(JSON.stringify(out));
"""


def reference(frontend: pathlib.Path) -> list[dict[str, Any]]:
    tsx = frontend / "node_modules" / ".bin" / "tsx"
    if not tsx.exists():
        sys.exit(f"{tsx} not found: run npm install in the frontend checkout")
    with tempfile.TemporaryDirectory() as scratch:
        script = pathlib.Path(scratch) / "running_goldens.ts"
        script.write_text(SCRIPT % {"model": (frontend / MODEL).as_posix()})
        done = subprocess.run(
            [str(tsx), str(script)], cwd=frontend, capture_output=True, text=True, check=True
        )
    return json.loads(done.stdout)


def mismatches(cases: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for case in cases:
        run = simulate_run(
            Character(case["id"]),
            start_base=case["s"],
            end_base=case["e"],
            is_superstar=case["sup"],
            hand=Hand.LEFT if case["side"] == "L" else Hand.RIGHT,
            rounding=case["path"] == "round",
            mash_every=case["every"],
        )
        last = run.trace[-1].location
        got = (run.frames, run.top_speed_frame, dict(run.base_frames), last[0], last[2])
        want = (
            case["frames"],
            case["top"],
            {b["base"]: b["frame"] for b in case["bases"]},
            case["x"],
            case["z"],
        )
        if got != want or len(run.overrun) != case["overrun"]:
            found.append(f"{case}: got {got}")
    return found


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    default = os.environ.get("PROJECTRIO_FRONTEND", str(ROOT.parent / "ProjectRio-frontend"))
    frontend = pathlib.Path(args[0] if args else default).resolve()
    cases = reference(frontend)
    bad = mismatches(cases)
    print(f"{len(cases) - len(bad)}/{len(cases)} runs match the frontend model")
    for line in bad[:20]:
        print(" ", line)
    if "--write" in sys.argv and not bad:
        with gzip.open(GOLDENS, "wt") as file:
            json.dump(cases, file, separators=(",", ":"))
        print(f"wrote {GOLDENS.relative_to(ROOT)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
