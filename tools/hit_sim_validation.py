"""Check the hit simulator against the contacts stat files recorded.

A recorded contact carries its own RNG values, so re-simulating it with
``HitInputs.from_event`` should give back exactly what the client wrote: the
contact type, the launch angles, the power and the ball's velocity. This
reports how often each one matches, over a file or a folder of files, with a
few mismatches to look at.

    python tools/hit_sim_validation.py STAT_FILE_OR_FOLDER [--examples N]
        [--since VERSION] [--skip-untagged] [--mod TAG ...]

A stat file doesn't record the gecko mods a game was played with, only its tag
set, and some mods change the contact: the non-red Toads' bat reach is one.
``--mod`` plays every game with a mod (by its Rio web tag), and
``--skip-untagged`` leaves out games with no tag set, which may have had
custom mods.

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
from pyrio import Contact, StatFileError, Version
from pyrio.sim import TAG_TO_MOD, Mod, simulate_contacts

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


def validate(
    paths: list[pathlib.Path],
    *,
    since: Version | None = None,
    skip_untagged: bool = False,
    mods: frozenset[Mod] = frozenset(),
) -> tuple[dict[str, Tally], int, list[str]]:
    tallies = {check.name: Tally() for check in CHECKS}
    contacts = 0
    skipped: list[str] = []
    for path in paths:
        try:
            game = pyrio.read_game(path)
        except StatFileError as e:
            skipped.append(f"{path.name}: {e}")
            continue
        if since is not None and game.version < since:
            continue
        if skip_untagged and game.tag_set_id is None:
            continue
        for record in simulate_contacts(game, mods=mods):
            contact = record.contact
            contacts += 1
            for check in CHECKS:
                recorded = check.recorded(contact)
                simulated = check.simulated(record.hit)
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
    parser.add_argument(
        "--since", type=Version.parse, help="only games from this client version on, e.g. 2.1.0"
    )
    parser.add_argument(
        "--skip-untagged", action="store_true", help="leave out games with no tag set"
    )
    parser.add_argument(
        "--mod",
        action="append",
        default=[],
        choices=sorted(TAG_TO_MOD),
        help="a gecko mod, by its Rio web tag, to play every game with (repeatable)",
    )
    args = parser.parse_args(argv)

    root: pathlib.Path = args.path
    paths = sorted(root.rglob("*.json")) if root.is_dir() else [root]
    mods = frozenset(TAG_TO_MOD[tag] for tag in args.mod)
    tallies, contacts, skipped = validate(
        paths, since=args.since, skip_untagged=args.skip_untagged, mods=mods
    )
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
