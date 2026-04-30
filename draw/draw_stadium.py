import matplotlib.pyplot as plt
import numpy as np


def draw_stad_3d(stadium, add_label=False):
    # Open the file for reading
    with open(f'{stadium}.txt', 'r') as file:
        # Initialize empty lists to store x, y, and z coordinates
        x_coords = []
        y_coords = []
        z_coords = []  # Assume a fixed z-coordinate for all points for simplicity

        # Read each line in the file
        for line in file:
            # Split the line into individual coordinates
            x, y = map(float, line.split())
            z = 0  # Example fixed z-coordinate

            # Append the coordinates to the respective lists
            x_coords.append(x)
            y_coords.append(y)
            z_coords.append(z)

    # Create a 3D plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Plot the stadium in 3D
    ax.plot3D(x_coords, y_coords, z_coords, label=stadium if add_label else None)

    draw_45_degree_lines(ax=ax)
    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title('3D Stadium Coordinates')

    if add_label:
        ax.legend()

    # uncommented to try to enable more plotting, recomment if it isn't working
    # plt.show()

    return ax

def draw_stad(stadium, add_label=False, ax=None):
    # Open the file for reading
    with open(f'{stadium}.txt', 'r') as file:
        # Initialize empty lists to store x and y coordinates
        x_coords = []
        y_coords = []

        # Read each line in the file
        for line in file:
            # Split the line into individual coordinates
            x, y = map(float, line.split())

            # Append the coordinates to the respective lists
            x_coords.append(x)
            y_coords.append(y)
    plot_stad(x_coords, y_coords, stadium, add_label, ax)

def draw_stad_part(stadium, add_label=False):
    # Open the file for reading
    with open(f'{stadium}.txt', 'r') as file:
        # Initialize empty lists to store x and y coordinates
        x_coords = []
        y_coords = []

        # Read each line in the file
        for line in file:
            # Split the line into individual coordinates
            x, y = map(float, line.split())

            # Append the coordinates to the respective lists
            # if y > 50.0 and x < -30.0:
            x_coords.append(x)
            y_coords.append(y)
    plot_stad(x_coords, y_coords, stadium, add_label)
    draw_45_degree_lines()
def plot_stad(x_coords, y_coords, stadium, add_label=False, ax=None):
    # Plot the coordinates with a label for the legend
    if ax:
        if add_label:
            ax.plot(x_coords, y_coords, label=stadium)
        else:
            ax.plot(x_coords, y_coords)

        ax.set_xlabel('X')
        ax.set_ylabel('Z')
        ax.set_title('Stadium Coords')
    else:
        if add_label:
            plt.plot(x_coords, y_coords, label=stadium)
        else:
            plt.plot(x_coords, y_coords)


        # Set labels and title
        plt.xlabel('X')
        plt.ylabel('Z')
        plt.title('Stadium Coordinates')


def draw_fielder_positions(draw_label=False, color='black', marker="s", ax=None):
    starting_coordinates = {
        'P': [0, 0.22299999, 18.3999996],
        'C': [0, -0, -3.7999995],
        '1B': [18.5, -0, 22],
        '2B': [11, -0, 36],
        '3B': [-18.5, -0, 22],
        'SS': [-11, -0, 36],
        'LF': [-34, -0, 60],
        'CF': [0, -0, 76],
        'RF': [34, 0, 60]
    }


    # Plot the fielder starting coordinates on top of the diagram
    x_coords = [coord[0] for coord in starting_coordinates.values()]
    y_coords = [coord[2] for coord in starting_coordinates.values()]

    # Use provided ax or default to plt
    if ax is not None:
        scatter = ax.scatter(x_coords, y_coords, color=color, label='Starting Coordinates' if draw_label else '',
                             marker=marker)
    else:
        scatter = plt.scatter(x_coords, y_coords, color=color, label='Starting Coordinates' if draw_label else '',
                              marker=marker)

    # Add labels for each position
    if draw_label:
        for position, coord in starting_coordinates.items():
            if ax is not None:
                ax.text(coord[0], coord[2], position, ha='center', va='bottom')  # Adjusted for Y-axis using coord[2]
            else:
                plt.text(coord[0], coord[2], position, ha='center', va='bottom')  # Adjusted for Y-axis using coord[2]

        # Add legend only if ax is provided
        if ax is not None:
            ax.legend()

    # Show the plot
    # plt.show()

# Call the draw_stad() function for each stadium
# add_label = True
# draw_stad_part('yoshi_park', add_label)
# # draw_stad_part('toy_field', add_label)
# draw_stad_part('mario_stadium', add_label)
# draw_stad_part('peach_garden', add_label)
# draw_stad_part('dk_jungle', add_label)
# draw_stad_part('wario_palace', add_label)
# draw_stad_part('bowser_castle', add_label)
# draw_fielder_positions()
# # # Display the color legend
# plt.legend()
# #
# # # Show the plot with overlaid coordinates
# plt.show()

def calculate_stadium_area(stadium):
    # Read stadium coordinates from the file
    with open(f'{stadium}.txt', 'r') as file:
        x_coords = []
        y_coords = []
        for line in file:
            x, y = map(float, line.split())
            x_coords.append(x)
            y_coords.append(y)

    # Shoelace formula on the ordered boundary polygon.
    x = np.asarray(x_coords)
    y = np.asarray(y_coords)
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def draw_45_degree_lines(color='red', ax=None, three_dim=False):
    # Calculate the angle in radians (45 degrees is pi/4 radians)
    angle_radians = np.pi / 4

    # Define the length of the lines (adjust this value to make the lines longer or shorter)
    line_length = 81

    # Calculate the end points of the lines
    x_end = line_length * np.cos(angle_radians)
    y_end = line_length * np.sin(angle_radians)

    # Draw the 45 degree angle of foul line from 0, 0 coordinate
    if not ax:
        plt.plot([0, x_end], [0, y_end], color=color)
        plt.plot([0, -x_end], [0, y_end], color=color)
    else:
        if three_dim:
            ax.plot3D([0, x_end], [0, y_end], [0, 0], color=color)
            ax.plot3D([0, -x_end], [0, y_end], [0, 0], color=color)
        else:
            ax.plot([0, x_end], [0, y_end], color=color)
            ax.plot([0, -x_end], [0, y_end], color=color)

    # Add a legend to the plot
    # plt.legend()


def draw_bases():
    pass


def draw_hazards():
    pass

