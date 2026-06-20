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
}

# Deliberately NOT compared: the similarly-named canonical map describes a
# different field than the pyrio dict.
#   cInputDirectionToHR (None/Towards/Away) vs INPUT_DIRECTION (stick bitmask)
#   cManualSelectDecode (selected fielder)  vs MANUAL_SELECT (selection state)


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
