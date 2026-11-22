import json
from pathlib import Path

import pytest

from pyrio import Bases, Character, Side, read_game, read_hud, to_jsonable

FIXTURES = Path(__file__).parent / "fixtures"
GAME_PATH = FIXTURES / "20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"


def test_a_game_round_trips_through_json():
    game = read_game(GAME_PATH)
    data = json.loads(json.dumps(to_jsonable(game)))
    assert data["id"] == 3896251267
    assert data["version"] == "2.2.0"
    assert data["stadium"] == "Bowser Castle"
    assert data["start_time"] == "2026-06-18T23:50:37+00:00"
    assert data["result"] == {
        "winner": "Home",
        "is_mercy": False,
        "quit_by": None,
        "crashed": False,
    }
    assert len(data["events"]) == len(game.events)


def test_spots_are_full_in_the_roster_and_references_elsewhere():
    data = to_jsonable(read_game(GAME_PATH))
    spot = data["away"]["roster"][0]
    assert spot["character"] == "DK"
    assert spot["batting"]["at_bats"] == 6
    assert spot["batters_per_position"] == {"2B": 42}
    event = data["events"][1]
    assert event["batter_spot"] == {"side": "Away", "index": 1}
    assert event["runners"][1]["spot"] == {"side": "Away", "index": 0}
    assert event["state"]["bases"] == "1--"
    assert event["pitch"]["type"] == "Curve"
    assert event["contact"] is None


def test_hud_spot_keys_become_strings():
    hud = read_hud(FIXTURES / "hud.json", version="2.2.0")
    data = json.loads(json.dumps(to_jsonable(hud)))
    assert data["fielding_positions"]["Away 0"] == "2B"
    assert data["away_logo"] == "Bowser Blue Shells"


def test_values():
    assert to_jsonable(Character.TOAD_B) == "Toad(B)"
    assert to_jsonable(Side.HOME) == "Home"
    assert to_jsonable(Bases.FIRST | Bases.THIRD) == "1-3"
    assert to_jsonable((1, 2.5, None)) == [1, 2.5, None]


def test_unknown_objects_raise():
    with pytest.raises(TypeError, match="object"):
        to_jsonable(object())
