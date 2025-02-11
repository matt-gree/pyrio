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

    # Add a 'winner' and 'loser' column
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