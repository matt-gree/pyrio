"""Source-agnostic core for hit-simulator validation.

Both validation front-ends compare simulated ``HitResult``s against recorded
values with the same machinery, and only differ in where the recorded values
come from:

  - hit_sim_validation     -- local decoded stat files (a contact dict per event)
  - hit_sim_api_validation -- ProjectRio's /landing_data/ endpoint (a flat row)

This module holds the parts that don't care about that source: the per-field
comparison (:class:`FieldSpec`), the tally + reporting (:class:`FieldStat`,
:class:`ValidationReport`), and the landing post-processing that mirrors how the
game records a landing (fence boundary nearest-point, in-park bounce-to-hang-
time, note-block exclusion). Each front-end supplies its own FieldSpecs (which
know how to pull a value out of its record type) and feeds this report.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from .. import stadiums


def ci(value) -> int:
    """Parse a possibly comma-grouped integer string, e.g. '1,181' -> 1181."""
    return int(str(value).replace(",", ""))


# ---------------------------------------------------------------- field specs

@dataclass(frozen=True)
class FieldSpec:
    """One comparison: pull a recorded value out of a ``record`` (a stat-file
    contact dict or an API row) and the matching value out of a HitResult, then
    test them within ``tol`` (None -> exact equality; a tuple recorded value is
    compared by euclidean distance)."""
    name: str
    recorded: Callable[[object], object]
    computed: Callable[[object], object]
    tol: Optional[float] = None

    def matches(self, record, result) -> tuple[bool, object, object]:
        rec = self.recorded(record)
        com = self.computed(result)
        if self.tol is None:
            ok = rec == com
        elif isinstance(rec, tuple):           # point: compare by euclidean distance
            ok = math.dist(rec, com) <= self.tol
        else:
            ok = abs(float(rec) - float(com)) <= self.tol
        return ok, rec, com


# ---------------------------------------------------------------- report types

@dataclass
class FieldStat:
    name: str
    matches: int = 0
    total: int = 0
    expected: int = 0                                # known-mod exceptions
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
    files: int = 0                                     # files (stat) or games (API)

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

        Known-mod exceptions are counted as expected, not failures. Excludes the
        informational 'landing' field, which depends on the (unverified vs ground
        truth) flight model.
        """
        return all(st.failures == 0
                   for name, st in self.fields.items()
                   if not name.startswith("landing"))

    def summary(self, max_mismatches: int = 8) -> str:
        lines = []
        lines.append(
            f"Files/games: {self.files} | events: {self.total_events} | "
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


# ---------------------------------------------------------------- landing post-processing
# How the game records a "landing" depends on what the ball did, so the simulated
# landing has to be pulled to the matching point before the 3D comparison. This is
# identical for both front-ends (the geometry lives in stadiums); only the inputs
# differ, so each passes its own recorded point / hang time / trajectory walker.

def resolve_landing(result, stadium, recorded_point, *, bounces: bool = False,
                    hang_time: Optional[int] = None,
                    walk_to_hang: Optional[Callable[[int], list]] = None) -> bool:
    """Pull ``result.landing`` to the point the recorded landing represents.

    - Ball left the park (HR / off the wall / foul into the netting): the recorded
      landing lies on the wall-free flight path, so snap to the nearest 3D point
      on the simulated trajectory.
    - Otherwise, if ``bounces`` and a ``hang_time`` is given: the recorded landing
      is where the in-park ball (bounce or skid) sits at hang time, so walk the
      trajectory there via ``walk_to_hang(hang_time)``.

    Returns True if the ball left the park. The simulated trajectory is never
    modified -- only ``result.landing`` (the comparison point) is.
    """
    left_park = stadiums.boundary_crossing(result.trajectory, stadium) is not None
    if left_park:
        if recorded_point is not None:
            near = stadiums.nearest_trajectory_point(result.trajectory, recorded_point)
            if near is not None:
                result.landing = near[2]
    elif bounces and hang_time and hang_time > 0 and walk_to_hang is not None:
        result.landing = walk_to_hang(hang_time)[-1]
    return left_park


def note_block_deflected(result, stadium) -> bool:
    """True if the flight path passes through a Peach Garden note block; the
    air-only sim can't model the deflection, so such landings are excluded."""
    return stadiums.note_block_hit(result.trajectory, stadium) is not None
