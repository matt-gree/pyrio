"""pyrio.plot: stadium drawings on matplotlib axes."""

from __future__ import annotations

import pathlib

import pytest

import pyrio
from pyrio import PrimaryContactResult, Stadium

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import pyrio.plot  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GAME = pyrio.read_game(FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json")


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def test_stadium_draws_on_new_axes_with_equal_scales():
    ax = pyrio.plot.stadium(Stadium.MARIO_STADIUM)
    assert ax.get_aspect() == 1.0
    assert len(ax.patches) == 1  # the field
    assert len(ax.lines) == 2  # the foul lines


def test_stadium_draws_on_the_axes_it_is_given():
    _, ax = plt.subplots()
    assert pyrio.plot.stadium(Stadium.MARIO_STADIUM, ax=ax, fielders=True) is ax
    assert len(ax.collections) == 9
    assert {t.get_text() for t in ax.texts} >= {"P", "C", "CF"}


def test_spray_chart_scatters_each_fair_ball():
    fair = sum(
        e.contact is not None and e.contact.primary_result is not PrimaryContactResult.FOUL
        for e in GAME.events
    )
    ax = pyrio.plot.spray_chart(GAME.events, stadium=GAME.stadium)
    assert len(ax.collections) == fair
