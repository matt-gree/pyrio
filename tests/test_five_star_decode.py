"""The "Star Swing Five-Star" stat. Older files and encoded files store an int;
newer decoded files store its name, and both have to read the same.
"""
import pytest

from dataclasses import replace

from pyrio.constants import game_constants as G
from pyrio.hit_simulator.hit_simulation import (HitInputs, _inputs_from_landing_row,
                                                _launched_as_texas_leaguer, simulate_hit)
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

# The same hit as a /landing_data/ row. ball_horiz_angle holds the vertical angle
# because the endpoint's angle columns are swapped.
_TEXAS_LEAGUER_ROW = {
    'batter_char_id': 37, 'pitcher_char_id': 1, 'type_of_swing': 3, 'pitch_type': 0,
    'stick_input': G.STICK_DOWN | G.STICK_LEFT, 'bat_x_contact_pos': -0.168056,
    'ball_x_contact_pos': -0.352598, 'ball_z_contact_pos': 1.78056, 'batting_hand': True,
    'frame_of_swing': 4, 'rng1': 9688.0, 'rng2': 0.0, 'rng3': 184.0,
    'ball_horiz_angle': 538, 'ball_vert_angle': 1336,
    'star_swing_five_star': 2, 'batter_team_stars': 5,
}


def _attempt_from_row(**fields):
    row = {**_TEXAS_LEAGUER_ROW, **fields}
    row = {key: value for key, value in row.items() if value is not None}
    return _inputs_from_landing_row(row, 0).five_star_attempt


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
    assert _launched_as_texas_leaguer(stars, batter, int(vert)) is expected


def test_landing_row_reproduces_the_recorded_texas_leaguer():
    row_inputs = _inputs_from_landing_row(_TEXAS_LEAGUER_ROW, 0, batter_stars_on=True,
                                          pitcher_stars_on=True)
    result = simulate_hit(row_inputs)
    assert (result.vertical_angle, result.power, result.horizontal_angle) == (538, 139, 1336)


def test_landing_row_flagged_as_an_attempt():
    assert _attempt_from_row(star_swing_five_star=1, ball_horiz_angle=300)
    assert _attempt_from_row(star_swing_five_star=2, ball_horiz_angle=300)


def test_older_landing_row_is_recognized_by_its_swapped_vertical_column():
    assert _attempt_from_row(star_swing_five_star=0)
    assert _attempt_from_row(star_swing_five_star=None)
    assert not _attempt_from_row(star_swing_five_star=0, ball_horiz_angle=300, ball_vert_angle=525)


def test_landing_row_from_the_current_endpoint_is_a_regular_star_swing():
    assert not _attempt_from_row(star_swing_five_star=None, batter_team_stars=None)


def test_only_a_star_swing_can_be_an_attempt():
    assert not _attempt_from_row(type_of_swing=2)
