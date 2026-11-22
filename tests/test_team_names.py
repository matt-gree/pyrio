"""Team names: the logo table, CAPTAIN_TEAMS, and naming a team from its roster."""

from collections import Counter

import pytest

from pyrio import (
    CAPTAIN_TEAMS,
    Character,
    CharacterFamily,
    TeamName,
    UnknownNameError,
    team_name,
)


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


# --- team_name and CAPTAIN_TEAMS ---------------------------------------------


def _roster(*characters: Character | None, fill: Character) -> list[Character | None]:
    return [*characters] + [fill] * (9 - len(characters))


def test_signature_team():
    roster = _roster(
        Character.LUIGI,
        Character.MONTY,
        Character.PIANTA_R,
        Character.NOKI_B,
        fill=Character.MARIO,
    )
    assert team_name(roster, Character.MARIO) is TeamName.MARIO_SUNSHINES


def test_any_variant_counts_for_a_signature():
    roster = _roster(
        Character.BOWSER,
        Character.TOAD_P,
        Character.BOO,
        Character.KING_BOO,
        fill=Character.LUIGI,
    )
    assert team_name(roster, Character.LUIGI) is TeamName.LUIGI_MANSIONEERS


def test_class_team_when_captain_class_is_the_plurality():
    # Daisy is Balance, like Mario.
    assert team_name([Character.DAISY] * 9, Character.MARIO) is TeamName.MARIO_FIREBALLS


def test_default_otherwise():
    # Wario is Power; Mario is Balance.
    assert team_name([Character.WARIO] * 9, Character.MARIO) is TeamName.MARIO_HEROES


def test_a_tied_plurality_is_not_the_class_team():
    balance = (Character.MARIO, Character.LUIGI, Character.DAISY, Character.BIRDO)
    power = (Character.DK, Character.WARIO, Character.BOWSER, Character.BOWSER_JR)
    roster = [*balance, *power, Character.DIDDY]
    assert team_name(roster, Character.MARIO) is TeamName.MARIO_HEROES


def test_signature_beats_class_team():
    # Peach, Yoshi, DK and Bowser would otherwise leave no Balance plurality, so
    # pad with Balance characters to show the signature still wins.
    roster = _roster(
        Character.PEACH,
        Character.YOSHI,
        Character.DK,
        Character.BOWSER,
        fill=Character.MARIO,
    )
    assert team_name(roster, Character.MARIO) is TeamName.MARIO_ALL_STARS


def test_three_family_signature():
    roster = _roster(
        Character.BOWSER_JR,
        Character.DRY_BONES_R,
        Character.BRO_F,
        fill=Character.BOWSER,
    )
    assert team_name(roster, Character.BOWSER) is TeamName.BOWSER_MONSTERS


def test_repeats_of_one_member_do_not_make_a_signature():
    # Nine Warios are not the Waluigi Flankers: a signature needs every family.
    assert team_name([Character.WARIO] * 9, Character.WALUIGI) is TeamName.WALUIGI_MYSTIQUES


def test_non_captain_has_no_team_name():
    assert team_name([Character.MARIO] * 9, Character.TOAD_R) is None


def test_incomplete_team_has_no_name_yet():
    assert team_name(_roster(Character.MARIO, None, fill=Character.LUIGI), Character.MARIO) is None
    assert team_name([Character.MARIO] * 9, None) is None


def test_roster_must_have_nine_slots():
    with pytest.raises(ValueError, match="9 slots"):
        team_name([], Character.MARIO)
    with pytest.raises(ValueError, match="9 slots"):
        team_name([Character.MARIO] * 8, Character.MARIO)
    with pytest.raises(ValueError, match="9 slots"):
        team_name([None] * 10, None)


def test_names_people_type_resolve_before_team_name():
    # team_name takes Characters; Character.parse is the door for human input.
    roster = [Character.parse(name) for name in ["donkey kong"] * 9]
    assert team_name(roster, Character.parse("donkey kong")) is TeamName.DK_WILD_ONES
    with pytest.raises(UnknownNameError):
        Character.parse("Not A Character")


def test_captain_teams_use_every_logo_once():
    logos = [
        team
        for teams in CAPTAIN_TEAMS.values()
        for team in (teams.default, teams.class_team, *(s.team for s in teams.signatures))
    ]
    assert sorted(logos) == list(TeamName)


def test_captain_teams_are_keyed_by_every_captain():
    assert set(CAPTAIN_TEAMS) == {c for c in Character if c.is_captain}


def test_captain_teams_agree_with_the_logo_table():
    for captain, teams in CAPTAIN_TEAMS.items():
        assert (teams.default.captain, teams.default.role) == (captain, "default")
        assert (teams.class_team.captain, teams.class_team.role) == (captain, "class_team")
        for signature in teams.signatures:
            assert (signature.team.captain, signature.team.role) == (captain, "signature")
            assert all(isinstance(m, CharacterFamily) for m in signature.members)


def test_captain_teams_are_read_only():
    with pytest.raises(TypeError):
        CAPTAIN_TEAMS[Character.MARIO] = CAPTAIN_TEAMS[Character.LUIGI]  # type: ignore[index]
    with pytest.raises(AttributeError):
        CAPTAIN_TEAMS[Character.MARIO].default = TeamName.LUIGI_GENTLEMEN  # type: ignore[misc]
