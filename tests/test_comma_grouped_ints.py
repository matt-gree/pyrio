"""Stat files group the digits of large numbers with commas, like "10,257"."""
import pytest

from pyrio.stat_file_parser import EventObj, StatObj


def contact_event(**contact) -> EventObj:
    return EventObj(StatObj({'Events': [{'Pitch': {'Contact': contact}}]}), 0)


@pytest.mark.parametrize('value, expected', [
    ('10,257', 10257),
    ('1,234,567', 1234567),
    ('257', 257),
    ('-1,241', -1241),
    (10257, 10257),
    (None, None),
])
def test_safe_int(value, expected):
    assert contact_event().safe_int(value) == expected


@pytest.mark.parametrize('value', ['abc', '', '1.5', 1.5])
def test_safe_int_still_rejects_what_isnt_an_int(value):
    with pytest.raises(ValueError):
        contact_event().safe_int(value)


def test_rng():
    event = contact_event(RNG1='10,257', RNG2='5', RNG3='32,768')
    assert event.rng() == (10257, 5, 32768)


def test_angles():
    event = contact_event(**{'Horiz Angle': '1,241', 'Vert Angle': '3,995'})
    assert event.horiz_angle() == 1241
    assert event.vert_angle() == 3995


def test_no_contact_returns_none():
    event = contact_event()
    assert event.rng() == (None, None, None)
    assert event.horiz_angle() is None
    assert event.vert_angle() is None
