"""Tests for the character-attribute layer (constants/character_data.py)."""
from dataclasses import fields

import pytest

from pyrio import Character, Tables
from pyrio.constants.character_data import (
    AttributeSpec, ATTRIBUTES, ATTRIBUTES_BY_KEY, CharacterAttributes,
    character_attributes,
)


def test_fields_match_registry():
    # The dataclass shape must not drift from the AttributeSpec registry.
    field_names = {f.name for f in fields(CharacterAttributes)}
    keys = {spec.key for spec in ATTRIBUTES}
    assert field_names == keys


def test_record_covers_and_matches_char_name_table():
    # The CSV must agree with the parity-verified id<->name authority.
    for char_id, name in Tables.CHAR_NAME.items():
        attrs = character_attributes(char_id)
        assert attrs.char_id == char_id
        assert attrs.name == name
        # resolvable by name too, to the same record
        assert character_attributes(name) is attrs


def test_lookup_by_id_and_name_are_identical():
    assert character_attributes(0) is character_attributes("Mario")


def test_unknown_character_raises():
    with pytest.raises(KeyError):
        character_attributes("Sans")
    with pytest.raises(KeyError):
        character_attributes(999)


def test_sample_attribute_values():
    mario = character_attributes("Mario")
    assert mario.char_class == "Balance"
    assert mario.is_captain is True
    assert mario.slap_hit_power == 50
    assert mario.fielding_arm == "Right"
    assert mario.captain_star_hit == "Fireball"
    assert mario.abilities == frozenset({"Sliding Catch", "Wall Jump"})

    koopa = character_attributes("Koopa(G)")
    assert koopa.char_class == "Balance"
    assert koopa.is_captain is False


def test_decoded_categoricals_are_strings_not_ints():
    mario = character_attributes("Mario")
    assert isinstance(mario.char_class, str)
    assert isinstance(mario.horizontal_hit_trajectory, str)
    assert isinstance(mario.fielding_arm, str)


def test_raw_reverses_decode():
    mario = character_attributes("Mario")
    # decoded label -> encoded int, round-tripping the AttributeSpec
    assert mario.raw("char_class") == 0           # "Balance"
    assert mario.raw("fielding_arm") == 0         # "Right"
    assert mario.raw("captain_star_hit") == 1     # "Fireball"
    # numeric attributes pass through unchanged
    assert mario.raw("slap_hit_power") == mario.slap_hit_power


def test_attribute_spec_encode_parse_round_trip():
    spec = ATTRIBUTES_BY_KEY["char_class"]
    for code, label in spec.decode.items():
        assert spec.encode(label) == code
        assert spec.parse(str(code)) == label


def test_with_superstar_caps_and_uncapped():
    mario = character_attributes("Mario")
    on = mario.with_superstar()
    # capped: charge power 64 + 50 -> clamped to 100
    assert mario.charge_hit_power == 64
    assert on.charge_hit_power == 100
    # capped exactly at the cap
    assert on.slap_hit_power == 100
    # non-boosted stat is unchanged
    assert on.weight == mario.weight

    # uncapped boosted stat exceeds 100
    diddy = character_attributes("Diddy")
    assert diddy.with_superstar().speed == diddy.speed + 50


def test_with_superstar_matches_spec_for_every_character():
    for char_id in Tables.CHAR_NAME:
        base = character_attributes(char_id)
        on = base.with_superstar()
        for spec in ATTRIBUTES:
            expected = spec.to_star_on(getattr(base, spec.key))
            assert getattr(on, spec.key) == expected
            if spec.cap is not None:
                assert getattr(on, spec.key) <= spec.cap


def test_base_character_dedups_variants():
    from pyrio import Character, BaseCharacter
    # All Pianta variants share one BaseCharacter.
    assert Character.from_raw("Pianta(R)").base == Character.from_raw("Pianta(B)").base
    assert BaseCharacter.from_raw("Pianta(R)") == BaseCharacter("Pianta")
    assert BaseCharacter.from_raw(0).name == "Mario"          # by id
    assert BaseCharacter.from_raw("DK") == BaseCharacter("DK")  # bare simplified name
    # base-level class/captain are variant-invariant
    assert Character.from_raw("Mario").base.char_class == "Balance"
    assert Character.from_raw("Mario").base.is_captain is True
    # value-to-value equality only; never equal to a raw string
    assert BaseCharacter("Pianta") != "Pianta"
    assert BaseCharacter("Pianta") in {Character.from_raw("Pianta(Y)").base}


def test_character_value_object_exposes_attributes():
    mario = Character.from_raw("mario")
    assert mario.attributes.char_class == "Balance"
    assert mario.attributes.is_captain is True
    # star-ON requires explicit conversion (a bare Character has no game context)
    assert mario.attributes.with_superstar().slap_hit_power == 100
