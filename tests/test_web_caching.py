"""CompleterCache contract: lazy, stale-tolerant, and never fatal.

The cache exists to save the CALLER time, not to spare the server. Everything
here is a statement of that: construction costs nothing, a section costs only
its own endpoint, an aged section answers immediately, and a damaged cache file
is a miss rather than an exception.
"""
import json
import os
import time

import pytest

from web_caching import CompleterCache, _FORMAT_VERSION


TAG_ROWS = [
    {"id": 1, "name": "Ranked", "type": "Community"},
    {"id": 2, "name": "SuperStar", "type": "Gecko Code"},
    {"id": 3, "name": "Netplay", "type": "Component"},
    {"id": 4, "name": "Casual", "type": "Community"},
]


class FakeClient:
    """Records which endpoints were hit, so laziness is observable."""

    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)

    def _maybe_fail(self, name):
        if name in self.fail:
            raise RuntimeError(f"{name} is down")

    def list_tags(self):
        self.calls.append("tags")
        self._maybe_fail("tags")
        return {"Tags": list(TAG_ROWS)}

    def list_users(self):
        self.calls.append("users")
        self._maybe_fail("users")
        return {"users": {"1": "ProjectRio", "2": "MsNecromancer"}}

    def list_game_modes(self, active=False, community_ids=None):
        self.calls.append("game_modes")
        self._maybe_fail("game_modes")
        return {"Tag Sets": [{"name": "PeacockBall", "id": 1}, {"name": "Xtreme", "id": 2}]}


@pytest.fixture
def cache_dir(tmp_path):
    return str(tmp_path / "cache")


def _cache(client, cache_dir, **kw):
    kw.setdefault("background_refresh", False)
    return CompleterCache(client, cache_dir=cache_dir, **kw)


# --- laziness -----------------------------------------------------------

def test_construction_never_touches_the_network(cache_dir):
    client = FakeClient()
    _cache(client, cache_dir)
    assert client.calls == []


def test_a_section_costs_only_its_own_endpoint(cache_dir):
    """The whole point. Asking for game modes used to fetch 9,600 users and a
    tag table as well, because the cache refreshed as one unit."""
    client = FakeClient()
    cache = _cache(client, cache_dir)
    assert cache.game_mode_dictionary() == {"PeacockBall": 1, "Xtreme": 2}
    assert client.calls == ["game_modes"]


def test_a_section_is_fetched_once_however_many_accessors_read_it(cache_dir):
    client = FakeClient()
    cache = _cache(client, cache_dir)
    cache.communities()
    cache.tags_dictionary()
    cache.return_tags_df()
    assert client.calls == ["tags"]


# --- persistence --------------------------------------------------------

def test_a_warm_cache_answers_without_the_network(cache_dir):
    first = FakeClient()
    _cache(first, cache_dir).game_mode_dictionary()

    second = FakeClient()
    cache = _cache(second, cache_dir)
    assert cache.game_mode_dictionary() == {"PeacockBall": 1, "Xtreme": 2}
    assert second.calls == []


def test_the_cache_file_is_json_not_pickle(cache_dir):
    client = FakeClient()
    _cache(client, cache_dir).game_mode_dictionary()
    with open(os.path.join(cache_dir, "cache.json"), encoding="utf-8") as f:
        blob = json.load(f)
    assert blob["version"] == _FORMAT_VERSION
    assert "game_modes" in blob["sections"]


@pytest.mark.parametrize("content", [
    b"\x80\x04 truncated pickle garbage",
    b"{not json at all",
    b"",
    b'{"version": 99999, "sections": {}}',      # a format we don't speak
])
def test_a_damaged_cache_file_is_a_miss_not_an_exception(cache_dir, content):
    """This used to raise UnpicklingError straight out of `client.cache`, and
    stayed broken until someone deleted the file by hand."""
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "cache.json"), "wb") as f:
        f.write(content)

    client = FakeClient()
    cache = _cache(client, cache_dir)                 # must not raise
    assert cache.game_mode_dictionary() == {"PeacockBall": 1, "Xtreme": 2}


def test_a_failed_write_leaves_the_previous_cache_intact(cache_dir, monkeypatch):
    """Atomic write: the in-place version was itself how the file got corrupted."""
    client = FakeClient()
    cache = _cache(client, cache_dir)
    cache.game_mode_dictionary()
    good = open(os.path.join(cache_dir, "cache.json"), encoding="utf-8").read()

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr("web_caching.os.replace", boom)

    cache.communities()          # triggers another save, which fails
    assert open(os.path.join(cache_dir, "cache.json"), encoding="utf-8").read() == good


# --- expiry -------------------------------------------------------------

def _age_section(cache_dir, section, days):
    path = os.path.join(cache_dir, "cache.json")
    blob = json.load(open(path, encoding="utf-8"))
    blob["sections"][section]["fetched_at"] = time.time() - days * 86400
    json.dump(blob, open(path, "w", encoding="utf-8"))


def test_a_stale_section_is_refreshed(cache_dir):
    _cache(FakeClient(), cache_dir).game_mode_dictionary()
    _age_section(cache_dir, "game_modes", days=3)

    client = FakeClient()
    cache = _cache(client, cache_dir)
    assert cache.game_mode_dictionary() == {"PeacockBall": 1, "Xtreme": 2}
    assert client.calls == ["game_modes"]


def test_stale_data_is_served_immediately_while_it_refreshes(cache_dir):
    """Expiry means 'worth updating', not 'make the caller wait'."""
    _cache(FakeClient(), cache_dir).game_mode_dictionary()
    _age_section(cache_dir, "game_modes", days=3)

    class Slow(FakeClient):
        def list_game_modes(self, active=False, community_ids=None):
            time.sleep(0.5)
            return super().list_game_modes(active, community_ids)

    cache = CompleterCache(Slow(), cache_dir=cache_dir, background_refresh=True)
    began = time.perf_counter()
    value = cache.game_mode_dictionary()
    elapsed = time.perf_counter() - began

    assert value == {"PeacockBall": 1, "Xtreme": 2}
    assert elapsed < 0.2, f"waited {elapsed:.2f}s on a background refresh"


def test_a_fresh_section_is_not_refetched(cache_dir):
    _cache(FakeClient(), cache_dir).game_mode_dictionary()
    client = FakeClient()
    _cache(client, cache_dir).game_mode_dictionary()
    assert client.calls == []


# --- failure ------------------------------------------------------------

def test_an_api_failure_with_nothing_cached_returns_empty_rather_than_raising(cache_dir):
    cache = _cache(FakeClient(fail=["game_modes"]), cache_dir)
    assert cache.game_mode_dictionary() == {}


def test_an_api_failure_falls_back_to_the_stale_value(cache_dir):
    _cache(FakeClient(), cache_dir).game_mode_dictionary()
    _age_section(cache_dir, "game_modes", days=3)
    cache = _cache(FakeClient(fail=["game_modes"]), cache_dir)
    assert cache.game_mode_dictionary() == {"PeacockBall": 1, "Xtreme": 2}


# --- explicit refresh ---------------------------------------------------

def test_refresh_cache_updates_every_section_exactly_once(cache_dir):
    client = FakeClient()
    cache = _cache(client, cache_dir)
    cache.refresh_cache()
    assert sorted(client.calls) == ["game_modes", "tags", "users"]
    assert len(client.calls) == 3, "each endpoint exactly once, not twice"


# --- accessor shapes ----------------------------------------------------

def test_accessors_return_their_documented_shapes(cache_dir):
    cache = _cache(FakeClient(), cache_dir)
    assert cache.communities() == ["Ranked", "Casual"]
    assert cache.tags_dictionary() == {"SuperStar": 2, "Netplay": 3}
    assert cache.users_dictionary() == {"1": "ProjectRio", "2": "MsNecromancer"}
    assert cache.users() == ["ProjectRio", "MsNecromancer"]
    df = cache.return_tags_df()
    assert df.index.name == "id"
    assert list(df["name"]) == ["Ranked", "SuperStar", "Netplay", "Casual"]
