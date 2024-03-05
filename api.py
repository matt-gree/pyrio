from dataclasses import dataclass, fields, asdict
from typing import Optional, List, Union
from lookup import Lookup
# @dataclass
# class StatsEndpoint:
#     # todo: some way to readily retrieve and manipulate params for requests, such as a parameter/query builder
#     params: StatsParameterList


def serialize_parameters(parameters):
    if isinstance(parameters, (GamesParameterList, EventsParameterList, LandingDataParameterList, StarChancesParameterList, StatsParameterList)):
        return {k: v for k, v in asdict(parameters).items() if v is not None}
    elif isinstance(parameters, dict):
        return {k: v for k, v in parameters.items() if v is not None}
    else:
        return {}


class Endpoint:
    LANDING_DATA = "/landing_data/"
    STATS = "/stats/"
    CHARACTERS = "/characters/"
    GAMES = "/games/"
    EVENTS = "/events/"
    STAR_CHANCES = "/star_chances/"


@dataclass
class RequestInfo:
    endpoint: Endpoint
    parameters: dict


class RequestBuilder:
    def __init__(self, params=None):
        self.requests = []
        self.params = params

    def add(self, endpoint: Endpoint, params=None):
        if params is None:
            params = self.params
        serialized_params = serialize_parameters(params)
        request_info = RequestInfo(endpoint, serialized_params)
        self.requests.append(request_info)
        return self

    def build(self):
        return [(request.endpoint, request.parameters) for request in self.requests if request is not None]


@dataclass
class ParameterList:
    """Base class for all ParameterLists - makes it easier to reference them in other functions."""
    pass


@dataclass
class GamesParameterList(ParameterList):
    tag: Optional[List[str]] = None
    exclude_tag: Optional[List[str]] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    username: Optional[List[str]] = None
    vs_username: Optional[List[str]] = None
    exclude_username: Optional[List[str]] = None
    captain: Optional[str] = None
    vs_captain: Optional[str] = None
    exclude_captain: Optional[str] = None
    limit_games: Optional[Union[int, bool]] = None
    include_teams: Optional[bool] = None
    stadium: Optional[int] = None


@dataclass
class EventsParameterList(GamesParameterList):
    games: Optional[List[int]] = None
    pitcher_char: Optional[List[int]] = None
    batter_char: Optional[List[int]] = None
    fielder_char: Optional[List[int]] = None
    fielder_pos: Optional[List[int]] = None
    contact: Optional[List[int]] = None
    swing: Optional[List[int]] = None
    pitch: Optional[List[int]] = None
    chem_link: Optional[List[int]] = None
    pitcher_hand: Optional[List[int]] = None
    batter_hand: Optional[List[int]] = None
    inning: Optional[List[int]] = None
    half_inning: Optional[List[int]] = None
    balls: Optional[List[int]] = None
    strikes: Optional[List[int]] = None
    outs: Optional[List[int]] = None
    star_chance: Optional[List[int]] = None
    users_as_batter: Optional[List[int]] = None
    users_as_pitcher: Optional[List[int]] = None
    final_result: Optional[List[int]] = None
    limit_events: Optional[Union[int, bool]] = None


@dataclass
class LandingDataParameterList(EventsParameterList):
    event_list: Optional[List[int]] = None
    game_list: Optional[List[int]] = None


@dataclass
class StarChancesParameterList:
    by_inning: Optional[bool] = None


@dataclass
class StatsParameterList(EventsParameterList):
    char_id: Optional[int] = None
    by_user: Optional[bool] = None
    by_char: Optional[bool] = None
    by_swing: Optional[bool] = None
    exclude_nonfair: Optional[bool] = None
    exclude_batting: Optional[bool] = None
    exclude_pitching: Optional[bool] = None
    exclude_misc: Optional[bool] = None
    exclude_fielding: Optional[bool] = None


def get_parameter_list(parameter_list_class, include_parent=False):
    param_list = []
    for field in fields(parameter_list_class):
        param_name = field.name
        param_type = field.type
        if include_parent or field.name in parameter_list_class.__annotations__:
            param_list.append((param_name, param_type))
    return param_list


def print_parameter_list(parameter_list_class, full_type_str=False, include_parent=True):
    param_list = get_parameter_list(parameter_list_class, include_parent)
    for name, param_type in param_list:
        if full_type_str:
            print(f"{name} ({param_type})")
        else:
            simplified_type_str = simplify_parameter_type(param_type)
            print(f"{name}: {simplified_type_str}")


def simplify_parameter_type(param_type):
    type_str = str(param_type) \
        .replace('typing.', '') \
        .replace('Optional[', '') \
        .replace('List[', '') \
        .replace('Union[', '') \
        .replace(']', '') \
        .replace(', NoneType', '')

    return type_str


class LandingData:

    def __init__(self, df):
        # I don't like this current setup at all, so I need to think through how I want to handle it.
        self.lookup = Lookup()
        self.data = self.lookup.create_translated_columns(df)
        self.coords = self.get_coordinates()
        self.hits = self.get_hits()
        self.outs = self.get_outs()
        self.sour = self.get_sour()
        self.nice = self.get_nice()
        self.perfect = self.get_perfect()
        self.data = self.add_rng_values()
        self.categorical = self.get_categorical_data()
        self.numeric = self.get_numeric_data()

    def get_coordinates(self):
        return self.data[['ball_x_contact_pos', 'ball_x_landing_pos', 'ball_x_velocity', 'ball_y_landing_pos', 'ball_y_velocity', 'ball_z_contact_pos', 'ball_z_landing_pos', 'ball_z_velocity']]

    def get_hits(self):
        return self.data[self.data['final_result'].isin([7, 8, 9, 10])]

    def get_outs(self):
        return self.data[self.data['final_result'].isin([5, 6, 14, 15, 16])]

    def get_sour(self):
        return self.data[self.data['type_of_contact'].isin([7, 8, 9, 10])]

    def get_nice(self):
        return self.data[self.data['type_of_contact'].isin([7, 8, 9, 10])]

    def get_perfect(self):
        return self.data[self.data['type_of_contact'].isin([7, 8, 9, 10])]

    def get_numeric_data(self):
        return self.data.select_dtypes(include=['int64', 'float64'])

    def get_categorical_data(self):
        return self.data.select_dtypes(include=['object', 'bool', 'category'])

    def calculate_rng_value(self, row):
        fin_sum = 100
        rng1 = (row['rng1'] - (int(row['rng2']) & 0xff)) + (int(row['rng2']) // fin_sum) + row['rng3']
        random_range = rng1 - (rng1 // fin_sum) * fin_sum
        random_range = int(random_range)
        random_sum = (random_range >> 31 ^ random_range) - (random_range >> 31)
        return random_sum

    def add_rng_values(self):
        self.data['rng_value'] = self.data.apply(self.calculate_rng_value, axis=1)
        return self.data