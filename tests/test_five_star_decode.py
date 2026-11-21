"""The "Star Swing Five-Star" field, and the failed Moonshot it reports.

Ported from main. Rio 2.3.0 writes 1 for a connected Moonshot and 2 for a
failed one (a Texas Leaguer); older files wrote 0 for both a failed attempt
and a swing that never was one, so those are recognised by launch angle
instead. prep reads the field as a MoonShotStatus value object, named after
the canonical cMoonShotStatus.
"""
from dataclasses import replace

import pytest

from pyrio.constants import game_constants as G
from pyrio.hit_simulation import (HitInputs, _inputs_from_landing_row,
                                  _launched_as_texas_leaguer, simulate_hit)
from pyrio.stat_file import EventObj


class _Stat:
    """Barest StatObj stand-in: one event, with or without a contact dict."""

    def __init__(self, contact):
        self._events = [{'Pitch': {'Contact': contact} if contact else {}}]

    def events(self):
        return self._events


# A failed Moonshot recorded in a real game (Rio 2.1.1): it launched at vertical
# angle 538 with power 139 and horizontal angle 1336, from Right Nice contact.
_TEXAS_LEAGUER = HitInputs(
    batter_name="King Boo", pitcher_name="Luigi", pitch_type_val=0, pos_x=-0.168056,
    ball_x=-0.352598, ball_z=1.78056, batter_hand=1, swing=0, is_star=True, frame=4,
    input_down=True, input_left=True, batter_stars_on=True, pitcher_stars_on=True,
    five_star_attempt=True, rng1=9688, rng2=0, rng3=184,
)

# The same hit as a /landing_data/ row. ball_horiz_angle holds the VERTICAL
# angle, because the endpoint's two angle columns are swapped.
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


# ------------------------------------------------------------------ decoding

@pytest.mark.parametrize("value, encoded", [
    (0, 0), (1, 1), (2, 2),
    ("None", 0), ("Moonshot", 1), ("Failed Moonshot", 2),
])
def test_int_and_decoded_values_read_the_same(value, encoded):
    assert _five_star_swing({'Star Swing Five-Star': value}).id == encoded


def test_no_contact_is_none():
    assert _five_star_swing(None) is None


def test_unknown_name_is_rejected():
    with pytest.raises(ValueError):
        _five_star_swing({'Star Swing Five-Star': "Moonshoot"})


# ------------------------------------------------- the recorded Texas Leaguer

def test_failed_moonshot_reproduces_the_recorded_texas_leaguer():
    result = simulate_hit(_TEXAS_LEAGUER)
    assert (result.vertical_angle, result.power, result.horizontal_angle) == (538, 139, 1336)


def test_without_the_attempt_it_is_a_regular_star_swing():
    result = simulate_hit(replace(_TEXAS_LEAGUER, five_star_attempt=False))
    assert result.vertical_angle < 500


def test_failed_attempt_by_a_captain_class_batter_is_a_regular_captain_star_hit():
    # A captain never has a failed Moonshot -- theirs is an ordinary captain
    # star hit, so the flag must make no difference.
    captain = replace(_TEXAS_LEAGUER, batter_name="Yoshi")
    assert simulate_hit(captain).vertical_angle == simulate_hit(
        replace(captain, five_star_attempt=False)).vertical_angle


@pytest.mark.parametrize("vert, batter, stars, expected", [
    (500, "King Boo", 5, True),    # bottom of the forced pop-fly band
    (549, "King Boo", 5, True),    # top of it
    (499, "King Boo", 5, False),   # just under
    (550, "King Boo", 5, False),   # just over -- the band is half-open
    (525, "King Boo", 4, False),   # not enough stars to have spent five
    (525, "Yoshi", 5, False),      # captain-class: never a failed Moonshot
])
def test_older_files_recognize_a_texas_leaguer_by_its_launch(vert, batter, stars, expected):
    assert _launched_as_texas_leaguer(stars, batter, vert) is expected


# ----------------------------------------------------------- /landing_data/

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
    assert not _attempt_from_row(star_swing_five_star=0, ball_horiz_angle=300,
                                 ball_vert_angle=525)


def test_landing_row_from_the_current_endpoint_is_a_regular_star_swing():
    # No star count in the row -> the angle fallback can't run.
    assert not _attempt_from_row(star_swing_five_star=None, batter_team_stars=None)


def test_only_a_star_swing_can_be_an_attempt():
    assert not _attempt_from_row(type_of_swing=2)
