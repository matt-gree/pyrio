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

    # Convert the coordinates to a NumPy array for the ConvexHull calculation
    points = np.array(list(zip(x_coords, y_coords)))

    # Calculate the Convex Hull
    hull = ConvexHull(points)

    # Calculate the area of the Convex Hull
    area = hull.area

    return area

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


if __name__ == '__main__':


    # vertices = []
    #
    # with open('untitled.obj', 'r') as obj_file:
    #     for line in obj_file:
    #         if line.startswith('v'):
    #             values = line.split()
    #             if float(values[2]) == 0.0:
    #                 x = float(values[1])
    #                 z = float(values[3])
    #                 vertices.append((x, z))
    #
    # Save the vertices to a file
    # with open('bowser_castle.txt', 'w') as output_file:
    #     for vertex in vertices:
    #         output_file.write(f"{vertex[0]} {vertex[1]}\n")
    #
    #
    # draw_stad('bowser_castle')
    # plt.show()
    import numpy as np
    from scipy.spatial import ConvexHull


    # Call the draw_stad() function for each stadium
    add_label = True
    # draw_stad_part('yoshi_park', add_label)
    # draw_stad_part('toy_field', add_label)
    draw_stad_part('mario_stadium', add_label)
    # draw_stad_part('peach_garden', add_label)
    # draw_stad_part('dk_jungle', add_label)
    # draw_stad_part('wario_palace', add_label)
    # draw_stad_part('bowser_castle', add_label)
    draw_fielder_positions()

    # Call the function to draw 45-degree lines
    # draw_45_degree_lines()
    # Calculate and print the area for each stadium
    # stadiums = ['yoshi_park', 'mario_stadium', 'peach_garden', 'dk_jungle', 'wario_palace', 'bowser_castle']
    # for stadium in stadiums:
    #     area = calculate_stadium_area(stadium)
    #     print(f"Stadium {stadium}: Area within 45-degree lines = {area:.2f}")
    # Display the plot
    # Sample hang times for the points
    x_coords = [-15, -10, -5, 15, -10, -15, -15, -5, -25, 25, 40]
    y_coords = [20, 25, 10, 20, 20, 25, 20, 25, 40, 40, 75]
    hang_times = [40, 40, 20, 40, 40, 50, 50, 40, 90, 100, 210]
    expected_batting_avg = [.263, .113, .150, .263, .275, .659, .086, .048, 1.0, .917, .647]

    # hang_times = [160]
    # x_coords = [-30]
    # heights = [50]
    # Sample coordinates for the points

    # Sample height values for the points (corresponding to hang times)
    # Create a colormap to map the hang time values to colors
    cmap = plt.cm.get_cmap('viridis')  # You can choose any other colormap

    # Define a function to plot a Bézier curve between two points with given control points
    def plot_bezier_curve(x0, y0, x1, y1, cx, cy, color, linewidth):
        t = np.linspace(0, 1, 100)
        x = (1 - t) ** 2 * x0 + 2 * t * (1 - t) * cx + t ** 2 * x1
        y = (1 - t) ** 2 * y0 + 2 * t * (1 - t) * cy + t ** 2 * y1
        plt.plot(x, y, color=color, linewidth=linewidth)

    # Plot the lines with curves from (0, 0) to each landing point
    for x, y, ht in zip(x_coords, y_coords, hang_times):
        curve_control_x = x / 4  # Adjust this value to control the curve
        curve_control_y = y / 1  # Adjust this value to control the curve
        # plot_bezier_curve(0, 0, x, y, curve_control_x, curve_control_y, color=cmap(ht / max(hang_times)), linewidth=ht / 50)
        plot_bezier_curve(0, 0, x, y, curve_control_x, curve_control_y, color="black", linewidth=ht / 100)

    # Plot the landing points with color representing hang time and size representing batting average
    sc = plt.scatter(x_coords, y_coords, c=expected_batting_avg, cmap=cmap, marker='o', s=[200 * avg for avg in expected_batting_avg])

    # Set labels and title
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title('Ball Traveling Through the Air')

    # Add a colorbar to show the mapping of hang times to colors
    cbar = plt.colorbar(sc)
    cbar.set_label('xBA')

    # Show the plot
    plt.show()
    # Plot the lines from (0, 0) to each landing point with size based on hang time
    # for x, y, ht in zip(x_coords, y_coords, hang_times):
    #     plt.plot([0, x], [0, y], color=cmap(ht / max(hang_times)), linewidth=ht / 50)
    #
    # # Plot the landing points with color representing hang time and size representing batting average
    # sc = plt.scatter(x_coords, y_coords, c=expected_batting_avg, cmap=cmap, marker='o', s=[100 * avg for avg in expected_batting_avg])
    #
    # # Set labels and title
    # plt.xlabel('X')
    # plt.ylabel('Y')
    # plt.title('Ball Traveling Through the Air')
    #
    # # Add a colorbar to show the mapping of hang times to colors
    # cbar = plt.colorbar(sc)
    # cbar.set_label('xBA')
    #
    # # Show the plot
    # plt.show()
    # Plot the points with varying heights and colors based on hang time
    # plt.scatter(x_coords, heights, c=hang_times, cmap=cmap, marker='o', s=20)
    #
    # # Set labels and title
    # plt.xlabel('X')
    # plt.ylabel('Height')
    # plt.title('Ball Traveling Through the Air')
    #
    # # Add a colorbar to show the mapping of hang times to colors
    # cbar = plt.colorbar()
    # cbar.set_label('Hang Time')
    #
    # # Show the plot
    # plt.show()
    # plt.scatter(-12.5, 22.5, color="red", marker="o", s=20)
    # plt.show()


    # # Sample data for hang times and expected batting averages
    # hang_times = [10, 20, 30, 40]
    # expected_batting_avg = [0.3, 0.4, 0.5, 0.6]
    #
    # # Sample coordinates for the points
    # x_coords = [-15, -10, -5, 0]
    # y_coords = [-20, -15, -10, -5]
    #
    # # Create a colormap to map the hang time values to colors
    # cmap = plt.cm.get_cmap('viridis')
    #
    # # Plot the lines from (0, 0) to each landing point with size based on hang time
    # for x, y, ht in zip(x_coords, y_coords, hang_times):
    #     plt.plot([0, x], [0, y], color=cmap(ht / max(hang_times)), linewidth=ht / 5)
    #
    # # Plot the landing points with color representing hang time and size representing batting average
    # sc = plt.scatter(x_coords, y_coords, c=hang_times, cmap=cmap, marker='o', s=[100 * avg for avg in expected_batting_avg])
    #
    # # Set labels and title
    # plt.xlabel('X')
    # plt.ylabel('Y')
    # plt.title('Ball Traveling Through the Air')
    #
    # # Add a colorbar to show the mapping of hang times to colors
    # cbar = plt.colorbar(sc)
    # cbar.set_label('Hang Time')
    #
    # # Show the plot
    # plt.show()

    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    from scipy.interpolate import griddata
    stadium = 'mario_stadium'
    # Assume x_coords and y_coords are the stadium's boundary coordinates
    x_coords, y_coords = zip(*np.loadtxt(f'{stadium}.txt'))

    # Create a plot for the stadium
    plt.figure(figsize=(10, 7))
    plt.plot(x_coords, y_coords, label='Stadium Boundary')

    # Create a grid for the heatmap
    grid_x, grid_y = np.mgrid[min(x_coords):max(x_coords):100j, min(y_coords):max(y_coords):100j]

    # Example heatmap data (replace with your data)
    points = np.random.rand(100, 2) * [max(x_coords) - min(x_coords), max(y_coords) - min(y_coords)] + [min(x_coords), min(y_coords)]
    values = np.random.rand(100)

    # Interpolate the data onto the grid
    grid_z = griddata(points, values, (grid_x, grid_y), method='cubic')

    # Mask out areas outside the stadium
    polygon = Path(list(zip(x_coords, y_coords)))
    mask = np.array([[not polygon.contains_point((i, j)) for j in np.linspace(min(y_coords), max(y_coords), 100)] for i in np.linspace(min(x_coords), max(x_coords), 100)])
    grid_z = np.ma.array(grid_z, mask=mask)

    # Plot the heatmap
    plt.imshow(grid_z.T, extent=(min(x_coords), max(x_coords), min(y_coords), max(y_coords)), origin='lower', alpha=0.5, cmap='viridis')

    plt.colorbar(label='Heatmap Intensity')
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title('Stadium with Heatmap')
    plt.legend()
    plt.show()

    import numpy as np
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D



    draw_stad_3d("mario_stadium")