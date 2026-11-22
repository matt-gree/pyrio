"""Check the hit simulator against the contacts stat files recorded.

A recorded contact carries its own RNG values, so re-simulating it with
``HitInputs.from_event`` should give back exactly what the client wrote: the
contact type, the launch angles, the power and the ball's velocity. This
reports how often each one matches, over a file or a folder of files, with a
few mismatches to look at.

    python tools/hit_sim_validation.py STAT_FILE_OR_FOLDER [--examples N]

The test suite holds the fixtures to this (``tests/sim/test_from_event.py``);
this is for running it over a large collection.
"""

from __future__ import annotations

import argparse
import math
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pyrio
from pyrio import Contact, StatFileError
from pyrio.sim import simulate_contacts

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyrio.sim import HitResult


@dataclass(frozen=True)
class Check:
    name: str
    recorded: Callable[[Contact], Any]
    simulated: Callable[[HitResult], Any]
    tolerance: float | None = None
    """None for exact equality."""


CHECKS = (
    Check("contact_type", lambda c: c.type, lambda r: r.contact_type),
    Check("contact_absolute", lambda c: c.absolute, lambda r: r.contact_absolute, 1e-3),
    Check("contact_quality", lambda c: c.quality, lambda r: r.contact_quality, 1e-3),
    Check("horizontal_angle", lambda c: c.horizontal_angle, lambda r: r.horizontal_angle_raw),
    Check("vertical_angle", lambda c: c.vertical_angle, lambda r: r.vertical_angle_raw),
    Check("power", lambda c: c.power, lambda r: r.power),
    *(
        Check(
            f"velocity_{axis}",
            lambda c, i=i: c.velocity[i],
            lambda r, i=i: r.velocity_per_frame[i],
            1e-3,
        )
        for i, axis in enumerate("xyz")
    ),
)


@dataclass
class Tally:
    checked: int = 0
    matched: int = 0
    mismatches: list[str] = field(default_factory=list[str])


def agrees(check: Check, recorded: Any, simulated: Any) -> bool:
    if recorded is None:
        return True  # an older client didn't write it
    if check.tolerance is None:
        return recorded == simulated
    return math.isclose(recorded, simulated, abs_tol=check.tolerance)


def validate(paths: list[pathlib.Path]) -> tuple[dict[str, Tally], int, list[str]]:
    tallies = {check.name: Tally() for check in CHECKS}
    contacts = 0
    skipped: list[str] = []
    for path in paths:
        try:
            game = pyrio.read_game(path)
        except StatFileError as e:
            skipped.append(f"{path.name}: {e}")
            continue
        events = {e.number: e for e in game.events}
        for record in simulate_contacts(game):
            contact = events[record.event_number].contact
            assert contact is not None
            contacts += 1
            for check in CHECKS:
                recorded = check.recorded(contact)
                simulated = check.simulated(record.simulation)
                tally = tallies[check.name]
                tally.checked += 1
                if agrees(check, recorded, simulated):
                    tally.matched += 1
                else:
                    tally.mismatches.append(
                        f"{path.name} event {record.event_number}: "
                        f"recorded {recorded}, simulated {simulated}"
                    )
    return tallies, contacts, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", type=pathlib.Path, help="a stat file or a folder of them")
    parser.add_argument("--examples", type=int, default=3, help="mismatches to show per field")
    args = parser.parse_args(argv)

    root: pathlib.Path = args.path
    paths = sorted(root.rglob("*.json")) if root.is_dir() else [root]
    tallies, contacts, skipped = validate(paths)
    print(f"{len(paths)} files, {contacts} simulated contacts, {len(skipped)} files skipped")
    for name, tally in tallies.items():
        rate = tally.matched / tally.checked if tally.checked else math.nan
        print(f"  {name:18} {tally.matched:>6}/{tally.checked:<6} {rate:7.2%}")
        for line in tally.mismatches[: args.examples]:
            print(f"      {line}")
    for line in skipped:
        print(f"  skipped {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
