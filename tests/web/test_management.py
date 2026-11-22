"""Every management call sends the method, path and body its route reads, sync and async."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
import respx

from pyrio.web import AsyncRioClient, RioClient, TagKind, TagSetKind

if TYPE_CHECKING:
    from collections.abc import Iterator

BASE = "https://api.projectrio.app"

_MEMBER = {
    "id": 1,
    "user_id": 2,
    "admin": False,
    "active": True,
    "invited": False,
    "banned": None,
    "date_joined": None,
}
_COMMUNITY = {
    "id": 1,
    "name": "NNL",
    "type": "Unofficial",
    "private": False,
    "url": None,
    "desc": None,
    "tag_set_limit": 5,
    "date_created": None,
}
_TAG = {
    "id": 5,
    "comm_id": 1,
    "name": "NNL",
    "type": "Component",
    "desc": None,
    "active": True,
    "date_created": None,
}
_NNL = {"community_name": "NNL"}

# (namespace, method, args, kwargs, HTTP method, path, response, expected body or query)
MANAGEMENT: list[tuple[str, str, tuple[Any, ...], dict[str, Any], str, str, Any, Any]] = [
    (
        "communities",
        "update",
        (7,),
        {"name": "N", "private": True, "global_link": False},
        "POST",
        "/community/update",
        "Success",
        {"community_id": 7, "name": "N", "private": True, "link": False},
    ),
    (
        "communities",
        "join",
        ("NNL",),
        {"url": "abc"},
        "POST",
        "/community/join",
        {"community name": "NNL", "active": True},
        _NNL | {"URL": "abc"},
    ),
    (
        "communities",
        "leave",
        ("NNL",),
        {},
        "POST",
        "/community/leave",
        {"community name": "NNL", "member": _MEMBER},
        _NNL,
    ),
    (
        "communities",
        "invite",
        ("NNL", ["Zed"]),
        {},
        "POST",
        "/community/invite",
        {"Invited Users": ["Zed"]},
        _NNL | {"invite_list": ["Zed"]},
    ),
    ("communities", "tags", ("NNL",), {}, "POST", "/community/tags", {"Tags": [_TAG]}, _NNL),
    (
        "communities",
        "remove_members",
        ("NNL", ["Zed"]),
        {},
        "POST",
        "/community/manage",
        {"members": [_MEMBER]},
        _NNL | {"user_list": [{"username": "Zed", "remove": True}]},
    ),
    (
        "communities",
        "set_admins",
        ("NNL", ["Zed"]),
        {"admin": False},
        "POST",
        "/community/manage",
        {"members": [_MEMBER]},
        _NNL | {"user_list": [{"username": "Zed", "admin": False}]},
    ),
    (
        "communities",
        "sponsor",
        ("NNL",),
        {},
        "POST",
        "/community/sponsor",
        {"sponsor": None},
        _NNL | {"action": "get"},
    ),
    (
        "communities",
        "become_sponsor",
        ("NNL",),
        {},
        "POST",
        "/community/sponsor",
        {"sponsor": "MattGree"},
        _NNL | {"action": "add"},
    ),
    (
        "communities",
        "withdraw_sponsorship",
        ("NNL",),
        {},
        "POST",
        "/community/sponsor",
        {"sponsor": None},
        _NNL | {"action": "remove"},
    ),
    (
        "communities",
        "revoke_key",
        ("NNL",),
        {},
        "POST",
        "/community/key",
        [_MEMBER],
        _NNL | {"action": "revoke"},
    ),
    (
        "communities",
        "generate_all_keys",
        ("NNL",),
        {},
        "POST",
        "/community/key",
        [{"user": "Zed", "comm_key": "WxYz"}],
        _NNL | {"action": "generate_all"},
    ),
    (
        "tags",
        "create",
        ("Hazards Off",),
        {
            "description": "d",
            "kind": TagKind.GECKO_CODE,
            "community": "NNL",
            "gecko_code": "0 0\n",
            "gecko_code_description": "g",
        },
        "POST",
        "/tag/create",
        _TAG,
        {
            "name": "Hazards Off",
            "desc": "d",
            "community_name": "NNL",
            "type": "Gecko Code",
            "gecko_code": "0 0\n",
            "gecko_code_desc": "g",
        },
    ),
    (
        "tags",
        "update",
        (5,),
        {"description": "new", "kind": TagKind.COMPONENT},
        "POST",
        "/tag/update",
        "Success",
        {"tag_id": 5, "desc": "new", "type": "Component"},
    ),
    (
        "tag_sets",
        "update",
        (198,),
        {
            "name": "S13",
            "kind": TagSetKind.LEAGUE,
            "add_tag_ids": [1],
            "remove_tag_ids": [2],
            "end_time": datetime(2026, 1, 1, tzinfo=UTC),
        },
        "POST",
        "/tag_set/update",
        "Success",
        {
            "tag_set_id": 198,
            "name": "S13",
            "type": "League",
            "add_tag_ids": [1],
            "remove_tag_ids": [2],
            "end_date": 1767225600,
        },
    ),
    ("tag_sets", "delete", ("S13",), {}, "POST", "/tag_set/delete", {"msg": "ok"}, {"name": "S13"}),
    (
        "users",
        "communities",
        ("MattGree",),
        {},
        "GET",
        "/user/community/",
        {"communities": [_COMMUNITY]},
        [("username", "MattGree")],
    ),
    (
        "users",
        "sponsored_communities",
        ("MattGree",),
        {},
        "GET",
        "/user/community/sponsor/",
        {"sponsored_communities": [_COMMUNITY]},
        [("username", "MattGree")],
    ),
    (
        "users",
        "is_in_group",
        ("MattGree", "Admin"),
        {},
        "GET",
        "/user_group/check_for_member",
        {"is_member": True},
        [("username", "MattGree"), ("group_name", "Admin")],
    ),
    (
        "users",
        "group_members",
        ("Admin",),
        {},
        "GET",
        "/user_group/members",
        {"users": ["MattGree"]},
        [("group_name", "Admin")],
    ),
    (
        "users",
        "list",
        (),
        {"include_unverified": True},
        "GET",
        "/user/all/",
        {"users": {}},
        [("verified", "false")],
    ),
]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


def _check(route: respx.Route, method: str, sent: Any) -> None:
    request = route.calls.last.request
    assert request.method == method
    if method == "GET":
        assert list(request.url.params.multi_items()) == sent
    else:
        assert json.loads(request.content) == sent


@pytest.mark.parametrize(
    ("namespace", "name", "args", "kwargs", "method", "path", "response", "sent"),
    MANAGEMENT,
    ids=[f"{row[0]}.{row[1]}" for row in MANAGEMENT],
)
def test_management_call(mock, namespace, name, args, kwargs, method, path, response, sent):
    route = mock.request(method, path).respond(json=response)
    with RioClient(api_key="k") as rio:
        getattr(getattr(rio, namespace), name)(*args, **kwargs)
    _check(route, method, sent)


def test_management_calls_async():
    async def run() -> None:
        async with AsyncRioClient(api_key="k") as rio:
            for namespace, name, args, kwargs, method, path, response, sent in MANAGEMENT:
                with respx.mock(base_url=BASE) as router:
                    route = router.request(method, path).respond(json=response)
                    await getattr(getattr(rio, namespace), name)(*args, **kwargs)
                    _check(route, method, sent)

    asyncio.run(run())


def test_group_membership_changes_use_the_session(mock):
    mock.post("/login/").respond(json={"msg": "", "username": "MattGree", "access_token": "t"})
    add = mock.post("/user_group/add_user").respond(json="User added to User Group.")
    remove = mock.post("/user_group/remove_user").respond(json="User removed from UserGroup.")
    with RioClient(api_key="k") as rio:
        rio.login(email="e", password="p")
        rio.users.add_to_group("Zed", "TrustedUser")
        rio.users.remove_from_group("Zed", "TrustedUser")
    assert json.loads(add.calls.last.request.content) == {
        "username": "Zed",
        "group_name": "TrustedUser",
    }
    assert remove.calls.last.request.headers["Authorization"] == "Bearer t"
