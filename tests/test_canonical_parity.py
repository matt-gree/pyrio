"""Parity check: pyrio's LookupDicts vs Project Rio's canonical C++ maps.

The canonical id/name mappings live in the Project Rio repo at
``Source/Core/Core/MSB_StatTracker.h``. This test parses those C++ maps and
asserts pyrio's tables match, so drift (e.g. a new character or a renamed
result) is caught.

Point it at a local Project Rio checkout with the PYRIO_PROJECTRIO_PATH env
var; otherwise it falls back to a sibling ``../ProjectRio`` and skips if absent.
"""
import os
import re
import pathlib

import pytest

from pyrio.lookup import LookupDicts

# canonical C++ map name -> LookupDicts attribute. Only maps describing the
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


def _find_header():
    env = os.environ.get("PYRIO_PROJECTRIO_PATH")
    candidates = []
    if env:
        candidates.append(pathlib.Path(env) / "Source/Core/Core/MSB_StatTracker.h")
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    candidates.append(repo_root.parent / "ProjectRio" / "Source/Core/Core/MSB_StatTracker.h")
    return next((c for c in candidates if c.is_file()), None)


HEADER = _find_header()

pytestmark = pytest.mark.skipif(
    HEADER is None,
    reason="Project Rio repo not found; set PYRIO_PROJECTRIO_PATH to enable parity tests",
)


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
    pymap = getattr(LookupDicts, pyrio_name)
    # compare on int keys (skip pyrio-only non-int keys like None/bool)
    py_int = {k: v for k, v in pymap.items() if isinstance(k, int) and not isinstance(k, bool)}
    if py_int != canon:
        lines = [
            f"  id {k}: canonical={canon.get(k)!r} pyrio={py_int.get(k)!r}"
            for k in sorted(set(canon) | set(py_int))
            if canon.get(k) != py_int.get(k)
        ]
        pytest.fail(f"{pyrio_name} diverges from canonical {canon_name}:\n" + "\n".join(lines))


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
    runner_json and the *_dict() views) so it doesn't pick up pyrio's own output
    dicts or value-string literals. Conservative: nested accesses (e.g. CharID
    on a sub-dict) may be missed, which is fine for a subset guard.
    """
    pkg = pathlib.Path(__file__).resolve().parent.parent / "stat_file"
    containers = r"(?:statJson|hud_json|eventDict|runner_json|pitch_dict\(\)|contact_dict\(\)|first_fielder_dict\(\))"
    pattern = containers + r"\s*(?:\[\s*|\.get\(\s*)['\"]([^'\"{}]+)['\"]"
    lits = set()
    for p in pkg.glob("*.py"):
        lits |= set(re.findall(pattern, p.read_text()))
    return lits


# Real fields the C++ emits via a constructed key ("Runner {n}B"), so they are
# not literal in the header/cpp even though they exist in the files.
_FIELD_ALLOWLIST: set[str] = {"Runner 1B", "Runner 2B", "Runner 3B"}


def test_pyrio_fields_are_canonical():
    """Every field the parser reads must exist in MSB_StatTracker (catches renames)."""
    canonical = _canonical_field_names()
    unknown = sorted(
        k for k in _pyrio_field_literals()
        if k not in canonical and k not in _FIELD_ALLOWLIST
    )
    assert not unknown, (
        "parser reads fields absent from canonical MSB_StatTracker "
        "(field rename/typo, or add to _FIELD_ALLOWLIST):\n  " + "\n  ".join(unknown)
    )
