"""Project Rio before 2.3.0 logged some contact results wrongly, and decoded files
keep what they were written with: a force out as 'Out-tag', a tag out as 'Foul',
and a foul that landed before the game called it foul as 'Fair' / 'Out-caught'.
Those read the same as a 2.3.0 file. A hit logged as 'Fair' stays that way, since the
file doesn't say whether it was fielded first.
"""
import pytest

from pyrio.stat_file_parser import EventObj, StatObj, UNFINISHED_PLAY_NUM_OUTS


AT_BAT = {'Inning': 1, 'Half Inning': 0, 'Batter Roster Loc': 3, 'Outs': 1, 'Balls': 1}


def event_with(result: str, primary: str, secondary: str, batter_out: str = 'None',
               version: str = '2.2.0', num_outs: int = 0, strikes: int = 1,
               next_event: dict = None) -> EventObj:
    events = [{
        **AT_BAT,
        'Strikes': strikes,
        'Result of AB': result,
        'Num Outs During Play': num_outs,
        'Runner Batter': {'Out Type': batter_out},
        'Pitch': {'Contact': {
            'Contact Result - Primary': primary,
            'Contact Result - Secondary': secondary,
        }},
    }]
    if next_event is not None:
        events.append(next_event)
    return EventObj(StatObj({'Version': version, 'Events': events}), 0)


def test_old_force_out():
    assert event_with('Out', 'Fair', 'Out-tag', 'Force').contact_result_secondary() == 'Out-force'


def test_old_tag_out():
    assert event_with('Out', 'Fair', 'Foul', 'Tag').contact_result_secondary() == 'Out-tag'


def test_old_force_out_with_no_result():
    event = event_with('None', 'Fair', 'Out-tag', 'Force', next_event={**AT_BAT, 'Batter Roster Loc': 4})
    assert event.contact_result_primary() == 'Fair'
    assert event.contact_result_secondary() == 'Out-force'


def test_old_tag_out_with_no_result():
    event = event_with('None', 'Fair', 'Foul', 'Tag', next_event={**AT_BAT, 'Batter Roster Loc': 4})
    assert event.contact_result_primary() == 'Fair'
    assert event.contact_result_secondary() == 'Out-tag'


def test_old_sac_fly_was_caught():
    event = event_with('SacFly', 'Fair', 'SacFly', 'Caught')
    assert event.contact_result_primary() == 'Out'
    assert event.contact_result_secondary() == 'SacFly'


@pytest.mark.parametrize('result', ['Single', 'Double', 'Triple', 'HR', 'Error', 'Fielders Choice',
                                    'Bunt', 'Ground ball double Play'])
def test_old_hit_stays_as_logged(result):
    assert event_with(result, 'Fair', result).contact_result_primary() == 'Fair'


def test_old_batter_safe_runner_out_is_left_alone():
    event = event_with('Out', 'Fair', 'Batter safe, runner out')
    assert event.contact_result_secondary() == 'Batter safe, runner out'


@pytest.mark.parametrize('primary', ['Fair', 'Fielded'])
@pytest.mark.parametrize('strikes, next_strikes', [(0, 1), (1, 2), (2, 2)])
def test_old_foul_that_landed_first(primary, strikes, next_strikes):
    event = event_with('None', primary, 'Out-caught', strikes=strikes,
                       next_event={**AT_BAT, 'Strikes': next_strikes})
    assert event.contact_result_primary() == 'Foul'
    assert event.contact_result_secondary() == 'Foul'


def test_old_foul_bunt_strikeout_needs_no_next_event():
    event = event_with('Strikeout', 'Fair', 'Out-caught', 'Strike-out', strikes=2)
    assert event.contact_result_primary() == 'Foul'
    assert event.contact_result_secondary() == 'Foul'


@pytest.mark.parametrize('next_event', [
    {**AT_BAT, 'Batter Roster Loc': 4, 'Strikes': 2},
    {**AT_BAT, 'Outs': 2, 'Strikes': 2},
    {**AT_BAT, 'Balls': 2, 'Strikes': 2},
    {**AT_BAT, 'Strikes': 1},
    None,
])
def test_old_no_result_that_doesnt_continue_the_at_bat_is_not_a_foul(next_event):
    event = event_with('None', 'Fair', 'Out-caught', next_event=next_event)
    assert event.contact_result_primary() == 'Fair'
    assert event.contact_result_secondary() == 'Out-caught'


def test_old_no_result_with_a_batter_out_is_not_a_foul():
    event = event_with('None', 'Fair', 'Out-tag', 'Force', next_event={**AT_BAT, 'Strikes': 2})
    assert event.contact_result_primary() == 'Fair'


def test_old_real_catch_is_left_alone():
    event = event_with('Caught', 'Out', 'Out-caught', 'Caught')
    assert event.contact_result_primary() == 'Out'
    assert event.contact_result_secondary() == 'Out-caught'


def test_old_error_label_is_renamed():
    assert event_with('Error - Chem', 'Fair', 'Error - Chem').contact_result_secondary() == 'Fielders Choice'


def test_unfinished_play_is_not_called_a_foul():
    event = event_with('None', 'Fair', 'Out-caught', num_outs=UNFINISHED_PLAY_NUM_OUTS)
    assert event.contact_result_primary() == 'Fair'
    assert event.contact_result_secondary() == 'Out-caught'


@pytest.mark.parametrize('result, primary, secondary, batter_out', [
    ('Out', 'Fair', 'Out-tag', 'Tag'),
    ('Out', 'Fair', 'Out-force', 'Force'),
    ('None', 'Foul', 'Foul', 'None'),
    ('None', 'Fair', 'None', 'None'),
    ('None', 'Fair', 'Out-tag', 'Tag'),
    ('SacFly', 'Out', 'SacFly', 'Caught'),
    ('SacFly', 'Fair', 'SacFly', 'Caught'),
    ('Single', 'Fielded', 'Single', 'None'),
])
def test_current_files_are_left_alone(result, primary, secondary, batter_out):
    event = event_with(result, primary, secondary, batter_out, version='2.3.0')
    assert event.contact_result_primary() == primary
    assert event.contact_result_secondary() == secondary


def test_no_contact_returns_none():
    event = EventObj(StatObj({'Version': '2.2.0', 'Events': [{
        'Result of AB': 'None', 'Num Outs During Play': 0, 'Pitch': {},
    }]}), 0)
    assert event.contact_result_primary() is None
    assert event.contact_result_secondary() is None
