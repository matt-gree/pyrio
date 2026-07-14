import numpy as np
import pandas as pd

# not sure where to include this for now
fielder_starting_positions = {
    0: [0, 0.22299999, 18.3999996],
    1: [0, 0, -3.7999995],
    2: [18.5, 0, 22],
    3: [11, 0, 36],
    4: [-18.5, 0, 22],
    5: [-11, 0, 36],
    6: [-34, 0, 60],
    7: [0, 0, 76],
    8: [34, 0, 60]
}

def calc_fielder_distance_speed(df: pd.DataFrame) -> pd.DataFrame:
    # Create columns for the differences initialized with NaN
    df['x_diff'] = np.nan
    df['y_diff'] = np.nan
    df['z_diff'] = np.nan


    # Calculate 3D adjusted hang time by subtracting lockout
    lockout = {
        "P": 25,
        "C": 40,
        "1B": 16,
        "2B": 15,
        "3B": 18,
        "SS": 17,
        "LF": 50,
        "CF": 50,
        "RF": 50
    }

    # Check if fielder_position is in the starting_positions and calculate the differences
    for i, pos in df['fielder_position'].items():
        start_pos = fielder_starting_positions.get(pos)
        if start_pos is not None:
            df.at[i, 'x_diff'] = df.at[i, 'fielder_x_pos'] - start_pos[0]
            df.at[i, 'y_diff'] = df.at[i, 'fielder_y_pos'] - start_pos[1]
            df.at[i, 'z_diff'] = df.at[i, 'fielder_z_pos'] - start_pos[2]

    # Calculate 3D distance
    df['fielder_distance'] = np.sqrt(df['x_diff'] ** 2 + df['y_diff'] ** 2 + df['z_diff'] ** 2)

    df['lockout'] = df['fielder_position_str'].map(lockout)
    df['ball_hang_time_adjusted'] = np.maximum(df['ball_hang_time'] - df['lockout'], 0)

    # Calculate 3D fielder speed, setting a minimum threshold of 0
    df['fielder_speed'] = df['fielder_distance'] / df['ball_hang_time_adjusted'].replace(0, np.nan)
    df['fielder_speed'] = df['fielder_speed'].clip(lower=0)  # Set negative speeds to 0

    # Calculate 2D distance
    df['fielder_distance_2d'] = np.sqrt(df['x_diff'] ** 2 + df['z_diff'] ** 2)

    # Calculate 2D adjusted hang time by subtracting lockout
    df['ball_hang_time_adjusted_2d'] = np.maximum(df['ball_hang_time'] - df['lockout'], 0)

    # Calculate 2D fielder speed, setting a minimum threshold of 0
    df['fielder_speed_2d'] = df['fielder_distance_2d'] / df['ball_hang_time_adjusted_2d'].replace(0, np.nan)
    df['fielder_speed_2d'] = df['fielder_speed_2d'].clip(lower=0)  # Set negative speeds to 0

    return df


def calc_fielder_distance_speed_from_ball(df: pd.DataFrame) -> pd.DataFrame:
    # Create columns for the differences initialized with NaN
    df['x_diff_ball'] = np.nan
    df['y_diff_ball'] = np.nan
    df['z_diff_ball'] = np.nan

    # Calculate the Euclidean distance

    # Apply lockout based on fielder position
    lockout = {
        "P": 25,
        "C": 40,
        "1B": 16,
        "2B": 15,
        "3B": 18,
        "SS": 17,
        "LF": 50,
        "CF": 50,
        "RF": 50
    }
    # Check if fielder_position is in the starting_positions and calculate the differences
    for i, pos in df['fielder_position'].items():
        start_pos = fielder_starting_positions.get(pos)
        if start_pos is not None:
            df.at[i, 'x_diff_ball'] = df.at[i, 'ball_x_landing_pos'] - start_pos[0]
            df.at[i, 'y_diff_ball'] = df.at[i, 'ball_y_landing_pos'] - start_pos[1]
            df.at[i, 'z_diff_ball'] = df.at[i, 'ball_z_landing_pos'] - start_pos[2]

    df['fielder_distance_ball'] = np.sqrt(df['x_diff_ball'] ** 2 + df['y_diff_ball'] ** 2 + df['z_diff_ball'] ** 2)

    df['lockout'] = df['fielder_position_str'].map(lockout)

    # Calculate adjusted hang time
    df['ball_hang_time_adjusted'] = df['ball_hang_time'].replace(0, np.nan) - df['lockout']

    # Calculate fielder speed, setting a minimum threshold of 0
    df['fielder_speed_ball'] = df['fielder_distance_ball'] / df['ball_hang_time_adjusted'].replace(0, np.nan)
    df['fielder_speed_ball'] = df['fielder_speed_ball'].clip(lower=0)  # Set negative speeds to 0

    # Calculate the Euclidean distance in 2D (ignoring y component)
    df['fielder_distance_ball_2d'] = np.sqrt(df['x_diff_ball'] ** 2 + df['z_diff_ball'] ** 2)

    # Calculate 2D fielder speed
    df['fielder_speed_ball_2d'] = df['fielder_distance_ball_2d'] / df['ball_hang_time_adjusted'].replace(0, np.nan)
    df['fielder_speed_ball_2d'] = df['fielder_speed_ball_2d'].clip(lower=0)  # Set negative speeds to 0

    return df

# def calc_fielder_distance_speed_from_ball(df):
#     # Create columns for the differences initialized with NaN
#     df['x_diff_ball'] = np.nan
#     df['y_diff_ball'] = np.nan
#     df['z_diff_ball'] = np.nan
#
#     lockout = {
#         "P": 25,
#         "C": 40,
#         "1B": 16,
#         "2B": 15,
#         "3B": 18,
#         "SS": 17,
#         "LF": 50,
#         "CF": 50,
#         "RF": 50
#     }
#
#     # Check if fielder_position is in the starting_positions and calculate the differences
#     for i, pos in df['fielder_position'].items():
#         start_pos = fielder_starting_positions.get(pos)
#         if start_pos is not None:
#             df.at[i, 'x_diff_ball'] = df.at[i, 'ball_x_landing_pos'] - start_pos[0]
#             df.at[i, 'y_diff_ball'] = df.at[i, 'ball_y_landing_pos'] - start_pos[1]
#             df.at[i, 'z_diff_ball'] = df.at[i, 'ball_z_landing_pos'] - start_pos[2]
#
#     # Calculate the Euclidean distance
#     df['fielder_distance_ball'] = np.sqrt(df['x_diff_ball'] ** 2 + df['y_diff_ball'] ** 2 + df['z_diff_ball'] ** 2)
#
#     # Calculate speed as distance/hang_time - lockout
#     df['lockout'] = df['fielder_position_str'].apply(lambda x: lockout.get(x, 0))
#     df['ball_hang_time_adjusted'] = df['ball_hang_time'].replace(0, np.nan) - df['lockout']
#
#     # Calculate fielder speed, setting a minimum threshold of 0
#     df['fielder_speed_ball'] = df['fielder_distance_ball'] / df['ball_hang_time_adjusted'].replace(0, np.nan)
#     df['fielder_speed_ball'] = df['fielder_speed_ball'].clip(lower=0)  # Set negative speeds to 0
#
#     return df

def calc_ball_fielder_diff(df: pd.DataFrame) -> pd.DataFrame:
    # Calculate the differences between ball and fielder positions
    df['x_fielder_ball_diff'] = df['ball_x_landing_pos'] - df['fielder_x_pos']
    df['y_fielder_ball_diff'] = df['ball_y_landing_pos'] - df['fielder_y_pos']
    df['z_fielder_ball_diff'] = df['ball_z_landing_pos'] - df['fielder_z_pos']

    df['fielder_ball_diff_distance'] = np.sqrt((df['x_fielder_ball_diff'] ** 2) + (df['y_fielder_ball_diff'] ** 2) + (df['z_fielder_ball_diff'] ** 2))
    df['fielder_ball_diff_distance_2d'] = np.sqrt((df['x_fielder_ball_diff'] ** 2) + (df['z_fielder_ball_diff'] ** 2))
    return df


