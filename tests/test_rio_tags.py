"""TagSetID -> gecko-mod tag names.

Ported from main. Only the offline behaviour is tested: the lookup itself
calls the ProjectRio API, which this suite does not do.
"""
import pyrio.rio_tags as rio_tags


def test_no_tag_set_id_is_an_empty_set_without_touching_the_network():
    rio_tags.clear_cache()
    assert rio_tags.tags_for_tag_set(None) == frozenset()


def test_a_stat_file_with_no_tag_set_id_resolves_to_nothing():
    class Stat:
        statJson = {}
    rio_tags.clear_cache()
    assert rio_tags.active_tags_for_stat(Stat()) == frozenset()


def test_an_unknown_id_is_an_empty_set_not_an_error():
    rio_tags.clear_cache()
    rio_tags._tag_sets_by_id = {7: frozenset({'Superstar Mode'})}
    assert rio_tags.tags_for_tag_set(999) == frozenset()
    assert rio_tags.tags_for_tag_set(7) == frozenset({'Superstar Mode'})
    rio_tags.clear_cache()


def test_clear_cache_forces_a_refetch():
    rio_tags._tag_sets_by_id = {1: frozenset()}
    rio_tags.clear_cache()
    assert rio_tags._tag_sets_by_id is None
