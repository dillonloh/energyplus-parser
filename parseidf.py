# This file is licensed under the terms of the MIT license. See the file
# "LICENSE" in the project root for more information.
#
# This module was developed by Daren Thomas at the assistant chair for
# Sustainable Architecture and Building Technologies (Suat) at the Institute of
# Technology in Architecture, ETH Zürich. See http://suat.arch.ethz.ch for
# more information.
'''
parseidf.py


parses an idf file into a dictionary of lists in the following manner:

    each idf object is represented by a list of its fields, with the first
    field being the objects type.

    each such list is appended to a list of objects with the same type in the
    dictionary, indexed by type:

    { [A] => [ [A, x, y, z], [A, a, b, c],
      [B] => [ [B, 1, 2], [B, 1, 2, 3] }

    also, all field values are strings, i.e. no interpretation of the values is
    made.
'''

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import ply.lex as lex
import ply.yacc as yacc

# list of token names
tokens = ('VALUE',
          'COMMA',
          'SEMICOLON')

# regular expression rules for simple tokens
t_COMMA = r'[ \t]*,[ \t]*'
t_SEMICOLON = r'[ \t]*;[ \t]*'


# ignore comments, tracking line numbers at the same time
def t_COMMENT(t):
    r'[ \t\r\n]*!.*'
    newlines = [n for n in t.value if n == '\n']
    t.lineno += len(newlines)
    pass
    # No return value. Token discarded


# Define a rule so we can track line numbers
def t_newline(t):
    r'[ \t]*(\r?\n)+'
    t.lexer.lineno += len(t.value)


def t_VALUE(t):
    r'[ \t]*([^!,;\n]|[*])+[ \t]*'
    return t


# Error handling rule
def t_error(t):
    raise SyntaxError("Illegal character '%s' at line %d of input"
                      % (t.value[0], t.lexer.lineno))
    t.lexer.skip(1)


# define grammar of idf objects
def p_idffile(p):
    'idffile : idfobjectlist'
    result = {}
    for idfobject in p[1]:
        name = idfobject[0]
        result.setdefault(name.upper(), []).append(idfobject)
    p[0] = result


def p_idfobjectlist(p):
    'idfobjectlist : idfobject'
    p[0] = [p[1]]


def p_idfobjectlist_multiple(p):
    'idfobjectlist : idfobject idfobjectlist'
    p[0] = [p[1]] + p[2]


def p_idfobject(p):
    'idfobject : objectname SEMICOLON'
    p[0] = [p[1]]


def p_idfobject_with_values(p):
    'idfobject : objectname COMMA valuelist SEMICOLON'
    p[0] = [p[1]] + p[3]


def p_objectname(p):
    'objectname : VALUE'
    p[0] = p[1].strip()


def p_valuelist(p):
    'valuelist : VALUE'
    p[0] = [p[1].strip()]


def p_valuelist_multiple(p):
    'valuelist : VALUE COMMA valuelist'
    p[0] = [p[1].strip()] + p[3]


# oh, and handle errors
def p_error(p):
    raise SyntaxError("Syntax error in input on line %d" % lex.lexer.lineno)


def parse(input):
    '''
    parses a string with the contents of the idf file and returns the
    dictionary representation.
    '''
    lexer = lex.lex(debug=False)
    lexer.input(input)
    parser = yacc.yacc()
    result = parser.parse(debug=False)
    return result


def extract_zones(parsed_idf):
    """
    Extracts the zones from the parsed IDF file and returns a dictionary
    containing the origin and surfaces of each zone.

    Args:
        parsed_idf (dict): The parsed IDF file. This should be the output of the `parse` function.

    Returns:
        dict: A dictionary containing the origin and surfaces of each zone. The dictionary is structured as follows:
        {
            "zone_name": {
                "origin": (x, y, z),
                "surfaces": [
                    [(x1, y1, z1), (x2, y2, z2), ...],
                    [(x1, y1, z1), (x2, y2, z2), ...],
                    ...
                ]
            },
            ...
        }
    """
    zones = {}
    for zone in parsed_idf.get('ZONE', []):
        zone_name = zone[1]
        zones[zone_name] = {
            "origin": (float(zone[3]), float(zone[4]), float(zone[5])),
            "surfaces": []
        }

    for surface in parsed_idf.get('BUILDINGSURFACE:DETAILED', []):
        zone_name = surface[4]
        if zone_name in zones:
            try:
                num_vertices_index = surface.index('4') #TODO: dynamically grab no. of vertices from the field
                num_vertices = int(surface[num_vertices_index])
                vertices_start_index = num_vertices_index + 1
                vertices = []
                for i in range(num_vertices):
                    x = float(surface[vertices_start_index + i * 3])
                    y = float(surface[vertices_start_index + i * 3 + 1])
                    z = float(surface[vertices_start_index + i * 3 + 2])
                    vertices.append((x, y, z))
                zones[zone_name]["surfaces"].append(vertices)
            except ValueError as e:
                print(f"Error parsing vertices for surface {surface}: {e}")
                continue
    
    return zones


def plot_2d_geometry(zones):
    fig, ax = plt.subplots()

    for zone_name, zone_info in zones.items():
        for surface in zone_info["surfaces"]:
            # Extract only the x and y coordinates for the 2D plot
            vertices_2d = [(x, y) for x, y, z in surface]
            polygon = patches.Polygon(vertices_2d, closed=True, edgecolor='r')
            ax.add_patch(polygon)

        # Calculate the centroid of the first surface to place the label
        if zone_info["surfaces"]:
            first_surface = zone_info["surfaces"][0]
            centroid_x = sum(x for x, y, z in first_surface) / len(first_surface)
            centroid_y = sum(y for x, y, z in first_surface) / len(first_surface)
            ax.text(centroid_x, centroid_y, zone_name, ha='center', va='center', color='black', fontsize=8, bbox=dict(facecolor='white', alpha=0.6))

    ax.set_xlim(0, 30)  # Adjust according to your building size
    ax.set_ylim(0, 20)  # Adjust according to your building size
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    plt.title('2D Geometry Plot')
    plt.show()


def plot_3d_point_cloud(zones, point_size=4, num_points=20):
    dense_points = []
    zone_colors = {}
    unique_colors = list(mcolors.TABLEAU_COLORS.values())

    for i, zone_name in enumerate(zones.keys()):
        zone_colors[zone_name] = unique_colors[i % len(unique_colors)]

    for zone_name, zone_info in zones.items():
        zone_color = zone_colors[zone_name]
        for surface in zone_info["surfaces"]:
            x_coords = [x for x, y, z in surface]
            y_coords = [y for x, y, z in surface]
            z_coords = [z for x, y, z in surface]

            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            z_min, z_max = min(z_coords), max(z_coords)

            x_points = np.linspace(x_min, x_max, num=num_points)
            y_points = np.linspace(y_min, y_max, num=num_points)
            z_points = np.linspace(z_min, z_max, num=num_points)

            for x in x_points:
                for y in y_points:
                    for z in z_points:
                        dense_points.append((x, y, z, zone_color))

    x_vals, y_vals, z_vals, colors = zip(*dense_points)

    print(f"Plotting 3D Geometry with {len(x_vals)} points...")
    scatter = go.Scatter3d(
        x=x_vals,
        y=y_vals,
        z=z_vals,
        mode='markers',
        marker=dict(
            size=point_size,
            color=colors,
            opacity=0.7
        )
    )

    layout = go.Layout(
        title='3D Geometry Plot',
        scene=dict(
            xaxis=dict(title='X Coordinate'),
            yaxis=dict(title='Y Coordinate'),
            zaxis=dict(title='Z Coordinate')
        )
    )

    fig = go.Figure(data=[scatter], layout=layout)
    fig.show()

def plot_3d_mesh(zones):
    fig = go.Figure()
    
    # Define a list of colors for different zones
    colors = ['blue', 'green', 'red', 'purple', 'orange', 'cyan', 'magenta']

    for zone_index, (zone_name, zone_info) in enumerate(zones.items()):
        color = colors[zone_index % len(colors)]  # Cycle through the colors

        for surface in zone_info["surfaces"]:
            x_coords = [x for x, y, z in surface]
            y_coords = [y for x, y, z in surface]
            z_coords = [z for x, y, z in surface]
            
            # Ensure the surface is closed by repeating the first point
            if x_coords[0] != x_coords[-1] or y_coords[0] != y_coords[-1] or z_coords[0] != z_coords[-1]:
                x_coords.append(x_coords[0])
                y_coords.append(y_coords[0])
                z_coords.append(z_coords[0])
            
            # Creating a triangular mesh by using indices of the vertices
            num_vertices = len(x_coords)
            i = []
            j = []
            k = []
            for idx in range(1, num_vertices - 2):
                i.append(0)
                j.append(idx)
                k.append(idx + 1)

            fig.add_trace(go.Mesh3d(
                x=x_coords,
                y=y_coords,
                z=z_coords,
                i=i,
                j=j,
                k=k,
                opacity=0.5,
                color=color,
                flatshading=True
            ))

    fig.update_layout(
        title='3D Mesh Plot',
        scene=dict(
            xaxis=dict(title='X Coordinate'),
            yaxis=dict(title='Y Coordinate'),
            zaxis=dict(title='Z Coordinate')
        )
    )

    fig.show()
