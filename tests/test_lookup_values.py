import pytest

from pyrio import Character, LookupValue, Lookup, Stadium


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
