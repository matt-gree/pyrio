"""Old stat files that the simulator can't reproduce have to be skipped, not crash the
whole game: bunts before Project Rio 1.9.6, contacts without a bat position, and error
results with labels that left LookupDicts in 2.3.0.
"""
import pytest

from pyrio.hit_simulator.hit_sim_validation import _is_natural_landing
from pyrio.hit_simulator.hit_simulation import _inputs_from_event
from pyrio.stat_file_parser import EventObj, StatObj


def contact_event(version: str, swing: str, bat_pos=0.5) -> EventObj:
    pitch = {'Type of Swing': swing, 'Contact': {'Contact Result - Primary': 'Fair'}}
    if bat_pos is not None:
        pitch['Bat Contact Pos - X'] = bat_pos
    return EventObj(StatObj({'Version': version, 'Events': [{'Pitch': pitch}]}), 0)


@pytest.mark.parametrize('version', ['1.9.2', '1.9.3', '1.9.4'])
def test_swing_none_before_1_9_6_is_rejected(version):
    with pytest.raises(ValueError):
        _inputs_from_event(contact_event(version, 'None'))


def test_missing_bat_position_is_rejected():
    with pytest.raises(ValueError):
        _inputs_from_event(contact_event('1.9.2', 'Slap', bat_pos=None))


@pytest.mark.parametrize('version, major_minor_patch, before', [
    ('1.9.5', (1, 9, 6), True),
    ('1.9.6', (1, 9, 6), False),
    ('1.10', (1, 9, 6), False),
    ('2.3.0-ICC', (2, 3), False),
    ('2.10.0', (2, 3), False),
    ('Pre 0.1.7', (1, 9, 6), True),
])
def test_version_before(version, major_minor_patch, before):
    assert StatObj({'Version': version}).versionBefore(*major_minor_patch) is before


@pytest.mark.parametrize('secondary', ['Error - Input', 'Error - Chem', 'Single', 'Foul', 7])
def test_old_error_labels_are_natural_landings(secondary):
    assert _is_natural_landing({'Contact Result - Secondary': secondary})


@pytest.mark.parametrize('secondary', ['Out-caught', 0])
def test_caught_balls_are_not_natural_landings(secondary):
    assert not _is_natural_landing({'Contact Result - Secondary': secondary})
