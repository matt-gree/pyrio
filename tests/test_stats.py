import math

import pytest

from pyrio import BattingLine, PitchingLine, format_batting_line, format_pitching_line

LINE = BattingLine(
    at_bats=10,
    hits=4,
    singles=2,
    doubles=1,
    home_runs=1,
    walks=1,
    hit_by_pitch=1,
    strikeouts=3,
    sac_flies=1,
    rbi=3,
)


def test_batting_rates():
    assert LINE.plate_appearances == 13
    assert LINE.total_bases == 8
    assert LINE.avg == pytest.approx(0.4)
    assert LINE.obp == pytest.approx(6 / 13)
    assert LINE.slg == pytest.approx(0.8)
    assert LINE.ops == pytest.approx(6 / 13 + 0.8)
    assert LINE.iso == pytest.approx(0.4)
    assert LINE.k_pct == pytest.approx(3 / 13)


def test_zero_denominators_are_nan():
    empty = BattingLine()
    assert math.isnan(empty.avg)
    assert math.isnan(empty.ops)
    assert math.isnan(PitchingLine().era)
    assert math.isnan(PitchingLine().whip)


def test_loose_numbers_go_through_the_line():
    assert BattingLine(hits=3, at_bats=10).avg == pytest.approx(0.3)


def test_unknown_field_is_an_error():
    with pytest.raises(TypeError):
        BattingLine(hit=3, at_bats=10)  # type: ignore[call-arg]


def test_lines_add_and_sum():
    total = LINE + LINE
    assert total.at_bats == 20
    assert total.home_runs == 2
    assert sum([LINE, LINE, LINE]) == BattingLine(**{k: 3 * v for k, v in vars_of(LINE).items()})
    assert sum([PitchingLine(outs_pitched=3)] * 2) == PitchingLine(outs_pitched=6)


def test_lines_of_different_kinds_dont_add():
    with pytest.raises(TypeError):
        LINE + PitchingLine()  # type: ignore[operator]


def test_lines_are_frozen_and_hashable():
    with pytest.raises(AttributeError):
        LINE.hits = 5  # type: ignore[misc]
    assert {LINE: 1}[BattingLine(**vars_of(LINE))] == 1


def test_pitching_rates():
    line = PitchingLine(
        batters_faced=30,
        outs_pitched=21,
        hits_allowed=6,
        earned_runs=2,
        runs_allowed=3,
        walks=2,
        hit_by_pitch=1,
        strikeouts=7,
        pitches_thrown=98,
    )
    assert line.innings_pitched == pytest.approx(7)
    assert line.era == pytest.approx(2 * 9 / 7)
    assert line.era_over(7) == pytest.approx(2)
    assert line.whip == pytest.approx(8 / 7)
    assert line.k_pct == pytest.approx(7 / 30)
    assert line.k_per_bb == pytest.approx(3.5)
    assert line.avg_against == pytest.approx(6 / 27)
    assert line.pitches_per_inning == pytest.approx(14)


def test_format_batting_line():
    assert format_batting_line(BattingLine(at_bats=3)) == "0-for-3"
    assert (
        format_batting_line(BattingLine(at_bats=4, hits=2, home_runs=1, doubles=1))
        == "2-for-4, HR, 2B"
    )
    assert format_batting_line(BattingLine(at_bats=5, hits=4, doubles=2)) == "4-for-5, 2 2B"


def test_format_batting_line_names_strikeouts():
    # "1-for-4" has to say where the other at bats went.
    line = BattingLine(at_bats=4, hits=1, home_runs=1, hit_by_pitch=1, strikeouts=2)
    assert format_batting_line(line) == "1-for-4, HR, HBP, 2 K"
    line = BattingLine(at_bats=4, hits=1, walks=1, strikeouts=1, rbi=2, stolen_bases=1)
    assert format_batting_line(line) == "1-for-4, BB, K, 2 RBI, SB"


def test_format_pitching_line():
    line = PitchingLine(
        outs_pitched=19,
        hits_allowed=3,
        runs_allowed=1,
        earned_runs=1,
        walks=2,
        strikeouts=4,
        pitches_thrown=87,
    )
    assert format_pitching_line(line) == "6.1 IP, 3 H, 1 R, 1 ER, 2 BB, 4 K, 0 HR, 87 P"


def test_format_pitching_line_counts_hit_batters_as_walks():
    line = PitchingLine(outs_pitched=9, walks=1, hit_by_pitch=2)
    assert format_pitching_line(line) == "3.0 IP, 0 H, 0 R, 0 ER, 3 BB, 0 K, 0 HR, 0 P"


def vars_of(line: BattingLine) -> dict[str, int]:
    return {name: getattr(line, name) for name in line.__dataclass_fields__}
