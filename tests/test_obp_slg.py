"""Rio's At Bats doesn't include walks or hit by pitches, so OBP adds them to the denominator and
SLG divides total bases by at-bats alone."""
import pytest

from pyrio.stat_file_parser import StatObj
from stat_builder import make_stat


def batter(**stats):
    return StatObj(make_stat(overrides={(0, 0): {'Offensive Stats': stats}}))


def test_obp_counts_walks_hit_by_pitch_and_sac_flies():
    # 4 at-bats, 1 hit, 1 walk, 1 hit by pitch, 1 sac fly: (1 + 1 + 1) / (4 + 1 + 1 + 1)
    stat = batter(**{'At Bats': 4, 'Hits': 1, 'Singles': 1, 'Walks (4 Balls)': 1, 'Walks (Hit)': 1,
                     'Sac Flys': 1})
    assert stat.obp(0, 0) == pytest.approx(3 / 7)


def test_obp_never_passes_one():
    stat = batter(**{'At Bats': 1, 'Hits': 1, 'Singles': 1, 'Walks (4 Balls)': 3})
    assert stat.obp(0, 0) == pytest.approx(1.0)


def test_obp_with_only_walks():
    stat = batter(**{'Walks (4 Balls)': 2})
    assert stat.obp(0, 0) == pytest.approx(1.0)


def test_slg_divides_total_bases_by_at_bats():
    # 1 single, 1 double, 1 home run in 5 at-bats, plus 2 walks that don't count: 7 / 5
    stat = batter(**{'At Bats': 5, 'Hits': 3, 'Singles': 1, 'Doubles': 1, 'Homeruns': 1,
                     'Walks (4 Balls)': 2})
    assert stat.slg(0, 0) == pytest.approx(7 / 5)
    assert stat.ops(0, 0) == pytest.approx(stat.obp(0, 0) + 7 / 5)


def test_slg_with_more_walks_than_at_bats():
    stat = batter(**{'At Bats': 1, 'Hits': 1, 'Singles': 1, 'Walks (4 Balls)': 3})
    assert stat.slg(0, 0) == pytest.approx(1.0)
