import os
import json
import pickle
from datetime import datetime, timedelta

from .web_functions import list_tags, list_users, list_game_modes, community_tags
from .api_manager import APIManager
import pandas as pd

class CompleterCache:
    def __init__(self, manager: APIManager, cache_dir='cache', cache_expiration_days=1):
        self.manager = manager
        self.cache_dir = cache_dir
        self.cache_expiration_days = cache_expiration_days
        self.cache_file = os.path.join(cache_dir, 'cache.pkl')  # File to store cached data

        # Ensure the cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Cache data
        self._cache = {
            'communities': [],
            'users_dict': {},
            'users_list': [],
            'tags_dict': {},
            'game_mode_dict': {},
            'tags_df': None,
            'last_updated': None
        }

        # Load cache if it's available and not expired
        self._load_cache()

    def _load_cache(self):
        """Load cached data from file if available and not expired."""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                cache_timestamp = cached_data.get('last_updated')

                # Check if the cache is expired
                if cache_timestamp and datetime.now() - cache_timestamp < timedelta(days=self.cache_expiration_days):
                    self._cache.update(cached_data)
                else:
                    # Cache is expired or missing, refresh it
                    self._refresh_cache()
        else:
            # No cache file exists, so refresh the cache
            self._refresh_cache()

    def _refresh_cache(self):
        """Fetch data from API and save to cache."""
        self._cache['last_updated'] = datetime.now()
        self._cache['tags_df'] = self._call_tags_api()
        self._cache['communities'] = self._cache['tags_df'][self._cache['tags_df']['type'] == 'Community']['name'].tolist()
        self._cache['users_dict'] = list_users(self.manager)['users']
        self._cache['users_list'] = list(self._cache['users_dict'].values())
        self._cache['tags_dict'] = {row['name']: idx for idx, row in self._cache['tags_df'][self._cache['tags_df']['type'].isin(['Gecko Code', 'Component'])].iterrows()}
        self._cache['game_mode_dict'] = {tag['name']: tag['id'] for tag in list_game_modes(self.manager)['Tag Sets']}

        # Save to file after refreshing
        self._save_cache()

    def _save_cache(self):
        """Save the current cache to a file."""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self._cache, f)

    def _call_tags_api(self):
        """Fetch tags data from API."""
        return pd.DataFrame(list_tags(self.manager)['Tags']).set_index('id')

    def return_tags_df(self):
        """Get the tags dataframe, fetching from the API if needed."""
        return self._cache['tags_df']
    
    def communities(self):
        """Get the community tags from the cache or fetch if needed."""
        return self._cache['communities']
    
    def users_dictionary(self):
        """Get the users dictionary from the cache or fetch if needed."""
        return self._cache['users_dict']
    
    def users(self):
        """Get the users list from the cache or fetch if needed."""
        return self._cache['users_list']
    
    def tags_dictionary(self):
        """Get the tags dictionary for Gecko Code and Component types."""
        return self._cache['tags_dict']

    def game_mode_dictionary(self):
        """Get the game mode dictionary from the cache or fetch if needed."""
        return self._cache['game_mode_dict']

    def refresh_cache(self):
        """Public method to force an update of the cache."""
        self._refresh_cache()
        print("Cache has been updated successfully.")

