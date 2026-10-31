"""Validate the hit simulator against recorded stat-file contact events.

Because a recorded event carries its own RNG seeds, the simulator should
reproduce that event's contact-stage outputs *exactly* (angles, power, velocity)
and its contact classification. This module compares simulated vs recorded
values across one file, many files, or a directory, and reports per-field match
rates plus example mismatches.

Primary (deterministic, exact/tol) fields -- these are the real validation:
    contact_type, contact_absolute, contact_quality,
    horizontal_angle, vertical_angle, power, velocity_x/y/z

Landing position is available via include_landing=True but is informational
only: for a caught ball the stat file records the FIELDER's location, not where
the ball would have hit the ground, so mismatches there are expected.

Usage:
    from pyrio import hit_sim_validation as v
    report = v.validate_file("decoded.json")
    print(report.summary())

    report = v.validate_directory(r"path/to/StatFiles")     # aggregates
    # or programmatically inspect report.fields[...].mismatches

CLI:
    python -m pyrio.hit_sim_validation <file-or-directory> [--landing]
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import hit_simulation as hs
from .. import rio_tags
from ..constants import game_constants as G
from ..lookup import LookupDicts
from .hit_sim_report import (FieldSpec, ValidationReport, ci,
                             note_block_deflected, resolve_landing)
from ..stat_file_parser import StatObj, EventObj

# Backwards-compatible aliases (the comparison core moved to hit_sim_report).
_ci = ci
_FieldSpec = FieldSpec


# ---------------------------------------------------------------- field specs
# Stat-file flavor: recorded values come from a decoded event's contact dict.

def _contact_field_specs(vel_tol: float, float_tol: float) -> list[FieldSpec]:
    return [
        FieldSpec("contact_type",
                  lambda c: G.to_encoded(LookupDicts.CONTACT_TYPE, c["Type of Contact"]),
                  lambda r: r.contact_type),
        FieldSpec("contact_absolute",
                  lambda c: float(c["Contact Absolute"]),
                  lambda r: r.contact_absolute, tol=float_tol),
        FieldSpec("contact_quality",
                  lambda c: float(c["Contact Quality"]),
                  lambda r: r.contact_quality, tol=float_tol),
        FieldSpec("horizontal_angle",
                  lambda c: ci(c["Horiz Angle"]),
                  lambda r: r.horizontal_angle),
        FieldSpec("vertical_angle",
                  lambda c: ci(c["Vert Angle"]),
                  lambda r: r.vertical_angle),
        FieldSpec("power",
                  lambda c: ci(c["Ball Power"]),
                  lambda r: r.power),
        FieldSpec("velocity_x",
                  lambda c: c["Ball Velocity - X"],
                  lambda r: r.velocity[0], tol=vel_tol),
        FieldSpec("velocity_y",
                  lambda c: c["Ball Velocity - Y"],
                  lambda r: r.velocity[1], tol=vel_tol),
        FieldSpec("velocity_z",
                  lambda c: c["Ball Velocity - Z"],
                  lambda r: r.velocity[2], tol=vel_tol),
    ]


def _landing_field_specs(landing_tol: float) -> list[FieldSpec]:
    # Single 3D field: euclidean distance between the recorded (X, Y, Z) landing
    # and the simulated landing (ground/bounce for in-park balls, the field-
    # boundary crossing for balls that left the park). Height is included.
    return [
        FieldSpec("landing",
                  lambda c: (float(c["Ball Landing Position - X"]),
                             float(c["Ball Landing Position - Y"]),
                             float(c["Ball Landing Position - Z"])),
                  lambda r: tuple(r.landing), tol=landing_tol),
    ]


# FieldStat and ValidationReport now live in hit_sim_report (shared with the API
# validator) and are imported at the top of this module.


# ---------------------------------------------------------------- core driver

# A failed Moonshot (Texas Leaguer) pops up into this raw vertical-angle band
# (hit_simulation: the forced pop-fly zone SHORT_ARRAY_ARRAY_807b6af4).
_TEXAS_LEAGUER_VERT_BAND = (500, 550)


def _is_texas_leaguer(event: EventObj, contact: dict, swing_code: int) -> bool:
    """True for a likely Texas Leaguer -- a failed 5-star Moonshot the simulator
    can't model.

    A Moonshot fires on a fully-charged 5-star swing; a Perfect connect is the
    dinger (recorded "Star Swing Five-Star" = 1, which hit_simulation DOES model),
    and any other contact pops weakly up the middle. But a star swing zeroes its
    charge in the recording, so a *failed* Moonshot is indistinguishable from a
    regular 5-star swing on inputs alone -- except its launch lands in the forced
    pop-fly vertical band. So flag it after the fact: a 5-star, non-dinger Star
    swing whose recorded Vert Angle is in that band, and exclude it from validation
    (the sim mis-handles it as a regular star swing).
    """
    if swing_code != 3:  # Star
        return False
    if _ci(contact.get("Star Swing Five-Star") or 0) == 1:
        return False  # connected dinger -- modeled
    if event.team_stars(event.batting_team()) < 5:
        return False
    try:
        vert = _ci(contact.get("Vert Angle"))
    except (TypeError, ValueError):
        return False
    lo, hi = _TEXAS_LEAGUER_VERT_BAND
    return lo <= vert <= hi


def _is_natural_landing(contact: dict) -> bool:
    """True if 'Ball Landing Position' is where the ball naturally came down,
    rather than a point determined by a fielder.

    Excluded otherwise, because the air-only sim cannot (and should not)
    reproduce a fielder-determined landing:
      - a ball caught for an out (secondary 'Out-caught') stores the fielder's
        location in 'Ball Landing Position'; and
      - any ball a fielder reached with a special action (Sliding, Walljump,
        ...) records the fielder-contact point (fielderActionCatchCoords), not
        the trajectory's landing -- e.g. a sliding interception fumbled into a
        hit. Only First Fielder Action 'None' is a clean natural landing.
    """
    sec = contact.get("Contact Result - Secondary")
    if sec is not None and G.to_encoded(LookupDicts.SECONDARY_CONTACT_RESULT, sec) == 0:
        return False  # caught for an out
    action = (contact.get("First Fielder") or {}).get("Fielder Action", 0)
    try:
        if G.to_encoded(LookupDicts.FIELDER_ACTIONS, action) != 0:  # 0 = None
            return False  # a fielder reached the ball before it landed
    except KeyError:
        pass
    return True


# ---------------------------------------------------------------- known mod exceptions
# Some matches run gecko-code mods that change in-game behavior the vanilla
# simulator doesn't model, so the recording legitimately diverges from the sim.
# Each exception is gated on the mod's tag (the `name` from the ProjectRio
# /tag/list) being active for the match, only excuses its listed fields, and
# only for events its predicate identifies. See rio_tags.active_tags_for_stat.

@dataclass(frozen=True)
class KnownModException:
    name: str                       # label for the report
    tag: str                        # gecko tag name that must be active
    fields: frozenset               # field names this exception may excuse
    predicate: Callable             # (event, contact, result) -> bool


# Both previously-listed mods ("Remove slice" and "Fix Non-red Toad Hitboxes and
# Bat Reach") are now modeled directly by the simulator from the match's active
# tags (hit_simulation.TAG_TO_FLAG), so they no longer need exceptions here. The
# framework below is retained for any future mod the simulator can't reproduce.
KNOWN_MOD_EXCEPTIONS: list = []


def _excused(field_name, event, contact, result, active_tags):
    """Return the KnownModException excusing this field mismatch, or None."""
    for exc in KNOWN_MOD_EXCEPTIONS:
        if (exc.tag in active_tags and field_name in exc.fields
                and exc.predicate(event, contact, result)):
            return exc
    return None


def validate_statobj(stat: StatObj, *, include_landing: bool = False,
                     landing_exclude_caught: bool = True, walls: bool = False,
                     bounces: bool = False,
                     vel_tol: float = 1e-4, float_tol: float = 1e-3,
                     landing_tol: float = 1.0, active_tags=None,
                     report: Optional[ValidationReport] = None) -> ValidationReport:
    """Compare every contact event in one game against the simulator.

    ``active_tags`` is the set of gecko-mod tag names active for this match (see
    rio_tags). Mismatches attributable to an active mod (KNOWN_MOD_EXCEPTIONS)
    are counted as expected rather than failures. If None, the match's tags are
    resolved automatically from its TagSetID (cached); pass an empty set to skip.

    Landing is compared in 3D (X, Y, Z) against the simulated landing. For a ball
    that leaves the park (home run / off the wall / foul into the netting) the
    recorded landing is the point where the ball crosses the field-boundary plane,
    so it is compared against stadiums.boundary_intersection (the field-boundary
    polygons in constants/stadiums); this is always on. The simulated trajectory
    itself is never modified.

    ``bounces`` compares in-park grounders/liners against the bounce-physics
    trajectory walked to the recorded "Ball Hang Time" (where the skidding ball
    actually is when the game records its landing), rather than the aerial first-
    contact landing. The boundary crossing takes precedence when the ball leaves
    the park. ``walls`` is deprecated (the boundary check is now the default).
    """
    report = report or ValidationReport()
    report.files += 1
    try:
        game_id = stat.gameID()
    except Exception:
        game_id = "?"
    stadium = stat.stadium()

    if active_tags is None:
        active_tags = rio_tags.active_tags_for_stat(stat)

    specs = _contact_field_specs(vel_tol, float_tol)
    if include_landing:
        specs = specs + _landing_field_specs(landing_tol)

    for i, _ev in enumerate(stat.events()):
        report.total_events += 1
        event = EventObj(stat, i)
        contact = event.contact_dict()
        if not contact:
            continue
        report.contact_events += 1

        # swing_code feeds the Texas-Leaguer check below; every supported swing
        # (bunt/slap/charge/star) is simulated. Genuinely unsupported swings raise
        # in _inputs_from_event and are caught as a skip in the try block.
        swing = event.pitch_dict().get("Type of Swing")
        swing_code = G.to_encoded(LookupDicts.TYPE_OF_SWING, swing) if swing is not None else None

        if _is_texas_leaguer(event, contact, swing_code):
            report.skipped.append((game_id, i, "texas leaguer (unmodeled failed moonshot)"))
            continue

        try:
            result = hs.simulate_hit_from_event(event, active_tags)
        except ValueError as ex:
            report.skipped.append((game_id, i, f"value error: {ex}"))
            continue
        except Exception as ex:  # noqa: BLE001 - surface unexpected failures
            report.errors.append((game_id, i, f"{type(ex).__name__}: {ex}"))
            continue

        report.simulated += 1
        if include_landing:
            try:
                rec_pt = (float(contact["Ball Landing Position - X"]),
                          float(contact["Ball Landing Position - Y"]),
                          float(contact["Ball Landing Position - Z"]))
            except (KeyError, TypeError, ValueError):
                rec_pt = None
            try:
                hang = _ci(contact.get("Ball Hang Time"))
            except (TypeError, ValueError):
                hang = None
            # Snap result.landing to the point the recorded landing represents
            # (fence boundary nearest-point, or the in-park ball at hang time).
            resolve_landing(result, stadium, rec_pt, bounces=bounces, hang_time=hang,
                            walk_to_hang=lambda f: hs.simulate_hit_trajectory_from_event(
                                event, f, active_tags))
        skip_landing = landing_exclude_caught and not _is_natural_landing(contact)
        # Peach Garden note blocks deflect/kill balls that fly through them; the
        # air-only sim can't model that, so exclude landings whose flight path
        # passes through a block (like fielder-determined landings).
        if include_landing and not skip_landing and note_block_deflected(result, stadium):
            skip_landing = True
        for spec in specs:
            if skip_landing and spec.name.startswith("landing"):
                continue
            try:
                ok, rec, com = spec.matches(contact, result)
            except (KeyError, TypeError, ValueError):
                continue  # field absent for this event (e.g. some fouls)
            st = report._stat(spec.name)
            st.total += 1
            if ok:
                st.matches += 1
                continue
            exc = _excused(spec.name, event, contact, result, active_tags)
            if exc:
                st.expected += 1
                st.expected_examples.append((game_id, i, exc.name))
            else:
                st.mismatches.append((game_id, i, rec, com))

    return report


def validate_file(path, **opts) -> ValidationReport:
    """Validate a single decoded stat-file path."""
    with open(path) as f:
        stat = StatObj(json.load(f))
    return validate_statobj(stat, **opts)


def _iter_decoded_files(directory) -> Iterable[Path]:
    for p in sorted(Path(directory).iterdir()):
        if p.is_file() and "decoded" in p.name and p.suffix == ".json":
            yield p


def validate_directory(directory, **opts) -> ValidationReport:
    """Validate every decoded stat file in a directory (aggregated report)."""
    report = ValidationReport()
    for path in _iter_decoded_files(directory):
        try:
            with open(path) as f:
                stat = StatObj(json.load(f))
        except (json.JSONDecodeError, OSError) as ex:
            report.errors.append((str(path), -1, f"load failed: {ex}"))
            continue
        validate_statobj(stat, report=report, **opts)
    return report


def validate(path, **opts) -> ValidationReport:
    """Validate a file or directory (dispatches on path type)."""
    return validate_directory(path, **opts) if Path(path).is_dir() else validate_file(path, **opts)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Validate the hit simulator against stat files")
    parser.add_argument("path", help="decoded stat file or a directory of them")
    parser.add_argument("--landing", action="store_true",
                        help="also compare landing position in 3D (informational; the "
                             "trajectory flight model is unverified, so misses are "
                             "expected). Balls that leave the park are compared against "
                             "the field-boundary crossing (constants/stadiums geometry).")
    parser.add_argument("--include-caught-landing", action="store_true",
                        help="include fielder-determined landings in the comparison "
                             "(caught-for-out balls and any ball a fielder reached "
                             "with a Sliding/Walljump action store the fielder "
                             "contact point, not the natural landing)")
    parser.add_argument("--walls", action="store_true",
                        help="deprecated/no-op: fence-ball landings are now compared "
                             "against the field-boundary crossing by default")
    parser.add_argument("--bounces", action="store_true",
                        help="compare in-park grounders/liners against the bounce "
                             "trajectory walked to the recorded hang time (where "
                             "the skidding ball is when its landing is recorded)")
    parser.add_argument("--no-tags", action="store_true",
                        help="don't resolve match tags from the ProjectRio API; "
                             "known-mod exceptions (e.g. Remove slice) won't be excused")
    args = parser.parse_args(argv)
    report = validate(args.path, include_landing=args.landing,
                      landing_exclude_caught=not args.include_caught_landing,
                      walls=args.walls, bounces=args.bounces,
                      active_tags=frozenset() if args.no_tags else None)
    print(report.summary())
    # Exit status reflects the deterministic fields only; landing is informational.
    return 0 if report.contact_fields_perfect() and not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
