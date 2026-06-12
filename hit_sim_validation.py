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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import hit_simulation as hs
from . import hit_sim_tables as T
from .stat_file_parser import StatObj, EventObj

# Map the simulator's Batter_ContactType index to the stat-file string.
_RECORDED_CONTACT_TYPE = {
    T.LeftSour: "Sour - Left",
    T.LeftNice: "Nice - Left",
    T.Perfect: "Perfect",
    T.RightNice: "Nice - Right",
    T.RightSour: "Sour - Right",
}

_SUPPORTED_SWINGS = ("Slap", "Charge", "Star")


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
        else:
            ok = abs(float(rec) - float(com)) <= self.tol
        return ok, rec, com


def _contact_field_specs(vel_tol: float, float_tol: float) -> list[_FieldSpec]:
    return [
        _FieldSpec("contact_type",
                   lambda c: c["Type of Contact"],
                   lambda r: _RECORDED_CONTACT_TYPE[r.contact_type]),
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
    return [
        _FieldSpec("landing_x",
                   lambda c: c["Ball Landing Position - X"],
                   lambda r: r.landing[0], tol=landing_tol),
        _FieldSpec("landing_z",
                   lambda c: c["Ball Landing Position - Z"],
                   lambda r: r.landing[2], tol=landing_tol),
    ]


# ---------------------------------------------------------------- report types

@dataclass
class FieldStat:
    name: str
    matches: int = 0
    total: int = 0
    mismatches: list = field(default_factory=list)  # (game_id, event_num, recorded, computed)

    @property
    def rate(self) -> float:
        return self.matches / self.total if self.total else 1.0


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
            mine.mismatches += st.mismatches
        return self

    def all_fields_perfect(self) -> bool:
        return all(st.matches == st.total for st in self.fields.values())

    def contact_fields_perfect(self) -> bool:
        """True if the deterministic contact-stage fields all match.

        Excludes the informational 'landing_*' fields, which are expected to
        diverge (the JS trajectory model was never verified against the game).
        """
        return all(st.matches == st.total
                   for name, st in self.fields.items()
                   if not name.startswith("landing_"))

    def summary(self, max_mismatches: int = 8) -> str:
        lines = []
        lines.append(
            f"Files: {self.files} | events: {self.total_events} | "
            f"with contact: {self.contact_events} | simulated: {self.simulated} | "
            f"skipped: {len(self.skipped)} | errors: {len(self.errors)}"
        )
        lines.append("")
        lines.append(f"{'field':18} {'match':>12}   rate")
        lines.append("-" * 44)
        for name, st in self.fields.items():
            lines.append(f"{name:18} {st.matches:>6}/{st.total:<5} {st.rate * 100:6.2f}%")

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

def _ball_reached_ground(contact: dict) -> bool:
    """True if the recorded landing is a real ground contact (not a fielder).

    For a ball caught in the air the stat file stores the fielder's location in
    'Ball Landing Position', so those events must be excluded from any landing
    comparison.
    """
    return contact.get("Contact Result - Secondary") != "Out-caught"


def validate_statobj(stat: StatObj, *, include_landing: bool = False,
                     landing_exclude_caught: bool = True,
                     vel_tol: float = 1e-4, float_tol: float = 1e-3,
                     landing_tol: float = 1.0,
                     report: Optional[ValidationReport] = None) -> ValidationReport:
    """Compare every contact event in one game against the simulator."""
    report = report or ValidationReport()
    report.files += 1
    try:
        game_id = stat.gameID()
    except Exception:
        game_id = "?"

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
        if swing not in _SUPPORTED_SWINGS:
            report.skipped.append((game_id, i, f"unsupported swing: {swing!r}"))
            continue

        try:
            result = hs.simulate_hit_from_event(event)
        except ValueError as ex:
            report.skipped.append((game_id, i, f"value error: {ex}"))
            continue
        except Exception as ex:  # noqa: BLE001 - surface unexpected failures
            report.errors.append((game_id, i, f"{type(ex).__name__}: {ex}"))
            continue

        report.simulated += 1
        skip_landing = landing_exclude_caught and not _ball_reached_ground(contact)
        for spec in specs:
            if skip_landing and spec.name.startswith("landing_"):
                continue
            try:
                ok, rec, com = spec.matches(contact, result)
            except (KeyError, TypeError, ValueError):
                continue  # field absent for this event (e.g. some fouls)
            st = report._stat(spec.name)
            st.total += 1
            if ok:
                st.matches += 1
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
                        help="also compare landing position (informational; the JS "
                             "trajectory model is unverified, so misses are expected)")
    parser.add_argument("--include-caught-landing", action="store_true",
                        help="include caught balls in the landing comparison "
                             "(their recorded landing is the fielder's position)")
    args = parser.parse_args(argv)
    report = validate(args.path, include_landing=args.landing,
                      landing_exclude_caught=not args.include_caught_landing)
    print(report.summary())
    # Exit status reflects the deterministic fields only; landing is informational.
    return 0 if report.contact_fields_perfect() and not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
