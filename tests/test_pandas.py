"""pyrio.pandas.frame: models to DataFrames."""

from __future__ import annotations

import math
import pathlib

import pytest

import pyrio
from pyrio import AtBatResult, BattingLine, Character, PitchingLine

pd = pytest.importorskip("pandas")
import pyrio.pandas  # noqa: E402  (after the skip, so a missing extra skips)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GAME = pyrio.read_game(FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json")


def test_one_row_per_event_with_flattened_columns():
    df = pyrio.pandas.frame(GAME.events)
    assert len(df) == len(GAME.events)
    for column in (
        "game_id",
        "state_inning",
        "batter_spot_character",
        "pitch_type",
        "contact_landing_location_x",
        "fielding_position",
    ):
        assert column in df.columns
    assert (df["game_id"] == GAME.id).all()


def test_values_match_the_model():
    df = pyrio.pandas.frame(GAME.events)
    for event, (_, row) in zip(GAME.events, df.iterrows(), strict=True):
        assert row["batter_spot_character"] == event.batter_spot.character.label
        assert row["result"] == event.result.label
        if event.contact is None:
            assert math.isnan(row["contact_landing_location_x"])
        else:
            x, y, z = event.contact.landing_location
            assert (row["contact_landing_location_x"], row["contact_landing_location_y"]) == (x, y)
            assert row["contact_landing_location_z"] == z


def test_enums_are_categories_in_enum_order():
    df = pyrio.pandas.frame(GAME.events)
    column = df["batter_spot_character"]
    assert isinstance(column.dtype, pd.CategoricalDtype)
    assert list(column.cat.categories) == [c.label for c in Character]
    assert list(df["result"].cat.categories) == [r.label for r in AtBatResult]


def test_bases_keep_their_positional_form():
    df = pyrio.pandas.frame(GAME.events)
    assert set(df["state_bases"]) <= {str(e.state.bases) for e in GAME.events}


def test_collections_and_none_models_leave_no_columns():
    df = pyrio.pandas.frame(GAME.events)
    for left_out in ("runners", "pitch", "contact", "fielding", "contact_rng", "batter_spot"):
        assert left_out not in df.columns


def test_a_roster_frames_every_field_of_each_spot():
    df = pyrio.pandas.frame(GAME.home.roster)
    assert len(df) == 9
    assert df["batting_hits"].sum() == sum(s.batting.hits for s in GAME.home.roster)
    assert "pitching_outs_pitched" in df.columns
    assert "batters_per_position" not in df.columns


def test_a_game_frames_its_teams_and_result():
    df = pyrio.pandas.frame([GAME])
    row = df.iloc[0]
    assert row["version"] == str(GAME.version)
    assert row["home_score"] == GAME.home.score
    assert row["result_winner"] == str(GAME.result.winner)
    assert "events" not in df.columns


def test_a_nested_model_missing_in_some_rows_reads_as_missing_values():
    from pyrio.web import StatRow

    rows = [
        StatRow(user="a", batting=BattingLine(at_bats=4, hits=2)),
        StatRow(user="b", pitching=PitchingLine(outs_pitched=27)),
    ]
    df = pyrio.pandas.frame(rows)
    assert "batting" not in df.columns
    assert df["batting_hits"].tolist()[0] == 2
    assert math.isnan(df["batting_hits"].tolist()[1])
    assert df["pitching_outs_pitched"].tolist()[1] == 27


def test_mixed_types_are_refused():
    with pytest.raises(TypeError, match="one type"):
        pyrio.pandas.frame([GAME.events[0], GAME.home])


def test_non_models_are_refused():
    with pytest.raises(TypeError, match="dataclass"):
        pyrio.pandas.frame([1, 2])


def test_nothing_gives_an_empty_frame():
    assert pyrio.pandas.frame([]).empty
