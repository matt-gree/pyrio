from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Optional, Union

import requests

from .api import (
    Endpoint,
    EventsParameterList,
    GamesParameterList,
    LandingDataParameterList,
    ParameterList,
    StarChancesParameterList,
    StatsParameterList,
)
from .exceptions import raise_for_status
from .rio_value import lookup, Tables

BASE_URL = "https://api.projectrio.app"


def _load_keys_from_file() -> dict:
    """Try to load rio_key and api_key from rio_key.json in the current directory."""
    if os.path.exists("rio_key.json"):
        with open("rio_key.json", "r") as f:
            data = json.load(f)
        return {key: data.get(key) for key in ("rio_key", "api_key")}
    return {}


class RioWeb:
    """Unified client for the Project Rio API.

    Usage:
        client = RioWeb()                           # credential from env or rio_key.json
        client = RioWeb(api_key="your_key_here")    # explicit

        games_df = client.get_games(tag=["tournament"])
        games_raw = client.get_games(tag=["tournament"], raw=True)

    Credentials, in the order this client looks for them:

        api_key=   /  PYRIO_API_KEY  /  "api_key" in rio_key.json
        rio_key=   /  PYRIO_KEY      /  "rio_key" in rio_key.json

    Public reads -- games, stats, events, characters, game-mode lists -- need
    no credential at all. Everything else is an API key's job: Rio Web bounds
    what a credential may do by its kind, and a Rio Key belongs to the game
    client (signing in, reading game modes, submitting games) rather than to a
    person managing communities. A Rio Key still works for management calls
    today and will stop; `request_api_key()` is the one-time migration.

    A few operations need a session rather than any key -- group membership,
    password or email changes, key rotation, account deletion, another user's
    IP history -- because a credential may not be used to increase its own
    authority. `login()` provides one.
    """

    def __init__(self, rio_key: str = None, api_key: str = None,
                 base_url: str = BASE_URL, cache_dir: str = None):
        keys = _load_keys_from_file()
        self.api_key = api_key or os.environ.get("PYRIO_API_KEY") or keys.get("api_key")
        self.rio_key = rio_key or os.environ.get("PYRIO_KEY") or keys.get("rio_key")
        if not self.api_key and not self.rio_key:
            print("WARNING: No Rio Web credential found. Set PYRIO_API_KEY (preferred) or "
                  "PYRIO_KEY, pass api_key=/rio_key=, or create rio_key.json.")
        self._warned_about_rio_key = False
        self.base_url = base_url
        self._cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._cache = None

    @property
    def cache(self):
        """Lazy-loaded CompleterCache for game mode / user lookups."""
        if self._cache is None:
            from .web_caching import CompleterCache
            kwargs = {}
            if self._cache_dir is not None:
                kwargs["cache_dir"] = self._cache_dir
            self._cache = CompleterCache(self, **kwargs)
        return self._cache

    # -------------------------------------------------------------------------
    # Internal HTTP methods
    # -------------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict = None, authed: bool = False) -> dict:
        url = self.base_url + endpoint
        response = self.session.get(url, params=params,
                                    headers=self._auth_headers() if authed else None)
        raise_for_status(response)
        return response.json()

    def _post(self, endpoint: str, data: dict = None, authed: bool = False) -> dict:
        url = self.base_url + endpoint
        response = self.session.post(url, json=data,
                                     headers=self._auth_headers() if authed else None)
        raise_for_status(response)
        return response.json()

    def _post_authed(self, endpoint: str, data: dict = None) -> dict:
        return self._post(endpoint, {} if data is None else data, authed=True)

    def _auth_headers(self) -> dict:
        """The credential to present on this request, as a header.

        Three things are going on here.

        **The API key is preferred.** Rio Web is moving to a model where a
        credential's *kind* bounds what it may do: a Rio Key belongs to the game
        client and is trusted for signing in, reading game modes and submitting
        games, while an API key is what a person at a terminal uses -- managing
        communities, game modes and moderation. They are deliberately disjoint,
        so a Rio Key will stop being accepted for the management calls on this
        client no matter who owns it. Run `request_api_key()` once; see the
        warning below.

        **It goes in `Authorization`, not the body or the query string.** A
        credential in a query string ends up in the server's access logs, which
        is why this replaced the old `rio_key` body field and `_key_params()`.
        The field is the standard one rather than a private `X-Rio-Auth`
        because `Authorization` is what the rest of the stack already treats as
        a secret: shared caches must not reuse a response to a request carrying
        it, HTTP clients drop it across a cross-origin redirect, and log
        pipelines redact it by default. A custom header name gets none of that.

        The scheme names are `ApiKey` and `RioKey` -- RFC 9110's
        `credentials = auth-scheme [ 1*SP token68 ]`, matched case-insensitively
        by the server. The hyphenated `api-key`/`rio-key` spellings this used to
        send are **not** accepted: they went with `X-Rio-Auth`, which never
        shipped, so there was no reason to carry two names for one scheme.

        **Nothing is sent when a session exists.** `login()` puts
        `Authorization: Bearer <jwt>` on the session, and a per-request header
        of the same name replaces it -- a key and a session share one field now,
        so they cannot both be sent. Returning `{}` here is what lets the
        session's token through, and that matters because the ceiling
        operations (group membership, password, key rotation) are session-only:
        a key reaching them is refused. See login().
        """
        if self._has_session:
            return {}
        if self.api_key:
            return {"Authorization": f"ApiKey {self.api_key}"}
        if self.rio_key:
            self._warn_about_rio_key()
            return {"Authorization": f"RioKey {self.rio_key}"}
        return {}

    def _warn_about_rio_key(self) -> None:
        """Say once, not per call, that a Rio Key is the wrong credential here."""
        if self._warned_about_rio_key:
            return
        self._warned_about_rio_key = True
        print("WARNING: using your Rio Key for a management call. Rio Web is moving these "
              "to API keys and will stop accepting a Rio Key for them. To get one: "
              "client.login(email, password) then client.request_api_key(), and set "
              "PYRIO_API_KEY or put api_key in rio_key.json.")

    @property
    def _has_session(self) -> bool:
        """True once login() has succeeded and not been undone by logout()."""
        return "Authorization" in self.session.headers

    @staticmethod
    def _strip_value(v):
        """Remove all whitespace from a string or list-of-strings value."""
        if isinstance(v, str):
            return "".join(v.split())
        if isinstance(v, list):
            return ["".join(item.split()) if isinstance(item, str) else item for item in v]
        return v

    @staticmethod
    def _serialize_params(params=None, kwargs: dict = None) -> dict:
        """Convert a ParameterList dataclass or kwargs into a dict for the API."""
        if params is not None:
            if isinstance(params, ParameterList):
                result = {k: v for k, v in asdict(params).items() if v is not None}
            elif isinstance(params, dict):
                result = {k: v for k, v in params.items() if v is not None}
            else:
                result = {}
        else:
            result = {}
        if kwargs:
            result.update({k: v for k, v in kwargs.items() if v is not None})
        # Strip whitespace from all string values
        return {k: RioWeb._strip_value(v) for k, v in result.items()}

    # -------------------------------------------------------------------------
    # Data endpoints (GET) - return DataFrames by default, raw=True for dict
    # -------------------------------------------------------------------------

    def get_games(self, params: Union[GamesParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch games data. Returns a DataFrame with winner/loser columns, timestamps, and resolved names."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.GAMES, serialized)
        if raw:
            return response
        return self._process_games(response)

    def get_stats(self, params: Union[StatsParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch stats data. Returns a DataFrame with grouping columns and flat stat columns (Category_stat)."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.STATS, serialized)
        if raw:
            return response
        return self._process_stats(response, serialized)

    def get_events(self, params: Union[EventsParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch event-level data."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.EVENTS, serialized)
        if raw:
            return response
        import pandas as pd
        return pd.DataFrame(response.get("Events", response.get("events", [])))

    def get_landing_data(self, params: Union[LandingDataParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch landing data (ball contact/landing positions)."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.LANDING_DATA, serialized)
        if raw:
            return response
        import pandas as pd
        return pd.DataFrame(response.get("Data", []))

    def get_star_chances(self, params: Union[StarChancesParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch star chance data."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.STAR_CHANCES, serialized)
        if raw:
            return response
        import pandas as pd
        return pd.DataFrame(response.get("Star Chances", response.get("star_chances", [])))

    def get_live_games(self) -> dict:
        """Fetch currently ongoing games."""
        return self._get("/populate_db/ongoing_game/")

    # -------------------------------------------------------------------------
    # Community management (POST)
    # -------------------------------------------------------------------------

    def create_community(self, community_name: str, private: bool, global_link: bool, desc: str, comm_type: str = "Unofficial") -> dict:
        return self._post_authed("/community/create", {
            "community_name": community_name,
            "type": comm_type,
            "private": private,
            "global_link": global_link,
            "desc": desc,
        })

    def community_invite(self, community_name: str, invite_list: list) -> dict:
        return self._post_authed("/community/invite", {
            "community_name": community_name,
            "invite_list": invite_list,
        })

    def community_members(self, community_name: str) -> dict:
        return self._post_authed("/community/members", {
            "community_name": community_name,
        })

    def community_tags(self, community_name: str) -> dict:
        return self._post_authed("/community/tags", {
            "community_name": community_name,
        })

    def community_manage(self, community_name: str, user_list: list) -> dict:
        """Manage community members.

        user_list: list of dicts with keys: username, admin, remove, ban, key
        """
        return self._post_authed("/community/manage", {
            "community_name": community_name,
            "user_list": user_list,
        })

    def community_sponsor(self, community_name: str, action: str) -> dict:
        """Manage community sponsors. action: 'Get', 'Remove', or 'Add'."""
        return self._post_authed("/community/sponsor", {
            "community_name": community_name,
            "action": action,
        })

    def community_key(self, community_name: str, action: str) -> dict:
        """Manage community keys. action: 'generate', 'revoke', or 'generate_all'."""
        return self._post_authed("/community/key", {
            "community_name": community_name,
            "action": action,
        })

    def community_update(self, community_id: str, name: str = None, desc: str = None,
                         comm_type: str = None, private: bool = None, global_link: bool = None,
                         active_tag_set_limit: int = None) -> dict:
        data = {"community_id": community_id}
        if name is not None:
            data["name"] = name
        if desc is not None:
            data["desc"] = desc
        if comm_type is not None:
            data["type"] = comm_type
        if global_link is not None:
            data["link"] = global_link
        if private is not None:
            data["private"] = private
        if active_tag_set_limit is not None:
            data["active_tag_set_limit"] = active_tag_set_limit
        return self._post_authed("/community/update", data)

    # -------------------------------------------------------------------------
    # Tag management (POST)
    # -------------------------------------------------------------------------

    def create_tag(self, name: str, desc: str, community_name: str, tag_type: str,
                   gecko_code_desc: str = None, gecko_code: str = None) -> dict:
        data = {
            "name": name,
            "desc": desc,
            "community_name": community_name,
            "type": tag_type,
        }
        if tag_type == "Gecko Code":
            if gecko_code_desc is not None:
                data["gecko_code_desc"] = gecko_code_desc
            if gecko_code is not None:
                data["gecko_code"] = gecko_code
        return self._post_authed("/tag/create", data)

    def update_tag(self, tag_id: int, name: str = None, desc: str = None, tag_type: str = None,
                   gecko_code_desc: str = None, gecko_code: str = None) -> dict:
        data = {"tag_id": tag_id}
        if name is not None:
            data["name"] = name
        if desc is not None:
            data["desc"] = desc
        if tag_type is not None:
            data["type"] = tag_type
        if tag_type == "Gecko Code":
            if gecko_code is not None:
                data["gecko_code"] = gecko_code
            if gecko_code_desc is not None:
                data["gecko_code_desc"] = gecko_code_desc
        return self._post_authed("/tag/update", data)

    def list_tags(self, tag_type=None, community_ids=None) -> dict:
        data = {}
        if tag_type:
            data["Types"] = tag_type
        if community_ids:
            data["community_ids"] = community_ids
        return self._post_authed("/tag/list", data)

    # -------------------------------------------------------------------------
    # Game mode management (POST)
    # -------------------------------------------------------------------------

    def create_game_mode(self, name: str, desc: str, game_mode_type: str, community_name: str,
                         start_date: str, end_date: str, add_tag_ids: list = None,
                         mirror_tags_from: int = None) -> dict:
        data = {
            "name": name,
            "desc": desc,
            "type": game_mode_type,
            "community_name": community_name,
            "start_date": start_date,
            "end_date": end_date,
        }
        if add_tag_ids:
            data["add_tag_ids"] = add_tag_ids
        if mirror_tags_from:
            data["tag_set_id"] = mirror_tags_from
        return self._post_authed("/tag_set/create", data)

    def update_game_mode(self, tag_set_id: int, name: str = None, desc: str = None,
                         game_mode_type: str = None, start_date: str = None, end_date: str = None,
                         add_tag_ids: list = None, remove_tag_ids: list = None) -> dict:
        data = {"tag_set_id": tag_set_id}
        if name is not None:
            data["name"] = name
        if desc is not None:
            data["desc"] = desc
        if game_mode_type is not None:
            data["type"] = game_mode_type
        if start_date is not None:
            data["start_date"] = start_date
        if end_date is not None:
            data["end_date"] = end_date
        if add_tag_ids is not None:
            data["add_tag_ids"] = add_tag_ids
        if remove_tag_ids is not None:
            data["remove_tag_ids"] = remove_tag_ids
        return self._post_authed("/tag_set/update", data)

    def delete_game_mode(self, name: str) -> dict:
        return self._post_authed("/tag_set/delete", {"name": name})

    def list_game_modes(self, active: bool = False, community_ids=None) -> dict:
        data = {}
        if active:
            data["Active"] = "t"
        if community_ids:
            data["Communities"] = community_ids
        return self._post_authed("/tag_set/list", data)

    def game_mode_tags(self, tag_set_id: int) -> dict:
        return self._get(f"/tag_set/{tag_set_id}")

    def game_mode_ladder(self, game_mode_name: str) -> dict:
        # The trailing slash is load-bearing; see Endpoint in api.py. Spelled
        # "/tag_set/ladder" until sweep S45, which cost this call a 308 and a
        # second round trip with the Authorization header re-sent to it.
        return self._post_authed("/tag_set/ladder/", {"TagSet": game_mode_name})

    # -------------------------------------------------------------------------
    # User management
    # -------------------------------------------------------------------------

    def login(self, email: str, password: str) -> str:
        """Start a session, and use it for every later request on this client.

        Some operations are deliberately unavailable to a Rio Key or an API key,
        however privileged their owner: changing group membership, changing a
        password or email, rotating a key, deleting an account, and reading
        another user's IP history. The rule is that a credential may not be used
        to increase its own authority -- an API key that can add its own holder
        to Admin is a lock with the key left in it. Those operations need a
        session, which is what this provides.

        Everything else keeps working on the Rio Key alone, so most scripts never
        need to call this.

        Returns the username the server associated with the session.

        The token is treated as opaque on purpose: it is a JWT today and is
        planned to become an opaque server-side session, so nothing here parses
        it or reads an expiry out of it. When it expires, calls begin returning
        401 and the fix is to call login() again.
        """
        response = self._post("/login/", {"Email": email, "Password": password})
        self.session.headers["Authorization"] = f"Bearer {response['access_token']}"
        return response.get("username")

    def logout(self) -> None:
        """Drop the session, falling back to the stored key for later requests."""
        self.session.headers.pop("Authorization", None)

    def request_api_key(self) -> str:
        """Mint this account's API key and start using it. Needs a session.

        An API key is the credential for everything this client does other than
        public reads. Rotating or minting one is deliberately session-only --
        a leaked key must not be able to roll the key it leaked and lock the
        owner out -- so call login() first:

            client = RioWeb()
            client.login(email, password)
            key = client.request_api_key()     # also mailed to the account

        Store it as PYRIO_API_KEY, or as "api_key" in rio_key.json, and later
        runs will pick it up with no login. One key per account: if the account
        already has one, this raises and reset_api_key() is the way back.
        """
        return self._remember_api_key(self._post("/api_key/register/"))

    def reset_api_key(self) -> str:
        """Roll this account's API key over and start using the new one.

        Needs a session, for the same reason as request_api_key(). This is the
        recovery path for a key you no longer have -- the old one stops working
        the moment this returns, so anything still holding it will need the new
        value.
        """
        return self._remember_api_key(self._post("/api_key/reset/"))

    def _remember_api_key(self, response: dict) -> str:
        """Use the key the server just issued for the rest of this client's life."""
        self.api_key = response["api_key"]
        if not response.get("email_sent", True):
            print("NOTE: Rio Web could not email this key. It is returned here and "
                  "nowhere else, so store it now.")
        return self.api_key

    def list_users(self) -> dict:
        # Slashed, as the server registers it -- see Endpoint in api.py. The
        # route is @public, so unlike the ladder above this one paid only the
        # wasted round trip.
        return self._get("/user/all/")

    def add_user_to_group(self, username: str, group_name: str) -> dict:
        return self._post_authed("/user_group/add_user", {
            "username": username,
            "group_name": group_name,
        })

    def remove_user_from_group(self, username: str, group_name: str) -> dict:
        return self._post_authed("/user_group/remove_user", {
            "username": username,
            "group_name": group_name,
        })

    def check_user_in_group(self, username: str, group_name: str) -> dict:
        return self._get("/user_group/check_for_member", {
            "username": username,
            "group_name": group_name,
        }, authed=True)

    def group_members(self, group_name: str) -> dict:
        return self._get("/user_group/members", {
            "group_name": group_name,
        }, authed=True)

    # -------------------------------------------------------------------------
    # Game management (POST)
    # -------------------------------------------------------------------------

    def delete_game(self, game_id: int) -> dict:
        return self._post_authed("/delete_game/", {"game_id": game_id})

    def manual_game_submit(self, winner_username: str, winner_score: int, loser_username: str,
                           loser_score: int, date: str, tag_set: str, recalc: bool = True,
                           game_id_hex: str = None, game_id_dec: int = None) -> dict:
        data = {
            "winner_username": winner_username,
            "winner_score": winner_score,
            "loser_username": loser_username,
            "loser_score": loser_score,
            "date": date,
            "tag_set": tag_set,
            "submitter_rio_key": self.rio_key,
            "recalc": recalc,
        }
        if game_id_dec is not None:
            data["game_id_dec"] = game_id_dec
        if game_id_hex is not None:
            data["game_id_hex"] = game_id_hex
        # submitter_rio_key stays: it is a field this endpoint reads by name to
        # decide who is submitting, not the request's credential. The header is
        # what authenticates the call.
        return self._post("/manual_submit_game/", data, authed=True)

    # -------------------------------------------------------------------------
    # Response processing (private)
    # -------------------------------------------------------------------------

    def _process_games(self, api_response: dict) -> pd.DataFrame:
        """Process raw games API response into a cleaned DataFrame."""
        import pandas as pd
        df = pd.DataFrame.from_dict(api_response["games"])
        if df.empty:
            return df

        home_wins = df["home_score"] > df["away_score"]
        df["winner_user"] = df["home_user"].where(home_wins, df["away_user"])
        df["winner_score"] = df["home_score"].where(home_wins, df["away_score"])
        df["loser_user"] = df["away_user"].where(home_wins, df["home_user"])
        df["loser_score"] = df["away_score"].where(home_wins, df["home_score"])

        df["date_time_start"] = pd.to_datetime(df["date_time_start"], unit="s", utc=True).dt.tz_convert("US/Eastern")
        df["date_time_end"] = pd.to_datetime(df["date_time_end"], unit="s", utc=True).dt.tz_convert("US/Eastern")

        reversed_game_mode_dict = {v: k for k, v in self.cache.game_mode_dictionary().items()}
        df["game_mode"] = df["game_mode"].map(reversed_game_mode_dict)

        df["stadium"] = lookup(Tables.STADIUM, df["stadium"].astype(int))

        return df

    @staticmethod
    def _process_stats(api_response: dict, params: dict = None) -> pd.DataFrame:
        """Process raw stats API response into a DataFrame.

        Uses the request params to determine the nesting structure of the response
        rather than guessing from the keys. Grouping dimensions become regular columns;
        stat names are flattened as Category_stat (e.g. Batting_hits, Pitching_strikeouts).
        With inner dimensions: Category_Sub_stat (e.g. Batting_Slap_hits).
        """
        import pandas as pd
        stats_data = api_response.get("Stats", {})
        if not stats_data:
            return pd.DataFrame()

        if params is None:
            params = {}

        # Outer dimensions in server nesting order: game → user → roster_order → char
        OUTER_DIMENSIONS = [
            ("by_game", "game_id"),
            ("by_user", "username"),
            ("by_roster_order", "roster_loc"),
            ("by_char", "char_name"),
        ]

        by_swing = bool(params.get("by_swing"))
        by_batting_hand = bool(params.get("by_batting_hand"))
        by_fielding_hand = bool(params.get("by_fielding_hand"))

        active_outer = [col_name for param_key, col_name in OUTER_DIMENSIONS
                        if params.get(param_key)]

        STAT_CATEGORIES = {"Batting", "Pitching", "Fielding", "Misc"}

        def _flatten_stat_leaf(stats: dict) -> dict:
            """Flatten a stat_type → values dict into underscore-joined column names."""
            flat = {}
            for category, values in stats.items():
                if category not in STAT_CATEGORIES:
                    continue
                if category == "Batting" and by_swing:
                    for swing_key, swing_stats in values.items():
                        if isinstance(swing_stats, dict):
                            for stat, val in swing_stats.items():
                                flat[f"Batting_{swing_key}_{stat}"] = val
                        else:
                            flat[f"Batting_{swing_key}"] = swing_stats
                elif category == "Batting" and by_batting_hand:
                    for hand_key, hand_stats in values.items():
                        for stat, val in hand_stats.items():
                            flat[f"Batting_{hand_key}_{stat}"] = val
                elif category == "Pitching" and by_fielding_hand:
                    for hand_key, hand_stats in values.items():
                        for stat, val in hand_stats.items():
                            flat[f"Pitching_{hand_key}_{stat}"] = val
                else:
                    for stat, val in values.items():
                        flat[f"{category}_{stat}"] = val
            return flat

        def _collect_rows(data, depth=0):
            """Recursively walk the nested dict, collecting flat rows."""
            if depth < len(active_outer):
                rows = []
                for key, nested in data.items():
                    sub_rows = _collect_rows(nested, depth + 1)
                    for row in sub_rows:
                        row[active_outer[depth]] = key
                    rows.extend(sub_rows)
                return rows
            else:
                return [_flatten_stat_leaf(data)]

        rows = _collect_rows(stats_data)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Reorder so grouping columns come first in nesting order
        ordered_grouping = [c for _, c in OUTER_DIMENSIONS if c in df.columns]
        stat_cols = [c for c in df.columns if c not in ordered_grouping]
        df = df[ordered_grouping + sorted(stat_cols)]

        return df
