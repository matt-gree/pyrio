"""Run expectancy, linear weights and the wOBA family."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import pytest

from pyrio import (
    AtBat,
    AtBatResult,
    Bases,
    BattingLine,
    Game,
    GameResult,
    LinearWeights,
    RunExpectancy,
    Side,
    linear_weights,
    read_game,
    run_expectancy,
)
from pyrio._run_values import _complete_halves

FIXTURES = Path(__file__).parent / "fixtures"
GAME_PATH = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
STAT_FILES = sorted((FIXTURES / "stat_files").rglob("*.json"))

R = AtBatResult
EMPTY = Bases(0)
FIRST = Bases.FIRST

# A small game to check by hand: (inning, side, outs, bases, result, runs) per event.
# Two innings are scheduled, so the bottom of the 2nd is where a walk-off could
# happen, and it is left out.
SMALL_GAME = [
    (1, Side.AWAY, 0, EMPTY, R.SINGLE, 0),
    (1, Side.AWAY, 0, FIRST, R.HOME_RUN, 2),
    (1, Side.AWAY, 0, EMPTY, R.STRIKEOUT, 0),
    (1, Side.AWAY, 1, EMPTY, R.OUT, 0),
    (1, Side.AWAY, 2, EMPTY, R.CAUGHT, 0),
    (1, Side.HOME, 0, EMPTY, R.WALK, 0),
    (1, Side.HOME, 0, FIRST, R.DOUBLE_PLAY, 0),
    (1, Side.HOME, 2, EMPTY, R.STRIKEOUT, 0),
    (2, Side.AWAY, 0, EMPTY, R.STRIKEOUT, 0),
    (2, Side.AWAY, 1, EMPTY, R.STRIKEOUT, 0),
    (2, Side.AWAY, 2, EMPTY, R.OUT, 0),
    (2, Side.HOME, 0, EMPTY, R.HOME_RUN, 1),
    (2, Side.HOME, 0, EMPTY, R.STRIKEOUT, 0),
    (2, Side.HOME, 1, EMPTY, R.OUT, 0),
    (2, Side.HOME, 2, EMPTY, R.OUT, 0),
]


@pytest.fixture(scope="module")
def real_game() -> Game:
    return read_game(GAME_PATH)


def build(
    real_game: Game,
    rows: list[tuple[int, Side, int, Bases, AtBatResult, int]],
    *,
    innings_selected: int = 2,
    result: GameResult | None = None,
) -> Game:
    template = real_game.events[0]
    events = []
    for number, (inning, side, outs, bases, ab_result, runs) in enumerate(rows):
        state = dataclasses.replace(
            template.state,
            inning=inning,
            batting_side=side,
            outs=outs,
            bases=bases,
            balls=0,
            strikes=0,
            is_star_chance=False,
        )
        events.append(
            dataclasses.replace(template, number=number, state=state, result=ab_result, runs=runs)
        )
    return dataclasses.replace(
        real_game,
        events=tuple(events),
        innings_selected=innings_selected,
        result=result or GameResult(winner=Side.AWAY, is_mercy=False, quit_by=None, crashed=False),
    )


@pytest.fixture
def small(real_game: Game) -> Game:
    return build(real_game, SMALL_GAME)


# --- Run expectancy ---------------------------------------------------------------------


def test_run_expectancy_by_hand(small: Game):
    expectancy = run_expectancy([small])
    # Bases empty, none out: four at-bats began there in the halves kept (the top
    # of the 1st scored 2 after the leadoff single), so 2 runs over 4.
    assert expectancy.occurrences == {(EMPTY, 0): 4, (EMPTY, 1): 2, (EMPTY, 2): 3, (FIRST, 0): 2}
    assert expectancy.runs == {(EMPTY, 0): 2, (EMPTY, 1): 0, (EMPTY, 2): 0, (FIRST, 0): 2}
    assert expectancy[EMPTY, 0] == 0.5
    assert expectancy[FIRST, 0] == 1.0
    assert math.isnan(expectancy[Bases.THIRD, 2])  # never occurred


def test_runs_on_the_third_out_play_count(real_game: Game):
    rows = [
        (1, Side.AWAY, 2, EMPTY, R.SINGLE, 0),
        (1, Side.AWAY, 2, Bases.FIRST | Bases.THIRD, R.SINGLE, 1),  # the batter is out at 2nd
        (1, Side.HOME, 0, EMPTY, R.OUT, 0),
        (1, Side.HOME, 1, EMPTY, R.OUT, 0),
        (1, Side.HOME, 2, EMPTY, R.OUT, 0),
    ]
    game = build(real_game, rows, innings_selected=3)
    expectancy = run_expectancy([game])
    assert expectancy.runs[Bases.FIRST | Bases.THIRD, 2] == 1


def test_a_walk_off_half_is_left_out(small: Game, real_game: Game):
    # Three innings scheduled: the bottom of the 2nd is an ordinary half, kept.
    longer = dataclasses.replace(small, innings_selected=3)
    assert run_expectancy([longer]).occurrences[EMPTY, 0] == 6
    # The same game ended by the home run (a walk-off) loses the half.
    walkoff = build(
        real_game,
        SMALL_GAME[:12],
        innings_selected=3,
        result=GameResult(winner=Side.HOME, is_mercy=False, quit_by=None, crashed=False),
    )
    assert run_expectancy([walkoff]).occurrences == run_expectancy([small]).occurrences


@pytest.mark.parametrize(
    "result",
    [
        GameResult(winner=Side.AWAY, is_mercy=False, quit_by=Side.HOME, crashed=False),
        GameResult(winner=Side.AWAY, is_mercy=False, quit_by=None, crashed=True),
    ],
)
def test_a_quit_or_crash_drops_the_last_half(real_game: Game, result: GameResult):
    rows = SMALL_GAME[:7]  # cut off after the double play
    game = build(real_game, rows, innings_selected=3, result=result)
    finished = build(real_game, SMALL_GAME[:8], innings_selected=3)
    assert run_expectancy([game]).occurrences == {
        (EMPTY, 0): 2,
        (EMPTY, 1): 1,
        (EMPTY, 2): 1,
        (FIRST, 0): 1,
    }
    assert run_expectancy([finished]).occurrences[EMPTY, 0] == 3


def test_run_expectancy_prints_the_grid(small: Game):
    lines = str(run_expectancy([small])).splitlines()
    assert len(lines) == 9
    assert lines[1].split() == ["---", "0.500", "0.000", "0.000"]
    assert lines[2].split() == ["1--", "1.000", "nan", "nan"]


def test_run_expectancy_counts_every_at_bat_in_the_halves_kept():
    assert STAT_FILES
    for path in STAT_FILES:
        game = read_game(path)
        expected = sum(len(half.at_bats) for half in _complete_halves(game))
        assert sum(run_expectancy([game]).occurrences.values()) == expected, path


# --- Linear weights ---------------------------------------------------------------------


def test_linear_weights_by_hand(small: Game):
    weights = linear_weights([small])
    # The leadoff single: RE 0.5 -> 1.0. The home run: 1.0 -> 0.5, plus 2 runs.
    assert weights[R.SINGLE] == 0.5
    assert weights[R.HOME_RUN] == 1.5
    assert weights[R.WALK] == 0.5
    assert weights[R.DOUBLE_PLAY] == -1.0
    assert weights[R.STRIKEOUT] == -0.25  # -0.5, 0, -0.5, 0
    assert weights.counts == {
        R.STRIKEOUT: 4,
        R.WALK: 1,
        R.OUT: 2,
        R.CAUGHT: 1,
        R.SINGLE: 1,
        R.HOME_RUN: 1,
        R.DOUBLE_PLAY: 1,
    }
    assert weights.out_value == -0.25  # -1 for the strikeouts, -1 for the double play, over 8
    assert weights.runs == 2
    assert weights.plate_appearances == 11
    assert weights.league_woba == pytest.approx((0.75 + 1.75 + 0.75) / 11)
    assert weights.league_runs_per_pa == pytest.approx(2 / 11)
    assert math.isnan(weights[R.TRIPLE])


def test_woba_by_hand(small: Game):
    weights = linear_weights([small])
    away = [ab for ab in small.at_bats if ab.batting_side is Side.AWAY and ab.inning == 1]
    # Single and home run credited at 0.75 and 1.75, over five plate appearances.
    assert weights.woba(away) == pytest.approx(2.5 / 5)
    assert weights.wraa(away) == pytest.approx(2.5 - weights.league_woba * 5)
    assert weights.wrc(away) == pytest.approx(weights.wraa(away) + 2 / 11 * 5)
    line = BattingLine(at_bats=5, hits=2, singles=1, home_runs=1, strikeouts=1)
    assert weights.woba(line) == weights.woba(away)


def test_woba_reads_complete_at_bats_and_leaves_bunts_out(small: Game):
    weights = linear_weights([small])
    single, home_run = small.at_bats[0], small.at_bats[1]
    unfinished = AtBat(events=(dataclasses.replace(single.final, result=R.NONE),))
    bunt = AtBat(events=(dataclasses.replace(single.final, result=R.BUNT),))
    assert weights.woba([single, home_run, unfinished, bunt]) == weights.woba([single, home_run])


def test_nothing_to_score(small: Game):
    weights = linear_weights([small])
    assert math.isnan(weights.woba([]))
    assert weights.wraa([]) == 0.0
    assert weights.wrc(BattingLine()) == 0.0


def test_results_off_the_table_are_skipped(small: Game):
    weights = linear_weights([small], expectancy=RunExpectancy())
    assert weights.values == {}
    assert math.isnan(weights.out_value)
    assert weights == LinearWeights(runs=2)


def test_the_league_is_average_and_creates_its_own_runs():
    # Over the half innings the weights were measured on, wRAA is zero and wRC
    # is the runs actually scored.
    games = [read_game(path) for path in STAT_FILES]
    weights = linear_weights(games)
    measured = [ab for game in games for half in _complete_halves(game) for ab in half.at_bats]
    assert weights.wraa(measured) == pytest.approx(0, abs=1e-9)
    assert weights.wrc(measured) == pytest.approx(weights.runs)
    assert weights.runs > 0
    # A handful of games is too few to order singles and doubles, but not the ends.
    assert 0 < weights[R.SINGLE] - weights.out_value < weights[R.HOME_RUN] - weights.out_value


def test_linear_weights_count_every_result_in_the_halves_kept():
    for path in STAT_FILES:
        game = read_game(path)
        expected = sum(
            1
            for half in _complete_halves(game)
            for event in half.events
            if event.result is not R.NONE
        )
        assert sum(linear_weights([game]).counts.values()) == expected, path
