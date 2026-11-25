"""Each public namespace's names, pinned.

Adding or removing a public name changes this file, so the change is reviewed
rather than slipping in. Update the list deliberately.
"""

import subprocess
import sys

import pytest

import pyrio

CORE = [
    "Ability",
    "AtBat",
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
    "Contact",
    "ContactType",
    "DeadBallReason",
    "Event",
    "FielderAction",
    "FielderBobble",
    "Fielding",
    "Game",
    "GameResult",
    "GameState",
    "HUDSnapshot",
    "HalfInning",
    "Hand",
    "HorizontalHitTrajectory",
    "InputDirection",
    "LinearWeights",
    "ManualSelect",
    "MoonshotStatus",
    "OutType",
    "Pitch",
    "PitchResult",
    "PitchType",
    "PitchingLine",
    "Position",
    "PrimaryContactResult",
    "PushPull",
    "RioError",
    "RosterSpot",
    "RunExpectancy",
    "Runner",
    "SecondaryContactResult",
    "Side",
    "SignatureTeam",
    "Stadium",
    "StarPitch",
    "StarSwing",
    "StatFileError",
    "StealType",
    "SwingType",
    "Team",
    "TeamName",
    "UnknownCodeError",
    "UnknownNameError",
    "Version",
    "VerticalHitTrajectory",
    "format_batting_line",
    "format_pitching_line",
    "linear_weights",
    "read_game",
    "read_hud",
    "run_expectancy",
    "team_name",
    "to_jsonable",
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


WEB = [
    "APIConnectionError",
    "APIError",
    "APIResponseError",
    "APITimeoutError",
    "AsyncRioClient",
    "AuthenticationError",
    "Community",
    "CommunityKind",
    "CommunityMember",
    "ContactLine",
    "DiskCache",
    "EventRef",
    "FieldingLine",
    "GameSummary",
    "IssuedKey",
    "LadderGame",
    "LadderRow",
    "LandingRow",
    "Linescore",
    "LiveGame",
    "LiveTeam",
    "NotFoundError",
    "PlayRunner",
    "RatingUpdate",
    "RecordLine",
    "RioClient",
    "ScoringPlay",
    "StarChanceRow",
    "StatRow",
    "Tag",
    "TagKind",
    "TagSet",
    "TagSetKind",
    "TeamSummary",
    "User",
]


def test_web_names():
    web = pytest.importorskip("pyrio.web", exc_type=ImportError)
    assert sorted(web.__all__) == WEB
    assert [name for name in web.__all__ if not hasattr(web, name)] == []


GEOMETRY = [
    "FIELDER_LOCKOUT_FRAMES",
    "FIELDER_START_LOCATIONS",
    "Hazard",
    "HazardKind",
    "Point",
    "StadiumPhysics",
    "Surface",
    "Triangle",
    "WallSegment",
    "area",
    "boundary",
    "boundary_crossing",
    "clears_wall",
    "hazards",
    "physics",
    "triangles",
    "wall_at",
    "wall_crossing",
    "walls",
]


def test_geometry_names():
    import pyrio.geometry

    assert sorted(pyrio.geometry.__all__) == GEOMETRY
    assert all(hasattr(pyrio.geometry, name) for name in GEOMETRY)


SIM = [
    "ContactRecord",
    "Highlights",
    "HitInputs",
    "HitOverrides",
    "HitResult",
    "LiveBallEvent",
    "LiveBallEventKind",
    "LiveBallOutcome",
    "LiveBallResult",
    "Mod",
    "TAG_TO_MOD",
    "best",
    "find_highlights",
    "format_highlights",
    "hazard_seed",
    "play_out",
    "play_out_flight",
    "simulate_all_zones",
    "simulate_contacts",
    "simulate_hit",
    "simulate_trajectory",
]


def test_sim_names():
    import pyrio.sim

    assert sorted(pyrio.sim.__all__) == SIM
    assert all(hasattr(pyrio.sim, name) for name in SIM)


SVG = ["Flight", "Mark", "MarkShape", "spray_chart", "stadium"]


def test_svg_names():
    import pyrio.svg

    assert sorted(pyrio.svg.__all__) == SVG
    assert all(hasattr(pyrio.svg, name) for name in SVG)


def test_plot_names():
    plot = pytest.importorskip("pyrio.plot", exc_type=ImportError)
    assert sorted(plot.__all__) == ["spray_chart", "stadium"]


def test_pandas_names():
    pandas = pytest.importorskip("pyrio.pandas", exc_type=ImportError)
    assert pandas.__all__ == ["frame"]
