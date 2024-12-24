import pandas as pd
from .web_caching import CompleterCache

def games_endpoints(api_response, cache: CompleterCache):
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
    df['date_time_start'] = pd.to_datetime(df['date_time_start'], unit='s')
    df['date_time_end'] = pd.to_datetime(df['date_time_end'], unit='s')

    # Map game_mode IDs to names using the reversed cache dictionary
    reversed_game_mode_dict = {v: k for k, v in cache.game_mode_dictionary().items()}
    df['game_mode'] = df['game_mode'].map(reversed_game_mode_dict)

    return df