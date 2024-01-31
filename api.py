from dataclasses import dataclass


@dataclass
class StatsEndpoint:
    # todo: some way to readily retrieve and manipulate params for requests, such as a parameter/query builder
    params: list


class Endpoint:
    LANDING_DATA = "/landing_data/"
    STATS = "/stats/"


@dataclass
class RequestInfo:
    endpoint: Endpoint
    parameters: dict


class RequestBuilder:
    def __init__(self):
        self.requests = []

    def add(self, endpoint: Endpoint, **kwargs):
        request_info = RequestInfo(endpoint, kwargs)
        self.requests.append(request_info)
        return self

    def build(self):
        return [(request.endpoint, request.parameters) for request in self.requests]


