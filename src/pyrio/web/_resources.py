"""The management namespaces: ``rio.communities``, ``rio.tags``, ``rio.tag_sets``,
``rio.users`` and ``rio.keys``, each in a sync and an async form.

Each method builds its request in ``_encode`` and hands it to the client, so the
two forms differ only in ``await``.
"""

from __future__ import annotations

# Runtime imports, so typing.get_type_hints() works on the public methods.
from collections.abc import Awaitable, Sequence  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Protocol, TypeVar

from . import _encode as encode
from ._models import (
    Community,
    CommunityKind,
    CommunityMember,
    IssuedKey,
    LadderGame,
    LadderRow,
    Tag,
    TagKind,
    TagSet,
    TagSetKind,
    User,
)

__all__ = [
    "AsyncCommunities",
    "AsyncKeys",
    "AsyncTagSets",
    "AsyncTags",
    "AsyncUsers",
    "Communities",
    "Keys",
    "TagSets",
    "Tags",
    "Users",
]

T = TypeVar("T")


class _Send(Protocol):
    def __call__(self, call: encode.Call[T], /) -> T: ...


class _AsyncSend(Protocol):
    def __call__(self, call: encode.Call[T], /) -> Awaitable[T]: ...


# --- sync -------------------------------------------------------------------


class Communities:
    """``rio.communities``: groups of players with their own tags and tag sets."""

    def __init__(self, send: _Send) -> None:
        self._send = send

    def list(self) -> list[Community]:
        """Every public community (every community, for site staff). Needs an API key."""
        return self._send(encode.list_communities())

    def create(
        self,
        name: str,
        *,
        description: str,
        private: bool,
        global_link: bool = False,
        kind: CommunityKind = CommunityKind.UNOFFICIAL,
    ) -> str | None:
        """Create a community you sponsor, and return its join link (``None`` if it has none).

        A public community always gets a link. Needs an API key and a Patreon
        tier with a sponsorship allowance.
        """
        return self._send(
            encode.create_community(
                name=name,
                kind=kind,
                private=private,
                global_link=global_link,
                description=description,
            )
        )

    def update(
        self,
        community_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        private: bool | None = None,
        global_link: bool | None = None,
        active_tag_set_limit: int | None = None,
    ) -> None:
        """Change a community you administer. Arguments left as ``None`` aren't changed."""
        self._send(
            encode.update_community(
                community_id,
                name=name,
                description=description,
                private=private,
                global_link=global_link,
                active_tag_set_limit=active_tag_set_limit,
            )
        )

    def join(self, name: str, *, url: str | None = None) -> bool:
        """Join a community, or ask to. Returns whether you're now an active member.

        A private community needs its join link (``url``) or an invitation;
        without either, this records a request for an admin to answer.
        """
        return self._send(encode.join_community(name, url=url))

    def leave(self, name: str) -> CommunityMember:
        """Leave a community; returns your membership row as it now stands."""
        return self._send(encode.leave_community(name))

    def invite(self, name: str, users: Sequence[str]) -> list[str]:
        """Invite users to a community you administer; returns the names invited."""
        return self._send(encode.invite(name, users))

    def members(self, name: str) -> list[CommunityMember]:
        """A community's membership rows. A private community's need a member's API key."""
        return self._send(encode.community_members(name))

    def tags(self, name: str) -> list[Tag]:
        """A community's tags. A private community's need a member's API key."""
        return self._send(encode.community_tags(name))

    def remove_members(self, name: str, users: Sequence[str]) -> list[CommunityMember]:
        """Remove members (not admins) from a community you administer."""
        return self._send(encode.manage_members(name, users, {"remove": True}))

    def ban_members(self, name: str, users: Sequence[str]) -> list[CommunityMember]:
        """Ban members (not admins) from a community you administer."""
        return self._send(encode.manage_members(name, users, {"ban": True}))

    def set_admins(self, name: str, users: Sequence[str], *, admin: bool) -> list[CommunityMember]:
        """Make active members admins (``admin=True``) or take it away."""
        return self._send(encode.manage_members(name, users, {"admin": admin}))

    def sponsor(self, name: str) -> str | None:
        """The name of the user sponsoring a community, or ``None``."""
        return self._send(encode.sponsor(name, "get"))

    def become_sponsor(self, name: str) -> None:
        """Sponsor a community that has no sponsor. Needs a sponsorship allowance."""
        self._send(encode.sponsor(name, "add"))

    def withdraw_sponsorship(self, name: str) -> None:
        """Stop sponsoring a community you sponsor."""
        self._send(encode.sponsor(name, "remove"))

    def generate_key(self, name: str) -> CommunityMember:
        """Issue yourself a new community key; it's on the returned row's ``key``."""
        return self._send(encode.community_key(name, "generate"))

    def revoke_key(self, name: str) -> CommunityMember:
        """Revoke your community key."""
        return self._send(encode.community_key(name, "revoke"))

    def generate_all_keys(self, name: str) -> dict[str, str]:
        """Issue every member a new key, as an admin; returns user name to key."""
        return self._send(encode.all_community_keys(name))


class Tags:
    """``rio.tags``: labels that games are filtered by."""

    def __init__(self, send: _Send) -> None:
        self._send = send

    def list(
        self,
        *,
        kinds: Sequence[TagKind] | None = None,
        community_ids: Sequence[int] | None = None,
    ) -> list[Tag]:
        """Every tag, or those of the given kinds and communities."""
        return self._send(encode.list_tags(kinds=kinds, community_ids=community_ids))

    def create(
        self,
        name: str,
        *,
        description: str,
        kind: TagKind,
        community: str,
        gecko_code: str | None = None,
        gecko_code_description: str | None = None,
    ) -> Tag:
        """Create a tag in a community you administer.

        A ``GECKO_CODE`` tag needs both code fields.
        """
        return self._send(
            encode.create_tag(
                name=name,
                description=description,
                kind=kind,
                community=community,
                gecko_code=gecko_code,
                gecko_code_description=gecko_code_description,
            )
        )

    def update(
        self,
        tag_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        kind: TagKind | None = None,
        gecko_code: str | None = None,
        gecko_code_description: str | None = None,
    ) -> None:
        """Change a tag. Arguments left as ``None`` aren't changed."""
        self._send(
            encode.update_tag(
                tag_id,
                name=name,
                description=description,
                kind=kind,
                gecko_code=gecko_code,
                gecko_code_description=gecko_code_description,
            )
        )


class TagSets:
    """``rio.tag_sets``: what the client and site currently call game modes."""

    def __init__(self, send: _Send) -> None:
        self._send = send

    def list(
        self, *, active_only: bool = False, community_ids: Sequence[int] | None = None
    ) -> list[TagSet]:
        """Every tag set (but test ones), or those active now or in the given communities."""
        return self._send(
            encode.list_tag_sets(active_only=active_only, community_ids=community_ids)
        )

    def get(self, tag_set_id: int) -> TagSet:
        """One tag set by id, such as a ``GameSummary.tag_set_id``."""
        return self._send(encode.get_tag_set(tag_set_id))

    def create(
        self,
        name: str,
        *,
        description: str,
        kind: TagSetKind,
        community: str,
        start_time: datetime,
        end_time: datetime,
        tag_ids: Sequence[int] | None = None,
        copy_tags_from: int | None = None,
    ) -> TagSet:
        """Create a tag set in a sponsored community you administer.

        ``copy_tags_from`` is another tag set's id whose tags it starts with.
        """
        return self._send(
            encode.create_tag_set(
                name=name,
                description=description,
                kind=kind,
                community=community,
                start_time=start_time,
                end_time=end_time,
                tag_ids=tag_ids,
                copy_tags_from=copy_tags_from,
            )
        )

    def update(
        self,
        tag_set_id: int,
        *,
        name: str | None = None,
        kind: TagSetKind | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        add_tag_ids: Sequence[int] | None = None,
        remove_tag_ids: Sequence[int] | None = None,
    ) -> None:
        """Change a tag set. Arguments left as ``None`` aren't changed."""
        self._send(
            encode.update_tag_set(
                tag_set_id,
                name=name,
                kind=kind,
                start_time=start_time,
                end_time=end_time,
                add_tag_ids=add_tag_ids,
                remove_tag_ids=remove_tag_ids,
            )
        )

    def delete(self, name: str) -> None:
        """Delete a tag set no game has been played under."""
        self._send(encode.delete_tag_set(name))

    def ladder(self, name: str) -> list[LadderRow]:
        """A tag set's standings, highest rating first."""
        return self._send(encode.ladder(name))

    def ladder_games(
        self,
        names: Sequence[str],
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[LadderGame]:
        """The 50 most recent results counted toward these tag sets' ladders."""
        return self._send(encode.ladder_games(names, start_time=start_time, end_time=end_time))


class Users:
    """``rio.users``: accounts and the groups they're in."""

    def __init__(self, send: _Send) -> None:
        self._send = send

    def list(self, *, include_unverified: bool = False) -> list[User]:
        """Every verified account (every account, with ``include_unverified``)."""
        return self._send(encode.users(include_unverified=include_unverified))

    def communities(self, user: str) -> list[Community]:
        """The communities a user is an active member of."""
        return self._send(encode.user_communities(user))

    def sponsored_communities(self, user: str) -> list[Community]:
        """The communities a user sponsors."""
        return self._send(encode.user_sponsored_communities(user))

    def is_in_group(self, user: str, group: str) -> bool:
        """Whether a user is in a group, such as ``"TrustedUser"``. Staff only."""
        return self._send(encode.is_in_group(user, group))

    def group_members(self, group: str) -> list[str]:
        """The names of a group's members. Staff only."""
        return self._send(encode.group_members(group))

    def add_to_group(self, user: str, group: str) -> None:
        """Add a user to a group. Staff only, and needs a session from ``login()``."""
        self._send(encode.add_to_group(user, group))

    def remove_from_group(self, user: str, group: str) -> None:
        """Remove a user from a group. Staff only, and needs a session from ``login()``."""
        self._send(encode.remove_from_group(user, group))


class Keys:
    """``rio.keys``: your account's API key. Both calls need a session from ``login()``."""

    def __init__(self, send: _Send) -> None:
        self._send = send

    def create(self) -> IssuedKey:
        """Mint your account's API key (one per account). Store it: it's shown once."""
        return self._send(encode.create_api_key())

    def reset(self) -> IssuedKey:
        """Replace your API key; the old one stops working at once."""
        return self._send(encode.reset_api_key())


# --- async ------------------------------------------------------------------


class AsyncCommunities:
    """The async form of :class:`Communities`."""

    def __init__(self, send: _AsyncSend) -> None:
        self._send = send

    async def list(self) -> list[Community]:
        return await self._send(encode.list_communities())

    async def create(
        self,
        name: str,
        *,
        description: str,
        private: bool,
        global_link: bool = False,
        kind: CommunityKind = CommunityKind.UNOFFICIAL,
    ) -> str | None:
        return await self._send(
            encode.create_community(
                name=name,
                kind=kind,
                private=private,
                global_link=global_link,
                description=description,
            )
        )

    async def update(
        self,
        community_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        private: bool | None = None,
        global_link: bool | None = None,
        active_tag_set_limit: int | None = None,
    ) -> None:
        await self._send(
            encode.update_community(
                community_id,
                name=name,
                description=description,
                private=private,
                global_link=global_link,
                active_tag_set_limit=active_tag_set_limit,
            )
        )

    async def join(self, name: str, *, url: str | None = None) -> bool:
        return await self._send(encode.join_community(name, url=url))

    async def leave(self, name: str) -> CommunityMember:
        return await self._send(encode.leave_community(name))

    async def invite(self, name: str, users: Sequence[str]) -> list[str]:
        return await self._send(encode.invite(name, users))

    async def members(self, name: str) -> list[CommunityMember]:
        return await self._send(encode.community_members(name))

    async def tags(self, name: str) -> list[Tag]:
        return await self._send(encode.community_tags(name))

    async def remove_members(self, name: str, users: Sequence[str]) -> list[CommunityMember]:
        return await self._send(encode.manage_members(name, users, {"remove": True}))

    async def ban_members(self, name: str, users: Sequence[str]) -> list[CommunityMember]:
        return await self._send(encode.manage_members(name, users, {"ban": True}))

    async def set_admins(
        self, name: str, users: Sequence[str], *, admin: bool
    ) -> list[CommunityMember]:
        return await self._send(encode.manage_members(name, users, {"admin": admin}))

    async def sponsor(self, name: str) -> str | None:
        return await self._send(encode.sponsor(name, "get"))

    async def become_sponsor(self, name: str) -> None:
        await self._send(encode.sponsor(name, "add"))

    async def withdraw_sponsorship(self, name: str) -> None:
        await self._send(encode.sponsor(name, "remove"))

    async def generate_key(self, name: str) -> CommunityMember:
        return await self._send(encode.community_key(name, "generate"))

    async def revoke_key(self, name: str) -> CommunityMember:
        return await self._send(encode.community_key(name, "revoke"))

    async def generate_all_keys(self, name: str) -> dict[str, str]:
        return await self._send(encode.all_community_keys(name))


class AsyncTags:
    """The async form of :class:`Tags`."""

    def __init__(self, send: _AsyncSend) -> None:
        self._send = send

    async def list(
        self,
        *,
        kinds: Sequence[TagKind] | None = None,
        community_ids: Sequence[int] | None = None,
    ) -> list[Tag]:
        return await self._send(encode.list_tags(kinds=kinds, community_ids=community_ids))

    async def create(
        self,
        name: str,
        *,
        description: str,
        kind: TagKind,
        community: str,
        gecko_code: str | None = None,
        gecko_code_description: str | None = None,
    ) -> Tag:
        return await self._send(
            encode.create_tag(
                name=name,
                description=description,
                kind=kind,
                community=community,
                gecko_code=gecko_code,
                gecko_code_description=gecko_code_description,
            )
        )

    async def update(
        self,
        tag_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        kind: TagKind | None = None,
        gecko_code: str | None = None,
        gecko_code_description: str | None = None,
    ) -> None:
        await self._send(
            encode.update_tag(
                tag_id,
                name=name,
                description=description,
                kind=kind,
                gecko_code=gecko_code,
                gecko_code_description=gecko_code_description,
            )
        )


class AsyncTagSets:
    """The async form of :class:`TagSets`."""

    def __init__(self, send: _AsyncSend) -> None:
        self._send = send

    async def list(
        self, *, active_only: bool = False, community_ids: Sequence[int] | None = None
    ) -> list[TagSet]:
        return await self._send(
            encode.list_tag_sets(active_only=active_only, community_ids=community_ids)
        )

    async def get(self, tag_set_id: int) -> TagSet:
        return await self._send(encode.get_tag_set(tag_set_id))

    async def create(
        self,
        name: str,
        *,
        description: str,
        kind: TagSetKind,
        community: str,
        start_time: datetime,
        end_time: datetime,
        tag_ids: Sequence[int] | None = None,
        copy_tags_from: int | None = None,
    ) -> TagSet:
        return await self._send(
            encode.create_tag_set(
                name=name,
                description=description,
                kind=kind,
                community=community,
                start_time=start_time,
                end_time=end_time,
                tag_ids=tag_ids,
                copy_tags_from=copy_tags_from,
            )
        )

    async def update(
        self,
        tag_set_id: int,
        *,
        name: str | None = None,
        kind: TagSetKind | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        add_tag_ids: Sequence[int] | None = None,
        remove_tag_ids: Sequence[int] | None = None,
    ) -> None:
        await self._send(
            encode.update_tag_set(
                tag_set_id,
                name=name,
                kind=kind,
                start_time=start_time,
                end_time=end_time,
                add_tag_ids=add_tag_ids,
                remove_tag_ids=remove_tag_ids,
            )
        )

    async def delete(self, name: str) -> None:
        await self._send(encode.delete_tag_set(name))

    async def ladder(self, name: str) -> list[LadderRow]:
        return await self._send(encode.ladder(name))

    async def ladder_games(
        self,
        names: Sequence[str],
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[LadderGame]:
        return await self._send(
            encode.ladder_games(names, start_time=start_time, end_time=end_time)
        )


class AsyncUsers:
    """The async form of :class:`Users`."""

    def __init__(self, send: _AsyncSend) -> None:
        self._send = send

    async def list(self, *, include_unverified: bool = False) -> list[User]:
        return await self._send(encode.users(include_unverified=include_unverified))

    async def communities(self, user: str) -> list[Community]:
        return await self._send(encode.user_communities(user))

    async def sponsored_communities(self, user: str) -> list[Community]:
        return await self._send(encode.user_sponsored_communities(user))

    async def is_in_group(self, user: str, group: str) -> bool:
        return await self._send(encode.is_in_group(user, group))

    async def group_members(self, group: str) -> list[str]:
        return await self._send(encode.group_members(group))

    async def add_to_group(self, user: str, group: str) -> None:
        await self._send(encode.add_to_group(user, group))

    async def remove_from_group(self, user: str, group: str) -> None:
        await self._send(encode.remove_from_group(user, group))


class AsyncKeys:
    """The async form of :class:`Keys`."""

    def __init__(self, send: _AsyncSend) -> None:
        self._send = send

    async def create(self) -> IssuedKey:
        return await self._send(encode.create_api_key())

    async def reset(self) -> IssuedKey:
        return await self._send(encode.reset_api_key())
