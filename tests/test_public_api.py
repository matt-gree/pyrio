"""Each public namespace's names, pinned.

Adding or removing a public name changes this file, so the change is reviewed
rather than slipping in. Update the list deliberately.
"""

import pyrio

CORE = [
    "Ability",
    "AtBatResult",
    "Bases",
    "CaptainStar",
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
    "Position",
    "PrimaryContactResult",
    "PushPull",
    "RioError",
    "SecondaryContactResult",
    "Side",
    "Stadium",
    "StarPitch",
    "StarSwing",
    "StealType",
    "SwingType",
    "TeamName",
    "UnknownCodeError",
    "UnknownNameError",
    "VerticalHitTrajectory",
]


def test_core_names():
    assert sorted(pyrio.__all__) == CORE


def test_every_core_name_exists():
    missing = [name for name in pyrio.__all__ if not hasattr(pyrio, name)]
    assert missing == []
