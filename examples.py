from api import RequestBuilder, Endpoint, LandingDataParameterList
from data_handler import WebHandler
from lookup import Lookup, LookupDicts
import pandas as pd
from api import print_parameter_list


# Basic example of current usage
# initialize instance of RequestBuilder, WebHandler, and Lookup
builder = RequestBuilder()
handler = WebHandler()
lookup = Lookup()

# Make parameter list using the appropriate list
# (classes that make use of game/event class have access to those variables)
# lookup function allows for passing key or value as argument, and will return the other
# params = LandingDataParameterList(
#     tag="starsoffseason7",
#     batter_char=lookup.lookup(LookupDicts.CHAR_NAME, 'Mario')
# )

# Use builder class to create a request list to pass to DataHandler
# request_list = builder \
#     .add(Endpoint.LANDING_DATA, params=params) \
#     .build()

# Fetch the data using the data handler and save it to a variable
# s7_off_mario = handler.fetch_data(request_list)

# You can save it to a CSV or a SQLite database
# handler.save_to_csv(s7_off_mario, file_name="Mario_LD_S7OFF")


# Load it using pandas
# mario = pd.read_csv('data/Mario_LD_S7OFF.csv')

lookup_func = lookup.lookup

print(lookup_func(LookupDicts.FINAL_RESULT, 'HR'))

print(LookupDicts.FINAL_RESULT.values())