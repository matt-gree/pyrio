"""Per-position defensive stats. Rio writes each as a list holding one {position: count} object."""
from pyrio.stat_file_parser import StatObj
from stat_builder import make_stat


def fielder(**stats):
    return StatObj(make_stat(overrides={(0, 0): {'Defensive Stats': stats}}))


def test_batters_per_position_reads_the_current_key():
    stat = fielder(**{'Batters Per Position': [{'CF': 3, 'LF': 1}]})
    assert stat.battersPerPosition(0, 0) == {'CF': 3, 'LF': 1}
    assert stat.pitchesPerPosition(0, 0) == {'CF': 3, 'LF': 1}


def test_batters_per_position_reads_the_pre_2022_key():
    data = make_stat(overrides={(0, 0): {'Defensive Stats': {'Pitches Per Position': [{'P': 12}]}}})
    del data['Character Game Stats']['Away Roster 0']['Defensive Stats']['Batters Per Position']
    assert StatObj(data).battersPerPosition(0, 0) == {'P': 12}
