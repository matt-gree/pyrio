"""Each public namespace's names, pinned.

Adding or removing a public name changes this file, so the change is reviewed
rather than slipping in. Update the list deliberately.
"""

import subprocess
import sys

import pyrio

CORE = [
    "Ability",
    "AtBatResult",
    "Bases",
    "BattingLine",
    "CAPTAIN_TEAMS",
    "CaptainStar",
    "CaptainTeams",
    "Character",
    "CharacterAttributes",
    "CharacterClass",
    "CharacterFamily",
    "ChargeType",
    "CodeEnum",
    "ContactType",
    "DeadBallReason",
    "FielderAction",
    "FielderBobble",
    "Hand",
    "HorizontalHitTrajectory",
    "InputDirection",
    "ManualSelect",
    "MoonshotStatus",
    "OutType",
    "PitchResult",
    "PitchType",
    "PitchingLine",
    "Position",
    "PrimaryContactResult",
    "PushPull",
    "RioError",
    "SecondaryContactResult",
    "Side",
    "SignatureTeam",
    "Stadium",
    "StarPitch",
    "StarSwing",
    "StealType",
    "SwingType",
    "TeamName",
    "UnknownCodeError",
    "UnknownNameError",
    "VerticalHitTrajectory",
    "format_batting_line",
    "format_pitching_line",
    "team_name",
]


def test_core_names():
    assert sorted(pyrio.__all__) == CORE


def test_every_core_name_exists():
    missing = [name for name in pyrio.__all__ if not hasattr(pyrio, name)]
    assert missing == []


RATINGS = ["Rating", "update", "win_probability"]


def test_ratings_names():
    import pyrio.ratings

    assert sorted(pyrio.ratings.__all__) == RATINGS


def test_import_pyrio_does_not_import_ratings():
    # A fresh interpreter: this test session may already have imported it.
    code = "import sys, pyrio; print('pyrio.ratings' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"
