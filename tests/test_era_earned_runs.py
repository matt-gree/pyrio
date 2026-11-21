"""ERA counts earned runs. Files without Earned Runs fall back to every run allowed."""
import pytest

from pyrio.stat_file_parser import StatObj
from stat_builder import make_stat


def pitcher(**stats):
    return make_stat(overrides={(0, 0): {'Defensive Stats': stats}})


def test_era_uses_earned_runs():
    stat = StatObj(pitcher(**{'Runs Allowed': 3, 'Earned Runs': 1, 'Outs Pitched': 9}))
    assert stat.earnedRuns(0, 0) == 1
    assert stat.era(0, 0) == pytest.approx(3.0)
    assert stat.era(0) == pytest.approx(3.0)


def test_era_falls_back_to_runs_allowed():
    data = pitcher(**{'Runs Allowed': 3, 'Outs Pitched': 9})
    for slot in data['Character Game Stats'].values():
        del slot['Defensive Stats']['Earned Runs']
    stat = StatObj(data)
    assert stat.earnedRuns(0, 0) == 3
    assert stat.era(0, 0) == pytest.approx(9.0)
