"""Parity check: pyrio's Tables vs Project Rio's canonical C++ maps.

The canonical id/name mappings live in the Project Rio repo at
``Source/Core/Core/MSB_StatTracker.h``. This test parses those C++ maps and
asserts pyrio's tables match, so drift (e.g. a new character or a renamed
result) is caught.

Point it at a local Project Rio checkout with the PYRIO_PROJECTRIO_PATH env
var, which makes a missing checkout an error (CI's parity job sets it).
Without it the test looks for a sibling ``../ProjectRio`` and skips if absent.
"""
import os
import re
import pathlib
import subprocess
import tempfile

import pytest

from pyrio.rio_value import Tables

# canonical C++ map name -> Tables attribute. Only maps describing the
# SAME field are listed here.
CANON_TO_PYRIO = {
    "cCharIdToCharName": "CHAR_NAME",
    "cStadiumIdToStadiumName": "STADIUM",
    "cLogoIdToTeamName": "TEAM_NAME",
    "cTypeOfContactToHR": "CONTACT_TYPE",
    "cHandToHR": "HAND",
    "cPitchTypeToHR": "PITCH_TYPE",
    "cChargePitchTypeToHR": "CHARGE_TYPE",
    "cTypeOfSwing": "TYPE_OF_SWING",
    "cPosition": "POSITION",
    "cFielderActions": "FIELDER_ACTIONS",
    "cFielderBobbles": "FIELDER_BOBBLES",
    "cStealType": "STEAL_TYPE",
    "cOutType": "OUT_TYPE",
    "cPitchResult": "PITCH_RESULT",
    "cPrimaryContactResult": "PRIMARY_CONTACT_RESULT",
    "cSecondaryContactResult": "SECONDARY_CONTACT_RESULT",
    "cAtBatResult": "FINAL_RESULT",
    "cManualSelectDecode": "MANUAL_SELECT",
    "cDeadBallReason": "DEAD_BALL_REASON",
}

# INPUT_DIRECTION is NOT compared here: it mirrors the C++ "StickVec" decoder
# (a computed 0-15 bitmask), not a header std::map -- it is checked directly in
# test_lookup_values.py. The header's cInputDirectionToHR is a *different* field
# (Input Direction - Push/Pull: None/Towards/Away), which pyrio has no dict for.


HEADER_REL = "Source/Core/Core/MSB_StatTracker.h"
CPP_REL = "Source/Core/Core/MSB_StatTracker.cpp"

# The Project Rio release pyrio tracks. Read from this ref rather than the
# checkout's working tree, so the comparison cannot depend on whatever someone
# happens to have modified or staged in another repository. Override with
# PYRIO_PROJECTRIO_REF.
DEFAULT_REF = "origin/2.3.0_release"


def _find_repo():
    env = os.environ.get("PYRIO_PROJECTRIO_PATH")
    if env:
        candidate = pathlib.Path(env)
    else:
        candidate = pathlib.Path(__file__).resolve().parent.parent.parent / "ProjectRio"
    return candidate if (candidate / HEADER_REL).is_file() else None


def _materialize(repo, ref):
    """Extract the tracker sources at ``ref`` into a temp dir.

    Returns (header_path, commit) or (None, None) if the ref does not resolve.
    """
    try:
        rev = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture_output=True, text=True, timeout=10,
        )
        if rev.returncode != 0:
            return None, None
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pyrio-canonical-"))
        for rel in (HEADER_REL, CPP_REL):
            blob = subprocess.run(
                ["git", "-C", str(repo), "show", f"{ref}:{rel}"],
                capture_output=True, text=True, timeout=30,
            )
            if blob.returncode != 0:
                if rel == HEADER_REL:
                    return None, None
                continue
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(blob.stdout)
        return tmp / HEADER_REL, rev.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None, None


REPO = _find_repo()
REF = os.environ.get("PYRIO_PROJECTRIO_REF", DEFAULT_REF)

# An explicit path means the caller (CI's parity job) wants the comparison, so a
# wrong path is an error, not a skip.
if os.environ.get("PYRIO_PROJECTRIO_PATH") and REPO is None:
    raise RuntimeError(
        f"PYRIO_PROJECTRIO_PATH={os.environ['PYRIO_PROJECTRIO_PATH']!r} has no {HEADER_REL}"
    )
HEADER = None
SOURCE = "no Project Rio checkout found"

if REPO is not None:
    HEADER, _commit = _materialize(REPO, REF)
    if HEADER is not None:
        SOURCE = f"{REPO} at {REF} ({_commit[:10]})"
    else:
        # No git, or the ref is absent (e.g. a bare copy of the sources).
        HEADER = REPO / HEADER_REL
        SOURCE = (
            f"{HEADER} -- WORKING TREE, because ref {REF!r} did not resolve; "
            "this may include uncommitted local edits"
        )

pytestmark = pytest.mark.skipif(
    HEADER is None,
    reason="Project Rio repo not found; set PYRIO_PROJECTRIO_PATH to enable parity tests",
)


# Divergences pyrio carries deliberately, because it has adopted a correction
# that is not merged upstream yet. (canonical map, id) -> pyrio's value.
# Each entry must cite why; remove it once upstream agrees -- the test fails
# with a "remove this entry" message when that happens, so these cannot rot.
PENDING_UPSTREAM = {
    # ProjectRio/ProjectRio#170 (open): 0xC is set when a throw could still
    # have retired a runner but none was put out, so it is neither a chem
    # error (2.2.0) nor a fielder's choice (2.3.0). Secondary result 0x4,
    # "Batter safe, runner out", is the play that is a fielder's choice.
    ("cAtBatResult", 12): "Batter safe, throw elsewhere",
    ("cSecondaryContactResult", 12): "Batter safe, throw elsewhere",
}


def _parse_canonical(path):
    text = path.read_text()
    maps = {}
    for name, body in re.findall(r"std::map<[^>]*>\s+(c\w+)\s*=\s*\{(.*?)\};", text, re.DOTALL):
        entries = re.findall(r'\{\s*(0x[0-9a-fA-F]+|\d+)\s*,\s*"([^"]*)"\s*\}', body)
        maps[name] = {int(k, 0): v for k, v in entries}
    return maps


_CANON = _parse_canonical(HEADER) if HEADER else {}


@pytest.mark.parametrize("canon_name,pyrio_name", sorted(CANON_TO_PYRIO.items()))
def test_lookupdict_matches_canonical(canon_name, pyrio_name):
    canon = _CANON.get(canon_name)
    assert canon, f"canonical map {canon_name} not found in {HEADER}"
    pymap = getattr(Tables, pyrio_name)
    # compare on int keys (skip pyrio-only non-int keys like None/bool)
    py_int = {k: v for k, v in pymap.items() if isinstance(k, int) and not isinstance(k, bool)}

    diffs, stale = [], []
    for k in sorted(set(canon) | set(py_int)):
        c, p = canon.get(k), py_int.get(k)
        pending = PENDING_UPSTREAM.get((canon_name, k))
        if pending is not None:
            if c == pending:
                stale.append(
                    f"  id {k}: upstream now says {c!r} too -- "
                    f"remove the PENDING_UPSTREAM entry for ({canon_name!r}, {k})"
                )
                continue
            if p == pending:
                continue        # deliberate divergence, still pending upstream
        if c != p:
            diffs.append(f"  id {k}: canonical={c!r} pyrio={p!r}")

    if diffs or stale:
        parts = [f"{pyrio_name} vs canonical {canon_name}", f"source: {SOURCE}"]
        if diffs:
            parts.append("diverges:\n" + "\n".join(diffs))
        if stale:
            parts.append("stale exceptions:\n" + "\n".join(stale))
        pytest.fail("\n".join(parts))


# --- field-name (schema) parity ---------------------------------------------

def _canonical_field_names():
    """Field names MSB_StatTracker emits (hardcoded JSON writes + TrackerValue names)."""
    fields = set(re.findall(r'Tracker(?:Value|Adr)<[^>]*>\("([^"]+)"', HEADER.read_text()))
    cpp = HEADER.with_suffix(".cpp")
    if cpp.is_file():
        fields |= set(re.findall(r'\\"([A-Z][^"\\]+)\\"\s*:', cpp.read_text()))
    return fields


def _pyrio_field_literals():
    """Explicit field names read off the stat/HUD JSON containers.

    Restricted to accesses on the raw-data objects (statJson/hud_json/eventDict/
    runner_json, the *_dict() views and the offensiveStats()/defensiveStats()
    helpers) so it doesn't pick up pyrio's own output
    dicts or value-string literals. Conservative: nested accesses (e.g. CharID
    on a sub-dict) may be missed, which is fine for a subset guard.
    """
    pkg = pathlib.Path(__file__).resolve().parent.parent / "src" / "pyrio" / "stat_file"
    containers = (
        r"(?:statJson|hud_json|eventDict|runner_json|character"
        r"|pitch_dict\(\)|contact_dict\(\)|first_fielder_dict\(\)"
        r"|offensiveStats\([^()]*\)|defensiveStats\([^()]*\))"
    )
    pattern = containers + r"\s*(?:\[\s*|\.get\(\s*)['\"]([^'\"{}]+)['\"]"
    lits = set()
    for p in pkg.glob("*.py"):
        lits |= set(re.findall(pattern, p.read_text()))
    return lits


# Real fields the C++ emits via a constructed key ("Runner {n}B"), so they are
# not literal in the header/cpp even though they exist in the files.
_FIELD_ALLOWLIST: set[str] = {"Runner 1B", "Runner 2B", "Runner 3B"}

# Fields older clients wrote and the current one no longer does. pyrio still reads them
# so old stat files parse. Each entry names the release that dropped it and what
# replaced it; checked against ProjectRio's history (`git log -S'<field>'`).
_LEGACY_FIELDS: dict[str, str] = {
    # Written by 0.1.6 through 1.9.1; renamed in 1.9.2 (ProjectRio ee757054f4), when the
    # count changed from pitches to batters.
    "Pitches Per Position": "replaced by 'Batters Per Position' in 1.9.2",
}


def test_pyrio_fields_are_canonical():
    """Every field the parser reads must exist in MSB_StatTracker (catches renames)."""
    canonical = _canonical_field_names()
    literals = _pyrio_field_literals()
    # Guard against scanning nothing: a moved package once made this pass vacuously.
    assert len(literals) > 50, f"only {len(literals)} field literals found; is the parser path right?"
    unknown = sorted(
        k for k in literals
        if k not in canonical and k not in _FIELD_ALLOWLIST and k not in _LEGACY_FIELDS
    )
    assert not unknown, (
        "parser reads fields absent from canonical MSB_StatTracker "
        "(a typo, a field the client renamed -- add it to _LEGACY_FIELDS with the release "
        "that dropped it -- or a constructed key for _FIELD_ALLOWLIST):\n  " + "\n  ".join(unknown)
    )


def test_legacy_fields_are_still_legacy():
    """A legacy field the current client writes again is no longer legacy."""
    canonical = _canonical_field_names()
    revived = sorted(k for k in _LEGACY_FIELDS if k in canonical)
    assert not revived, (
        "canonical MSB_StatTracker writes these again; remove them from _LEGACY_FIELDS:\n  "
        + "\n  ".join(revived)
    )
