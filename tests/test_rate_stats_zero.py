"""Rate stats return 0.0, not ZeroDivisionError, when there's nothing to divide by: a character
with no at-bats, or one who never pitched. That's most of a roster in a short game."""
import pytest

from pyrio.stat_file import StatObj
from stat_builder import make_stat


@pytest.mark.parametrize('method', ['battingAvg', 'obp', 'slg', 'ops', 'era'])
@pytest.mark.parametrize('roster', [0, -1])
def test_no_denominator_is_zero(method, roster):
    stat = StatObj(make_stat())
    assert getattr(stat, method)(0, roster) == 0.0


def test_era_with_runs_but_no_innings_is_zero():
    stat = StatObj(make_stat(overrides={(0, 0): {'Defensive Stats': {'Runs Allowed': 2}}}))
    assert stat.era(0, 0) == 0.0


def test_real_values_are_unchanged():
    stat = StatObj(make_stat(overrides={(0, 0): {
        'Offensive Stats': {'At Bats': 4, 'Hits': 2, 'Singles': 2},
        'Defensive Stats': {'Runs Allowed': 1, 'Earned Runs': 1, 'Outs Pitched': 9}}}))
    assert stat.battingAvg(0, 0) == pytest.approx(0.5)
    assert stat.era(0, 0) == pytest.approx(3.0)
