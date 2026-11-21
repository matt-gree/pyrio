"""Files before 1.9.2 number the home team 0. teamNumVersionCorrection flips the team for them,
and it must happen exactly once: roster_obj applies it, so stats built on it must not.
"""
import pytest

from pyrio.stat_file_parser import StatObj
from stat_builder import make_stat

# The away team's first slot gets 5 at-bats, the home team's gets 2.
OLD_AWAY_IN_FILE = 1  # pre-1.9.2 files store away as team 1


def stat_with_away_ab(version, away_file_team):
    home_file_team = 1 - away_file_team
    return StatObj(make_stat(version, {
        (away_file_team, 0): {'Offensive Stats': {'At Bats': 5, 'Hits': 1, 'Singles': 1, 'RBI': 3},
                              'Defensive Stats': {'Runs Allowed': 4, 'Outs Pitched': 3}},
        (home_file_team, 0): {'Offensive Stats': {'At Bats': 2, 'Hits': 2, 'Singles': 2, 'RBI': 0}},
    }))


@pytest.mark.parametrize('version, away_file_team', [('1.9.1', OLD_AWAY_IN_FILE), ('2.3.0', 0)])
def test_stats_read_the_away_team(version, away_file_team):
    stat = stat_with_away_ab(version, away_file_team)
    assert stat.atBats(0, 0) == 5
    assert stat.atBats(1, 0) == 2
    assert stat.rbi(0) == 3
    assert stat.runsAllowed(0, 0) == 4


@pytest.mark.parametrize('version, away_file_team', [('1.9.1', OLD_AWAY_IN_FILE), ('2.3.0', 0)])
def test_combined_stats_read_the_away_team(version, away_file_team):
    stat = stat_with_away_ab(version, away_file_team)
    assert stat.battingAvg(0, 0) == pytest.approx(1 / 5)
    assert stat.battingAvg(1, 0) == pytest.approx(2 / 2)
    assert stat.inningsPitched(0, 0) == pytest.approx(1.0)
