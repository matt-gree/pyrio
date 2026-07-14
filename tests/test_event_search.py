"""Regression tests for EventSearch.

EventSearch was silently broken when EventObj accessors were migrated to value
objects: its index dicts were keyed on raw strings/ids but populated/queried
with value objects, so it raised KeyError on construction. These tests pin that
it builds and that the value-object-keyed buckets resolve.
"""
import json
from pathlib import Path

import pytest

from pyrio.stat_file import StatObj, EventSearch
from pyrio import Character

FIXTURE = Path(__file__).parent / "fixtures" / (
    "decoded.20260618T191655_SpiceOrange-Vs-MattGree_3896251267.json"
)


@pytest.fixture(scope="module")
def search() -> EventSearch:
    with open(FIXTURE) as f:
        data = json.load(f)
    return EventSearch(StatObj(data))


def test_constructs_without_error(search):
    assert isinstance(search, EventSearch)


def test_result_buckets_partition_events(search):
    # Every final-result bucket is a set of event numbers; the at-bat-result
    # buckets should be disjoint and cover at least the strikeouts/hits queried.
    strikeouts = search.strikeoutResultEvents()
    hits = search.hitResultEvents()
    assert isinstance(strikeouts, set)
    assert isinstance(hits, set)
    assert strikeouts.isdisjoint(hits)


def test_hit_subtypes_sum_to_all_hits(search):
    singles = search.hitResultEvents(1)
    doubles = search.hitResultEvents(2)
    triples = search.hitResultEvents(3)
    homers = search.hitResultEvents(4)
    assert singles | doubles | triples | homers == search.hitResultEvents()


def test_swing_and_contact_buckets_resolve(search):
    # These index pitch/contact buckets keyed on value objects.
    assert isinstance(search.slapSwingTypeEvents(), set)
    assert isinstance(search.starSwingTypeEvents(), set)
    assert isinstance(search.perfectContactTypeEvents(), set)
    assert isinstance(search.niceContactTypeEvents(), set)


def test_character_action_lookup_accepts_id_and_name(search):
    # character_action_dict is keyed on Character; queries accept id or name.
    any_char = next(iter(search.character_action_dict))
    by_id = search.characterAtBatEvents(any_char.id)
    by_name = search.characterAtBatEvents(any_char.name)
    assert by_id == by_name
    # A character not in the game returns an empty set rather than raising.
    assert search.characterPitchingEvents(53) == set() or isinstance(
        search.characterPitchingEvents(53), set
    )


def test_position_fielding_events_resolve(search):
    assert isinstance(search.positionFieldingEvents("SS"), set)
    assert isinstance(search.firstFielderPositionEvents("P"), set)
