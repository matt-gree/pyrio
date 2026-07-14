import pytest

from pyrio import (
    Character, RioValue, Tables, Stadium,
    PitchType, ChargeType, SwingType, ContactType,
    FinalResult, PrimaryContactResult, SecondaryContactResult,
    OutType, StealType, PitchResult,
    Hand, Position, FielderAction, FielderBobble, ManualSelect, TeamName,
    DeadBallReason,
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
    assert Character(0, "Mario") != RioValue(0, "Mario")


def test_hash_and_set_membership_are_value_based():
    assert hash(Character(5, "Daisy")) == hash(Character(5, "Daisy"))
    assert Character(5, "Daisy") in {Character(5, "Daisy")}
    assert Character(5, "Daisy") not in {5}        # not interchangeable with int
    assert 5 not in {Character(5, "Daisy")}


def test_character_properties_variant():
    pianta = Character.from_raw(0x16)  # Pianta(R)
    assert pianta.name == "Pianta(R)"
    assert pianta.name_no_variant == "Pianta"
    assert pianta.hex == "0x16"
    # char_class / is_captain now live on the attribute record.
    assert pianta.attributes.char_class == "Power"
    assert pianta.attributes.is_captain is False


def test_character_properties_captain():
    mario = Character.from_raw("mario")
    assert mario.id == 0
    assert mario.attributes.char_class == "Balance"
    assert mario.attributes.is_captain is True


def test_lookup_character_by_id_name_and_alias():
    assert Character.from_raw(5) == Character.from_raw("Daisy")
    assert Character.from_raw("daisy").id == 5  # case-insensitive alias


def test_lookup_character_rejects_unknown():
    with pytest.raises(ValueError):
        Character.from_raw("not a character")
    with pytest.raises(ValueError):
        Character.from_raw(999)


def test_lookup_stadium_by_id_name_and_legacy():
    s = Stadium.from_raw(1)
    assert isinstance(s, Stadium)
    assert s.id == 1 and s.name == "Bowser Castle"
    assert Stadium.from_raw("Bowser Castle") == s        # by name
    assert Stadium.from_raw("Bowser's Castle") == s      # legacy name alias
    assert Stadium.from_raw("1") == s                    # digit string


def test_lookup_stadium_rejects_unknown():
    with pytest.raises(ValueError):
        Stadium.from_raw("Not A Stadium")


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

    assert Tables.INPUT_DIRECTION == {v: stickvec(v) for v in range(16)}


def test_pitch_event_type_factories():
    assert isinstance(PitchType.from_raw(0), PitchType)
    assert PitchType.from_raw(0).name == "Curve"
    assert PitchType.from_raw(0) == PitchType.from_raw("Curve")   # id == name input
    assert ChargeType.from_raw(0).name == "N/A"
    assert SwingType.from_raw(1).name == "Slap"
    assert ContactType.from_raw(255).name == "Miss"
    assert ContactType.from_raw("Perfect").id == 2


def test_value_factories_pass_through_none():
    assert PitchType.from_raw(None) is None
    assert ChargeType.from_raw(None) is None
    assert SwingType.from_raw(None) is None
    assert ContactType.from_raw(None) is None


def test_factories_tolerate_capitalization_drift():
    # Decoded client casing may drift; resolution is case-insensitive and the
    # value object always carries the canonical name.
    assert PitchType.from_raw("changeup").name == "ChangeUp"
    assert PitchType.from_raw("CURVE") == PitchType.from_raw("Curve")
    assert ContactType.from_raw("perfect").name == "Perfect"
    assert Stadium.from_raw("bowser CASTLE").name == "Bowser Castle"


def test_result_type_factories():
    assert isinstance(OutType.from_raw(1), OutType)
    assert FinalResult.from_raw(7).name == "Single"
    assert FinalResult.from_raw(7) == FinalResult.from_raw("Single")
    assert PrimaryContactResult.from_raw(1).name == "Foul"
    assert SecondaryContactResult.from_raw(7).name == "Single"
    assert OutType.from_raw(1).name == "Caught"
    assert StealType.from_raw(2).name == "Normal"
    assert PitchResult.from_raw(0).name == "HBP"
    assert FinalResult.from_raw(None) is None


def test_roster_and_fielding_factories():
    assert Hand.from_raw(0).name == "Right"
    assert Hand.from_raw(1).name == "Left"
    assert Hand.from_raw("Left").id == 1            # canonical 0=Right, 1=Left
    assert Position.from_raw(0).name == "P"
    assert Position.from_raw("RF").id == 8
    assert ManualSelect.from_raw(1).name == "Pitcher"
    assert TeamName.from_raw(2).name == "Mario Fireballs"
    assert TeamName.from_raw("Jr Fangs").id == 47
    # round-trip without hardcoding ids for the action/bobble tables
    assert isinstance(FielderAction.from_raw("Sliding"), FielderAction)
    assert FielderAction.from_raw("Sliding").name == "Sliding"
    assert isinstance(FielderBobble.from_raw("Fumble"), FielderBobble)
    assert FielderBobble.from_raw("Fumble").name == "Fumble"
    assert Hand.from_raw(None) is None
    assert isinstance(DeadBallReason.from_raw(1), DeadBallReason)
    assert DeadBallReason.from_raw(1).name == "Home Run"
    assert DeadBallReason.from_raw("Foul Ball").id == 2
    assert DeadBallReason.from_raw(None) is None
