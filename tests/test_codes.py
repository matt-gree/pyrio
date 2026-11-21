"""The game's coded values: groupings, legacy labels and the flag types."""

import pytest

from pyrio import (
    AtBatResult,
    Bases,
    ContactType,
    InputDirection,
    Position,
    SecondaryContactResult,
    Side,
    Stadium,
    UnknownCodeError,
    UnknownNameError,
)


@pytest.mark.parametrize(
    ("text", "stadium"),
    [
        ("bc", Stadium.BOWSER_CASTLE),
        ("toy", Stadium.TOY_FIELD),
        ("Bowser's Castle", Stadium.BOWSER_CASTLE),
        ("dk jungle", Stadium.DK_JUNGLE),
        ("Yoshi's Island", Stadium.YOSHI_PARK),
        ("PEACH GARDEN", Stadium.PEACH_GARDEN),
    ],
)
def test_stadium_parse(text: str, stadium: Stadium):
    assert Stadium.parse(text) is stadium


def test_stadium_parse_suggests_on_a_miss():
    with pytest.raises(UnknownNameError) as info:
        Stadium.parse("bowsr castle")
    assert info.value.suggestions == ("Bowser Castle",)


# --- results ----------------------------------------------------------------


def test_hits_and_their_bases():
    hits = {result: result.bases for result in AtBatResult if result.is_hit}
    assert hits == {
        AtBatResult.SINGLE: 1,
        AtBatResult.DOUBLE: 2,
        AtBatResult.TRIPLE: 3,
        AtBatResult.HOME_RUN: 4,
    }
    assert AtBatResult.OUT.bases == 0


def test_walks():
    assert {r for r in AtBatResult if r.is_walk} == {AtBatResult.WALK, AtBatResult.HIT_BY_PITCH}


def test_outs():
    # The set League Tools' wOBA script spells as ids {1, 4, 5, 6, 14, 15, 16}.
    assert {r.id for r in AtBatResult if r.is_out} == {1, 4, 5, 6, 14, 15, 16}


def test_caught_line_drive_and_caught_are_the_corrected_way_round():
    assert AtBatResult(5) is AtBatResult.CAUGHT_LINE_DRIVE
    assert AtBatResult(6) is AtBatResult.CAUGHT
    assert AtBatResult("Caught line-drive").id == 5


@pytest.mark.parametrize("cls", [AtBatResult, SecondaryContactResult])
@pytest.mark.parametrize(
    ("label", "code"),
    [("Error - Input", 0xB), ("Error - Chem", 0xC), ("Fielders Choice", 0xC)],
)
def test_older_result_labels_still_resolve(
    cls: type[AtBatResult] | type[SecondaryContactResult], label: str, code: int
):
    assert cls(label) is cls(code)


def test_contact_groupings():
    assert {c for c in ContactType if c.is_sour} == {ContactType.SOUR_LEFT, ContactType.SOUR_RIGHT}
    assert {c for c in ContactType if c.is_nice} == {ContactType.NICE_LEFT, ContactType.NICE_RIGHT}


@pytest.mark.parametrize("value", [0xFF, "Inv", "None"])
def test_position_has_no_member_for_no_position(value: object):
    with pytest.raises(UnknownCodeError):
        Position(value)


# --- flags and sides --------------------------------------------------------


def _stickvec(value: int) -> str:
    """Project Rio's C++ "StickVec" decoder, transcribed."""
    words = [w for bit, w in ((1, "Left"), (2, "Right"), (4, "Down"), (8, "Up")) if value & bit]
    return "+".join(words)


@pytest.mark.parametrize("value", range(16))
def test_input_direction_matches_the_stickvec_decoder(value: int):
    direction = InputDirection(value)
    assert direction.label == str(direction) == _stickvec(value)
    assert InputDirection(_stickvec(value)) is direction


def test_input_direction_flags():
    direction = InputDirection("Left+Up")
    assert InputDirection.UP in direction
    assert InputDirection.DOWN not in direction
    assert direction is InputDirection.LEFT | InputDirection.UP


@pytest.mark.parametrize("value", [16, -1, "Sideways", "Left+Sideways"])
def test_input_direction_rejects_anything_else(value: object):
    with pytest.raises(UnknownCodeError):
        InputDirection(value)


@pytest.mark.parametrize(
    ("bases", "text"),
    [
        (Bases(0), "---"),
        (Bases.FIRST, "1--"),
        (Bases.SECOND, "-2-"),
        (Bases.FIRST | Bases.THIRD, "1-3"),
        (Bases.FIRST | Bases.SECOND | Bases.THIRD, "123"),
    ],
)
def test_bases_str(bases: Bases, text: str):
    assert str(bases) == text


def test_side():
    assert Side.HOME.other is Side.AWAY
    assert Side.AWAY.other is Side.HOME
    assert str(Side.HOME) == "Home"
