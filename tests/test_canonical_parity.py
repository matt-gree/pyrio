"""Parity check: pyrio's enums vs Project Rio's canonical C++ maps.

The canonical id/label maps live in the Project Rio repo at
``Source/Core/Core/MSB_StatTracker.h``. This test parses those C++ maps and
checks each ``CodeEnum`` against its map in both directions, so drift (a new
character, a renamed result) fails with the line to paste.

Point it at a local Project Rio checkout with the PYRIO_PROJECTRIO_PATH env
var, which makes a missing checkout an error (CI's parity job sets it).
Without it the test looks for a sibling ``../ProjectRio`` and skips if absent.
"""

import ast
import os
import pathlib
import re
import subprocess
import tempfile

import pytest

import pyrio
from pyrio import (
    AtBatResult,
    CaptainStar,
    Character,
    CharacterClass,
    ChargeType,
    CodeEnum,
    ContactType,
    DeadBallReason,
    FielderAction,
    FielderBobble,
    Hand,
    HorizontalHitTrajectory,
    ManualSelect,
    MoonshotStatus,
    OutType,
    PitchResult,
    PitchType,
    Position,
    PrimaryContactResult,
    PushPull,
    SecondaryContactResult,
    Stadium,
    StarPitch,
    StarSwing,
    StealType,
    SwingType,
    TeamName,
    VerticalHitTrajectory,
)

# Canonical C++ map -> the enum that mirrors it.
CANON_TO_ENUM: dict[str, type[CodeEnum]] = {
    "cCharIdToCharName": Character,
    "cStadiumIdToStadiumName": Stadium,
    "cLogoIdToTeamName": TeamName,
    "cTypeOfContactToHR": ContactType,
    "cHandToHR": Hand,
    "cInputDirectionToHR": PushPull,
    "cPitchTypeToHR": PitchType,
    "cChargePitchTypeToHR": ChargeType,
    "cTypeOfSwing": SwingType,
    "cMoonShotStatus": MoonshotStatus,
    "cPosition": Position,
    "cFielderActions": FielderAction,
    "cFielderBobbles": FielderBobble,
    "cStealType": StealType,
    "cOutType": OutType,
    "cPitchResult": PitchResult,
    "cPrimaryContactResult": PrimaryContactResult,
    "cSecondaryContactResult": SecondaryContactResult,
    "cAtBatResult": AtBatResult,
    "cDeadBallReason": DeadBallReason,
    "cManualSelectDecode": ManualSelect,
}

# Coded values whose ids come from the character attribute sheet, not the header.
NOT_IN_HEADER: set[type[CodeEnum]] = {
    CharacterClass,
    HorizontalHitTrajectory,
    VerticalHitTrajectory,
    CaptainStar,
    StarPitch,
    StarSwing,
}

# Upstream ids that pyrio reads as None rather than as a member.
READ_AS_NONE = {
    ("cPosition", 0xFF),  # "Inv": no position, so Position | None
}

# InputDirection is not compared here: it mirrors the C++ "StickVec" decoder (a
# computed 0-15 bitmask), not a header std::map, and tests/test_codes.py checks
# it against that decoder's rules.

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
            capture_output=True,
            text=True,
            timeout=10,
        )
        if rev.returncode != 0:
            return None, None
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pyrio-canonical-"))
        for rel in (HEADER_REL, CPP_REL):
            blob = subprocess.run(
                ["git", "-C", str(repo), "show", f"{ref}:{rel}"],
                capture_output=True,
                text=True,
                timeout=30,
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
HEADER = None
SOURCE = "no Project Rio checkout found"

# An explicit path means the caller (CI's parity job) wants the comparison, so a
# wrong path is an error, not a skip.
if os.environ.get("PYRIO_PROJECTRIO_PATH") and REPO is None:
    raise RuntimeError(
        f"PYRIO_PROJECTRIO_PATH={os.environ['PYRIO_PROJECTRIO_PATH']!r} has no {HEADER_REL}"
    )

if REPO is not None:
    HEADER, _commit = _materialize(REPO, REF)
    if HEADER is not None and _commit is not None:
        SOURCE = f"ProjectRio @ {REF}, {_commit[:10]}"
    else:
        # No git, or the ref is absent (e.g. a bare copy of the sources).
        HEADER = REPO / HEADER_REL
        SOURCE = (
            f"{HEADER} -- WORKING TREE, because ref {REF!r} did not resolve; "
            "this may include uncommitted local edits"
        )

needs_header = pytest.mark.skipif(
    HEADER is None,
    reason="Project Rio repo not found; set PYRIO_PROJECTRIO_PATH to enable parity tests",
)


# Divergences pyrio carries deliberately, because it has adopted a correction
# that is not merged upstream yet. (canonical map, id) -> pyrio's label.
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


def _member_name(label):
    """A member name for a new upstream label: 'Captain Toad' -> 'CAPTAIN_TOAD'."""
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")


def _enum_ids(cls):
    """id -> member, including the extra ids a member accepts (0xFF for NONE)."""
    ids = {member.id: member for member in cls}
    for member in cls:
        for alias in member._aliases:
            if isinstance(alias, int):
                ids[alias] = member
    return ids


def _literal(member, label):
    """The member's declaration with ``label`` first, keeping its other labels as aliases."""
    labels = [label] + [
        old for old in (member.label, *member._aliases) if isinstance(old, str) and old != label
    ]
    values = [str(member.id), *(f'"{x}"' for x in labels)]
    return f"{member.name} = {', '.join(values)}"


@needs_header
@pytest.mark.parametrize(
    ("canon_name", "cls"), sorted(CANON_TO_ENUM.items()), ids=sorted(CANON_TO_ENUM)
)
def test_enum_matches_canonical(canon_name, cls):
    canon = _CANON.get(canon_name)
    assert canon, f"canonical map {canon_name} not found in {HEADER}"
    ours = _enum_ids(cls)

    problems = []
    for code in sorted(set(canon) | set(ours)):
        upstream, member = canon.get(code), ours.get(code)
        pending = PENDING_UPSTREAM.get((canon_name, code))
        if pending is not None and upstream == pending:
            problems.append(
                f"  id {code}: upstream now says {upstream!r} too -- "
                f"remove the PENDING_UPSTREAM entry for ({canon_name!r}, {code})"
            )
        elif (canon_name, code) in READ_AS_NONE:
            if member is not None:
                problems.append(f"  id {code} is read as None; remove {member.name}")
        elif member is None:
            problems.append(
                f"  missing id {code} {upstream!r} -- add:    "
                f'{_member_name(upstream)} = {code}, "{upstream}"'
            )
        elif upstream is None:
            problems.append(
                f"  id {code} {member.label!r} is not upstream -- remove {member.name}, "
                "or list it in PENDING_UPSTREAM with the reason"
            )
        elif pending is not None and member.label == pending:
            continue  # deliberate divergence, still pending upstream
        elif member.label != upstream:
            problems.append(
                f"  id {code}: upstream says {upstream!r}, pyrio says {member.label!r} -- "
                f"change to:    {_literal(member, upstream)}"
            )

    if problems:
        pytest.fail(f"{cls.__name__} vs canonical {canon_name} ({SOURCE})\n" + "\n".join(problems))


@needs_header
def test_every_canonical_map_is_mirrored():
    """A map upstream adds fails here until an enum mirrors it."""
    unmirrored = sorted(
        name for name, entries in _CANON.items() if entries and name not in CANON_TO_ENUM
    )
    assert not unmirrored, f"canonical maps with no enum in CANON_TO_ENUM: {unmirrored}"


def _subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def test_every_code_enum_is_checked():
    """Each public CodeEnum is compared with the header, or says where its ids come from."""
    public = [getattr(pyrio, name) for name in pyrio.__all__]  # a list: not every name is hashable
    enums = {cls for cls in _subclasses(CodeEnum) if cls in public}
    unchecked = enums - set(CANON_TO_ENUM.values()) - NOT_IN_HEADER
    assert not unchecked, (
        f"add to CANON_TO_ENUM or NOT_IN_HEADER: {sorted(c.__name__ for c in unchecked)}"
    )


# --- field-name (schema) parity ---------------------------------------------


def _canonical_field_names():
    """Field names MSB_StatTracker emits (hardcoded JSON writes + TrackerValue names)."""
    assert HEADER is not None
    fields = set(re.findall(r'Tracker(?:Value|Adr)<[^>]*>\("([^"]+)"', HEADER.read_text()))
    cpp = HEADER.with_suffix(".cpp")
    if cpp.is_file():
        fields |= set(re.findall(r'\\"([A-Z][^"\\]+)\\"\s*:', cpp.read_text()))
    return fields


def _pyrio_field_literals():
    """Field names the decoder reads: string literals passed to a call or listed in a tuple.

    Restricted to strings shaped like Rio's keys (capitalised words), so error
    messages and format strings don't count. Literals inside f-strings are
    skipped; constructed keys ("Away Roster 3") are covered by the fixtures.
    """
    source = pathlib.Path(__file__).resolve().parent.parent / "src" / "pyrio" / "_decode.py"
    tree = ast.parse(source.read_text())
    in_fstrings = {
        id(node)
        for joined in ast.walk(tree)
        if isinstance(joined, ast.JoinedStr)
        for node in ast.walk(joined)
    }
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            candidates += node.args
        elif isinstance(node, ast.Tuple):
            candidates += node.elts
    return {
        node.value
        for node in candidates
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in in_fstrings
        and re.fullmatch(r"[A-Z][A-Za-z0-9]*(?:[ -/()+]+[A-Za-z0-9()]+)*", node.value)
    }


# Real fields the C++ emits via a constructed key ("Runner {n}B"), so they are
# not literal in the header/cpp even though they exist in the files.
_FIELD_ALLOWLIST: set[str] = {"Runner Batter", "Runner 1B", "Runner 2B", "Runner 3B"}

# Fields older clients wrote and the current one no longer does. pyrio still reads them
# so old stat files parse. Each entry names the release that dropped it and what
# replaced it; checked against ProjectRio's history (`git log -S'<field>'`).
_LEGACY_FIELDS: dict[str, str] = {
    # Written by 0.1.6 through 1.9.1; renamed in 1.9.2 (ProjectRio ee757054f4), when the
    # count changed from pitches to batters.
    "Pitches Per Position": "replaced by 'Batters Per Position' in 1.9.2",
}


@needs_header
def test_pyrio_fields_are_canonical():
    """Every field the parser reads must exist in MSB_StatTracker (catches renames)."""
    canonical = _canonical_field_names()
    literals = _pyrio_field_literals()
    # Guard against scanning nothing: a moved package once made this pass vacuously.
    assert len(literals) > 80, (
        f"only {len(literals)} field literals found; is the decoder path right?"
    )
    unknown = sorted(
        k
        for k in literals
        if k not in canonical and k not in _FIELD_ALLOWLIST and k not in _LEGACY_FIELDS
    )
    assert not unknown, (
        "parser reads fields absent from canonical MSB_StatTracker "
        "(a typo, a field the client renamed -- add it to _LEGACY_FIELDS with the release "
        "that dropped it -- or a constructed key for _FIELD_ALLOWLIST):\n  " + "\n  ".join(unknown)
    )


@needs_header
def test_legacy_fields_are_still_legacy():
    """A legacy field the current client writes again is no longer legacy."""
    canonical = _canonical_field_names()
    revived = sorted(k for k in _LEGACY_FIELDS if k in canonical)
    assert not revived, (
        "canonical MSB_StatTracker writes these again; remove them from _LEGACY_FIELDS:\n  "
        + "\n  ".join(revived)
    )
