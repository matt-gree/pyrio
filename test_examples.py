from api import RequestBuilder, Endpoint, LandingDataParameterList
from data_handler import WebHandler
from lookup import Lookup, LookupDicts
import pandas as pd
from api import print_parameter_list
import seaborn as sns
import matplotlib.pyplot as plt
import glob
import re

class LandingData:

    def __init__(self, df):
        # I don't like this current setup at all, so I need to think through how I want to handle it.
        self.lookup = Lookup()
        self.data = lookup.create_translated_columns(df)
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

"""Basic example of current usage"""
# initialize instance of RequestBuilder, WebHandler, and Lookup
builder = RequestBuilder()
handler = WebHandler()
lookup = Lookup()

# for i in range(6):
#     # Create a new RequestBuilder instance for each request
#     params_dict = {
#         'tag': ["starsoffseason7", "starsoffseason6", "starsoffhazardousseason7", "starsoffhazardousrandomsseason7"],
#         'swing': lookup.lookup(LookupDicts.TYPE_OF_SWING, 'Star'),
#         'limit_games': 99999,
#         'stadium': i  # Dynamically set the stadium parameter
#     }
#     rq_builder = RequestBuilder()
#
#     # Build the request for the current stadium
#     request_list = rq_builder.add(Endpoint.LANDING_DATA, params=params_dict).build()
#
#     # Fetch the data using the data handler
#     stadium_data = handler.fetch_data(request_list)  # Assuming you want a single DataFrame
#
#     # Save the fetched data to a CSV file, named according to the stadium
#     csv_filename = f"star_stadium_{i}_data"
#     handler.save_to_csv(stadium_data, csv_filename)

# Make parameter list using the appropriate list
# (classes that make use of game/event class have access to those variables)
# lookup function allows for passing key or value as argument, and will return the other
# params = LandingDataParameterList(
#     # tag=["starsoffseason7", "starsoffseason6", "starsoffhazardousseason7", "starsoffhazardousrandomsseason7"],
#     swing=lookup.lookup(LookupDicts.TYPE_OF_SWING, 'Slap'),
#     limit_games=99999,
#     tag=['starsoffseason6'],
#     # contact=[1, 2, 3]
# )

# Use builder class to create a request list to pass to DataHandler
# request_list = builder \
#     .add(Endpoint.LANDING_DATA, params=params) \
#     .build()

# Fetch the data using the data handler and save it to a variable
# s7_off_mario = handler.fetch_data(request_list)

# Initialize your WebHandler outside the loop
# handler = WebHandler(cache=True)
# rq = builder
# Loop through the stadium IDs and fetch data for each one
# for i in range(6):
#     params = LandingDataParameterList(
#         tag=["starsoffseason7", "starsoffseason6", "starsoffhazardousseason7", "starsoffhazardousrandomsseason7"],
#         swing=lookup.lookup(LookupDicts.TYPE_OF_SWING, 'Slap'),
#         limit_games=99999,
#         stadium=i,  # Set the stadium parameter
#     )
#
#     # Build the request for the current stadium
#     rq = rq.add(Endpoint.LANDING_DATA, params=params)
#
# # Fetch the data using the data handler and save it to a variable
# stadium_data = handler.fetch_data(rq)
#
# # Save the fetched data to a CSV file, named according to the stadium
# csv_filename = f"stadium_{i}_data"
# handler.save_to_csv(stadium_data, csv_filename)

# You can save it to a CSV or a SQLite database
# handler.save_to_csv(s7_off_mario, file_name="Mario_LD_S7OFF")

# Load it using pandas
#
# csv_files = glob.glob('stadium_*.csv') + glob.glob('charge_stadium_*.csv') + glob.glob('star_stadium_*.csv')
#
# dfs = []  # List to hold dataframes
#
# for file in csv_files:
#     # Use regex to extract the stadium number from the filename
#     match = re.search(r'stadium_(\d+)_data\.csv', file)
#     if match:
#         stadium_id = int(match.group(1))
#         temp_df = pd.read_csv(file)
#         temp_df['stadium'] = stadium_id  # Add the stadium variable
#         dfs.append(temp_df)
#
# # Concatenate all the dataframes in the list
# combined_df = pd.concat(dfs, ignore_index=True)

# Save the combined dataframe
# combined_df.to_csv("combined_stadium_data.csv", index=False)
data = pd.read_csv('combined_stadium_data.csv')

ld = LandingData(data)
coords = ld.get_coordinates()
num = ld.get_numeric_data()
cat = ld.get_categorical_data()
hits = ld.get_hits()
outs = ld.get_outs()
# Calculate hits
data['is_hit'] = data['final_result'].isin([7, 8, 9, 10])

# Calculate outs based on the specified final_result codes
data['is_out'] = data['final_result'].isin([4, 5, 6, 14, 15, 16])

# Define at-bats as any row that is either a hit or an out
data['is_at_bat'] = data['is_hit'] | data['is_out']

# Calculate total hits and at-bats
total_hits = data['is_hit'].sum()
total_at_bats = data['is_at_bat'].sum()

# Calculate batting average
batting_average = total_hits / total_at_bats if total_at_bats > 0 else 0

print(f"Batting Average: {batting_average:.3f}")


def print_contact_ratios_query(data, swing_type):
    contact_counts = data.query('type_of_swing_str == @swing_type')['type_of_contact_str'].value_counts()
    total_swings = contact_counts.sum()
    contact_ratios = contact_counts / total_swings
    print(f"Ratios for {swing_type} swings:")
    print(contact_ratios)
    print()


print(num.final_result.value_counts())

# Calculate and print ratios for each swing type
print_contact_ratios_query(data, "Charge")
print_contact_ratios_query(data, "Star")
print_contact_ratios_query(data, "Slap")

# sns.heatmap(data, x='ball_x_landing_pos', y='ball_z_landing_pos', cmap='viridis')