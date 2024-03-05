from api import RequestBuilder, Endpoint, LandingDataParameterList
from data_handler import WebHandler
from lookup import Lookup, LookupDicts
import pandas as pd
from api import print_parameter_list


"""Basic example of current usage"""
# initialize instance of RequestBuilder, WebHandler, and Lookup
builder = RequestBuilder()
handler = WebHandler()
lookup = Lookup()

# Make parameter list using the appropriate list
# (classes that make use of game/event class have access to those variables)
# lookup function allows for passing key or value as argument, and will return the other
params = LandingDataParameterList(
    tag="starsoffseason7",
    batter_char=lookup.lookup(LookupDicts.CHAR_NAME, 'Mario')
)

# Use builder class to create a request list to pass to DataHandler
request_list = builder \
    .add(Endpoint.LANDING_DATA, params=params) \
    .build()

# Fetch the data using the data handler and save it to a variable
s7_off_mario = handler.fetch_data(request_list)

# You can save it to a CSV or a SQLite database
handler.save_to_csv(s7_off_mario, file_name="Mario_LD_S7OFF")


# Load it using pandas
mario = pd.read_csv('data/Mario_LD_S7OFF.csv')

# wario_charge = wario[wario['type_of_swing'] == 2].copy()
# wario_charge.loc[:, 'IsSour'] = wario_charge['type_of_contact'].isin([0, 4])
# sour_percent = wario_charge.groupby('batter_username')['IsSour'].mean() * 100
# wario_valid_contact = wario_charge[wario_charge['type_of_contact'].isin([1, 2, 3])]
#
# grouped = wario_valid_contact.groupby('batter_username').agg({
#     'contact_quality': 'mean',
#     'frame_of_swing': 'mean'
# })
#
# grouped = grouped.join(sour_percent.rename('sour%'))
# swing_count = wario_charge.groupby('batter_username').size()
#
# grouped = grouped.join(swing_count.rename('count'))
# filtered_grouped = grouped[grouped['count'] >= 100]
# valid_usernames = filtered_grouped.index.tolist()

# Determine the number of subplots needed
# n = len(valid_usernames)
#
# # Create subplots - one for each player
# fig, axs = plt.subplots(n, 1, figsize=(10, n * 2))
#
# # Define the range and bins for the histogram
# data_range = (-1, 1)
# num_bins = 20
# bin_edges = np.linspace(data_range[0], data_range[1], num_bins + 1)
#
# for i, username in enumerate(valid_usernames):
#     # Select the current axis
#     ax = axs[i]
#
#     # Filter data for the current player
#     player_data = wario_valid_contact[
#         (wario_valid_contact['batter_username'] == username)]
#
#     # Create a 1D histogram for heatmap
#     x_hist, _ = np.histogram(player_data['ball_x_contact_pos'], bins=bin_edges, density=True)
#     x_hist = x_hist.reshape(1, -1)  # Reshape for heatmap compatibility
#
#     # Generate custom x-tick labels
#     x_tick_labels = [f"{edge:.1f}" for edge in bin_edges[::10]]  # Adjust step for fewer labels
#
#     # Plot heatmap for the current player's x position
#     sns.heatmap(x_hist, ax=ax, cmap='coolwarm', cbar=True,
#                 xticklabels=x_tick_labels)
#     ax.set_title(username)
#     ax.set_xlabel('Ball X Contact Position')
#     ax.set_xticks(np.arange(0, num_bins, step=10))
#
#     # Setting custom ticks to align with the labels
#     ax.set_xticks(np.arange(0, num_bins, step=10))
#     zero_pos = np.searchsorted(bin_edges, 0.0)  # Find the index for 0.0
#     pos_54 = np.searchsorted(bin_edges, 0.54)  # Find the index for 0.54
#     neg_54 = np.searchsorted(bin_edges, -0.54)  # Find the index for -0.54
#
#     ax.axvline(zero_pos, color='black', linestyle='dotted')
#     ax.axvline(pos_54, color='red', linestyle='dotted')
#     ax.axvline(neg_54, color='red', linestyle='dotted')
#     ax.set_yticks([])  # Hide Y-axis ticks
#
# # Adjust layout
# plt.tight_layout()
# plt.show()


# sorted_grouped = filtered_grouped.sort_values(by='contact_quality', ascending=False)
#
# print(sorted_grouped)
#
# # Filter the data to include only rows where 'final_result' is 10
# filtered_final_result_10 = wario_valid_contact[wario_valid_contact['final_result'] == 10]
#
# # Group the data by 'batter_username' and 'chem_links_ob' and count the occurrences
# result_counts = filtered_final_result_10.groupby(['batter_username', 'chem_links_ob']).size().unstack(fill_value=0)
#
# # Filter users with at least 10 total occurrences of 'final_result == 10'
# users_with_at_least_10_counts = result_counts[result_counts.sum(axis=1) >= 10]
#
# # Print the result
# print(users_with_at_least_10_counts)
#
# # Filter the data to include only rows where 'final_result' is 10
# filtered_final_result_10 = wario_valid_contact[wario_valid_contact['final_result'] == 10]
#
# # Group the data by 'batter_username' and count the total occurrences
# total_counts = wario_valid_contact.groupby('batter_username').size().reset_index(name='total_count')
#
# # Group the filtered data by 'batter_username' and count the occurrences of 'final_result == 10'
# result_counts = filtered_final_result_10.groupby('batter_username').size().reset_index(name='result_10_count')
#
# # Merge the total counts and result counts dataframes on 'batter_username'
# merged_counts = pd.merge(total_counts, result_counts, on='batter_username')
#
# # Calculate the percentage rate of 'final_result == 10' compared to the overall count and round to one decimal place
# merged_counts['percentage'] = round((merged_counts['result_10_count'] / merged_counts['total_count']) * 100, 1)
#
# # Filter users with at least 10 total occurrences
# users_with_at_least_10_counts = merged_counts[merged_counts['total_count'] >= 75]
#
# # Print the result
# print(users_with_at_least_10_counts)
