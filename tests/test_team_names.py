"""Team names: the logo table and what its structure says."""

from collections import Counter

from pyrio import Character, TeamName


def test_logo_structure():
    assert TeamName.MARIO_FIREBALLS.captain is Character.MARIO
    assert TeamName.JR_FANGS.captain is Character.BOWSER_JR
    assert [TeamName(i).role for i in range(4)] == [
        "signature",
        "signature",
        "class_team",
        "default",
    ]


def test_four_logos_per_captain():
    assert set(Counter(team.captain for team in TeamName).values()) == {4}
    assert all(team.captain.is_captain for team in TeamName)


def test_captains_match_the_pre_1_0_table():
    """Transitional: against rio_value.TeamName, until step 7 deletes it."""
    from pyrio.rio_value import TeamName as OldTeamName

    for team in TeamName:
        assert team.captain.label == OldTeamName.from_raw(team.id).captain.name
        assert team.role == OldTeamName.from_raw(team.id).role
