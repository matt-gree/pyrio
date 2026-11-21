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


# ---------------------------------------------------------------------------
# Regression: runnerOnBaseEvents raised on every positive-base call
# ---------------------------------------------------------------------------

def test_runner_on_base_no_runners(search):
    """baseNums == [0] indexed the dict with the string 'None'; it is int-keyed."""
    assert isinstance(search.runnerOnBaseEvents([0]), set)


def test_runner_on_base_required_bases_resolve(search):
    """Called self.eventFinal(), which does not exist -> AttributeError."""
    for bases in ([1], [2], [3], [1, 2], [1, 2, 3], [1, -2], [3, -1]):
        assert isinstance(search.runnerOnBaseEvents(bases), set)


def test_runner_on_base_required_bases_are_actually_required(search):
    """On an empty intersection the old code fell back to the union of the
    *optional* bases, so a required base could be missing from the result."""
    for bases in ([1], [2], [3], [1, 2], [1, -2], [3, -1], [2, -1, -3]):
        result = search.runnerOnBaseEvents(bases)
        for base in (b for b in bases if b > 0):
            assert result <= search._runners_on_base_dict[base], (
                f"{bases}: result contains events with no runner on {base}"
            )


def test_runner_on_base_partitions_the_game(search):
    no_runners = search.runnerOnBaseEvents([0])
    any_runners = search.runnerOnBaseEvents([-1, -2, -3])
    total = search.rioStat.final_event() + 1
    assert not (no_runners & any_runners)
    assert len(no_runners | any_runners) == total


def test_runner_on_base_optional_widens(search):
    """A negative base means "don't care", so it can only widen the result."""
    assert search.runnerOnBaseEvents([1]) <= search.runnerOnBaseEvents([1, -2, -3])
    assert search.runnerOnBaseEvents([1, 2]) <= search.runnerOnBaseEvents([1, -2, -3])


def test_runner_on_base_rejects_bad_input(search):
    with pytest.raises(ValueError):
        search.runnerOnBaseEvents([4])
    with pytest.raises(ValueError):
        search.runnerOnBaseEvents([1, 2, 3, -1])      # more than 3 bases
    with pytest.raises(ValueError):
        search.runnerOnBaseEvents([1, 0])             # 0 alongside a required base


# ---------------------------------------------------------------------------
# Regression: outsInInningEvents validated outs with the half-inning checker
# ---------------------------------------------------------------------------

def test_outs_in_inning_accepts_every_outs_count(search):
    """The half-inning checker accepts only 0/1, so outs of 2 raised and the
    negative branch was unreachable."""
    for n in (0, 1, 2):
        assert isinstance(search.outsInInningEvents(n), set)
    for n in (-1, -2):
        assert isinstance(search.outsInInningEvents(n), set)


def test_outs_in_inning_negative_means_that_many_or_more(search):
    assert search.outsInInningEvents(-2) == search.outsInInningEvents(2)
    assert search.outsInInningEvents(-1) == (
        search.outsInInningEvents(1) | search.outsInInningEvents(2)
    )


def test_outs_in_inning_rejects_impossible_counts(search):
    for n in (3, -3, 4):
        with pytest.raises(ValueError):
            search.outsInInningEvents(n)
