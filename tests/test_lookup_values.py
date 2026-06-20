import pytest

from pyrio import Character, LookupValue, Lookup


def test_lookupvalue_behaves_like_id_and_name():
    c = Character(0, "Mario")
    assert int(c) == 0
    assert str(c) == "Mario"
    assert c == 0                       # equals its int id
    assert c == Character(0, "Mario")   # equals same type + id
    assert c != Character(1, "Luigi")
    assert c != True                    # bool is not treated as id
    assert ["a", "b", "c"][Character(2, "DK")] == "c"  # __index__
    assert repr(c) == "Character(0, 'Mario')"


def test_cross_type_inequality():
    # same id, different value-object type -> not equal
    assert Character(0, "Mario") != LookupValue(0, "Mario")


def test_hash_consistent_with_int():
    assert hash(Character(5, "Daisy")) == hash(5)
    assert Character(5, "Daisy") in {5}
    assert 5 in {Character(5, "Daisy")}


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
    assert int(Lookup.character("daisy")) == 5  # case-insensitive alias


def test_lookup_character_rejects_unknown():
    with pytest.raises(ValueError):
        Lookup.character("not a character")
    with pytest.raises(ValueError):
        Lookup.character(999)
