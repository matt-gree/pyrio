"""The "Star Swing Five-Star" stat. Older files and encoded files store an int;
newer decoded files store its name, and both have to read the same.
"""
import pytest

from dataclasses import replace

from pyrio.hit_simulator.hit_simulation import (HitInputs, _is_unflagged_texas_leaguer,
                                                simulate_hit)
from pyrio.stat_file_parser import EventObj


class _Stat:
    def __init__(self, contact):
        self._events = [{'Pitch': {'Contact': contact} if contact else {}}]

    def events(self):
        return self._events


class _FiveStarEvent:
    def __init__(self, batter="King Boo", stars=5):
        self._batter = batter
        self._stars = stars

    def batter(self):
        return self._batter

    def batting_team(self):
        return 0

    def team_stars(self, team):
        return self._stars


# A failed Moonshot recorded in a real game (v2.1.1): it launched at vertical angle
# 538 with power 139 and horizontal angle 1336, from Right Nice contact.
_TEXAS_LEAGUER = HitInputs(
    batter_name="King Boo", pitcher_name="Luigi", pitch_type_val=0, pos_x=-0.168056,
    ball_x=-0.352598, ball_z=1.78056, batter_hand=1, swing=0, is_star=True, frame=4,
    input_down=True, input_left=True, batter_stars_on=True, pitcher_stars_on=True,
    five_star_attempt=True, rng1=9688, rng2=0, rng3=184,
)


def _five_star_swing(contact):
    return EventObj(_Stat(contact), 0).five_star_swing()


@pytest.mark.parametrize("value, encoded", [
    (0, 0), (1, 1), (2, 2),
    ("None", 0), ("Moonshot", 1), ("Failed Moonshot", 2),
])
def test_int_and_decoded_values_read_the_same(value, encoded):
    assert _five_star_swing({'Star Swing Five-Star': value}) == encoded


def test_no_contact_is_none():
    assert _five_star_swing(None) is None


def test_unknown_name_is_rejected():
    with pytest.raises(KeyError):
        _five_star_swing({'Star Swing Five-Star': "Moonshoot"})


def test_failed_moonshot_reproduces_the_recorded_texas_leaguer():
    result = simulate_hit(_TEXAS_LEAGUER)
    assert (result.vertical_angle, result.power, result.horizontal_angle) == (538, 139, 1336)


def test_without_the_attempt_it_is_a_regular_star_swing():
    result = simulate_hit(replace(_TEXAS_LEAGUER, five_star_attempt=False))
    assert result.vertical_angle < 500


def test_failed_attempt_by_a_captain_class_batter_is_a_regular_captain_star_hit():
    captain = replace(_TEXAS_LEAGUER, batter_name="Yoshi")
    assert simulate_hit(captain).vertical_angle == simulate_hit(
        replace(captain, five_star_attempt=False)).vertical_angle


@pytest.mark.parametrize("vert, batter, stars, expected", [
    ("500", "King Boo", 5, True),
    ("549", "King Boo", 5, True),
    ("499", "King Boo", 5, False),
    ("550", "King Boo", 5, False),
    ("525", "King Boo", 4, False),
    ("525", "Yoshi", 5, False),
])
def test_older_files_recognize_a_texas_leaguer_by_its_launch(vert, batter, stars, expected):
    event = _FiveStarEvent(batter, stars)
    assert _is_unflagged_texas_leaguer(event, {'Vert Angle': vert}) is expected
