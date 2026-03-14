import os
import pickle
from datetime import datetime, timedelta

import pandas as pd


class CompleterCache:
    """Caches reference data (users, tags, game modes) from the Rio API.

    Accepts a RioWeb client instance. Data is refreshed when the cache
    expires (default: 1 day) or when refresh_cache() is called.
    """

    def __init__(self, client, cache_dir: str = 'cache', cache_expiration_days: int = 1):
        self.client = client
        self.cache_dir = cache_dir
        self.cache_expiration_days = cache_expiration_days
        self.cache_file = os.path.join(cache_dir, 'cache.pkl')

        os.makedirs(self.cache_dir, exist_ok=True)

        self._cache = {
            'communities': [],
            'users_dict': {},
            'users_list': [],
            'tags_dict': {},
            'game_mode_dict': {},
            'tags_df': None,
            'last_updated': None,
        }

        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached data from file if available and not expired."""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                cache_timestamp = cached_data.get('last_updated')

                if cache_timestamp and datetime.now() - cache_timestamp < timedelta(days=self.cache_expiration_days):
                    self._cache.update(cached_data)
                else:
                    self._refresh_cache()
        else:
            self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Fetch data from API and save to cache."""
        self._cache['last_updated'] = datetime.now()

        tags_response = self.client.list_tags()
        self._cache['tags_df'] = pd.DataFrame(tags_response['Tags']).set_index('id')
        self._cache['communities'] = self._cache['tags_df'][self._cache['tags_df']['type'] == 'Community']['name'].tolist()

        users_response = self.client.list_users()
        self._cache['users_dict'] = users_response['users']
        self._cache['users_list'] = list(self._cache['users_dict'].values())

        self._cache['tags_dict'] = {
            row['name']: idx
            for idx, row in self._cache['tags_df'][self._cache['tags_df']['type'].isin(['Gecko Code', 'Component'])].iterrows()
        }

        game_modes_response = self.client.list_game_modes()
        self._cache['game_mode_dict'] = {tag['name']: tag['id'] for tag in game_modes_response['Tag Sets']}

        self._save_cache()

    def _save_cache(self) -> None:
        """Save the current cache to a file."""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self._cache, f)

    def return_tags_df(self) -> pd.DataFrame:
        return self._cache['tags_df']

    def communities(self) -> list[str]:
        return self._cache['communities']

    def users_dictionary(self) -> dict:
        return self._cache['users_dict']

    def users(self) -> list:
        return self._cache['users_list']

    def tags_dictionary(self) -> dict:
        return self._cache['tags_dict']

    def game_mode_dictionary(self) -> dict:
        return self._cache['game_mode_dict']

    def refresh_cache(self) -> None:
        """Force an update of the cache."""
        self._refresh_cache()
        print("Cache has been updated successfully.")
