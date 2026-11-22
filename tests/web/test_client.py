"""The client's lifecycle: credentials, errors, retries, timeouts, caching, async."""

from __future__ import annotations

import asyncio
import inspect
import subprocess
import sys
import typing
from datetime import timedelta

import httpx
import pytest
import respx

import pyrio
from pyrio.web import (
    APIConnectionError,
    APIError,
    APIResponseError,
    APITimeoutError,
    AsyncRioClient,
    AuthenticationError,
    DiskCache,
    NotFoundError,
    RioClient,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

BASE = "https://api.projectrio.app"

WERKZEUG_409 = """<!doctype html>
<html lang=en>
<title>409 Conflict</title>
<h1>Conflict</h1>
<p>Could not find TagSet with name=nope &amp; co</p>
"""


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


# --- credentials ----------------------------------------------------------------


def test_constructor_reads_nothing_implicitly(monkeypatch):
    monkeypatch.setenv("PYRIO_API_KEY", "from-env")
    with RioClient() as rio:
        assert rio.api_key is None


def test_from_env_reads_pyrio_api_key(monkeypatch):
    monkeypatch.setenv("PYRIO_API_KEY", "from-env")
    with RioClient.from_env() as rio:
        assert rio.api_key == "from-env"
    monkeypatch.delenv("PYRIO_API_KEY")
    with RioClient.from_env() as rio:
        assert rio.api_key is None


def test_authed_endpoint_without_a_key_raises_before_any_request(mock):
    with RioClient() as rio:
        with pytest.raises(AuthenticationError, match="needs an API key"):
            rio.communities.list()
        with pytest.raises(AuthenticationError, match="needs an API key"):
            rio.delete_game(1)
    assert len(mock.calls) == 0


def test_session_only_endpoint_refuses_an_api_key(mock):
    with RioClient(api_key="k") as rio, pytest.raises(AuthenticationError, match="session"):
        rio.keys.create()
    assert len(mock.calls) == 0


def test_login_session_replaces_the_key(mock):
    mock.post("/login/").respond(
        json={"msg": "login successful", "username": "MattGree", "access_token": "jwt"}
    )
    register = mock.post("/api_key/register/").respond(
        json={"api_key": "new-key", "email_sent": True}
    )
    with RioClient(api_key="old") as rio:
        assert rio.login(email="m@example.com", password="pw") == "MattGree"
        assert rio.user == "MattGree"
        issued = rio.keys.create()
        assert (issued.key, issued.was_emailed) == ("new-key", True)
        assert register.calls.last.request.headers["Authorization"] == "Bearer jwt"
        assert rio.api_key == "old"  # nothing changed behind the caller's back
        rio.logout()
        assert rio.user is None


def test_public_endpoint_works_without_a_key(mock):
    route = mock.get("/games/").respond(json={"games": []})
    with RioClient() as rio:
        assert rio.games() == []
    assert "Authorization" not in route.calls.last.request.headers


# --- errors -----------------------------------------------------------------------


def test_status_errors_carry_the_werkzeug_reason(mock):
    mock.post("/tag_set/ladder/").respond(
        409, text=WERKZEUG_409, headers={"content-type": "text/html"}
    )
    with RioClient() as rio, pytest.raises(APIError) as info:
        rio.tag_sets.ladder("nope")
    error = info.value
    assert type(error) is APIError
    assert error.status_code == 409
    assert "Could not find TagSet with name=nope & co" in str(error)
    assert isinstance(error, pyrio.RioError)


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, AuthenticationError), (403, AuthenticationError), (404, NotFoundError)],
)
def test_status_codes_map_to_error_types(mock, status, kind):
    mock.get("/games/").respond(status, text="<p>no</p>")
    with RioClient() as rio, pytest.raises(kind) as info:
        rio.games()
    assert info.value.status_code == status


def test_non_json_success_is_a_response_error(mock):
    mock.get("/games/").respond(200, text="Error: something", headers={"content-type": "text/html"})
    with RioClient() as rio, pytest.raises(APIResponseError, match="expected JSON"):
        rio.games()


def test_timeouts_and_connection_failures_are_wrapped(mock):
    mock.get("/games/").mock(side_effect=httpx.ReadTimeout("slow"))
    mock.get("/stats/").mock(side_effect=httpx.ConnectError("down"))
    with RioClient(max_retries=0) as rio:
        with pytest.raises(APITimeoutError) as timeout:
            rio.games()
        assert isinstance(timeout.value, TimeoutError)
        assert isinstance(timeout.value, APIConnectionError)
        with pytest.raises(APIConnectionError, match="ConnectError"):
            rio.stats()


def test_default_timeout_is_set():
    with RioClient() as rio:
        assert rio.timeout == 30.0
        assert rio._http.timeout.read == 30.0


# --- retries ----------------------------------------------------------------------


def test_gets_retry_transient_failures(mock):
    route = mock.get("/games/").mock(
        side_effect=[
            httpx.Response(503),
            httpx.ConnectError("blip"),
            httpx.Response(200, json={"games": []}),
        ]
    )
    with RioClient(max_retries=2) as rio:
        assert rio.games() == []
    assert route.call_count == 3


def test_retries_stop_at_max_retries(mock):
    route = mock.get("/games/").respond(503)
    with RioClient(max_retries=1) as rio, pytest.raises(APIError) as info:
        rio.games()
    assert info.value.status_code == 503
    assert route.call_count == 2


def test_server_errors_that_repeat_are_not_retried(mock):
    route = mock.get("/games/").respond(500)
    with RioClient(max_retries=3) as rio, pytest.raises(APIError):
        rio.games()
    assert route.call_count == 1


def test_posts_are_never_retried(mock):
    route = mock.post("/tag_set/ladder/").respond(503)
    with RioClient(max_retries=3) as rio, pytest.raises(APIError):
        rio.tag_sets.ladder("S13")
    assert route.call_count == 1


# --- lifecycle --------------------------------------------------------------------


def test_context_manager_closes_its_own_client_only():
    with RioClient() as rio:
        pass
    assert rio._http.is_closed

    supplied = httpx.Client()
    with RioClient(http_client=supplied):
        pass
    assert not supplied.is_closed
    supplied.close()


def test_repr_hides_the_key():
    with RioClient(api_key="secret") as rio:
        assert "secret" not in repr(rio)
        assert "api_key" in repr(rio)


# --- cache ------------------------------------------------------------------------


def test_cache_serves_reference_data_from_json(mock, contract, tmp_path):
    route = mock.post("/tag_set/list").respond(json=contract("tag_sets.json"))
    cache = DiskCache(tmp_path / "rio", ttl=timedelta(minutes=5))
    with RioClient(cache=cache) as rio:
        first = rio.tag_sets.list()
        second = rio.tag_sets.list()
    assert first == second
    assert route.call_count == 1
    files = list((tmp_path / "rio").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    cache.clear()
    assert list((tmp_path / "rio").iterdir()) == []


def test_cache_ignores_non_reference_calls(mock, tmp_path):
    route = mock.get("/games/").respond(json={"games": []})
    with RioClient(cache=DiskCache(tmp_path)) as rio:
        rio.games()
        rio.games()
    assert route.call_count == 2
    assert list(tmp_path.iterdir()) == []


def test_cache_entries_expire(contract, tmp_path, monkeypatch):
    cache = DiskCache(tmp_path, ttl=10)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}
    real = __import__("time").time
    monkeypatch.setattr("pyrio.web._cache.time.time", lambda: real() + 11)
    assert cache.get("k") is None


def test_cache_creates_nothing_at_construction(tmp_path):
    DiskCache(tmp_path / "later")
    assert not (tmp_path / "later").exists()
    with pytest.raises(ValueError, match="ttl"):
        DiskCache(tmp_path, ttl=0)


# --- async ------------------------------------------------------------------------


def _public_methods(cls: type) -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_")
    }


def test_async_client_mirrors_the_sync_client():
    sync = _public_methods(RioClient)
    asynchronous = _public_methods(AsyncRioClient)
    sync.pop("close")
    asynchronous.pop("aclose")
    assert sync.keys() == asynchronous.keys()
    for name, signature in sync.items():
        assert str(asynchronous[name]).replace("AsyncClient", "Client") == str(signature), name
        if name not in ("from_env", "logout"):
            assert inspect.iscoroutinefunction(getattr(AsyncRioClient, name)), name


def test_async_resources_mirror_the_sync_resources():
    with RioClient() as rio:
        pairs = [
            (type(rio.communities), "communities"),
            (type(rio.tags), "tags"),
            (type(rio.tag_sets), "tag_sets"),
            (type(rio.users), "users"),
            (type(rio.keys), "keys"),
        ]
    ario = AsyncRioClient()
    for sync_type, attribute in pairs:
        async_type = type(getattr(ario, attribute))
        assert _public_methods(sync_type) == _public_methods(async_type), attribute
    asyncio.run(ario.aclose())


def test_public_signatures_resolve_at_runtime():
    # RioWebCLI derives prompts from these, so get_type_hints must work.
    for cls in (RioClient, AsyncRioClient):
        for name, member in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith("_"):
                typing.get_type_hints(member)
    with RioClient() as rio:
        typing.get_type_hints(type(rio.tag_sets).create)


def test_async_client_round_trip(contract):
    async def run() -> None:
        with respx.mock(base_url=BASE) as router:
            router.get("/games/").respond(json=contract("games.json"))
            router.get("/stats/").mock(
                side_effect=[httpx.Response(502), httpx.Response(200, json=contract("stats.json"))]
            )
            async with AsyncRioClient(api_key="k") as rio:
                games = await rio.games()
                stats = await rio.stats()
                with pytest.raises(AuthenticationError):
                    await rio.keys.create()
            assert rio._http.is_closed
        assert games[0].game_id == 3896251267
        assert stats[0].batting is not None

    asyncio.run(run())


# --- import ------------------------------------------------------------------------


def test_import_without_httpx_explains_the_extra():
    code = (
        "import sys; sys.modules['httpx'] = None\n"
        "try:\n"
        "    import pyrio.web\n"
        "except ImportError as e:\n"
        "    print(e)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out == "pyrio.web needs httpx: pip install 'projectrio[web]'"
