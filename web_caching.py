from web_functions import list_tags, list_users, list_game_modes
from api_manager import APIManager
import pandas as pd

class CompleterCache:
    def __init__(self, manager: APIManager):
        self.manager = manager
        self.communities_list = []
        self.users_dict = {}
        self.users_list = []
        self.tags_dict = {}
        self.game_mode_dict = {}
        self.tags_df = None

    def call_tags_api(self):
        if self.tags_df is None:
            self.tags_df = pd.DataFrame(list_tags(self.manager)['Tags']).set_index('id')

    def return_tags_df(self):
        self.call_tags_api()

        return self.tags_df
    
    def communities(self):
        self.call_tags_api()
        self.communities_list = self.tags_df[self.tags_df['type'] == 'Community']['name'].tolist()
        
        return self.communities_list
    
    def users_dictionary(self):
        if not self.users_dict:
            self.users_dict = list_users(self.manager)['users']
        
        return self.users_dict
    
    def users(self):
        if not self.users_dict:
            self.users_dict = list_users(self.manager)['users']
        if not self.users_list:
            self.users_list = list(self.users_dict.values())

        return self.users_list
    
    def tags_dictionary(self):
        self.call_tags_api()
        self.tags_dict = {row['name']: idx for idx, row in self.tags_df[self.tags_df['type'].isin(['Gecko Code', 'Component'])].iterrows()}

        return self.tags_dict
    
    def game_mode_dictionary(self):
        if not self.game_mode_dict:
            self.game_mode_dict = {tag['name']: tag['id'] for tag in list_game_modes(self.manager)['Tag Sets']}

        return self.game_mode_dict