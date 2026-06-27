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
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import hit_simulation as hs
from . import rio_tags
from . import stadiums
from .constants import game_constants as G
from .stat_file_parser import StatObj, EventObj

# game Type of Swing codes that the simulator supports: 1 Slap, 2 Charge, 3 Star.
_SUPPORTED_SWING_CODES = (1, 2, 3)


def _ci(value) -> int:
    """Parse a possibly comma-grouped integer string, e.g. '1,181' -> 1181."""
    return int(str(value).replace(",", ""))


# ---------------------------------------------------------------- field specs

@dataclass(frozen=True)
class _FieldSpec:
    name: str
    recorded: Callable[[dict], object]      # from the contact dict
    computed: Callable[[hs.HitResult], object]
    tol: Optional[float] = None             # None -> exact equality

    def matches(self, contact: dict, result: hs.HitResult) -> tuple[bool, object, object]:
        rec = self.recorded(contact)
        com = self.computed(result)
        if self.tol is None:
            ok = rec == com
        elif isinstance(rec, tuple):           # point: compare by euclidean distance
            ok = math.dist(rec, com) <= self.tol
        else:
            ok = abs(float(rec) - float(com)) <= self.tol
        return ok, rec, com


def _contact_field_specs(vel_tol: float, float_tol: float) -> list[_FieldSpec]:
    return [
        _FieldSpec("contact_type",
                   lambda c: G.to_encoded(G.TYPE_OF_CONTACT, c["Type of Contact"]),
                   lambda r: r.contact_type),
        _FieldSpec("contact_absolute",
                   lambda c: float(c["Contact Absolute"]),
                   lambda r: r.contact_absolute, tol=float_tol),
        _FieldSpec("contact_quality",
                   lambda c: float(c["Contact Quality"]),
                   lambda r: r.contact_quality, tol=float_tol),
        _FieldSpec("horizontal_angle",
                   lambda c: _ci(c["Horiz Angle"]),
                   lambda r: r.horizontal_angle),
        _FieldSpec("vertical_angle",
                   lambda c: _ci(c["Vert Angle"]),
                   lambda r: r.vertical_angle),
        _FieldSpec("power",
                   lambda c: _ci(c["Ball Power"]),
                   lambda r: r.power),
        _FieldSpec("velocity_x",
                   lambda c: c["Ball Velocity - X"],
                   lambda r: r.velocity[0], tol=vel_tol),
        _FieldSpec("velocity_y",
                   lambda c: c["Ball Velocity - Y"],
                   lambda r: r.velocity[1], tol=vel_tol),
        _FieldSpec("velocity_z",
                   lambda c: c["Ball Velocity - Z"],
                   lambda r: r.velocity[2], tol=vel_tol),
    ]


def _landing_field_specs(landing_tol: float) -> list[_FieldSpec]:
    # Single 3D field: euclidean distance between the recorded (X, Y, Z) landing
    # and the simulated landing (ground/bounce for in-park balls, the field-
    # boundary crossing for balls that left the park). Height is included.
    return [
        _FieldSpec("landing",
                   lambda c: (float(c["Ball Landing Position - X"]),
                              float(c["Ball Landing Position - Y"]),
                              float(c["Ball Landing Position - Z"])),
                   lambda r: tuple(r.landing), tol=landing_tol),
    ]


# ---------------------------------------------------------------- report types

@dataclass
class FieldStat:
    name: str
    matches: int = 0
    total: int = 0
    expected: int = 0                                # known-mod exceptions (see KNOWN_MOD_EXCEPTIONS)
    mismatches: list = field(default_factory=list)   # (game_id, event_num, recorded, computed)
    expected_examples: list = field(default_factory=list)  # (game_id, event_num, exception_name)

    @property
    def rate(self) -> float:
        # Expected exceptions count as accounted-for, not failures.
        return (self.matches + self.expected) / self.total if self.total else 1.0

    @property
    def failures(self) -> int:
        return self.total - self.matches - self.expected


@dataclass
class ValidationReport:
    fields: dict = field(default_factory=dict)         # name -> FieldStat
    total_events: int = 0
    contact_events: int = 0
    simulated: int = 0
    skipped: list = field(default_factory=list)        # (game_id, event_num, reason)
    errors: list = field(default_factory=list)         # (game_id, event_num, message)
    files: int = 0

    def _stat(self, name: str) -> FieldStat:
        return self.fields.setdefault(name, FieldStat(name))

    def merge(self, other: "ValidationReport") -> "ValidationReport":
        self.total_events += other.total_events
        self.contact_events += other.contact_events
        self.simulated += other.simulated
        self.skipped += other.skipped
        self.errors += other.errors
        self.files += other.files
        for name, st in other.fields.items():
            mine = self._stat(name)
            mine.matches += st.matches
            mine.total += st.total
            mine.expected += st.expected
            mine.mismatches += st.mismatches
            mine.expected_examples += st.expected_examples
        return self

    def all_fields_perfect(self) -> bool:
        return all(st.failures == 0 for st in self.fields.values())

    def contact_fields_perfect(self) -> bool:
        """True if the deterministic contact-stage fields all match.

        Known-mod exceptions (e.g. Remove slice) are counted as expected, not
        failures. Excludes the informational 'landing' field, which is expected
        to diverge (the trajectory flight model was never verified).
        """
        return all(st.failures == 0
                   for name, st in self.fields.items()
                   if not name.startswith("landing"))

    def summary(self, max_mismatches: int = 8) -> str:
        lines = []
        lines.append(
            f"Files: {self.files} | events: {self.total_events} | "
            f"with contact: {self.contact_events} | simulated: {self.simulated} | "
            f"skipped: {len(self.skipped)} | errors: {len(self.errors)}"
        )
        lines.append("")
        lines.append(f"{'field':18} {'match':>12} {'exp':>5} {'fail':>5}   rate")
        lines.append("-" * 56)
        for name, st in self.fields.items():
            lines.append(f"{name:18} {st.matches:>6}/{st.total:<5} {st.expected:>5} "
                         f"{st.failures:>5} {st.rate * 100:6.2f}%")

        # group skip reasons
        if self.skipped:
            reasons: dict[str, int] = {}
            for _, _, reason in self.skipped:
                key = reason.split(":")[0] if ":" in reason else reason
                reasons[key] = reasons.get(key, 0) + 1
            lines.append("")
            lines.append("Skipped reasons:")
            for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {n:>4}  {reason}")

        # known-mod exceptions, grouped by exception name
        exc_counts: dict[str, int] = {}
        for st in self.fields.values():
            for _, _, exc_name in st.expected_examples:
                exc_counts[exc_name] = exc_counts.get(exc_name, 0) + 1
        if exc_counts:
            lines.append("")
            lines.append("Expected (known mod exceptions):")
            for exc_name, n in sorted(exc_counts.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {n:>4}  {exc_name}")

        # mismatch examples per field
        flagged = [st for st in self.fields.values() if st.mismatches]
        if flagged:
            lines.append("")
            lines.append("Example mismatches:")
            for st in flagged:
                lines.append(f"  [{st.name}] {len(st.mismatches)} total")
                for gid, ev, rec, com in st.mismatches[:max_mismatches]:
                    lines.append(f"      game {gid} ev{ev}: recorded={rec} computed={com}")

        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for gid, ev, msg in self.errors[:max_mismatches]:
                lines.append(f"  game {gid} ev{ev}: {msg}")

        return "\n".join(lines)


# ---------------------------------------------------------------- core driver

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
    if sec is not None and G.to_encoded(G.SECONDARY_CONTACT_RESULT, sec) == 0:
        return False  # caught for an out
    action = (contact.get("First Fielder") or {}).get("Fielder Action", 0)
    try:
        if G.to_encoded(G.FIELDER_ACTIONS, action) != 0:  # 0 = None
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

        swing = event.pitch_dict().get("Type of Swing")
        swing_code = G.to_encoded(G.TYPE_OF_SWING, swing) if swing is not None else None
        if swing_code not in _SUPPORTED_SWING_CODES:
            report.skipped.append((game_id, i, f"unsupported swing: {swing!r}"))
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
            left_park = stadiums.boundary_crossing(result.trajectory, stadium) is not None
            if left_park:
                # Left the park (HR / off the wall / foul into the netting): the
                # recorded landing is where the ball struck something, which lies
                # on the wall-free flight path (a few frames past the boundary for
                # a ball that clears the fence). Compare to the nearest 3D point.
                try:
                    rec = (float(contact["Ball Landing Position - X"]),
                           float(contact["Ball Landing Position - Y"]),
                           float(contact["Ball Landing Position - Z"]))
                except (KeyError, TypeError, ValueError):
                    rec = None
                near = stadiums.nearest_trajectory_point(result.trajectory, rec) if rec else None
                if near is not None:
                    result.landing = near[2]
            elif bounces:
                # Recorded landing for an in-park grounder/liner is where the
                # skidding ball is at "Ball Hang Time"; walk the bounce there.
                try:
                    hang = _ci(contact.get("Ball Hang Time"))
                except (TypeError, ValueError):
                    hang = None
                if hang and hang > 0:
                    result.landing = hs.simulate_hit_trajectory_from_event(
                        event, hang, active_tags)[-1]
        skip_landing = landing_exclude_caught and not _is_natural_landing(contact)
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
