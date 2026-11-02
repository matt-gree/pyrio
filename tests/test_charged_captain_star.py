"""A charged captain star pitch. Rio 2.3.0 logs "Charged Captain Star" and older files
logged an undecodable value, so every label has to read the same.
"""
import pytest

from pyrio.hit_simulator.hit_simulation import HitInputs, _inputs_from_event
from pyrio.lookup import LookupDicts
from pyrio.stat_file_parser import EventObj, EventSearch, StatObj


LABELS = ['Charged Captain Star', 'ChargedStar', 'Unable to Decode. Invalid Value (1).']

ROSTER = {f'{team} Roster {slot}': {
    'CharID': 'Mario', 'Captain': 0, 'Superstar': 0, 'Batting Hand': 'Right',
} for team in ('Away', 'Home') for slot in range(9)}


def charge_event(charge_type) -> EventObj:
    return EventObj(StatObj({'Version': '2.3.0', 'Events': [{'Pitch': {'Charge Type': charge_type}}]}), 0)


def simulator_inputs(charge_type) -> HitInputs:
    return _inputs_from_event(EventObj(StatObj({
        'Version': '2.3.0',
        'StadiumID': 'Mario Stadium',
        'Character Game Stats': ROSTER,
        'Events': [{
            'Half Inning': 0, 'Batter Roster Loc': 0, 'Pitcher Roster Loc': 0,
            'Away Stars': 0, 'Home Stars': 0, 'Chemistry Links on Base': 0,
            'Pitch': {
                'Pitch Type': 'Charge', 'Charge Type': charge_type, 'Type of Swing': 'Slap',
                'Bat Contact Pos - X': 0.0, 'Ball Position - Strikezone': 0.0,
                'Contact': {'Vert Angle': '0', 'Frame of Swing Upon Contact': 4,
                            'Star Swing Five-Star': 'None', 'RNG1': '0', 'RNG2': '0', 'RNG3': '0',
                            'Input Direction - Stick': 'None', 'Ball Contact Pos - X': 0.0,
                            'Ball Contact Pos - Z': 0.0},
            },
        }],
    }), 0))


def test_lookup_matches_the_emulator():
    assert LookupDicts.CHARGE_TYPE[1] == 'Charged Captain Star'


@pytest.mark.parametrize('label', LABELS)
def test_every_label_reads_the_same(label):
    assert charge_event(label).charge_type() == 'Charged Captain Star'


@pytest.mark.parametrize('value', ['N/A', 'Slider', 'Perfect', 0, 1, 2, 3])
def test_other_values_are_left_alone(value):
    assert charge_event(value).charge_type() == value


def test_no_pitch_returns_none():
    assert EventObj(StatObj({'Events': [{}]}), 0).charge_type() is None


@pytest.mark.parametrize('charge_type', LABELS + [1])
def test_simulator_reads_every_label_as_a_charged_star_pitch(charge_type):
    assert simulator_inputs(charge_type).pitch_type_val == 4


@pytest.mark.parametrize('charge_type, pitch_type_val', [('Slider', 1), ('Perfect', 2)])
def test_simulator_reads_other_charge_types(charge_type, pitch_type_val):
    assert simulator_inputs(charge_type).pitch_type_val == pitch_type_val


def test_simulator_rejects_an_unknown_charge_type():
    with pytest.raises(ValueError):
        simulator_inputs('Unable to Decode. Invalid Value (9).')
