import pytest

from pyrio import (
    Character, LookupValue, Lookup, Stadium, LookupDicts,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
)


def test_value_to_value_equality_only():
    c = Character(0, "Mario")
    assert c == Character(0, "Mario")     # same type + id
    assert c != Character(1, "Luigi")
    assert c != 0                         # never equal to a raw int
    assert c != "Mario"                   # never equal to a raw str
    assert c != True


def test_explicit_conversions():
    c = Character(0, "Mario")
    assert int(c) == 0
    assert str(c) == "Mario"
    assert f"{c}" == "Mario"
    assert c.id == 0 and c.name == "Mario"
    assert repr(c) == "Character(0, 'Mario')"


def test_cross_type_inequality():
    # same id, different value-object type -> not equal
    assert Character(0, "Mario") != LookupValue(0, "Mario")


def test_hash_and_set_membership_are_value_based():
    assert hash(Character(5, "Daisy")) == hash(Character(5, "Daisy"))
    assert Character(5, "Daisy") in {Character(5, "Daisy")}
    assert Character(5, "Daisy") not in {5}        # not interchangeable with int
    assert 5 not in {Character(5, "Daisy")}


def test_character_properties_variant():
    pianta = Lookup.character(0x16)  # Pianta(R)
    assert pianta.name == "Pianta(R)"
    assert pianta.name_no_variant == "Pianta"
    assert pianta.hex == "0x16"
    assert pianta.char_class == "Power"
    assert pianta.is_captain is False


def test_character_properties_captain():
    mario = Lookup.character("mario")
    assert mario.id == 0
    assert mario.char_class == "Balance"
    assert mario.is_captain is True


def test_lookup_character_by_id_name_and_alias():
    assert Lookup.character(5) == Lookup.character("Daisy")
    assert Lookup.character("daisy").id == 5  # case-insensitive alias


def test_lookup_character_rejects_unknown():
    with pytest.raises(ValueError):
        Lookup.character("not a character")
    with pytest.raises(ValueError):
        Lookup.character(999)


def test_lookup_stadium_by_id_name_and_legacy():
    s = Lookup.stadium(1)
    assert isinstance(s, Stadium)
    assert s.id == 1 and s.name == "Bowser Castle"
    assert Lookup.stadium("Bowser Castle") == s        # by name
    assert Lookup.stadium("Bowser's Castle") == s      # legacy name alias
    assert Lookup.stadium("1") == s                    # digit string


def test_lookup_stadium_rejects_unknown():
    with pytest.raises(ValueError):
        Lookup.stadium("Not A Stadium")


def test_input_direction_matches_stickvec_bitmask():
    # Canonical "StickVec" decoder: 0x1 Left, 0x2 Right, 0x4 Down, 0x8 Up, '+'-joined.
    def stickvec(value):
        parts = []
        if value & 0x1:
            parts.append("Left")
        if value & 0x2:
            parts.append("Right")
        if value & 0x4:
            parts.append("Down")
        if value & 0x8:
            parts.append("Up")
        return "+".join(parts)

    assert LookupDicts.INPUT_DIRECTION == {v: stickvec(v) for v in range(16)}


def test_pitch_event_type_factories():
    assert isinstance(Lookup.pitch_type(0), PitchType)
    assert Lookup.pitch_type(0).name == "Curve"
    assert Lookup.pitch_type(0) == Lookup.pitch_type("Curve")   # id == name input
    assert Lookup.charge_type(0).name == "N/A"
    assert Lookup.swing_type(1).name == "Slap"
    assert Lookup.contact_type(255).name == "Miss"
    assert Lookup.contact_type("Perfect").id == 2


def test_value_factories_pass_through_none():
    assert Lookup.pitch_type(None) is None
    assert Lookup.charge_type(None) is None
    assert Lookup.swing_type(None) is None
    assert Lookup.contact_type(None) is None


def test_factories_tolerate_capitalization_drift():
    # Decoded client casing may drift; resolution is case-insensitive and the
    # value object always carries the canonical name.
    assert Lookup.pitch_type("changeup").name == "ChangeUp"
    assert Lookup.pitch_type("CURVE") == Lookup.pitch_type("Curve")
    assert Lookup.contact_type("perfect").name == "Perfect"
    assert Lookup.stadium("bowser CASTLE").name == "Bowser Castle"


def test_result_type_factories():
    assert isinstance(Lookup.out_type(1), OutType)
    assert Lookup.final_result(7).name == "Single"
    assert Lookup.final_result(7) == Lookup.final_result("Single")
    assert Lookup.primary_contact_result(1).name == "Foul"
    assert Lookup.secondary_contact_result(7).name == "Single"
    assert Lookup.out_type(1).name == "Caught"
    assert Lookup.steal_type(2).name == "Normal"
    assert Lookup.pitch_result(0).name == "HBP"
    assert Lookup.final_result(None) is None


def test_roster_and_fielding_factories():
    assert Lookup.hand(0).name == "Right"
    assert Lookup.hand(1).name == "Left"
    assert Lookup.hand("Left").id == 1            # canonical 0=Right, 1=Left
    assert Lookup.position(0).name == "P"
    assert Lookup.position("RF").id == 8
    assert Lookup.manual_select(1).name == "Pitcher"
    assert Lookup.team_name(2).name == "Mario Fireballs"
    assert Lookup.team_name("Jr Fangs").id == 47
    # round-trip without hardcoding ids for the action/bobble tables
    assert isinstance(Lookup.fielder_action("Sliding"), FielderAction)
    assert Lookup.fielder_action("Sliding").name == "Sliding"
    assert isinstance(Lookup.fielder_bobble("Fumble"), FielderBobble)
    assert Lookup.fielder_bobble("Fumble").name == "Fumble"
    assert Lookup.hand(None) is None
