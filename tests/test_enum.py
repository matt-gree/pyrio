"""CodeEnum: how every coded value looks up, compares and converts."""

import pickle

import pytest

import pyrio
from pyrio import AtBatResult, CodeEnum, FielderBobble, Hand, RioError, Stadium, UnknownCodeError
from pyrio._enum import _index


def _subclasses(cls: type) -> list[type]:
    return [s for sub in cls.__subclasses__() for s in (sub, *_subclasses(sub))]


CODE_ENUMS = sorted(
    (cls for cls in _subclasses(CodeEnum) if cls.__name__ in pyrio.__all__),
    key=lambda cls: cls.__name__,
)


def test_finds_the_code_enums():
    assert len(CODE_ENUMS) > 20


def test_looks_up_by_id_digit_string_label_and_alias():
    assert Stadium(1) is Stadium.BOWSER_CASTLE
    assert Stadium("1") is Stadium.BOWSER_CASTLE
    assert Stadium("Bowser Castle") is Stadium.BOWSER_CASTLE
    assert Stadium("Bowser's Castle") is Stadium.BOWSER_CASTLE


def test_labels_ignore_case():
    assert Stadium("bowser castle") is Stadium.BOWSER_CASTLE
    assert Stadium("BOWSER'S CASTLE") is Stadium.BOWSER_CASTLE


def test_an_alias_id_means_the_same_member():
    assert FielderBobble(0xFF) is FielderBobble.NONE
    assert FielderBobble("255") is FielderBobble.NONE


@pytest.mark.parametrize("value", [99, "99", "Bowser  Castle", "bc", " 1", "", None])
def test_strict_lookup_rejects_anything_else(value: object):
    with pytest.raises(UnknownCodeError) as info:
        Stadium(value)
    assert info.value.kind is Stadium
    assert info.value.value == value


def test_unknown_code_error_is_a_value_error_and_a_rio_error():
    assert issubclass(UnknownCodeError, ValueError)
    assert issubclass(UnknownCodeError, RioError)


def test_never_equal_to_a_raw_id_or_label():
    assert Hand.LEFT != 1
    assert Hand.LEFT != "Left"
    assert Hand.LEFT.id == 1
    assert Hand.LEFT.label == "Left"


def test_explicit_conversions():
    assert int(Stadium.TOY_FIELD) == 6
    assert str(Stadium.TOY_FIELD) == "Toy Field"
    assert f"{Stadium.TOY_FIELD}" == "Toy Field"


def test_sorts_by_id_within_a_type():
    assert sorted([AtBatResult.HOME_RUN, AtBatResult.NONE, AtBatResult.SINGLE]) == [
        AtBatResult.NONE,
        AtBatResult.SINGLE,
        AtBatResult.HOME_RUN,
    ]
    assert AtBatResult.NONE < AtBatResult.SINGLE <= AtBatResult.SINGLE


def test_does_not_compare_across_types():
    with pytest.raises(TypeError):
        _ = Hand.LEFT < Stadium.TOY_FIELD


def test_pickles_to_the_same_member():
    assert pickle.loads(pickle.dumps(Stadium.TOY_FIELD)) is Stadium.TOY_FIELD


@pytest.mark.parametrize("cls", CODE_ENUMS, ids=lambda cls: cls.__name__)
def test_every_id_and_label_names_one_member(cls: type[CodeEnum]):
    # Enum would silently make a second member with a taken id an alias.
    assert len(cls.__members__) == len(cls), "two members share an id"
    _index(cls)  # raises if two members share a label, alias or alias id
    for member in cls:
        assert cls(member.id) is member
        assert cls(member.label) is member
        assert cls(member.label.upper()) is member
