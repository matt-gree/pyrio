"""Tests for team_name_algo.team_name (value-object backed)."""
import pytest

from pyrio.rio_value import Tables, Character, TeamName, BaseCharacter
from pyrio.team_name_algo import team_name, IN_GAME_TEAM_NAMES, CAPTAIN_TEAMS


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
    # '' and None both mean a not-yet-filled slot, for roster and captain alike.
    assert team_name(["Mario", ""] + ["Luigi"] * 7, "Mario") is None
    assert team_name(["Mario", None] + ["Luigi"] * 7, "Mario") is None
    assert team_name(["Mario"] * 9, "") is None
    assert team_name(["Mario"] * 9, None) is None


def test_wrong_roster_length_raises():
    with pytest.raises(ValueError):
        team_name([], "Mario")
    with pytest.raises(ValueError):
        team_name(["Mario"] * 8, "Mario")


def test_unresolvable_slot_raises():
    with pytest.raises(ValueError):
        team_name(["Not A Character"] + ["Mario"] * 8, "Mario")
    with pytest.raises(ValueError):
        team_name([999] + ["Mario"] * 8, "Mario")


def test_accepts_ids_and_character_objects():
    # Slots and captain accept ids and already-resolved Characters, not just names.
    assert str(team_name([5] * 9, 0)) == "Mario Fireballs"
    mario = Character.from_raw("Mario")
    assert str(team_name([mario] * 9, mario)) == "Mario Fireballs"


def test_captain_accepts_aliases_and_variants():
    # Captain is resolved to its canonical Character, so aliases work (the old
    # implementation indexed by raw string and would KeyError on an alias).
    assert team_name(["DK"] * 9, "donkey kong") == TeamName.from_raw("DK Wild Ones")


def test_result_is_always_a_known_logo():
    out = team_name(["Bowser"] * 9, "Bowser")
    assert out in IN_GAME_TEAM_NAMES


def test_captain_teams_cover_logo_table_exactly():
    # CAPTAIN_TEAMS must cover exactly the canonical logo names (no drift/dupes).
    names = set()
    for teams in CAPTAIN_TEAMS.values():
        names.add(str(teams.default))
        names.add(str(teams.class_team))
        names.update(str(sig.team) for sig in teams.signatures)
    assert names == set(Tables.TEAM_NAME.values())


def test_captain_teams_keys_match_is_captain_attribute():
    # CAPTAIN_TEAMS and the is_captain attribute are two sources of truth for
    # 'who is a captain'; this pins them together so drift fails loudly.
    captains = {Character.from_raw(cid) for cid in Tables.CHAR_NAME
                if Character.from_raw(cid).attributes.is_captain}
    assert set(CAPTAIN_TEAMS) == captains


def test_captain_teams_match_logo_id_structure():
    # The logo table encodes captain (id // 4) and role (id % 4) structurally;
    # every CAPTAIN_TEAMS entry must agree with TeamName.captain / TeamName.role.
    for cap, teams in CAPTAIN_TEAMS.items():
        assert teams.default.captain == cap and teams.default.role == "default"
        assert teams.class_team.captain == cap and teams.class_team.role == "class_team"
        for sig in teams.signatures:
            assert sig.team.captain == cap and sig.team.role == "signature"


def test_signature_members_are_base_characters():
    # Signatures hold BaseCharacter value objects, each a valid simplified name
    # (this guards the 'Donkey Kong'/'Dixie Kong'/'Bry Bones' class of bug).
    valid = set(Tables.SIMPLIFIED_NAME.values())
    for cap, teams in CAPTAIN_TEAMS.items():
        for sig in teams.signatures:
            for member in sig.members:
                assert isinstance(member, BaseCharacter)
                assert str(member) in valid, f"{cap}/{sig.team}: {member!r}"


def test_duplicates_of_one_member_do_not_fake_a_signature():
    # A signature needs all its distinct characters: nine Warios are not the
    # 'Waluigi Flankers' (the old summed-occurrence counting said they were).
    assert str(team_name(["Wario"] * 9, "Waluigi")) == "Waluigi Mystiques"


def test_fixed_signature_triggers():
    # 'Mario All Stars' uses DK (was the unmatchable 'Donkey Kong').
    roster = ["Peach", "Yoshi", "DK", "Bowser", "Mario", "Mario", "Mario", "Mario", "Mario"]
    assert team_name(roster, "Mario") == TeamName.from_raw("Mario All Stars")


def test_three_character_signature_triggers():
    # 'Bowser Monsters' needs only its three characters present.
    roster = ["Bowser Jr", "Dry Bones(R)", "Bro(F)"] + ["Bowser"] * 6
    assert team_name(roster, "Bowser") == TeamName.from_raw("Bowser Monsters")
