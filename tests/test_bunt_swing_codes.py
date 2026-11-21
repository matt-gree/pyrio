"""Bunts are logged as swing 0 ("None" with contact) before Project Rio 2.3.0
and as swing 4 ("Bunt") from then on. Both have to reach the simulator as a
bunt, or every bunt in a 2.3.0 stat file raises as an unsupported swing.

Ported from main. prep's engine always had bunt support; it was the two input
builders that refused them, which is what these pin.
"""
import pytest

from pyrio.constants import game_constants as G
from pyrio.constants import hit_sim_tables as T
from pyrio.hit_simulation import _inputs_from_landing_row

_ROW = {
    'batter_char_id': 37, 'pitcher_char_id': 1, 'pitch_type': 0,
    'stick_input': G.STICK_DOWN | G.STICK_LEFT, 'bat_x_contact_pos': -0.168056,
    'ball_x_contact_pos': -0.352598, 'ball_z_contact_pos': 1.78056, 'batting_hand': True,
    'frame_of_swing': 4, 'rng1': 9688.0, 'rng2': 0.0, 'rng3': 184.0,
    'ball_horiz_angle': 538, 'ball_vert_angle': 1336,
}


@pytest.mark.parametrize('swing_code', [0, 4])
def test_both_bunt_codes_are_bunts(swing_code):
    assert _inputs_from_landing_row({**_ROW, 'type_of_swing': swing_code}, 0).swing == T.Bunt


@pytest.mark.parametrize('swing_code', [1, 2, 3])
def test_other_swings_are_not_bunts(swing_code):
    assert _inputs_from_landing_row({**_ROW, 'type_of_swing': swing_code}, 0).swing != T.Bunt


def test_unknown_swing_is_rejected():
    with pytest.raises(ValueError):
        _inputs_from_landing_row({**_ROW, 'type_of_swing': 5}, 0)


def test_a_bunt_actually_simulates():
    """Not just classified as a bunt -- it has to run through the bunt branches
    of the angle and power stages without raising."""
    from pyrio.hit_simulation import simulate_hit
    result = simulate_hit(_inputs_from_landing_row({**_ROW, 'type_of_swing': 4}, 0))
    assert result.power > 0
    lower, upper = T.BuntHitPowerRanges[result.contact_type][0], \
        T.BuntHitPowerRanges[result.contact_type][1]
    assert lower <= result.power <= upper
