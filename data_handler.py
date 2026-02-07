import pandas as pd
from enum import Enum
from urllib.parse import urlencode
import requests
from dataclasses import dataclass, asdict
from typing import Union, List, Dict
from api import RequestBuilder, Endpoint
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests_cache import CachedSession
from sqlalchemy import create_engine
from abc import ABC, abstractmethod


class StatFileHandler:
    def __init__(self):
        self.dataframes = []

    def load_files(self, filepaths):
        pass


class WebHandler:
    def __init__(self, cache=False):
        self.api_url = "https://api.projectrio.app"
        self.request_builder = RequestBuilder()
        self.cache = cache
        if cache:
            self.session = CachedSession('api_cache', backend='sqlite', expire_after=300)
    def _api_data_to_dataframe(self, endpoint: str, parameters: dict): #, to_csv=False, csv_file_name=None, to_db=False, db_file_name=None):
        df_list = []
        url = self.api_url + endpoint
        if parameters:
            url += "?" + urlencode(parameters, doseq=True)

        try:
            if self.cache:
                response = self.session.get(url, timeout=60).json()
            else:
                response = requests.get(url, timeout=60).json()
        except Exception as e:
            response_text = response.text if response else "No response"
            print(f"Error fetching data: {e}, Response: {response_text}")
            return pd.DataFrame()

        if endpoint == Endpoint.LANDING_DATA:
            response = response["Data"]
            df_list.append(pd.DataFrame(response))
        elif endpoint == Endpoint.STATS:
            # need to test the following - likely doesn't work exactly how it needs to
            """
            def process_batting_data(data):
                summary_stats = {k: v for k, v in data.items() if k.startswith('summary_')}
                batting_categories = {k: v for k, v in data.items() if not k.startswith('summary_')}
                flat_data = []
                for category, stats in batting_categories.items():
                    stats['category'] = category
                    flat_data.append(stats)
                return pd.DataFrame(flat_data), summary_stats
            """
            # todo: maybe always call all data? this one is a little harder to determine format for since it's much smaller amounts of data
            response = response["Stats"]
            # I don't like hardcoding this, but a) not sure how I'd do it otherwise b) seems unlikely to change
            if "by_user" in parameters and parameters["by_user"] == 1:
                # todo: process the user data
                pass
            for category in ["Batting", "Fielding", "Misc", "Pitching"]:
                # todo: process when by_swing=1
                if category == "Batting":
                    if "by_swing" in parameters and parameters["by_swing"] == 1:
                        # process_batting_data()
                        pass
                category_data = response.get(category)
                if category_data:
                    df_list.append(pd.DataFrame([category_data]))
        else:
            print(f"Error: Invalid endpoint: {url}")
            return pd.DataFrame()

        return df_list

    def _generate_csv_filename(self, endpoint, parameters):
        # Generate a CSV filename based on the endpoint and parameters
        f_name = endpoint.replace("/", "")
        for key in parameters:
            f_name += f"-{key}"
        return f_name

    def fetch_data(self, requests_info, concatenate=False):
        """
        Fetch data from one or more endpoints. Handles both single and multiple requests efficiently.

        :param requests_info: List of tuples. Each tuple contains an endpoint and parameters.
                              Example: [(Endpoint.STATS, {'param1': 'value1'}), ...]
        :param concatenate: If True, concatenates the results into a single DataFrame.
                            Otherwise, returns a list of DataFrames.
        :return: A single DataFrame if concatenate is True, or a list of DataFrames otherwise.
        """
        with ThreadPoolExecutor(max_workers=len(requests_info)) as executor:
            futures = {executor.submit(self._api_data_to_dataframe, req[0], req[1]): req for req in requests_info}
            results = []
            for future in as_completed(futures):
                try:
                    data = future.result()
                    results.extend(data)
                except Exception as e:
                    print(f"Request failed: {e}")
                    print(requests_info)

            # if concatenate and results:
            return pd.concat(results, ignore_index=True) if results else pd.DataFrame()
            # else:
            #     return results


    def save_to_csv(self, data, file_name):
        # todo: allow for calling data fetch within this function
        data.to_csv(f"{file_name}.csv", index=False)

    def save_to_database(self, data, table_name, db_file_name="data", db="sqlite", exists="replace"):
        # todo: allow for calling data fetch within this function
        engine = create_engine(f"{db}:///{db_file_name}.db")
        data.to_sql(table_name, con=engine, if_exists=exists, index=False)


class CSVHandler:
    def __init__(self):
        self.dataframes = []

    def load_files(self, filepaths):
        df_list = []
        for filepath in filepaths:
            df_list.append(pd.read_csv(f"{filepath}.csv"))

        return df_list


class DatabaseHandler:
    def __init__(self, db="sqlite", db_file_name="data"):
        self.databases = []
        self.engine = create_engine(f"{db}:{db_file_name}.db")

    def load_tables(self, tables):
        tables_list = []
        for table in tables:
            tables_list.append(pd.read_sql(table, con=self.engine))
        return tables_list

#
# @dataclass
# class Parameter:
#     keyword: str
#     value: Union[str, List, int, bool]


# @dataclass
# class Parameters:
#     parameters: List[Parameter]
#
#     def



# @dataclass
# class RequestInfo:
#     endpoint: Endpoint
#     parameters: Parameters


class DataProcessor(ABC):
    @abstractmethod
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """Process the DataFrame and return a dataframe based on the endpoint."""
        pass


class StatsDataProcessor(DataProcessor):
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        return data


class LandingDataProcessor(DataProcessor):
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        return data


class EventsDataProcessor(DataProcessor):
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        return data


class GamesDataProcessor(DataProcessor):
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        return data


class ProcessorFactory:
    processors = {
        Endpoint.LANDING_DATA: LandingDataProcessor(),
        Endpoint.STATS: StatsDataProcessor(),
        Endpoint.GAMES: GamesDataProcessor(),
        Endpoint.EVENTS: EventsDataProcessor()
    }

    @staticmethod
    def get_processor(endpoint: Endpoint) -> DataProcessor:
        return ProcessorFactory.processors.get(endpoint, DataProcessor())


def process_endpoint_data(endpoint: Endpoint, data: pd.DataFrame) -> pd.DataFrame:
    processor = ProcessorFactory.get_processor(endpoint)
    return processor.process(data)