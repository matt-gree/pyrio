"""A charged captain star pitch.

Rio 2.3.0 logs "Charged Captain Star"; older files could not decode the value
and wrote 'Unable to Decode. Invalid Value (1).' instead. Every spelling has to
read as the same ChargeType, or a strict lookup raises on a real file.

Ported from main, rewritten against prep's value objects: ChargeType compares
by identity, not against a bare string, so these assert on .name / .id.
"""
import pytest

from pyrio.rio_value import Tables, ChargeType
from pyrio.hit_simulation import HitInputs, hit_inputs_from_event
from pyrio.stat_file import EventObj, StatObj

LABELS = ['Charged Captain Star', 'ChargedStar', 'Unable to Decode. Invalid Value (1).']

ROSTER = {f'{team} Roster {slot}': {
    'CharID': 'Mario', 'Captain': 0, 'Superstar': 0, 'Batting Hand': 'Right',
} for team in ('Away', 'Home') for slot in range(9)}


def charge_event(charge_type) -> EventObj:
    return EventObj(StatObj({'Version': '2.3.0',
                             'Events': [{'Pitch': {'Charge Type': charge_type}}]}), 0)


def simulator_inputs(charge_type) -> HitInputs:
    return hit_inputs_from_event(EventObj(StatObj({
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
    assert Tables.CHARGE_TYPE[1] == 'Charged Captain Star'


@pytest.mark.parametrize('label', LABELS)
def test_every_label_reads_the_same(label):
    assert charge_event(label).charge_type() == ChargeType.from_raw(1)


@pytest.mark.parametrize('label', LABELS)
def test_every_label_carries_the_canonical_name_and_id(label):
    charge = charge_event(label).charge_type()
    assert (charge.id, charge.name) == (1, 'Charged Captain Star')


@pytest.mark.parametrize('value, expected_id', [
    ('N/A', 0), ('Slider', 2), ('Perfect', 3), (0, 0), (1, 1), (2, 2), (3, 3),
])
def test_other_values_are_left_alone(value, expected_id):
    assert charge_event(value).charge_type().id == expected_id


def test_no_pitch_returns_none():
    assert EventObj(StatObj({'Events': [{}]}), 0).charge_type() is None


def test_an_unknown_charge_type_still_raises():
    # The correction is for one known label, not a blanket catch.
    with pytest.raises(ValueError):
        charge_event('Unable to Decode. Invalid Value (9).').charge_type()


@pytest.mark.parametrize('charge_type', LABELS + [1])
def test_simulator_reads_every_label_as_a_charged_star_pitch(charge_type):
    assert simulator_inputs(charge_type).pitch_type_val == 4


@pytest.mark.parametrize('charge_type, pitch_type_val', [('Slider', 1), ('Perfect', 2)])
def test_simulator_reads_other_charge_types(charge_type, pitch_type_val):
    assert simulator_inputs(charge_type).pitch_type_val == pitch_type_val


def test_simulator_rejects_an_unknown_charge_type():
    with pytest.raises(ValueError):
        simulator_inputs('Unable to Decode. Invalid Value (9).')
