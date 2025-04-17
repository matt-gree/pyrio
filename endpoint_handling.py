import pandas as pd
from pytz import timezone

from .web_caching import CompleterCache
from .lookup import Lookup, LookupDicts

def games_endpoint(api_response, cache: CompleterCache):
    """
    RESPONSE: {"away_captain":"Mario", "away_score":9, "away_user":"Flatbread", 
    "date_time_end":1737426433,"date_time_start":1737424838, "game_id":238119057288,
    "game_mode":113, "home_captain":"Bowser Jr" ,"home_score":10, "home_user":"hellzhero",
    "innings_played":9, "innings_selected":9, "loser_incoming_elo":1635, "loser_result_elo":1540"
    "stadium":4, "winner_incoming_elo":1793, "winner_result_elo":1888}
    """
    
    df = pd.DataFrame.from_dict(api_response['games'])

    df['winner_user'] = df.apply(
        lambda row: row['home_user'] if row['home_score'] > row['away_score'] else row['away_user'], axis=1
    )

    df['winner_score'] = df.apply(
        lambda row: row['home_score'] if row['home_score'] > row['away_score'] else row['away_score'], axis=1
    )

    df['loser_user'] = df.apply(
        lambda row: row['away_user'] if row['home_score'] > row['away_score'] else row['home_user'], axis=1
    )

    df['loser_score'] = df.apply(
        lambda row: row['away_score'] if row['home_score'] > row['away_score'] else row['home_score'], axis=1
    )

    # Convert timestamp columns to human-readable dates
    df['date_time_start'] = pd.to_datetime(df['date_time_start'], unit='s', utc=True).dt.tz_convert('US/Eastern')
    df['date_time_end'] = pd.to_datetime(df['date_time_end'], unit='s', utc=True).dt.tz_convert('US/Eastern')

    # Map game_mode IDs to names using the reversed cache dictionary
    reversed_game_mode_dict = {v: k for k, v in cache.game_mode_dictionary().items()}
    df['game_mode'] = df['game_mode'].map(reversed_game_mode_dict)

    df['stadium'] = Lookup().lookup(LookupDicts.STADIUM, df['stadium'].astype(int))

    return df

def stats_endpoints(api_response, cache):
    stats_data = api_response.get("Stats", {})
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
                            col[2]
                        ))
                    )
                )
            elif df.columns.nlevels == 2:
                df = df.sort_index(axis=1)
        return df

    def _df_aggregate_no_swing(stats_data: dict) -> pd.DataFrame:
        flat = {}
        for category, values in stats_data.items():
            for stat, val in values.items():
                flat[(category, stat)] = val
        df = pd.DataFrame([flat], index=["Total"])
        df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Stat"])
        return sort_columns(df)

    def _df_aggregate_with_swing(stats_data: dict) -> pd.DataFrame:
        flat = {}
        for category, values in stats_data.items():
            if category == "Batting":
                for swing_key, swing_stats in values.items():
                    if swing_key.startswith("summary_"):
                        flat[("Batting", "summary", swing_key)] = swing_stats
                    else:
                        for stat, val in swing_stats.items():
                            flat[("Batting", swing_key, stat)] = val
            else:
                for stat, val in values.items():
                    flat[(category, "summary", stat)] = val
        df = pd.DataFrame([flat], index=["Total"])
        df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Swing Type", "Stat"])
        return sort_columns(df)

    def _df_by_user(stats_data: dict, with_swing: bool) -> pd.DataFrame:
        rows = []
        for user, user_stats in stats_data.items():
            flat = {}
            for category, values in user_stats.items():
                if category == "Batting" and with_swing:
                    for swing_key, swing_stats in values.items():
                        if swing_key.startswith("summary_"):
                            flat[("Batting", "summary", swing_key)] = swing_stats
                        else:
                            for stat, val in swing_stats.items():
                                flat[("Batting", swing_key, stat)] = val
                else:
                    for stat, val in values.items():
                        key = (category, stat) if not with_swing else (category, "summary", stat)
                        flat[key] = val
            rows.append((user, flat))

        index = [r[0] for r in rows]
        data = [r[1] for r in rows]
        df = pd.DataFrame(data, index=pd.Index(index, name="User"))
        if with_swing:
            df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Swing Type", "Stat"])
        else:
            df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Stat"])
        return sort_columns(df)

    def _df_by_character(stats_data: dict, with_swing: bool) -> pd.DataFrame:
        rows = []
        for char, stats in stats_data.items():
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
                        key = (category, stat) if not with_swing else (category, "summary", stat)
                        flat[key] = val
            rows.append((char, flat))

        index = [r[0] for r in rows]
        data = [r[1] for r in rows]
        df = pd.DataFrame(data, index=pd.Index(index, name="Character"))
        if with_swing:
            df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Swing Type", "Stat"])
        else:
            df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Stat"])
        return sort_columns(df)

    def _df_by_user_and_character(stats_data: dict, with_swing: bool) -> pd.DataFrame:
        rows = []
        for user, characters in stats_data.items():
            for char, stats in characters.items():
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
                            key = (category, stat) if not with_swing else (category, "summary", stat)
                            flat[key] = val
                rows.append(((user, char), flat))

        index = [r[0] for r in rows]
        data = [r[1] for r in rows]
        df = pd.DataFrame(data, index=pd.MultiIndex.from_tuples(index, names=["User", "Character"]))
        if with_swing:
            df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Swing Type", "Stat"])
        else:
            df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Category", "Stat"])
        return sort_columns(df)

    # Dispatch logic
    if any(k in ["Batting", "Pitching", "Fielding", "Misc"] for k in stats_data):
        batting = stats_data.get("Batting", {})
        if has_swing_types(batting):
            return _df_aggregate_with_swing(stats_data)
        else:
            return _df_aggregate_no_swing(stats_data)

    keys = list(stats_data.keys())
    first_val = stats_data[keys[0]]

    if all(k in possible_characters for k in keys):
        return _df_by_character(stats_data, with_swing=has_swing_types(first_val.get("Batting", {})))

    if all(k in ["Batting", "Fielding", "Pitching", "Misc"] for k in first_val):
        return _df_by_user(stats_data, with_swing=has_swing_types(first_val.get("Batting", {})))

    return _df_by_user_and_character(
        stats_data,
        with_swing=has_swing_types(
            next(iter(next(iter(stats_data.values())).values())).get("Batting", {})
        )
    )
