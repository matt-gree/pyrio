"""Tests for team_name_algo.team_name (value-object backed)."""
import pytest

from pyrio.rio_value import Tables, TeamName, BaseCharacter
from pyrio.team_name_algo import team_name, in_game_team_names_list, CAPTAIN_TEAMS


def test_signature_roster():
    # All of a signature team's characters present -> that named team.
    roster = ["Luigi", "Monty", "Pianta(R)", "Noki(B)", "Mario", "Mario", "Mario", "Mario", "Mario"]
    assert team_name(roster, "Mario") == TeamName.from_raw("Mario Sunshines")


def test_captain_class_plurality():
    # No signature match; captain's class is the strict plurality.
    assert str(team_name(["Daisy"] * 9, "Mario")) == "Mario Fireballs"


def test_fallback_default():
    # No signature, captain class not the plurality -> default.
    assert str(team_name(["Wario"] * 9, "Mario")) == "Mario Heroes"


def test_returns_team_name_value_object():
    out = team_name(["Daisy"] * 9, "Mario")
    assert isinstance(out, TeamName)


def test_non_captain_returns_none():
    assert team_name(["Mario"] * 9, "Toad") is None


def test_incomplete_roster_returns_none():
    assert team_name(["Mario", ""] + ["Luigi"] * 7, "Mario") is None


def test_captain_accepts_aliases_and_variants():
    # Captain is resolved to its canonical Character, so aliases work (the old
    # implementation indexed by raw string and would KeyError on an alias).
    assert team_name(["DK"] * 9, "donkey kong") == TeamName.from_raw("DK Wild Ones")


def test_result_is_always_a_known_logo():
    out = team_name(["Bowser"] * 9, "Bowser")
    assert out in in_game_team_names_list


def test_captain_teams_cover_logo_table_exactly():
    # CAPTAIN_TEAMS must cover exactly the canonical logo names (no drift/dupes).
    names = set()
    for teams in CAPTAIN_TEAMS.values():
        names.add(str(teams.default))
        names.add(str(teams.class_team))
        names.update(str(name) for name, _ in teams.signatures)
    assert names == set(Tables.TEAM_NAME.values())


def test_signature_members_are_base_characters():
    # Signatures hold BaseCharacter value objects, each a valid simplified name
    # (this guards the 'Donkey Kong'/'Dixie Kong'/'Bry Bones' class of bug).
    valid = set(Tables.SIMPLIFIED_NAME.values())
    for cap, teams in CAPTAIN_TEAMS.items():
        for name, signature in teams.signatures:
            for member in signature:
                assert isinstance(member, BaseCharacter)
                assert str(member) in valid, f"{cap}/{name}: {member!r}"


def test_fixed_signature_triggers():
    # 'Mario All Stars' uses DK (was the unmatchable 'Donkey Kong').
    roster = ["Peach", "Yoshi", "DK", "Bowser", "Mario", "Mario", "Mario", "Mario", "Mario"]
    assert team_name(roster, "Mario") == TeamName.from_raw("Mario All Stars")


def test_three_character_signature_triggers():
    # 'Bowser Monsters' needs only its three characters present.
    roster = ["Bowser Jr", "Dry Bones(R)", "Bro(F)"] + ["Bowser"] * 6
    assert team_name(roster, "Bowser") == TeamName.from_raw("Bowser Monsters")
