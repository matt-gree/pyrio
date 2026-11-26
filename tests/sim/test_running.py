"""Running the bases, against the frontend's running model and the game's rules.

``tests/fixtures/running_goldens.json.gz`` holds the frontend model's results
(ProjectRio-frontend ``lib/mssb/RunningSimulation``) over characters,
superstar, mashing, rounding, every leg and both batting hands. The port
agrees exactly: the same frames and the same final position to the bit.
``tools/check_running_parity.py`` regenerates them from a frontend checkout.
"""

from __future__ import annotations

import gzip
import json
import pathlib
from typing import Any

import pytest

from pyrio import Character, Hand
from pyrio.sim import RunnerAction, batter_location, simulate_run

GOLDENS = pathlib.Path(__file__).parent.parent / "fixtures" / "running_goldens.json.gz"


def _goldens() -> list[dict[str, Any]]:
    with gzip.open(GOLDENS, "rt") as file:
        return json.load(file)


def _run(case: dict[str, Any]):
    return simulate_run(
        Character(case["id"]),
        initial_base=case["s"],
        result_base=case["e"],
        is_superstar=case["sup"],
        hand=Hand.LEFT if case["side"] == "L" else Hand.RIGHT,
        rounding=case["path"] == "round",
        mash_every=case["every"],
    )


def test_the_port_matches_the_frontend_model_exactly():
    cases = _goldens()
    assert len(cases) > 1000
    for case in cases:
        run = _run(case)
        last = run.trace[-1].location
        assert run.frames == case["frames"], case
        assert run.top_speed_frame == case["top"], case
        assert dict(run.base_frames) == {b["base"]: b["frame"] for b in case["bases"]}, case
        assert (last[0], last[2]) == (case["x"], case["z"]), case
        assert len(run.overrun) == case["overrun"], case


def test_the_batter_waits_30_frames_and_a_runner_5():
    batter = simulate_run(Character.MARIO)
    assert all(f.is_held for f in batter.trace[:29])
    assert not batter.trace[29].is_held
    runner = simulate_run(Character.MARIO, initial_base=1, result_base=2)
    assert all(f.is_held for f in runner.trace[:4])
    assert not runner.trace[4].is_held


def test_faster_characters_and_mashing_get_there_sooner():
    slow = simulate_run(Character.BOWSER).frames
    fast = simulate_run(Character.YOSHI).frames
    assert fast < slow
    starred = simulate_run(Character.BOWSER, is_superstar=True).frames
    assert starred < slow
    lazy = simulate_run(Character.MARIO, mash_every=None).frames
    tas = simulate_run(Character.MARIO, mash_every=1).frames
    assert tas <= simulate_run(Character.MARIO).frames < lazy  # every 3rd frame fills the meter too


def test_rounding_keeps_speed_and_stopping_slides():
    straight = simulate_run(Character.MARIO, result_base=4)
    rounded = simulate_run(Character.MARIO, result_base=4, rounding=True)
    assert rounded.frames < straight.frames
    assert RunnerAction.SLIDE in {f.action for f in straight.trace}
    assert RunnerAction.SLIDE not in {f.action for f in rounded.trace}
    assert list(rounded.base_frames) == [1, 2, 3, 4]


def test_a_rounding_runner_stopping_at_second_overruns_it():
    run = simulate_run(Character.MARIO, result_base=2, rounding=True)
    assert run.overrun
    assert simulate_run(Character.MARIO, result_base=2).overrun == ()


def test_the_batter_starts_where_they_stand():
    right = batter_location(Character.MARIO, Hand.RIGHT)
    left = batter_location(Character.MARIO, Hand.LEFT)
    assert left == (-right[0], 0.0, right[2])
    a = Character.MARIO.attributes
    assert right == (0.0 + a.bat_offset[0], 0.0, 0.4 + a.bat_offset[1])
    corner = batter_location(Character.MARIO, Hand.RIGHT, (99.0, 99.0))  # clamped to the box
    assert corner[0] == a.horizontal_range_far + a.bat_offset[0]
    assert simulate_run(Character.MARIO, hand=Hand.LEFT).start == left


@pytest.mark.parametrize(("start", "end"), [(1, 1), (2, 1), (0, 5), (-1, 2)])
def test_a_run_must_go_forward(start: int, end: int):
    with pytest.raises(ValueError, match="initial_base"):
        simulate_run(Character.MARIO, initial_base=start, result_base=end)


def test_mash_every_must_be_positive():
    with pytest.raises(ValueError, match="mash_every"):
        simulate_run(Character.MARIO, mash_every=0)
