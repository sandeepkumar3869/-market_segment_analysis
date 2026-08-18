import requests
import re
import io
from PIL import Image
import pandas as pd
import numpy as np
import geopandas as gpd
import math
from shapely import geometry, affinity
from shapely.ops import polygonize, unary_union
from shapely.geometry import Point, Polygon, LineString, MultiLineString, MultiPolygon, box
from shapely.wkt import loads
from shapely.errors import WKTReadingError
from dataminer.connector import BigRed3
import ast
from ast import literal_eval
import itertools

try:
    import cairosvg
except ImportError as e:
    print("Error importing cairosvg:", e)
    pass 


"""  
Any changes in this file will need approval from the team first. :)

Update Logs:

####### Date - 2026-07-08 #######  - Sandeep
#### Add function - prep_register_shapes_from_hand_draw_vertical, function to convert manually defined  coordinates for register shapes this works if the check lanes are Verticle (eg.1332).

####### Date - 2026-02-24 #######  - Alieen
#### Add function - prep_register_shapes_from_hand_draw, function to convert manually defined  coordinates for register shapes this works if the check lanes are Horizontal (eg.1010).

####### Date - 2025-11-19 #######  - Alieen
#### Update function - get_grids, round the outer_coord of tba to int so each grid will be the same size 

####### Date - 2025-07-23 #######  - Alieen
#### Update new function - prep_register_shapes, prep check area shape by union all polygon from neptune checkout merch area

####### Date - 2025-07-15 #######  - Alieen
#### Add new function - identify_polygon_from_svg, trim_polygon_by_directional_shift,extend_polygon_by_directional_buffer, prep_register_shapes,find_cut_corner_direction,create_register_shape,identify_shape

####### Date - 2025-06-12 #######  - Alieen
#### fix function - def parse_polygon_string. error with string/json into shapely.wkt.loads() contains extra or malformed characters after the geometry definition.

####### Date - 2024-09-17 #######  - Alieen
#### Changes in the geopandas.sjoin() function starting from version 0.10.0 or higher - The op='within' has been replaced by predicate='within'.
#### Add new function - fetch_custom_adj
""" 


class store_map:

    def __init__(self, str_num,flr_num,str_path, pw, api_key):
        """ The __init__ method is roughly what represents a constructor in Python. 
        When we call arguments, it creates an object and passes it as the first parameter to the __init__ method. 
        Args:
            self: represents the instance of the object itself
            str_num: Type: String; Representing store number 
            flr_num: Type: Integer; Representing floor number (default input would be 1, wont be able to handle multi floor stores in this file, refer to store_map.v2 for multi foor stores)
            str_path: Type: String; Representing git location path (default input would be '/home/dataminer/workspace/TrIPS_BR3/') 
            api_key: Type: String; Representing key for api (default setting, no input needed)
            username: Type: String; Representing our team username
            pw: Type: String; Representing our password for team username
        """
        self.str_num = str_num
        self.flr_num = flr_num
        self.str_path = str_path
        self.api_key = api_key
        self.username = 'SVTPA002'
        self.pw = pw
    
    def get_store_map_api(self, excluded_layers=None):
        """ This function retrieves an SVG map from neptune api 
        """
        layers = ['wall-shapes', 'total-building-shapes', 'stockroom-shapes', 'stockroom-aisle-shapes', 'sales-floor-island-shapes', 'register-shapes', 'pharmacy-shapes',
                  'optical-shapes', 'floor-pads', 'fitting-room-shapes', 'clinic-shapes', 'aisle-shapes', 'admin-space-shapes', 'adjacency-names'] 
        if excluded_layers:
        # Ensure excluded_layers is a list, even if a single value is passed
            if isinstance(excluded_layers, str):
                excluded_layers = [excluded_layers]
            layers = [layer for layer in layers if layer not in excluded_layers]
        str_svg_url = f'https://api-internal.target.com/store_maps/v1/internal/svg_images?location_id={self.str_num}&floor_id={self.flr_num}&layers={",".join(layers)}&css_name=basic&key={self.api_key}'
        str_svg_res = requests.get(str_svg_url)
        return str_svg_res

    def extract_viewbox_and_scale(self, excluded_layers=None):
        """ This function retrieves an SVG map for a given store, converts it to a PNG,
        extracts viewbox details, and calculates the map scale.
        Returns:
            tuple: A tuple containing:
                - viewbox_width (float): The width of the viewbox.
                - viewbox_height (float): The height of the viewbox.
                - viewbox_min_x (float): The minimum x-coordinate of the viewbox.
                - viewbox_min_y (float): The minimum y-coordinate of the viewbox.
                - map_scale (float): The calculated map scale.
        Raises:
            ValueError: If the viewbox pattern is not found in the SVG data.
        """
        str_svg_res = self.get_store_map_api(excluded_layers)
        str_svg = str_svg_res.text
        svg_bytes = str_svg.encode('utf-8')
        png_bytes = cairosvg.svg2png(bytestring=svg_bytes, scale=11)
        # Load PNG image as PIL Image object
        png_io = io.BytesIO(png_bytes)
        image = Image.open(png_io)
        pattern = r'dc:wholeStoreViewBoxWidth="([0-9.-]+)"\s+dc:wholeStoreViewBoxHeight="([0-9.-]+)"\s+dc:wholeStoreViewBoxMinX="([0-9.-]+)"\s+dc:wholeStoreViewBoxMinY="([0-9.-]+)"'
        # Search for pattern in SVG bytes
        match = re.search(pattern, svg_bytes.decode())

        if match:
            # Extract values from match object
            viewbox_width = float(match.group(1))
            viewbox_height = float(match.group(2))
            viewbox_min_x = float(match.group(3))
            viewbox_min_y = float(match.group(4))
            map_scale = min(800/viewbox_height, 1400/viewbox_width)
            return image, viewbox_width, viewbox_height, viewbox_min_x, viewbox_min_y, map_scale
        else:
            raise ValueError("Viewbox pattern not found in SVG data.")


    def get_coords(self, geometry):
        """
        This function extracts the coordinates from a given geometry object.
        It handles both 'Polygon' and 'MultiPolygon' types, returning the coordinates as a list of [x, y] pairs.

        Args:
            geometry (shapely.geometry.base.BaseGeometry): The geometry object from which to extract coordinates. 
            The geometry should be either of type 'Polygon' or 'MultiPolygon'.

        Returns:
            list: A list of [x, y] pairs representing the coordinates of the geometry.

        Raises:
            ValueError: If the geometry type is not 'Polygon' or 'MultiPolygon'.
        """
        if geometry.geom_type == 'Polygon':
            coords = list(geometry.exterior.coords)
            return [[coord[0], coord[1]] for coord in coords]
        elif geometry.geom_type == 'Point':
            return [[geometry.x, geometry.y]] 
        elif geometry.geom_type == 'LineString':
            coords = list(geometry.coords)
            return [[coord[0], coord[1]] for coord in coords]    
        elif geometry.geom_type == 'MultiPolygon':
            all_coords = []
            for polygon in geometry.geoms:
                coords = list(polygon.exterior.coords)
                all_coords.extend([[coord[0], coord[1]] for coord in coords])
            return all_coords
        else:
            raise ValueError("Unsupported geometry type: {}".format(geometry.geom_type))

    
    def parse_polygon_string(self, x):
        if isinstance(x, str):
            try:
                # Safely evaluate string to list
                wkt_list = ast.literal_eval(x)
                if isinstance(wkt_list, list) and len(wkt_list) > 0:
                    return loads(wkt_list[0])
            except (ValueError, SyntaxError, WKTReadingError) as e:
                return None  # Or log error
        return None
    
    def fetch_merch_zone(self, data, shape_zones):
        """ Function to return polygon shape
            Args:
                data: A ping-level dataframe containing the following columns: 'position_date', 'location_id', 'floor_id', 'device_id', 'position_id', 'store_map_local_x_coordinate', 'store_map_local_y_coordinate'.
                shape_zones: A shapes dataframe extracted directly from BR3 TABLE prd_tpd_fnd.store_shape_agg filtered to MERCHANDISE_ZONES with other selected Non - MERCHANDISE_AREAS shapes , without any data type changes.
            Returns:
                The function adds additional columns to the input data dataframe:'zone_unique_id', 'zone_name', 'zone_area_in_square_meter', 'is_unique_record_f'
        """
        adj_zone = shape_zones[['adjacency_id', 'unique_id_by_shape_type', 'shape_name', 'shape_area','shape_centroid_struct', 'shape_outer_coordinates_arr',
                                'shape_outer_coordinates_geo','shape_inner_coordinates_arr', 'shape_inner_coordinates_geo']].copy(deep= True)
        adj_zone['shape_outer_coordinates_arr'] = adj_zone['shape_outer_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_zone['shape_inner_coordinates_arr'] = adj_zone['shape_inner_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_zone['shape_centroid_struct'] = adj_zone['shape_centroid_struct'].apply(lambda x: literal_eval(x) if x else x)
        adj_zone['shape_name'] = adj_zone.shape_name.str.lower()
        # Filter for Outer polygon 
        adj_outer_zone = adj_zone[['unique_id_by_shape_type', 'adjacency_id','shape_name', 'shape_outer_coordinates_geo', 'shape_area', 'shape_centroid_struct']]
        adj_outer_zone['shape_outer_coordinates_geo'] = adj_outer_zone['shape_outer_coordinates_geo'].apply(loads)
        adj_outer_zone_gdf = gpd.GeoDataFrame(adj_outer_zone, geometry = 'shape_outer_coordinates_geo')
        adj_outer_zone_gdf.columns = ['zone_unique_id', 'zone_adjacency_id','zone_name', 'shape_outer_coordinates_geo', 'zone_area_in_square_meter', 'zone_centroid_struct']
        # Filter for Inner polygon 
        adj_inner_zone = adj_zone[['adjacency_id', 'shape_name', 'shape_inner_coordinates_geo']]
        adj_inner_zone = adj_inner_zone[adj_inner_zone['shape_inner_coordinates_geo'] != '["null"]'].reset_index(drop = True)
        adj_inner_zone['shape_inner_coordinates_geo'] = adj_inner_zone['shape_inner_coordinates_geo'].apply(self.parse_polygon_string)
        adj_inner_zone_gdf = gpd.GeoDataFrame(adj_inner_zone, geometry = 'shape_inner_coordinates_geo')
        adj_inner_zone_gdf.columns = ['zone_inner_adjacency_id', 'zone_inner_adjacency_name', 'shape_inner_coordinates_geo']
        data_gdf = gpd.GeoDataFrame(data[['position_date', 'location_id', 'floor_id', 'device_id', 'position_id', 'store_map_local_x_coordinate', 'store_map_local_y_coordinate']], 
                                    geometry=gpd.points_from_xy(data['store_map_local_x_coordinate'], data['store_map_local_y_coordinate']))
        joined_outer = gpd.sjoin(data_gdf, adj_outer_zone_gdf,  how='left', predicate='within').drop(['index_right'], axis=1).reset_index(drop = True)      
        joined_inner = gpd.sjoin(joined_outer, adj_inner_zone_gdf,  how='left', predicate='within').drop(['index_right'], axis=1).reset_index(drop = True)
        duplicates = joined_inner.duplicated(subset=['position_date', 'location_id', 'floor_id', 'device_id', 'position_id', 'store_map_local_x_coordinate', 'store_map_local_y_coordinate'], keep=False)
        joined_inner.loc[duplicates, 'is_unique_record_f'] = False
        joined_inner['is_unique_record_f'].fillna(True, inplace=True)
        if duplicates.any():
            # Condition 1: Check if zone_inner_adjacency_name != shape_name and zone_inner_adjacency_name is not NaN
            condition1 = (joined_inner['zone_inner_adjacency_name'] != joined_inner['zone_name']) & (joined_inner['zone_inner_adjacency_name'].isna() == False)
            # Condition 2: Find the row with the largest shape_area
            min_area_idx = joined_inner['zone_area_in_square_meter'] == joined_inner.groupby('position_id')['zone_area_in_square_meter'].transform('min')
            condition2 = joined_inner['zone_inner_adjacency_name'].isna() & duplicates
            joined_inner.loc[duplicates & condition1, 'is_unique_record_f'] = True
            joined_inner.loc[min_area_idx & condition2 , 'is_unique_record_f'] = True
    #     duplicates = joined_inner.duplicated(subset=['position_date', 'location_id', 'floor_id', 'device_id', 'position_id',
    #                                                  'store_map_local_x_coordinate', 'store_map_local_y_coordinate'], keep=False)
    #     joined_inner.loc[~duplicates, 'is_unique_record_f'] = True
        result = pd.merge(joined_inner[joined_inner['is_unique_record_f'] == True][['position_date', 'location_id', 'floor_id', 'device_id', 'position_id',
                                                                                    'store_map_local_x_coordinate','store_map_local_y_coordinate',
                                                                                    'zone_unique_id', 'zone_name', 'zone_area_in_square_meter',
                                                                                    'is_unique_record_f']], data, on =['position_date', 'location_id', 'floor_id', 'device_id',
                                                                                                                    'position_id','store_map_local_x_coordinate','store_map_local_y_coordinate'], how = 'left')

    #     result = pd.merge(joined_inner[['position_date', 'location_id', 'floor_id', 'device_id', 'position_id', 'store_map_local_x_coordinate','store_map_local_y_coordinate',
    #                                     'zone_unique_id', 'zone_name', 'zone_area_in_square_meter', 'is_unique_record_f']], data, on =['position_date', 'location_id', 'floor_id', 'device_id',
    #                                                                                                                                    'position_id','store_map_local_x_coordinate','store_map_local_y_coordinate'], how = 'left')
            
        return result

    def fetch_merch_area(self, data, shape_areas):
        """ Function to return polygon shape
            Args:
                data: A ping-level dataframe containing the following columns: 'position_date', 'location_id', 'floor_id', 'device_id', 'position_id', 'store_map_local_x_coordinate', 'store_map_local_y_coordinate'.
                shape_zones: A shapes dataframe extracted directly from BR3 TABLE prd_tpd_fnd.store_shape_agg filtered to MERCHANDISE_AREAS shapes only, without any data type changes.
            Returns:
                The function adds additional columns to the input data dataframe:'zone_unique_id', 'zone_name','zone_area_in_square_meter','is_unique_record_f', 'is_position_in_racetrack_f', 
        """
        adj_area = shape_areas[['adjacency_id', 'unique_id_by_shape_type', 'shape_name', 'shape_area','shape_centroid_struct', 'shape_outer_coordinates_arr', 
                                'shape_outer_coordinates_geo','shape_inner_coordinates_arr', 'shape_inner_coordinates_geo']].copy(deep= True)

        adj_area['shape_outer_coordinates_arr'] = adj_area['shape_outer_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_area['shape_centroid_struct'] = adj_area['shape_centroid_struct'].apply(lambda x: literal_eval(x) if x else x)
        adj_area['shape_name'] = adj_area.shape_name.str.lower()
        # Filter for Outer polygon 
        adj_outer_area = adj_area[['unique_id_by_shape_type', 'adjacency_id','shape_name', 'shape_outer_coordinates_geo', 'shape_area', 'shape_centroid_struct']]
        adj_outer_area['shape_outer_coordinates_geo'] = adj_outer_area['shape_outer_coordinates_geo'].apply(loads)
        adj_outer_area_gdf = gpd.GeoDataFrame(adj_outer_area, geometry = 'shape_outer_coordinates_geo')
        adj_outer_area_gdf.columns = ['merch_area_unique_id', 'merch_area_adjacency_id','merch_area_adjacency_name', 'shape_outer_coordinates_geo', 'merch_area_in_square_meter', 'merch_area_centroid_struct']
        data_gdf = gpd.GeoDataFrame(data[['position_date', 'location_id', 'floor_id', 'device_id', 'position_id', 'store_map_local_x_coordinate', 'store_map_local_y_coordinate','zone_unique_id', 'zone_name','zone_area_in_square_meter', 'is_unique_record_f']], 
                                    geometry=gpd.points_from_xy(data['store_map_local_x_coordinate'], data['store_map_local_y_coordinate']))
        joined_outer = gpd.sjoin(data_gdf, adj_outer_area_gdf,  how='left', predicate='within').drop(['index_right'], axis=1).reset_index(drop = True)

        result = pd.merge(joined_outer[['position_date', 'location_id', 'floor_id', 'device_id', 'position_id',
                                        'store_map_local_x_coordinate', 'store_map_local_y_coordinate','zone_unique_id', 'zone_name','zone_area_in_square_meter', 'merch_area_unique_id',
                                        'merch_area_adjacency_name', 'merch_area_in_square_meter', 'is_unique_record_f']],
                        data, on =['position_date', 'location_id', 'floor_id', 'device_id','position_id','store_map_local_x_coordinate','store_map_local_y_coordinate',
                                    'zone_unique_id', 'zone_name','zone_area_in_square_meter','is_unique_record_f'], how = 'left').reset_index(drop = True)

        duplicates = result[result['is_unique_record_f'] == True].duplicated(subset=['position_date', 'location_id', 'floor_id', 'device_id', 'position_id','store_map_local_x_coordinate', 'store_map_local_y_coordinate', 'is_unique_record_f'], keep=False)

        if duplicates.any():
            result.loc[duplicates[duplicates].index, 'is_unique_record_f'] = False
            min_area_idx = result['merch_area_in_square_meter'] == result.groupby('position_id')['merch_area_in_square_meter'].transform('min')
            result.loc[min_area_idx & duplicates, 'is_unique_record_f'] = True
            
        result = result[result['is_unique_record_f'] == True].reset_index(drop = True)
        #CANNOT fill gap when there is a merch area but no zone assigned to the ping - there is no link between area and zone shape
    #     mask = (result['zone_name'].isna()) & (result['merch_area_adjacency_name'].isna() == False)
    #     result.loc[mask, 'zone_name'] = result.loc[mask, 'merch_area_adjacency_name']
    #     result.loc[mask, 'zone_unique_id'] = result.loc[mask, 'merch_area_unique_id']
    #     result.loc[mask, 'zone_area_in_square_meter'] = result.loc[mask, 'merch_area_in_square_meter']
        #logic for is_position_in_racetrack_f
        result['is_position_in_racetrack_f'] = np.where((result['zone_name'].isin(shape_areas['shape_name'].str.lower().unique())) 
                                                        & (result['merch_area_adjacency_name'].isna()), True, False)
        
        result['final_adjacency_name'] = result['zone_name']
        mask = result['final_adjacency_name'].isna() & result['merch_area_adjacency_name'].notna()
        result.loc[mask, 'final_adjacency_name'] = result.loc[mask, 'merch_area_adjacency_name']
        result['final_adjacency_name'] = np.where(result['is_position_in_racetrack_f'] == True, "racetrack", result['final_adjacency_name'])

    # 
            # Only set the first True occurrence per position_id to True
    #     first_true_idx = result.groupby('position_id')['is_unique_record_f'].idxmax()
    #     result.loc[result['is_unique_record_f'] & ~result.index.isin(first_true_idx), 'is_unique_record_f'] = False
    #     no_true_idx = result.groupby('position_id')['is_unique_record_f'].first().isna()
    #     result.loc[no_true_idx, 'is_unique_record_f'] = True
        return result  
    
    def fetch_custom_adj(self, data, col_lx, col_ly, custom_shape, col_shape_name, col_geo):
        """
        Function to return the customized adjacency name for the pings that fall into the customized adj shape.

        Args:
            data (pd.DataFrame): The ping level data table.
            col_lx (str): Column name representing store_map_local_x_coordinate in the ping level data table.
            col_ly (str): Column name representing store_map_local_y_coordinate in the ping level data table.
            custom_shape (gpd.GeoDataFrame): The DataFrame of customized adjacency information with geometry.
            col_shape_name (str): Column name for the adjacency name in the custom_shape DataFrame.
            col_geo (str): Column name for the geometry in the custom_shape DataFrame.

        Returns:
            pd.Series: A series representing whether the ping falls into the customized shape.
            If True, it will be the customized adjacency name; otherwise, it will be np.nan.
        """

        # Create a GeoDataFrame from the ping data
        custom_shape_gdf = gpd.GeoDataFrame(custom_shape, geometry = col_geo)
        data_gdf = gpd.GeoDataFrame(data[[col_lx, col_ly]], geometry=gpd.points_from_xy(data[col_lx], data[col_ly]))
        joined = gpd.sjoin(data_gdf, custom_shape_gdf,  how='left', predicate='within').drop(['index_right'], axis=1).reset_index(drop = True)      
        # Extract the custom adjacency names
        cust_name_series = joined[col_shape_name]
        return cust_name_series
    
    
    def calculate_distances_across_polygon(self, polygon):
        # Calculate the bounding box of the polygon
        minx, miny, maxx, maxy = polygon.bounds
        width = maxx - minx
        height = maxy - miny
        
        # Calculate longest distance (diagonal of bounding box)
        longest_distance = round((width ** 2 + height ** 2) ** 0.5,3)
        
        # Calculate shortest distance (diameter of bounding box)
        shortest_distance = min(width, height)/2
        
        return shortest_distance, longest_distance

    def calculate_travel_time_in_zones(self, shape_zones):
        adj_zone = shape_zones[['adjacency_id', 'unique_id_by_shape_type', 'shape_name', 'shape_area','shape_centroid_struct', 'shape_outer_coordinates_arr',
                                'shape_outer_coordinates_geo','shape_inner_coordinates_arr', 'shape_inner_coordinates_geo']].copy(deep= True)
        adj_zone['shape_outer_coordinates_arr'] = adj_zone['shape_outer_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_zone['shape_inner_coordinates_arr'] = adj_zone['shape_inner_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_zone['shape_centroid_struct'] = adj_zone['shape_centroid_struct'].apply(lambda x: literal_eval(x) if x else x)
        adj_zone['shape_name'] = adj_zone.shape_name.str.lower()
        # Filter for Outer polygon 
        adj_outer_zone = adj_zone[['unique_id_by_shape_type','shape_name', 'shape_outer_coordinates_geo', 'shape_area']]
        adj_outer_zone['shape_outer_coordinates_geo'] = adj_outer_zone['shape_outer_coordinates_geo'].apply(loads)
        adj_outer_zone_gdf = gpd.GeoDataFrame(adj_outer_zone, geometry = 'shape_outer_coordinates_geo')
        adj_outer_zone_gdf.columns = ['zone_unique_id','zone_name', 'shape_outer_coordinates_geo', 'zone_area_in_square_meter']
        adj_outer_zone_gdf['zone_shortest_dis'], adj_outer_zone_gdf['zone_longest_dis'] = zip(*adj_outer_zone_gdf['shape_outer_coordinates_geo'].apply(lambda x: self.calculate_distances_across_polygon(x)))
        adj_outer_zone_gdf['zone_low_travel_time'] = round(adj_outer_zone_gdf['zone_shortest_dis'] / 1.42, 3)
        adj_outer_zone_gdf['zone_med_travel_time'] = round(adj_outer_zone_gdf['zone_longest_dis'] / 1.42,3)
        return adj_outer_zone_gdf

    def calculate_travel_time_in_areas(self, shape_areas):
        adj_area = shape_areas[['adjacency_id', 'unique_id_by_shape_type', 'shape_name', 'shape_area','shape_centroid_struct', 'shape_outer_coordinates_arr',
                                'shape_outer_coordinates_geo','shape_inner_coordinates_arr', 'shape_inner_coordinates_geo']].copy(deep= True)
        adj_area['shape_outer_coordinates_arr'] = adj_area['shape_outer_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_area['shape_centroid_struct'] = adj_area['shape_centroid_struct'].apply(lambda x: literal_eval(x) if x else x)
        adj_area['shape_name'] = adj_area.shape_name.str.lower()
        # Filter for Outer polygon 
        adj_outer_area = adj_area[['unique_id_by_shape_type','shape_name', 'shape_outer_coordinates_geo', 'shape_area']]
        adj_outer_area['shape_outer_coordinates_geo'] = adj_outer_area['shape_outer_coordinates_geo'].apply(loads)
        adj_outer_area_gdf = gpd.GeoDataFrame(adj_outer_area, geometry = 'shape_outer_coordinates_geo')
        adj_outer_area_gdf.columns = ['merch_area_unique_id','merch_area_adjacency_name', 'shape_outer_coordinates_geo', 'merch_area_in_square_meter']
        adj_outer_area_gdf['area_shortest_dis'], adj_outer_area_gdf['area_longest_dis'] = zip(*adj_outer_area_gdf['shape_outer_coordinates_geo'].apply(lambda x: self.calculate_distances_across_polygon(x)))
        adj_outer_area_gdf['area_low_travel_time'] = round(adj_outer_area_gdf['area_shortest_dis'] / 1.42, 3)
        adj_outer_area_gdf['area_med_travel_time'] = round(adj_outer_area_gdf['area_longest_dis'] / 1.42,3)
        return adj_outer_area_gdf

    def calculate_longest_shortest_sides(self, polygon):
        if polygon.geom_type == 'Polygon':
            exterior_coords = list(polygon.exterior.coords)
            num_coords = len(exterior_coords)
            
            if num_coords > 0:
                sides = []
                for i in range(num_coords - 1):
                    line = LineString([exterior_coords[i], exterior_coords[i + 1]]).length
                    sides.append(line)
                shortest_side = min(sides)
                longest_side = max(sides)
                if shortest_side >= longest_side:
                    longest_side = shortest_side * 2
                elif shortest_side * 4 > longest_side:
                    longest_side = longest_side
                else:
                    longest_side = longest_side / 2
            else:
                shortest_side = None
                longest_side = None
        else:
            shortest_side = None
            longest_side = None
            
        return shortest_side, longest_side
        
    def calculate_travel_time_in_endcap(self, zone_gdf, area_gdf):
        
        non_overlap_gdf = gpd.GeoDataFrame(columns=['zone_name', 'non_overlap_geometry', 'endcap_area'])
        
        for zone_name in area_gdf['merch_area_adjacency_name'].unique():
            zone_polygons = zone_gdf[zone_gdf['zone_name'] == zone_name]['shape_outer_coordinates_geo']
            area_polygons = area_gdf[area_gdf['merch_area_adjacency_name'] == zone_name]['shape_outer_coordinates_geo']

            for zone_polygon in zone_polygons:
                non_overlap_polygon = zone_polygon.buffer(0)
                for area_polygon in area_polygons:
                    area_polygon = area_polygon.buffer(0)
                    if non_overlap_polygon.intersects(area_polygon):
                        non_overlap_polygon = non_overlap_polygon.difference(area_polygon.buffer(0))
    #             if non_overlap_polygon.is_valid and non_overlap_polygon.area > 0:
                if non_overlap_polygon.geom_type == 'MultiPolygon':
                    max_area = 0
                    for polygon in non_overlap_polygon.geoms:
                        area = polygon.area
                        if area > max_area:
                            max_area = area
                            largest_polygon = polygon.simplify(0.9)
                else:
                    largest_polygon = non_overlap_polygon.simplify(0.9)
                new_row = gpd.GeoDataFrame([{'zone_name': zone_name, 
                                             'non_overlap_geometry': largest_polygon, 
                                            'endcap_area': largest_polygon.area
                                            }], geometry='non_overlap_geometry')
                # non_overlap_gdf = non_overlap_gdf.append({'zone_name': zone_name, 'non_overlap_geometry': largest_polygon, 'endcap_area': largest_polygon.area}, ignore_index=True)
                non_overlap_gdf = pd.concat([non_overlap_gdf, new_row], ignore_index=True)

        non_overlap_gdf['endcap_shortest_dis'], non_overlap_gdf['endcap_longest_dis'] = zip(*non_overlap_gdf['non_overlap_geometry'].apply(lambda x: self.calculate_longest_shortest_sides(x)))
        non_overlap = non_overlap_gdf.groupby(['zone_name'], as_index=False).agg({'endcap_area': 'mean',
                                                                                                'endcap_shortest_dis': 'mean',
                                                                                                'endcap_longest_dis': 'mean',
                                                                                                })
        non_overlap['endcap_low_travel_time'] = round(non_overlap['endcap_shortest_dis'] / 1.42,3)
        non_overlap['endcap_med_travel_time'] = round(non_overlap['endcap_longest_dis'] / 1.42,3)
        non_overlap = non_overlap.dropna().reset_index(drop = True)
        return non_overlap


    
    def extract_coordinates(self, json_string):
        coordinates = pd.read_json(json_string)
        x_values = coordinates['x'].values
        y_values = coordinates['y'].values
        return pd.Series({'x_min': x_values.min(), 'x_max': x_values.max(), 'y_min': y_values.min(), 'y_max': y_values.max()})


    def get_grids(self, grid_size, tba):
        """
        Function to generate a grid of polygons from a bounding box  - neptune shape TOTAL_BUILDING_AREAS 

        Args:
            grid_size: Type: float; size of each grid cell in meters.
            tba: TOTAL_BUILDING_AREAS from neptune (see query below).

        Returns:
            Type: geopandas.GeoDataFrame; contains:
                - geometry: polygon shapes of the grids in meters
                - grids_c: centroid coordinates of each grid
                - grid_id: sequential ID of each grid starting from bottom-left, increasing left to right, bottom to top (In neptune map, will be starting the top left)
        
        Example query for `tba`:
        ---------------------------------------------------------------
        start_time = time.time()
        br3_session.execute('set hive.resultset.use.unique.column.names=false')
        query = f'''
            SELECT *
            FROM prd_tpd_fnd.store_shape_agg
            WHERE active_record_f = 'Y'
            AND location_id IN ({register_location_ids})
            AND shape_name = 'TOTAL_BUILDING_AREAS';
        '''
        tba = br3_session.query(query)
        end_time = time.time()
        print(f"Query time: {end_time - start_time:.2f} seconds")
        ---------------------------------------------------------------
        """
        tba[['x_min', 'x_max', 'y_min', 'y_max']] = tba['shape_outer_coordinates_arr'].apply(lambda x: self.extract_coordinates(x))
        tba['outer_coord'] = tba[['x_min', 'x_max', 'y_min', 'y_max']].values.tolist()
        x_min,x_max,y_min,y_max,outer_coord = tba[['x_min', 'x_max', 'y_min', 'y_max','outer_coord']].iloc[0]
        # x = np.linspace(x_min, x_max, int((x_max-x_min) / grid_size))
        # y = np.linspace(y_min, y_max, int((y_max-y_min) / grid_size))
        # Align to integer grid boundaries
        x_min_floor = math.floor(x_min)
        x_max_ceil = math.ceil(x_max)
        y_min_floor = math.floor(y_min)
        y_max_ceil = math.ceil(y_max)

        # Compute number of grid steps (+1 ensures inclusive of upper bounds)
        num_x = int((x_max_ceil - x_min_floor) / grid_size) + 1
        num_y = int((y_max_ceil - y_min_floor) / grid_size) + 1
        # Generate grid line coordinates
        x = np.linspace(x_min_floor, x_max_ceil, num_x)
        y = np.linspace(y_min_floor, y_max_ceil, num_y)
        hlines = [((x1, yi), (x2, yi)) for x1, x2 in zip(x[:-1], x[1:]) for yi in y]
        vlines = [((xi, y1), (xi, y2)) for y1, y2 in zip(y[:-1], y[1:]) for xi in x]
        #generate the polygon for each grids
        grids = list(polygonize(MultiLineString(vlines + hlines)))
        grids_c = [list(x.centroid.coords) for x in grids]  # to get coords (grids_c[0][0][0],grids_c[0][0][1])
        grid_df = gpd.GeoDataFrame()
        grid_df['geometry'] = grids
        grid_df['grids_c'] = grids_c
        grid_df['grid_id'] = grid_df.index + 1
        return grid_df, x, y 
    
    def return_poly_meters(self, coords):
        """ Function to return polygon shape, and converts unit of length is in meter
            Args:
                coords: Type: String; input value in feet 
            Returns:
                Type: polygon shape, output polygon in meter 
        """
        coord = pd.Series(coords).apply(pd.Series)
        coord.columns = ['X', 'Y']
        coord['XY'] = coord.apply(lambda row: (row.X, row.Y), axis=1)
        ret_poly = Polygon(coord['XY'].tolist())
        return ret_poly

    def add_grid_map(self,data,grid_df,lx,ly):    
        """ Function to return the grid id for each ping point, 
    Args: 
        data Type: DataFrame; Representing the ping level data table 
        lx Type: DataFrame; Representing localx column in ping level data table  
        ly Type: DataFrame; Representing localy column in ping level data table  
        n Type: Integer; Representing the grid_size (default input value is 10) 
    Returns:
        grd_poly['grid_id'].values Type: Series; Representing the grid id for each ping point
        grd_poly['geometry_poly'].values Type: Series; Representing the polygon shape for the grid id
        """
        data_gpd = gpd.GeoDataFrame()
        data_gpd['id'] = data.index
        geometry = [Point(xy) for xy in zip(data[lx], data[ly])]
        data_gpd['geometry'] = geometry
        grd_join = gpd.sjoin(data_gpd, grid_df, how='left', predicate='within').drop(['index_right'], axis=1)
        grd_poly  = grd_join.merge(grid_df, on='grid_id', how='left')
        return grd_poly['grid_id'].values#we are returning the polygon in meters
    
    def custom_adj(self, data, lx, ly, custom_adj):
        """ Function to return the customized adjacency name for the pings that falls into the customized adj shape
        Args: 
            data Type: DataFrame; Representing the ping level data table 
            lx Type: DataFrame; Representing store_map_local_x_coordinate column in ping level data table  
            ly Type: DataFrame; Representing store_map_local_y_coordinate column in ping level data table  
            custom_adj Type: DataFrame; Representing the DataFrame of customized adjacency infor, 
                       Contains Columns: 'cust_coords'- list of boundary point from customized adj shape, 'cust_adj'- customized adjacency name (In String) 
        Returns:
            cust_adj Type: Series; Representing whether the ping falls into the customized adj shape, if True will be the customized adjacency name, False will be np.nan
        """
        if not isinstance(custom_adj, gpd.GeoDataFrame) or 'geometry' not in custom_adj.columns:
            custom_adj['geometry'] = [self.return_poly_meters(eval(x)) for x in custom_adj['cust_coords'].values]
            custom_adj = gpd.GeoDataFrame(custom_adj.fillna(float('NaN')))
        data_gp = gpd.GeoDataFrame(data)  
        geometry = gpd.GeoDataFrame(geometry=[Point(xy) for xy in zip(data_gp[lx], data_gp[ly])])
        cust_adj_chk = gpd.sjoin(geometry, custom_adj, how='left', predicate ='within').drop(['index_right'], axis=1)
        cust_adj = cust_adj_chk.cust_adj.values    
        return cust_adj
    
    def get_nearby_adj(self, shape_df_br3, selected_shape):
        """Function to find nearby adjacent shapes. It accepts either a string shape_name or a GeoDataFrame 
            with a column shape_name along with column shape_outer_coordinates_geo for polygon information as input.
            It checks the type of input and handles them accordingly.
        Args:
            shape_df_br3 (DataFrame): DataFrame containing shape information.
            selected_shape (str) or selected_shape (gpd.GeoDataFrame): Name of the selected shape or selected gpd.GeoDataFrame
        Returns:
            set: Set of nearby adjacent shape names.
        """
        adj_df = shape_df_br3[['adjacency_id', 'unique_id_by_shape_type', 'shape_name', 'shape_area','shape_centroid_struct', 'shape_outer_coordinates_arr', 
                            'shape_outer_coordinates_geo','shape_inner_coordinates_arr', 'shape_inner_coordinates_geo']].copy(deep= True)
        adj_df['shape_outer_coordinates_arr'] = adj_df['shape_outer_coordinates_arr'].apply(lambda x: literal_eval(x) if x else x)
        adj_df['shape_centroid_struct'] = adj_df['shape_centroid_struct'].apply(lambda x: literal_eval(x) if x else x)
        adj_df['shape_name'] = adj_df.shape_name.str.lower()
        adj_outer_df = adj_df[['unique_id_by_shape_type', 'adjacency_id','shape_name', 'shape_outer_coordinates_geo', 'shape_area', 'shape_centroid_struct']]
        adj_outer_df['shape_outer_coordinates_geo'] = adj_outer_df['shape_outer_coordinates_geo'].apply(loads)
        adj_outer_gdf = gpd.GeoDataFrame(adj_outer_df, geometry = 'shape_outer_coordinates_geo')

        if isinstance(selected_shape, str):
            selected_polygons = adj_outer_gdf[adj_outer_gdf['shape_name'] == selected_shape]['shape_outer_coordinates_geo']

        elif isinstance(selected_shape, gpd.GeoDataFrame) and len(selected_shape) == 1:
            selected_polygons = selected_shape['shape_outer_coordinates_geo']
        else:
            raise ValueError("Input selected_shape_name must be either a string or a DataFrame with a valid single shape_name along with polygon information")
        nearby_adj = set()
        for polygon in selected_polygons:
            polygon = polygon.buffer(0.01)
            nearby_polygons_gdf = adj_outer_gdf[adj_outer_gdf['shape_outer_coordinates_geo'].overlaps(polygon) | adj_outer_gdf['shape_outer_coordinates_geo'].touches(polygon)].reset_index(drop = True)
            nearby_polygons_names = nearby_polygons_gdf['shape_name'].unique()
            nearby_adj.update(nearby_polygons_names)
        return nearby_adj,nearby_polygons_gdf


    def identify_polygon_from_svg(self, str_svg, pattern):
        """
        Function to extract polygon shapes from an SVG path string using a regex pattern.
        Args:
            str_svg (str): A string containing SVG path data.
            pattern (str): A regex pattern to extract relevant path segments from the SVG string.

        Returns:
            pd.DataFrame: A DataFrame with two columns:
                - 'polygon': Shapely Polygon object created from the coordinates.
                - 'coordinates': List of (x, y) tuples representing the polygon's vertices.
        """
        paths = re.findall(pattern, str_svg)
        polygons_data = []
        for path in paths:
            # Split commands and coordinates into individual elements
            commands = re.split(r'(?=[MLZ])', path.strip())
            coords = []
        #     print(f"Parsing path: {path}")  # Debug output for each path
            for command in commands:
                if command.startswith('M') or command.startswith('L'):
                    # Extract numerical parts, remove any non-numeric parts
                    numbers = re.findall(r'[-+]?\d*\.\d+|\d+', command)
                    # Ensure we have pairs of coordinates
                    for i in range(0, len(numbers), 2):
                        try:
                            x = float(numbers[i])
                            y = float(numbers[i + 1])
                            coords.append((x, y))
                        except (IndexError, ValueError) as e:
                            print(f"Error parsing command '{command}': {e}")
            if len(coords) > 2:  # Polygons require at least 3 points
                polygon = Polygon(coords)
                polygons_data.append({
                    'polygon': polygon,
                    'coordinates': coords
                })
            else:
                print(f"Insufficient coordinates for a polygon in path: {path}")
        df = pd.DataFrame(polygons_data)
        return df

    def trim_polygon_by_directional_shift(self, polygon, direction_distances=None):
        """
        Moves a copy of the polygon in the specified direction(s) by the given distance(s),
        then intersects it with the original.

        Parameters:
        - polygon: shapely.geometry.Polygon
        - direction_distances: dict
            Dictionary where keys are directions ('top', 'bottom', 'left', 'right')
            and values are distances (float) to move in that direction.

        Returns:
        - trimmed shapely.geometry.Polygon (intersection of original and shifted polygon)
        """
        if direction_distances is None:
            direction_distances = {}
        if not isinstance(direction_distances, dict):
            raise ValueError("direction_distances must be a dictionary with directions as keys and distances as values.")

        dx, dy = 0, 0
        for direction, distance in direction_distances.items():
            if direction == 'right':
                dx -= distance
            elif direction == 'left':
                dx += distance
            elif direction == 'bottom':
                dy -= distance
            elif direction == 'top':
                dy += distance
            else:
                raise ValueError(f"Invalid direction: {direction}. Must be one of 'top', 'bottom', 'left', 'right'.")

        shifted_polygon = affinity.translate(polygon, xoff=dx, yoff=dy)
        return polygon.intersection(shifted_polygon)

    def extend_polygon_by_directional_buffer(self, polygon, direction_distances=None):
        """
        Extends a polygon by buffering it in specified directions or uniformly.

        Parameters:
        - polygon: shapely.geometry.Polygon
        - direction_distances: dict, int, or None
            - If dict: keys are 'top', 'bottom', 'left', 'right' with float values.
            - If int: applies a uniform buffer to the entire polygon.
            - If None: no extension is applied.

        Returns:
        - shapely.geometry.Polygon: The extended polygon.
        """
        if direction_distances is None:
            return polygon

        if isinstance(direction_distances, int):
            return polygon.buffer(direction_distances)

        if not isinstance(direction_distances, dict):
            raise ValueError("direction_distances must be a dictionary or an integer.")

        minx, miny, maxx, maxy = polygon.bounds

        # Apply directional extensions
        minx -= direction_distances.get('left', 0)
        maxx += direction_distances.get('right', 0)
        miny -= direction_distances.get('top', 0)
        maxy += direction_distances.get('bottom', 0)

        # Create a new extended bounding box and union with original polygon
        extended_box = box(minx, miny, maxx, maxy)
        return polygon.union(extended_box)

    def prep_register_shapes(self, shape_areas, check_lane_area_df, cl_compactness_p_min,cl_compactness_p_max,
                            selected_aisle_index, trim_direction_distances, extend_direction_distances):
        """
        Function to prepare register shapes from store SVG map data and shape metadata.
        This function extracts aisle polygons from SVG path data, trims and extends the checklane area,
        filters aisle shapes based on compactness or selected indices, and generates final checkout lane
        polygons and intersection lines. It also constructs an extended exit zone polygon.

        Args:
            shape_areas (GeoDataFrame): GeoDataFrame containing all shape metadata including coordinates.
            check_lane_area_df (DataFrame): DataFrame with check lane area metadata.
            cl_compactness_p_min (float): Minimum compactness threshold for identifying register shapes.
            cl_compactness_p_max (float): Maximum compactness threshold for identifying register shapes.
            selected_aisle_index (list or None): Optional list of indices to manually select aisle shapes.
            trim_direction_distances (dict): Dictionary specifying how much to trim the checklane area in each direction.
            extend_direction_distances (dict): Dictionary specifying how much to extend the bounding box in each direction.

        Returns:
            tuple:
                - final_ckl_area (Polygon): Final checkout lane area polygon including exit zone.
                - final_ckl_area_coords (list): Coordinates of the final checkout lane area.
                - ckl_poly_gdf (GeoDataFrame): GeoDataFrame of register shapes with coordinates.
                - ckl_line_gdf (GeoDataFrame): GeoDataFrame of checkout lane intersection lines.
        """
        
        # function will be updated with additional parameter    
        str_svg_res = self.get_store_map_api(['wall-shapes', 'total-building-shapes', 'stockroom-shapes', 'stockroom-aisle-shapes', 'sales-floor-island-shapes',
                                                'register-shapes', 'pharmacy-shapes','optical-shapes', 'floor-pads', 'fitting-room-shapes', 
                                                'clinic-shapes', 'admin-space-shapes', 'adjacency-names'] )
        str_svg = str_svg_res.text
        pattern = r'<path[^>]*?d="([^"]+)"'
        aisle_shape = self.identify_polygon_from_svg(str_svg, pattern)
        ckl_area_df = shape_areas[(shape_areas['shape_name'].str.contains('Checklanes')) & (shape_areas['location_id'].astype(str) == self.str_num)]
        ckl_area_df['shape_outer_coordinates_geo'] = ckl_area_df['shape_outer_coordinates_geo'].apply(loads)
        ckl_area_gdf = gpd.GeoDataFrame(ckl_area_df, geometry='shape_outer_coordinates_geo')
        ckl_area = ckl_area_gdf['shape_outer_coordinates_geo'].unary_union
        # ckl_area_coords  = self.get_coords(ckl_area)
        aisle_shape = gpd.GeoDataFrame(aisle_shape, geometry='polygon')
        aisle_shape = aisle_shape[aisle_shape['polygon'].intersects(self.trim_polygon_by_directional_shift(ckl_area, trim_direction_distances))]
        ckl_area_value = ckl_area.area
        aisle_shape = aisle_shape[aisle_shape['polygon'].area <= ckl_area_value]
        minx, miny, maxx, maxy = aisle_shape['polygon'].total_bounds
        bounding_box = box(minx, miny, maxx, maxy)
        bounding_box1 = self.extend_polygon_by_directional_buffer(bounding_box, extend_direction_distances)
        clipped_ckl_area = ckl_area.intersection(bounding_box1)
        # clipped_ckl_area_coords  = self.get_coords(clipped_ckl_area)
        # create register shape - cl_compactness_p_min will be changed into input parameter
        aisle_shape['area'] = aisle_shape['polygon'].area
        aisle_shape['perimeter'] = aisle_shape['polygon'].length
        aisle_shape['compactness'] = 4 * np.pi * aisle_shape['area'] / (aisle_shape['perimeter'] ** 2)
        aisle_shape = aisle_shape.sort_values(['compactness']).reset_index(drop = True)
        if cl_compactness_p_min is not None and cl_compactness_p_max is not None:
            aisle_shape['shape_cluster'] = np.where(
                (aisle_shape['compactness'] >= cl_compactness_p_min) &
                (aisle_shape['compactness'] <= cl_compactness_p_max),
                'CL', np.nan
            )
            cl = aisle_shape[aisle_shape['shape_cluster'] == 'CL']
        elif selected_aisle_index is not None:
            cl = aisle_shape.loc[selected_aisle_index]
        else:
            raise ValueError("Either compactness thresholds or selected_indices must be provided.")
        # cl = aisle_shape[aisle_shape['shape_cluster'] == 'CL']
        minx, miny, maxx, cl_ys = cl['polygon'].total_bounds
        _, _, _, merch_max_y = clipped_ckl_area.bounds
        last_quarter_y = merch_max_y - (merch_max_y - miny) * 0.25
        centroid_line_y = max(last_quarter_y, cl_ys)
        ckl_poly_gdf = self.create_register_shape(cl, clipped_ckl_area, check_lane_area_df)
        ckl_poly_gdf['coordinates'] = ckl_poly_gdf['geometry'].apply(self.get_coords)
        ckl_poly_gdf = ckl_poly_gdf.rename(columns={'geometry': 'shape_outer_coordinates_geo'})
        # create checkout interesection line
        ckl_poly_gdf['centroid_y'] = ckl_poly_gdf['shape_outer_coordinates_geo'].centroid.y
        # Group by check_lane_area and compute horizontal lines
        line_records = []
        for area, group in ckl_poly_gdf.groupby("check_lane_area"):
            combined = group['shape_outer_coordinates_geo'].unary_union
            minx, _, maxx, _ = combined.bounds
            line = LineString([(minx, centroid_line_y), (maxx, centroid_line_y)])
            line_records.append({"check_lane_area": area, "geometry": line})

        ckl_line_gdf = gpd.GeoDataFrame(line_records, geometry="geometry")
        ckl_line_gdf['coordinates'] = ckl_line_gdf['geometry'].apply(self.get_coords)
        minx, miny, maxx, maxy = clipped_ckl_area.bounds
        exit_zone = Polygon([
                (minx-2, maxy),         # Bottom-left
                (maxx+2, maxy),         # Bottom-right
                (maxx+2, maxy + 2),     # Extended bottom-right
                (minx-2, maxy + 2),     # Extended bottom-left
                (minx-2, maxy)          # Close the polygon
            ])
        final_ckl_area = unary_union([exit_zone,clipped_ckl_area]).buffer(0.1).buffer(-0.1)
        final_ckl_area_coords = self.get_coords(final_ckl_area)
        return final_ckl_area,final_ckl_area_coords, ckl_poly_gdf,ckl_line_gdf

    def prep_register_shapes_from_hand_draw(self,register_shapes):
        output_register_shape = []
        for name, coords in register_shapes.items():
            output_register_shape.append({
                'custom_coordinates_meters': coords,
                'location_id': self.str_num,
                'custom_adj_name': name,
                'user_name': 'TRIPS',
                'floor_id': self.flr_num
            })
        output_register_shape = pd.DataFrame(output_register_shape)
        output_register_shape['geometry'] = output_register_shape['custom_coordinates_meters'].apply(Polygon)
        register_gdf = gpd.GeoDataFrame(output_register_shape, geometry='geometry')
        output_register_shape['geometry'] = output_register_shape['custom_coordinates_meters'].apply(Polygon)
        register_gdf = gpd.GeoDataFrame(output_register_shape, geometry='geometry')
        check_lane_gdf = register_gdf[register_gdf['custom_adj_name'].str.contains('checklane_')].reset_index(drop=True)
        sco_gdf = register_gdf[register_gdf['custom_adj_name'].str.contains('checklane_') == False].reset_index(drop=True)
        sco_gdf['check_lane_area'] = sco_gdf['custom_adj_name'].str.split("_").str[:2].str.join("_")
        merged_shape = check_lane_gdf.unary_union
        if merged_shape.geom_type == 'Polygon':
            islands_list = [merged_shape]
        else:
            islands_list = list(merged_shape.geoms)

        islands = gpd.GeoDataFrame(geometry=islands_list)
        bounds = islands.geometry.bounds
        islands['minx'] = bounds['minx']
        islands = islands.sort_values(by='minx').reset_index(drop=True)
        islands['check_lane_area'] = [f'check_lane_area_{i}' for i in range(len(islands))]
        check_lane_gdf1 = gpd.sjoin(check_lane_gdf, islands[['geometry', 'check_lane_area']], how='left', predicate='intersects').drop(columns=['index_right'])
        register_gdf1 = pd.concat([check_lane_gdf1,sco_gdf],ignore_index=True)
        clipped_ckl_area = register_gdf1['geometry'].unary_union
        minx, miny, maxx, maxy = clipped_ckl_area.bounds
        last_quarter_y = maxy - (maxy - miny) * 0.25
        exit_zone = Polygon([
                (minx-2, maxy),         # Bottom-left
                (maxx+2, maxy),         # Bottom-right
                (maxx+2, maxy + 2),     # Extended bottom-right
                (minx-2, maxy + 2),     # Extended bottom-left
                (minx-2, maxy)          # Close the polygon
            ])
        final_ckl_area = unary_union([exit_zone,clipped_ckl_area])
        line_records = []
        for area, group in register_gdf1.groupby("check_lane_area"):
            combined = group['geometry'].unary_union
            minx, _, maxx, _ = combined.bounds
            line = LineString([(minx, last_quarter_y), (maxx, last_quarter_y)])
            line_records.append({"custom_adj_name": 'end_break_line_' + area, "geometry": line})
        ckl_line_gdf = gpd.GeoDataFrame(line_records, geometry="geometry")
        poly_gdf = gpd.GeoDataFrame({"custom_adj_name": ["checklanes"], "geometry": [final_ckl_area]},)
        final_gdf = pd.concat([register_gdf1[["custom_adj_name", "geometry"]],
                            ckl_line_gdf[["custom_adj_name", "geometry"]],
                            poly_gdf[["custom_adj_name", "geometry"]],
                            ],ignore_index=True)
        final_gdf['coordinates'] = final_gdf['geometry'].apply(self.get_coords)
        return final_gdf
    

    def find_cut_corner_direction(slef, polygon: Polygon):
        """Returns the edge opposite the missing corner and the direction to extend."""
        coords = list(polygon.exterior.coords)
        if len(coords) <= 4:
            return None, None  # Not a cut shape
        # Sort by x then y to get ordered corners
        sorted_coords = sorted(coords, key=lambda pt: (pt[0], pt[1]))
        leftmost = sorted_coords[0]
        rightmost = sorted_coords[-1]
        
        centroid_x = polygon.centroid.x
        mid_x = (leftmost[0] + rightmost[0]) / 2

        if centroid_x < mid_x:
            # cut is on right, extend from leftmost edge toward right
            return leftmost[0], 'right'
        else:
            # cut is on left, extend from rightmost edge toward left
            return rightmost[0], 'left'


    def create_register_shape(self, cl_aisle_shape, ckl_area, check_lane_area_df):
        """
        Function to generate register shapes and SCO (self-checkout) polygons from aisle shapes and checklane area.

        This function aligns aisle polygons with register metadata, splits them into rows if needed, and constructs
        rectangular register shapes. It also calculates the remaining area in the checklane zone and assigns SCO
        polygons based on the leftover space.

        Args:
            cl_aisle_shape (GeoDataFrame): GeoDataFrame containing aisle polygons and their centroids.
            ckl_area (Polygon): The main checklane area polygon.
            check_lane_area_df (DataFrame): DataFrame containing metadata for checklane areas, including register IDs and SCO count.

        Returns:
            GeoDataFrame: A combined GeoDataFrame containing:
                - Rectangular register shapes aligned with metadata.
                - SCO polygons derived from the remaining checklane area.
                - Columns: 'check_lane_area', 'register_shape_name', 'geometry'
        """

        check_lane = check_lane_area_df[check_lane_area_df['check_lane_area'].str.contains('check_lane_area')].reset_index(drop=True)
        check_lane['register_shape_id'] = check_lane['register_shape_id'].astype(int)

        if len(cl_aisle_shape) != len(check_lane):
            raise ValueError("Mismatch between number of aisle polygons and register shapes.")

        cl_aisle_shape['centroid_x'] = cl_aisle_shape['polygon'].centroid.x
        cl_aisle_shape['centroid_y'] = cl_aisle_shape['polygon'].centroid.y
        cl_aisle_shape = cl_aisle_shape.sort_values(by=['centroid_x', 'centroid_y']).reset_index(drop=True)

        check_lane = check_lane.sort_values(by='register_shape_id').reset_index(drop=True)
        cl_aisle_shape['check_lane_area'] = check_lane['check_lane_area']
        cl_aisle_shape['register_shape_name'] = check_lane['register_shape_name']

        chk_lane_row_count = int(check_lane_area_df['chk_lane_row_count'].iloc[0])
        miny_ckl, maxy_ckl = ckl_area.bounds[1], ckl_area.bounds[3]
        register_polygons = []
        # Split into rows if needed
        if chk_lane_row_count == 1:
            row_groups = [cl_aisle_shape]
        else:
            cl_aisle_shape['row_index'] = np.where(cl_aisle_shape['centroid_y'] > ckl_area.centroid.y, 0, 1)
            row_groups = [cl_aisle_shape[cl_aisle_shape['row_index'] == k] for k in range(chk_lane_row_count)]
            mid_y = row_groups[0]['polygon'].apply(lambda p: p.bounds[1]).max()

        for k, row_group in enumerate(row_groups):
            row_group = row_group.sort_values(by='centroid_x').reset_index(drop=True)
            miny, maxy = (miny_ckl, maxy_ckl) if chk_lane_row_count == 1 else \
                        ((mid_y, maxy_ckl) if k == 0 else (miny_ckl, mid_y))

            for area, group in row_group.groupby('check_lane_area'):
                group = group.reset_index(drop=True)
                starts = []
                widths = []

                for i in range(len(group)):
                    poly = group.loc[i, 'polygon']
                    current_x, direction = self.find_cut_corner_direction(poly)
                    starts.append(current_x)

                for i in range(len(starts)):
                    if i < len(starts) - 1:
                        width = abs(starts[i + 1] - starts[i])
                    else:
                        width = sum(widths[-2:]) / min(len(widths), 2) if widths else 1.0
                    widths.append(width)

                for i in range(len(group)):
                    start_x, direction = self.find_cut_corner_direction(group.loc[i, 'polygon'])
                    width = widths[i]
                    if direction == 'right':
                        x0 = start_x
                        x1 = x0 + width
                    else:
                        x1 = start_x
                        x0 = x1 - width
                    rect = box(x0, miny, x1, maxy)
                    register_polygons.append({
                        'check_lane_area': group.loc[i, 'check_lane_area'],
                        'register_shape_name': group.loc[i, 'register_shape_name'],
                        'geometry': rect
                    })

        register_polygons_gdf = gpd.GeoDataFrame(register_polygons, geometry='geometry')
        remaining_area = ckl_area
        for poly in register_polygons_gdf['geometry']:
            remaining_area = remaining_area.difference(poly)

        sco_count = int(check_lane_area_df['sco_count'].iloc[0])
        if remaining_area.is_empty:
            sco_gdf = gpd.GeoDataFrame(columns=['check_lane_area', 'register_shape_name', 'geometry'])
        else:
            remaining_parts = list(remaining_area.geoms) if remaining_area.geom_type == 'MultiPolygon' else [remaining_area]
            remaining_parts = sorted(remaining_parts, key=lambda g: (-g.area, g.centroid.x))
            sco_polygons = sorted(remaining_parts[:sco_count], key=lambda g: g.centroid.x)
            sco_names = [f'sco_{i}' for i in range(len(sco_polygons))]
            sco_gdf = gpd.GeoDataFrame({'check_lane_area': sco_names, 'register_shape_name': sco_names, 'geometry': sco_polygons})

        return pd.concat([register_polygons_gdf, sco_gdf], ignore_index=True)

## later sandeep faced issue in left and right side if the entrance for example 1332  has entrace left and 1428 has right 

#     def prep_register_shapes_from_hand_draw_verticalw(self, register_shapes):  
#         output_register_shape = []
#         for name, coords in register_shapes.items():
#             output_register_shape.append({
#                 'custom_coordinates_meters': coords,
#                 'location_id': self.str_num,
#                 'custom_adj_name': name,
#                 'user_name': 'TRIPS',
#                 'floor_id': self.flr_num
#             })
#         output_register_shape = pd.DataFrame(output_register_shape)
#         output_register_shape['geometry'] = output_register_shape[
#             'custom_coordinates_meters'
#         ].apply(Polygon)
#         register_gdf = gpd.GeoDataFrame(
#             output_register_shape,
#             geometry='geometry'
#         )
#         check_lane_gdf = register_gdf[
#             register_gdf['custom_adj_name'].str.contains('checklane_')
#         ].reset_index(drop=True)

#         sco_gdf = register_gdf[
#             ~register_gdf['custom_adj_name'].str.contains('checklane_')
#         ].reset_index(drop=True)

#         sco_gdf['check_lane_area'] = (
#             sco_gdf['custom_adj_name']
#             .str.split("_")
#             .str[:2]
#             .str.join("_")
#         )
#         merged_shape = check_lane_gdf.unary_union
#         if merged_shape.geom_type == 'Polygon':
#             islands_list = [merged_shape]
#         else:
#             islands_list = list(merged_shape.geoms)
#         islands = gpd.GeoDataFrame(geometry=islands_list)
#         bounds = islands.geometry.bounds
#         islands['minx'] = bounds['minx']
#         islands = islands.sort_values(by='minx').reset_index(drop=True)
#         islands['check_lane_area'] = [
#             f'check_lane_area_{i}'
#             for i in range(len(islands))
#         ]
#         check_lane_gdf1 = gpd.sjoin(
#             check_lane_gdf,
#             islands[['geometry', 'check_lane_area']],
#             how='left',
#             predicate='intersects'
#         ).drop(columns=['index_right'])
#         register_gdf1 = pd.concat(
#             [check_lane_gdf1, sco_gdf],
#             ignore_index=True
#         )
#         clipped_ckl_area = register_gdf1['geometry'].unary_union
#         minx, miny, maxx, maxy = clipped_ckl_area.bounds
#         last_quarter_x = maxx - 0.75 * (maxx - minx)
#         exit_zone = Polygon([
#             (minx - 2, miny - 2),
#             (minx, miny - 2),
#             (minx, maxy + 2),
#             (minx - 2, maxy + 2),
#             (minx - 2, miny - 2)
#         ])
#         final_ckl_area = unary_union([
#             exit_zone,
#             clipped_ckl_area
#         ])
#         line_records = []
#         for area, group in register_gdf1.groupby("check_lane_area"):
#             combined = group["geometry"].unary_union
#             _, miny, _, maxy = combined.bounds
#             line = LineString([
#                 (last_quarter_x, miny),
#                 (last_quarter_x, maxy)
#             ])
#             line_records.append({
#                 "custom_adj_name": "end_break_line_" + area,
#                 "geometry": line
#             })

#         ckl_line_gdf = gpd.GeoDataFrame(
#             line_records,
#             geometry="geometry"
#         )
#         poly_gdf = gpd.GeoDataFrame({
#             "custom_adj_name": ["checklanes"],
#             "geometry": [final_ckl_area]
#         })
#         final_gdf = pd.concat([
#             register_gdf1[["custom_adj_name", "geometry"]],
#             ckl_line_gdf[["custom_adj_name", "geometry"]],
#             poly_gdf[["custom_adj_name", "geometry"]]
#         ], ignore_index=True)
#         final_gdf["coordinates"] = final_gdf["geometry"].apply(self.get_coords)
#         return final_gdf
    def prep_register_shapes_from_hand_draw_vertical(
        self,
        register_shapes,
        exit_side="right"
    ):
        output_register_shape = []

        for name, coords in register_shapes.items():
            output_register_shape.append({
                "custom_coordinates_meters": coords,
                "location_id": self.str_num,
                "custom_adj_name": name,
                "user_name": "TRIPS",
                "floor_id": self.flr_num
            })

        output_register_shape = pd.DataFrame(output_register_shape)
        output_register_shape["geometry"] = output_register_shape[
            "custom_coordinates_meters"
        ].apply(Polygon)

        register_gdf = gpd.GeoDataFrame(
            output_register_shape,
            geometry="geometry"
        )

        check_lane_gdf = register_gdf[
            register_gdf["custom_adj_name"].str.contains("checklane_")
        ].reset_index(drop=True)

        sco_gdf = register_gdf[
            ~register_gdf["custom_adj_name"].str.contains("checklane_")
        ].reset_index(drop=True)

        sco_gdf["check_lane_area"] = (
            sco_gdf["custom_adj_name"]
            .str.split("_")
            .str[:2]
            .str.join("_")
        )

        merged_shape = check_lane_gdf.unary_union

        if merged_shape.geom_type == "Polygon":
            islands_list = [merged_shape]
        else:
            islands_list = list(merged_shape.geoms)

        islands = gpd.GeoDataFrame(geometry=islands_list)

        bounds = islands.geometry.bounds

        if exit_side == "left":
            # Left-most island is Area 0
            islands["sort_key"] = bounds["minx"]
            islands = islands.sort_values("sort_key").reset_index(drop=True)
        elif exit_side == "right":
            # Right-most island is Area 0
            islands["sort_key"] = bounds["maxx"]
            islands = islands.sort_values("sort_key", ascending=False).reset_index(drop=True)
        else:
            raise ValueError("exit_side must be either 'left' or 'right'")

        islands["check_lane_area"] = [
            f"check_lane_area_{i}"
            for i in range(len(islands))
        ]

        check_lane_gdf1 = gpd.sjoin(
            check_lane_gdf,
            islands[["geometry", "check_lane_area"]],
            how="left",
            predicate="intersects"
        ).drop(columns=["index_right"])

        register_gdf1 = pd.concat(
            [check_lane_gdf1, sco_gdf],
            ignore_index=True
        )

        clipped_ckl_area = register_gdf1["geometry"].unary_union

        minx, miny, maxx, maxy = clipped_ckl_area.bounds
        width = maxx - minx

        if exit_side == "left":
            line_x = minx + 0.25 * width

            exit_zone = Polygon([
                (minx - 2, miny - 2),
                (minx, miny - 2),
                (minx, maxy + 2),
                (minx - 2, maxy + 2),
                (minx - 2, miny - 2)
            ])
        else:  # right
            line_x = minx + 0.75 * width

            exit_zone = Polygon([
                (maxx, miny - 2),
                (maxx + 2, miny - 2),
                (maxx + 2, maxy + 2),
                (maxx, maxy + 2),
                (maxx, miny - 2)
            ])

        final_ckl_area = unary_union([
            exit_zone,
            clipped_ckl_area
        ])

        line_records = []

        for area, group in register_gdf1.groupby("check_lane_area"):
            combined = group["geometry"].unary_union
            _, miny, _, maxy = combined.bounds

            line = LineString([
                (line_x, miny),
                (line_x, maxy)
            ])

            line_records.append({
                "custom_adj_name": "end_break_line_" + area,
                "geometry": line
            })

        ckl_line_gdf = gpd.GeoDataFrame(
            line_records,
            geometry="geometry"
        )

        poly_gdf = gpd.GeoDataFrame({
            "custom_adj_name": ["checklanes"],
            "geometry": [final_ckl_area]
        })

        final_gdf = pd.concat([
            register_gdf1[["custom_adj_name", "geometry"]],
            ckl_line_gdf[["custom_adj_name", "geometry"]],
            poly_gdf[["custom_adj_name", "geometry"]]
        ], ignore_index=True)

        final_gdf["coordinates"] = final_gdf["geometry"].apply(self.get_coords)

        return final_gdf

    def identify_shape(self, shape_str, draw_crd_str, store_param):
        """
        Function to identify and construct key spatial zones in a store layout, including the salesfloor,
        entrance zones, and nearby entrance areas.

        This function processes shape metadata and store configuration parameters to:
        - Build the salesfloor polygon excluding specified adjacencies.
        - Determine the entrance area using either hand-drawn or configured parameters.
        - Construct a buffered start polygon for routing or spatial analysis.
        - Identify nearby entrance zones by subtracting receiving and salesfloor areas from the store wall.

        Args:
            shape_str (DataFrame): DataFrame containing shape metadata including names, centroids, and geometries.
            draw_crd_str (DataFrame): DataFrame containing hand-drawn coordinates for cart storage or entrances.
            store_param (dict): Dictionary of store parameters including:
                - 'salesfloor_buffer_dis': Buffer distance for salesfloor.
                - 'count_of_entries': Number of store entrances.
                - 'salesfloor_exclude_adjs': List of adjacency names to exclude from salesfloor.
                - 'start_polys_param': Dictionary of directional shift and buffer configs for entrances.

        Returns:
                - salesfloor_coords (list): Coordinates of the cleaned and buffered salesfloor polygon.
                - start_poly_coords (list): Coordinates of the entrance + cart storage union polygon.
                - buffered_start_poly_coords (list): Coordinates of the buffered entrance polygon.
                - nearby_entrance_coords (list): Coordinates of the nearby entrance zone polygon.
        """

        salesfloor_buffer = store_param['salesfloor_buffer_dis']
        count_of_entries = store_param['count_of_entries']
        salesfloor_exclude_adjs = store_param['salesfloor_exclude_adjs']
        shape_str['shape_centroid_struct'] = shape_str['shape_centroid_struct'].apply(self.parse_polygon_string)
        # Create polygon for salesfloor 
        shape_gdf = gpd.GeoDataFrame(shape_str, geometry='geometry')
        salesfloor_poly = shape_gdf[(shape_gdf['shape_name'].isin(salesfloor_exclude_adjs) == False) & (shape_gdf['shape_group'] == 'merchandise_areas')]['geometry']#.unary_union.buffer(salesfloor_buffer).buffer(-salesfloor_buffer)
        cleaned_geometries = [geom.buffer(0) for geom in salesfloor_poly]
        salesfloor_poly = unary_union(cleaned_geometries).buffer(salesfloor_buffer).buffer(-salesfloor_buffer)
        if salesfloor_poly.geom_type == 'MultiPolygon':
            max_area = 0
            max_area_polygon = None
            for polygon in salesfloor_poly.geoms:
                if polygon.area > max_area:
                    max_area = polygon.area
                    max_area_polygon = polygon
            salesfloor_poly = max_area_polygon  # Assign the polygon with maximum area
            
        salesfloor_coords = self.get_coords(salesfloor_poly)    
        
        # Find entrance centroid and create Point object
        # entrance_centroid = shape_str.loc[shape_str['shape_name'].str.contains('entrance')].iloc[0]['shape_centroid_struct']
        # entrance_centroid_point = Point(entrance_centroid['x'], entrance_centroid['y'])
        # Filter out cart_storage, 3 Scenario - using hand draw cart storage shape; using neptune entrance shape with buffer; using neptune cart storage shape
        if draw_crd_str.shape[0] > 0:
            # using hand draw cart storage shape
            draw_crd_str['custom_coordinates_meters'] = draw_crd_str['custom_coordinates_meters'].apply(literal_eval)
            draw_crd_str['geometry'] = draw_crd_str['custom_coordinates_meters'].apply(Polygon)
            draw_crd_gdf = gpd.GeoDataFrame(draw_crd_str, geometry='geometry')
            start_poly = shape_gdf[shape_gdf['shape_name'].str.lower().str.contains('entrance')]['geometry'].unary_union
            buffered_start_poly = draw_crd_gdf[draw_crd_gdf['custom_adj_name'].str.lower().str.contains('entrance')]['geometry'].unary_union
            
        else:
            # using neptune entrance shape with buffer
            if count_of_entries == 1:
                start_poly_config = store_param['start_polys_param']
                start_key = next(iter(start_poly_config))
                start_poly_config = start_poly_config[start_key]
                start_poly = shape_gdf[shape_gdf['shape_name'].str.contains('entrance', case=False)]['geometry'].unary_union
                shift_params = start_poly_config.get("trim_polygon_by_directional_shift")
                buffer_params = start_poly_config.get("extend_direction_distances")
                # Use the actual function, not a shadowed variable
                buffered_start_poly = self.trim_polygon_by_directional_shift(start_poly, direction_distances=shift_params)
                buffered_start_poly = self.extend_polygon_by_directional_buffer(buffered_start_poly, direction_distances=buffer_params)
                
            else:
                start_a_poly_config = store_param['start_polys_param'].get('entrance_a')
                a_shift_params = start_a_poly_config.get("trim_polygon_by_directional_shift")
                a_buffer_params = start_a_poly_config.get("extend_direction_distances")
                start_b_poly_config = store_param['start_polys_param'].get('entrance_b')
                b_shift_params = start_b_poly_config.get("trim_polygon_by_directional_shift")
                b_buffer_params = start_b_poly_config.get("extend_direction_distances")
                entrance_a_poly = shape_gdf[shape_gdf['shape_name'].str.lower().str.contains('entrance_a')]['geometry'].unary_union
                buffered_a_start_poly = self.trim_polygon_by_directional_shift(entrance_a_poly, direction_distances=a_shift_params)
                buffered_a_start_poly = self.extend_polygon_by_directional_buffer(buffered_a_start_poly, direction_distances=a_buffer_params)
                entrance_b_poly = shape_gdf[shape_gdf['shape_name'].str.lower().str.contains('entrance_b')]['geometry'].unary_union
                buffered_b_start_poly = self.trim_polygon_by_directional_shift(entrance_b_poly, direction_distances=b_shift_params)
                buffered_b_start_poly = self.extend_polygon_by_directional_buffer(buffered_b_start_poly, direction_distances=b_buffer_params)
                start_poly = entrance_a_poly.union(entrance_b_poly).buffer(1).buffer(-1)  
                buffered_start_poly = buffered_a_start_poly.union(buffered_b_start_poly).buffer(1).buffer(-1) 
        sales_floor_wall = shape_gdf[(shape_gdf['shape_name'].str.lower().str.contains('sales_floor_wall') == True)]['geometry'].unary_union.buffer(-1)#.buffer(1)
        receiving = shape_gdf[(shape_gdf['shape_name'].str.lower().str.contains('receiving') == True)]['geometry'].unary_union.buffer(1)
#         print(type(start_poly))
#         print(start_poly.geom_type)
#         print(start_poly)

        print("start_poly type:", start_poly.geom_type)
        print("start_poly empty:", start_poly.is_empty)
        print(start_poly)

        print(shape_gdf[shape_gdf['shape_name'].str.contains('entrance', case=False)][['shape_name', 'geometry']])
        start_poly_coords = self.get_coords(start_poly)
        buffered_start_poly_coords = self.get_coords(buffered_start_poly)
        # identify nearby_entrance_coords
        nonoverlap = (sales_floor_wall.difference(receiving))
        nearby_entrance = nonoverlap.difference(salesfloor_poly)
        if nearby_entrance.geom_type == 'MultiPolygon':
            max_area = 0
            max_area_polygon = None
            for polygon in nearby_entrance.geoms:
                if polygon.area > max_area:
                    max_area = polygon.area
                    max_area_polygon = polygon
                nearby_entrance = max_area_polygon.buffer(1)
        else:
            nearby_entrance = nearby_entrance.buffer(1)

        nearby_entrance_coords = self.get_coords(nearby_entrance)
        return salesfloor_coords, start_poly_coords, buffered_start_poly_coords, nearby_entrance_coords

#     def identify_shape(self, shape_str, draw_crd_str, store_param):

#         salesfloor_buffer = store_param["salesfloor_buffer_dis"]
#         salesfloor_exclude_adjs = store_param["salesfloor_exclude_adjs"]

#         shape_str["shape_centroid_struct"] = shape_str["shape_centroid_struct"].apply(
#             self.parse_polygon_string
#         )

#         shape_gdf = gpd.GeoDataFrame(shape_str, geometry="geometry")

#         # ------------------------------------------------------------------
#         # Salesfloor polygon
#         # ------------------------------------------------------------------

#         salesfloor_poly = shape_gdf[
#             (~shape_gdf["shape_name"].isin(salesfloor_exclude_adjs))
#             & (shape_gdf["shape_group"] == "merchandise_areas")
#         ]["geometry"]

#         cleaned_geometries = [geom.buffer(0) for geom in salesfloor_poly]

#         salesfloor_poly = (
#             unary_union(cleaned_geometries)
#             .buffer(salesfloor_buffer)
#             .buffer(-salesfloor_buffer)
#         )

#         if salesfloor_poly.geom_type == "MultiPolygon":
#             salesfloor_poly = max(
#                 salesfloor_poly.geoms,
#                 key=lambda p: p.area
#             )

#         salesfloor_coords = self.get_coords(salesfloor_poly)

#         # ------------------------------------------------------------------
#         # Start polygon
#         # ------------------------------------------------------------------

#         if draw_crd_str.shape[0] > 0:

#             draw_crd_str["custom_coordinates_meters"] = (
#                 draw_crd_str["custom_coordinates_meters"].apply(literal_eval)
#             )

#             draw_crd_str["geometry"] = (
#                 draw_crd_str["custom_coordinates_meters"].apply(Polygon)
#             )

#             draw_crd_gdf = gpd.GeoDataFrame(
#                 draw_crd_str,
#                 geometry="geometry"
#             )

#             start_poly = shape_gdf[
#                 shape_gdf["shape_name"].str.lower().str.contains("entrance")
#             ]["geometry"].unary_union

#             buffered_start_poly = draw_crd_gdf[
#                 draw_crd_gdf["custom_adj_name"].str.lower().str.contains("entrance")
#             ]["geometry"].unary_union

#         else:

#             entrance_polygons = []
#             buffered_polygons = []

#             for entrance_name, config in store_param["start_polys_param"].items():

#                 entrance_poly = shape_gdf[
#                     shape_gdf["shape_name"].str.lower() == entrance_name.lower()
#                 ]["geometry"].unary_union

#                 if entrance_poly.is_empty:
#                     print(f"{entrance_name} not found.")
#                     continue

#                 shift_params = config.get("trim_polygon_by_directional_shift")
#                 buffer_params = config.get("extend_direction_distances")

#                 buffered_poly = self.trim_polygon_by_directional_shift(
#                     entrance_poly,
#                     direction_distances=shift_params,
#                 )

#                 buffered_poly = self.extend_polygon_by_directional_buffer(
#                     buffered_poly,
#                     direction_distances=buffer_params,
#                 )

#                 entrance_polygons.append(entrance_poly)
#                 buffered_polygons.append(buffered_poly)

#             if len(entrance_polygons) == 0:
#                 raise ValueError("No entrance polygons found.")

#             start_poly = unary_union(entrance_polygons).buffer(1).buffer(-1)

#             buffered_start_poly = (
#                 unary_union(buffered_polygons)
#                 .buffer(1)
#                 .buffer(-1)
#             )

#         # ------------------------------------------------------------------
#         # Nearby entrance
#         # ------------------------------------------------------------------

#         sales_floor_wall = shape_gdf[
#             shape_gdf["shape_name"].str.lower().str.contains("sales_floor_wall")
#         ]["geometry"].unary_union.buffer(-1)

#         receiving = shape_gdf[
#             shape_gdf["shape_name"].str.lower().str.contains("receiving")
#         ]["geometry"].unary_union.buffer(1)

#         nonoverlap = sales_floor_wall.difference(receiving)

#         nearby_entrance = nonoverlap.difference(salesfloor_poly)

#         if nearby_entrance.geom_type == "MultiPolygon":
#             nearby_entrance = unary_union(
#                 [poly.buffer(1) for poly in nearby_entrance.geoms]
#             )
#         else:
#             nearby_entrance = nearby_entrance.buffer(1)

#         # ------------------------------------------------------------------
#         # Output
#         # ------------------------------------------------------------------

#         start_poly_coords = self.get_coords(start_poly)

#         buffered_start_poly_coords = self.get_coords(buffered_start_poly)

#         nearby_entrance_coords = self.get_coords(nearby_entrance)

#         return (
#             salesfloor_coords,
#             start_poly_coords,
#             buffered_start_poly_coords,
#             nearby_entrance_coords,
#         )