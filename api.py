from dataclasses import dataclass, fields, asdict
from typing import Optional, List, Union

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

# @dataclass
# class ParameterList:


@dataclass
class GamesParameterList:
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
