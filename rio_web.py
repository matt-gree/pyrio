import json
import os
from dataclasses import asdict
from typing import Optional, Union

import pandas as pd
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
from .lookup import Lookup, LookupDicts

BASE_URL = "https://api.projectrio.app"


def _load_key_from_file() -> Optional[str]:
    """Try to load rio_key from rio_key.json in the current directory."""
    if os.path.exists("rio_key.json"):
        with open("rio_key.json", "r") as f:
            return json.load(f).get("rio_key")
    return None


class RioWeb:
    """Unified client for the Project Rio API.

    Usage:
        client = RioWeb()                           # key from env or rio_key.json
        client = RioWeb(rio_key="your_key_here")    # explicit key

        games_df = client.get_games(tag=["tournament"])
        games_raw = client.get_games(tag=["tournament"], raw=True)
    """

    def __init__(self, rio_key: str = None, base_url: str = BASE_URL):
        self.rio_key = rio_key or os.environ.get("PYRIO_KEY") or _load_key_from_file()
        if not self.rio_key:
            print("WARNING: No Rio API key found. Set PYRIO_KEY env var, pass rio_key=, or create rio_key.json.")
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._cache = None

    @property
    def cache(self):
        """Lazy-loaded CompleterCache for game mode / user lookups."""
        if self._cache is None:
            from .web_caching import CompleterCache
            self._cache = CompleterCache(self)
        return self._cache

    # -------------------------------------------------------------------------
    # Internal HTTP methods
    # -------------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = self.base_url + endpoint
        response = self.session.get(url, params=params)
        raise_for_status(response)
        return response.json()

    def _post(self, endpoint: str, data: dict = None) -> dict:
        url = self.base_url + endpoint
        response = self.session.post(url, json=data)
        raise_for_status(response)
        return response.json()

    def _post_with_key(self, endpoint: str, data: dict = None) -> dict:
        if data is None:
            data = {}
        data["rio_key"] = self.rio_key
        return self._post(endpoint, data)

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
        return result

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
        """Fetch stats data. Returns a MultiIndex DataFrame organized by category/stat."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.STATS, serialized)
        if raw:
            return response
        return self._process_stats(response)

    def get_events(self, params: Union[EventsParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch event-level data."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.EVENTS, serialized)
        if raw:
            return response
        return pd.DataFrame(response.get("Events", response.get("events", [])))

    def get_landing_data(self, params: Union[LandingDataParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch landing data (ball contact/landing positions)."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.LANDING_DATA, serialized)
        if raw:
            return response
        return pd.DataFrame(response.get("Data", []))

    def get_star_chances(self, params: Union[StarChancesParameterList, dict] = None, raw: bool = False, **kwargs) -> Union[pd.DataFrame, dict]:
        """Fetch star chance data."""
        serialized = self._serialize_params(params, kwargs)
        response = self._get(Endpoint.STAR_CHANCES, serialized)
        if raw:
            return response
        return pd.DataFrame(response.get("Star Chances", response.get("star_chances", [])))

    def get_live_games(self) -> dict:
        """Fetch currently ongoing games."""
        return self._get("/populate_db/ongoing_game/")

    # -------------------------------------------------------------------------
    # Community management (POST)
    # -------------------------------------------------------------------------

    def create_community(self, community_name: str, private: bool, global_link: bool, desc: str, comm_type: str = "Unofficial") -> dict:
        return self._post_with_key("/community/create", {
            "community_name": community_name,
            "type": comm_type,
            "private": private,
            "global_link": global_link,
            "desc": desc,
        })

    def community_invite(self, community_name: str, invite_list: list) -> dict:
        return self._post_with_key("/community/invite", {
            "community_name": community_name,
            "invite_list": invite_list,
        })

    def community_members(self, community_name: str) -> dict:
        return self._post_with_key("/community/members", {
            "community_name": community_name,
        })

    def community_tags(self, community_name: str) -> dict:
        return self._post_with_key("/community/tags", {
            "community_name": community_name,
        })

    def community_manage(self, community_name: str, user_list: list) -> dict:
        """Manage community members.

        user_list: list of dicts with keys: username, admin, remove, ban, key
        """
        return self._post_with_key("/community/manage", {
            "community_name": community_name,
            "user_list": user_list,
        })

    def community_sponsor(self, community_name: str, action: str) -> dict:
        """Manage community sponsors. action: 'Get', 'Remove', or 'Add'."""
        return self._post_with_key("/community/sponsor", {
            "community_name": community_name,
            "action": action,
        })

    def community_key(self, community_name: str, action: str) -> dict:
        """Manage community keys. action: 'generate', 'revoke', or 'generate_all'."""
        return self._post_with_key("/community/key", {
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
        return self._post_with_key("/community/update", data)

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
        return self._post_with_key("/tag/create", data)

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
        return self._post_with_key("/tag/update", data)

    def list_tags(self, tag_type=None, community_ids=None) -> dict:
        data = {}
        if tag_type:
            data["Types"] = tag_type
        if community_ids:
            data["community_ids"] = community_ids
        return self._post_with_key("/tag/list", data)

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
        return self._post_with_key("/tag_set/create", data)

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
        return self._post_with_key("/tag_set/update", data)

    def delete_game_mode(self, name: str) -> dict:
        return self._post_with_key("/tag_set/delete", {"name": name})

    def list_game_modes(self, active: bool = False, community_ids=None) -> dict:
        data = {}
        if active:
            data["Active"] = "t"
        if community_ids:
            data["Communities"] = community_ids
        return self._post_with_key("/tag_set/list", data)

    def game_mode_tags(self, tag_set_id: int) -> dict:
        return self._get(f"/tag_set/{tag_set_id}")

    def game_mode_ladder(self, game_mode_name: str) -> dict:
        return self._post_with_key("/tag_set/ladder", {"TagSet": game_mode_name})

    # -------------------------------------------------------------------------
    # User management
    # -------------------------------------------------------------------------

    def list_users(self) -> dict:
        return self._get("/user/all")

    def add_user_to_group(self, username: str, group_name: str) -> dict:
        return self._post_with_key("/user_group/add_user", {
            "username": username,
            "group_name": group_name,
        })

    def remove_user_from_group(self, username: str, group_name: str) -> dict:
        return self._post_with_key("/user_group/remove_user", {
            "username": username,
            "group_name": group_name,
        })

    def check_user_in_group(self, username: str, group_name: str) -> dict:
        return self._get("/user_group/check_for_member", {
            "username": username,
            "group_name": group_name,
            "rio_key": self.rio_key,
        })

    def group_members(self, group_name: str) -> dict:
        return self._get("/user_group/members", {"group_name": group_name})

    # -------------------------------------------------------------------------
    # Game management (POST)
    # -------------------------------------------------------------------------

    def delete_game(self, game_id: int) -> dict:
        return self._post_with_key("/delete_game/", {"game_id": game_id})

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
        return self._post("/manual_submit_game/", data)

    # -------------------------------------------------------------------------
    # Response processing (private)
    # -------------------------------------------------------------------------

    def _process_games(self, api_response: dict) -> pd.DataFrame:
        """Process raw games API response into a cleaned DataFrame."""
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

        df["stadium"] = Lookup.lookup(LookupDicts.STADIUM, df["stadium"].astype(int))

        return df

    @staticmethod
    def _process_stats(api_response: dict) -> pd.DataFrame:
        """Process raw stats API response into a MultiIndex DataFrame."""
        stats_data = api_response.get("Stats", {})
        if not stats_data:
            return pd.DataFrame()

        possible_characters = set(LookupDicts.CHAR_NAME.values())

        def has_swing_types(batting_data: dict) -> bool:
            swing_keys = {"charge", "slap", "star", "none"}
            return any(k.lower() in swing_keys for k in batting_data)

        def sort_columns(df):
            if isinstance(df.columns, pd.MultiIndex):
                if df.columns.nlevels == 3:
                    swing_order = ["slap", "charge", "star", "none", "summary"]
                    df = df.reindex(
                        columns=pd.MultiIndex.from_tuples(
                            sorted(df.columns, key=lambda col: (
                                col[0],
                                swing_order.index(col[1].lower()) if col[1].lower() in swing_order else 99,
                                col[2],
                            ))
                        )
                    )
                elif df.columns.nlevels == 2:
                    df = df.sort_index(axis=1)
            return df

        def _flatten_stats(stats: dict, with_swing: bool) -> dict:
            flat = {}
            for category, values in stats.items():
                if category == "Batting" and with_swing:
                    for swing_key, swing_stats in values.items():
                        if swing_key.startswith("summary_"):
                            flat[("Batting", "summary", swing_key)] = swing_stats
                        else:
                            for stat, val in swing_stats.items():
                                flat[("Batting", swing_key, stat)] = val
                else:
                    for stat, val in values.items():
                        key = (category, "summary", stat) if with_swing else (category, stat)
                        flat[key] = val
            return flat

        def _build_df(rows, index, with_swing):
            data = [r[1] for r in rows]
            df = pd.DataFrame(data, index=index)
            if with_swing:
                df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Swing Type", "Stat"])
            else:
                df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Stat"])
            return sort_columns(df)

        # Aggregate (no user/char breakdown)
        if any(k in ("Batting", "Pitching", "Fielding", "Misc") for k in stats_data):
            batting = stats_data.get("Batting", {})
            with_swing = has_swing_types(batting)
            flat = _flatten_stats(stats_data, with_swing)
            df = pd.DataFrame([flat], index=["Total"])
            if with_swing:
                df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Swing Type", "Stat"])
            else:
                df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Stat"])
            return sort_columns(df)

        keys = list(stats_data.keys())
        first_val = stats_data[keys[0]]

        # By character
        if all(k in possible_characters for k in keys):
            with_swing = has_swing_types(first_val.get("Batting", {}))
            rows = [(char, _flatten_stats(stats, with_swing)) for char, stats in stats_data.items()]
            return _build_df(rows, pd.Index([r[0] for r in rows], name="Character"), with_swing)

        # By user
        if all(k in ("Batting", "Fielding", "Pitching", "Misc") for k in first_val):
            with_swing = has_swing_types(first_val.get("Batting", {}))
            rows = [(user, _flatten_stats(user_stats, with_swing)) for user, user_stats in stats_data.items()]
            return _build_df(rows, pd.Index([r[0] for r in rows], name="User"), with_swing)

        # By user and character
        with_swing = has_swing_types(
            next(iter(next(iter(stats_data.values())).values())).get("Batting", {})
        )
        rows = []
        for user, characters in stats_data.items():
            for char, stats in characters.items():
                rows.append(((user, char), _flatten_stats(stats, with_swing)))
        index = pd.MultiIndex.from_tuples([r[0] for r in rows], names=["User", "Character"])
        return _build_df(rows, index, with_swing)
