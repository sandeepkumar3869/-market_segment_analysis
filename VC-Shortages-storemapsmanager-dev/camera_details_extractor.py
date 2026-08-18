"""
Camera Details Extractor

This script extracts comprehensive camera details for a specific store including:
- Camera name and ID
- X, Y coordinates (store map local coordinates in meters)
- Coverage area (section name)
- Area coverage (in square meters)
- Viewing angle/compactness
- Travel time within coverage area
- Camera viewing distance (shortest and longest)

Author: Sandeep Kumar
Date: 2026-08-18
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from shapely.wkt import loads
from ast import literal_eval
import numpy as np
from typing import Dict, List, Any, Optional
import json


class CameraDetailsExtractor:
    """
    Extract and analyze camera details for a given store including:
    - Position coordinates
    - Coverage zones
    - Viewing angles
    - Travel time metrics
    """
    
    def __init__(self, store_number: str, floor_number: int = 1):
        """
        Initialize the Camera Details Extractor
        
        Args:
            store_number (str): Store number (e.g., '1234')
            floor_number (int): Floor number (default: 1)
        """
        self.store_number = store_number
        self.floor_number = floor_number
        self.camera_data = None
        self.shape_zones = None
        self.shape_areas = None
        
    def parse_wkt_geometry(self, wkt_string: str):
        """
        Parse WKT (Well-Known Text) geometry string
        
        Args:
            wkt_string (str): WKT format geometry string
            
        Returns:
            shapely.geometry object or None
        """
        try:
            if isinstance(wkt_string, str):
                return loads(wkt_string)
        except Exception as e:
            print(f"Error parsing WKT: {e}")
        return None
    
    def extract_coordinates(self, json_coords: str) -> Dict[str, float]:
        """
        Extract min/max coordinates from JSON string
        
        Args:
            json_coords (str): JSON string with x, y coordinates
            
        Returns:
            Dictionary with x_min, x_max, y_min, y_max
        """
        try:
            coords_df = pd.read_json(json_coords)
            return {
                'x_min': coords_df['x'].min(),
                'x_max': coords_df['x'].max(),
                'y_min': coords_df['y'].min(),
                'y_max': coords_df['y'].max()
            }
        except Exception as e:
            print(f"Error extracting coordinates: {e}")
            return {}
    
    def calculate_coverage_distance(self, polygon) -> Dict[str, float]:
        """
        Calculate the shortest and longest viewing distance across a polygon
        
        Args:
            polygon: Shapely Polygon object representing coverage area
            
        Returns:
            Dictionary with shortest_distance and longest_distance in meters
        """
        if not polygon or polygon.is_empty:
            return {'shortest_distance': 0, 'longest_distance': 0}
        
        try:
            minx, miny, maxx, maxy = polygon.bounds
            width = maxx - minx
            height = maxy - miny
            
            # Longest distance = diagonal of bounding box
            longest_distance = round((width ** 2 + height ** 2) ** 0.5, 3)
            
            # Shortest distance = half of minimum dimension
            shortest_distance = min(width, height) / 2
            shortest_distance = round(shortest_distance, 3)
            
            return {
                'shortest_distance': shortest_distance,
                'longest_distance': longest_distance,
                'width': round(width, 3),
                'height': round(height, 3)
            }
        except Exception as e:
            print(f"Error calculating coverage distance: {e}")
            return {'shortest_distance': 0, 'longest_distance': 0}
    
    def calculate_compactness(self, polygon) -> float:
        """
        Calculate polygon compactness (circularity)
        Formula: 4π × area / perimeter²
        Values closer to 1 indicate more circular/compact shape
        
        Args:
            polygon: Shapely Polygon object
            
        Returns:
            Compactness value (0-1 scale)
        """
        if not polygon or polygon.is_empty:
            return 0.0
        
        try:
            area = polygon.area
            perimeter = polygon.length
            
            if perimeter == 0:
                return 0.0
            
            compactness = round(4 * np.pi * area / (perimeter ** 2), 4)
            return compactness
        except Exception as e:
            print(f"Error calculating compactness: {e}")
            return 0.0
    
    def calculate_travel_time(self, distance: float, speed: float = 1.42) -> float:
        """
        Calculate travel time based on distance and walking/movement speed
        
        Args:
            distance (float): Distance in meters
            speed (float): Movement speed in m/s (default: 1.42 m/s for walking)
            
        Returns:
            Travel time in seconds
        """
        if distance <= 0 or speed <= 0:
            return 0.0
        
        travel_time = round(distance / speed, 3)
        return travel_time
    
    def load_camera_data(self, camera_data: pd.DataFrame):
        """
        Load camera ping data
        
        Args:
            camera_data (pd.DataFrame): DataFrame with camera positions
                Expected columns: 'device_id', 'store_map_local_x_coordinate', 
                                 'store_map_local_y_coordinate', 'position_id'
        """
        self.camera_data = camera_data
    
    def load_shape_data(self, shape_zones: pd.DataFrame, shape_areas: pd.DataFrame):
        """
        Load store shape data (zones and areas)
        
        Args:
            shape_zones (pd.DataFrame): Zone shapes from BR3
            shape_areas (pd.DataFrame): Area shapes from BR3
        """
        self.shape_zones = shape_zones
        self.shape_areas = shape_areas
    
    def get_camera_details_by_name(self, 
                                   camera_name: str,
                                   camera_data: Optional[pd.DataFrame] = None,
                                   shape_zones: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Extract comprehensive details for a specific camera by name/device_id
        
        Args:
            camera_name (str): Camera name or device_id (e.g., 'CAM_001')
            camera_data (pd.DataFrame, optional): Camera position data
            shape_zones (pd.DataFrame, optional): Zone shape data
            
        Returns:
            Dictionary containing all camera details
        """
        
        # Use provided data or class-level data
        if camera_data is not None:
            self.camera_data = camera_data
        if shape_zones is not None:
            self.shape_zones = shape_zones
        
        if self.camera_data is None:
            return {'error': 'No camera data loaded'}
        
        # Filter for specific camera
        camera_records = self.camera_data[
            (self.camera_data['device_id'].astype(str) == camera_name) |
            (self.camera_data['device_id'].astype(str).str.contains(camera_name, case=False, na=False))
        ]
        
        if camera_records.empty:
            return {'error': f'Camera "{camera_name}" not found in store {self.store_number}'}
        
        # Extract the first record (most recent or representative)
        camera_record = camera_records.iloc[0]
        
        camera_details = {
            'store_number': self.store_number,
            'floor_number': self.floor_number,
            'camera_name': camera_name,
            'camera_id': camera_record.get('device_id', 'N/A'),
            'position_id': camera_record.get('position_id', 'N/A'),
            'total_records': len(camera_records),
        }
        
        # ========== COORDINATES ==========
        if 'store_map_local_x_coordinate' in camera_record and 'store_map_local_y_coordinate' in camera_record:
            camera_details['coordinates'] = {
                'x_coordinate': round(float(camera_record['store_map_local_x_coordinate']), 3),
                'y_coordinate': round(float(camera_record['store_map_local_y_coordinate']), 3),
                'unit': 'meters'
            }
        
        # ========== COVERAGE ZONE INFORMATION ==========
        if 'zone_name' in camera_record and pd.notna(camera_record['zone_name']):
            camera_details['coverage_zone'] = {
                'zone_name': camera_record['zone_name'],
                'zone_unique_id': camera_record.get('zone_unique_id', 'N/A'),
                'zone_area_sqm': round(float(camera_record['zone_area_in_square_meter']), 2) 
                    if 'zone_area_in_square_meter' in camera_record else 'N/A'
            }
        
        # ========== MERCHANDISE AREA ==========
        if 'merch_area_adjacency_name' in camera_record and pd.notna(camera_record['merch_area_adjacency_name']):
            camera_details['merchandise_area'] = {
                'area_name': camera_record['merch_area_adjacency_name'],
                'area_unique_id': camera_record.get('merch_area_unique_id', 'N/A'),
                'area_sqm': round(float(camera_record['merch_area_in_square_meter']), 2)
                    if 'merch_area_in_square_meter' in camera_record else 'N/A'
            }
        
        # ========== RACETRACK INFORMATION ==========
        if 'is_position_in_racetrack_f' in camera_record:
            camera_details['is_in_racetrack'] = bool(camera_record['is_position_in_racetrack_f'])
        
        # ========== ZONE-LEVEL COVERAGE METRICS ==========
        if self.shape_zones is not None and 'zone_name' in camera_record:
            zone_name = camera_record['zone_name']
            zone_records = self.shape_zones[
                self.shape_zones['shape_name'].str.lower() == str(zone_name).lower()
            ]
            
            if not zone_records.empty:
                zone_record = zone_records.iloc[0]
                
                # Parse geometry
                if 'shape_outer_coordinates_geo' in zone_record:
                    geometry = self.parse_wkt_geometry(zone_record['shape_outer_coordinates_geo'])
                    
                    if geometry:
                        distances = self.calculate_coverage_distance(geometry)
                        compactness = self.calculate_compactness(geometry)
                        
                        camera_details['zone_coverage_metrics'] = {
                            'shortest_viewing_distance_m': distances['shortest_distance'],
                            'longest_viewing_distance_m': distances['longest_distance'],
                            'zone_width_m': distances.get('width', 0),
                            'zone_height_m': distances.get('height', 0),
                            'compactness_ratio': compactness,
                            'compactness_description': self._get_compactness_description(compactness),
                            'total_area_sqm': round(float(zone_record['shape_area']), 2) 
                                if 'shape_area' in zone_record else 'N/A'
                        }
                        
                        # Calculate travel times
                        travel_metrics = {
                            'shortest_travel_time_sec': self.calculate_travel_time(distances['shortest_distance']),
                            'longest_travel_time_sec': self.calculate_travel_time(distances['longest_distance']),
                            'avg_travel_time_sec': self.calculate_travel_time(
                                (distances['shortest_distance'] + distances['longest_distance']) / 2
                            ),
                            'walking_speed_assumption_ms': 1.42
                        }
                        camera_details['zone_travel_time'] = travel_metrics
        
        return camera_details
    
    def _get_compactness_description(self, compactness: float) -> str:
        """
        Get human-readable description of compactness value
        
        Args:
            compactness (float): Compactness ratio (0-1)
            
        Returns:
            Description string
        """
        if compactness >= 0.9:
            return "Highly Compact (Nearly circular)"
        elif compactness >= 0.7:
            return "Moderately Compact"
        elif compactness >= 0.5:
            return "Moderate Shape"
        elif compactness >= 0.3:
            return "Elongated Shape"
        else:
            return "Highly Elongated"
    
    def get_all_cameras_in_store(self, 
                                 camera_data: Optional[pd.DataFrame] = None,
                                 shape_zones: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Extract details for all cameras in the store
        
        Args:
            camera_data (pd.DataFrame, optional): Camera position data
            shape_zones (pd.DataFrame, optional): Zone shape data
            
        Returns:
            List of dictionaries containing camera details
        """
        if camera_data is not None:
            self.camera_data = camera_data
        if shape_zones is not None:
            self.shape_zones = shape_zones
        
        if self.camera_data is None:
            return [{'error': 'No camera data loaded'}]
        
        # Get unique camera names
        unique_cameras = self.camera_data['device_id'].unique()
        
        all_camera_details = []
        for camera in unique_cameras:
            details = self.get_camera_details_by_name(str(camera))
            all_camera_details.append(details)
        
        return all_camera_details
    
    def export_camera_details(self, 
                            camera_details: Dict[str, Any],
                            file_format: str = 'json',
                            output_path: Optional[str] = None) -> str:
        """
        Export camera details to file
        
        Args:
            camera_details (Dict): Camera details dictionary
            file_format (str): 'json' or 'csv'
            output_path (str, optional): Output file path
            
        Returns:
            Formatted string of camera details
        """
        if file_format == 'json':
            return json.dumps(camera_details, indent=2)
        elif file_format == 'csv':
            # Flatten nested dictionaries for CSV
            flat_details = self._flatten_dict(camera_details)
            return pd.DataFrame([flat_details]).to_csv(index=False)
        else:
            return str(camera_details)
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """
        Flatten nested dictionary
        
        Args:
            d (Dict): Dictionary to flatten
            parent_key (str): Parent key prefix
            sep (str): Separator for nested keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """
    Example: Extract camera details for store 1234, camera 'CAM_001'
    """
    
    # Initialize extractor
    extractor = CameraDetailsExtractor(store_number='1234', floor_number=1)
    
    # === SAMPLE DATA (In real scenario, load from BR3/Database) ===
    
    # Sample camera data
    camera_data = pd.DataFrame({
        'device_id': ['CAM_001', 'CAM_002', 'CAM_003', 'CAM_001'],
        'store_map_local_x_coordinate': [100.5, 150.2, 200.8, 100.3],
        'store_map_local_y_coordinate': [200.3, 180.5, 220.1, 200.5],
        'position_id': ['POS_1', 'POS_2', 'POS_3', 'POS_1'],
        'zone_name': ['electronics', 'grocery', 'electronics', 'electronics'],
        'zone_unique_id': ['ZONE_001', 'ZONE_002', 'ZONE_001', 'ZONE_001'],
        'zone_area_in_square_meter': [500.0, 750.0, 500.0, 500.0],
        'merch_area_adjacency_name': ['electronics_area', 'grocery_area', 'electronics_area', 'electronics_area'],
        'merch_area_unique_id': ['MA_001', 'MA_002', 'MA_001', 'MA_001'],
        'merch_area_in_square_meter': [1200.0, 1800.0, 1200.0, 1200.0],
        'is_position_in_racetrack_f': [False, True, False, False]
    })
    
    # Sample zone shape data
    shape_zones = pd.DataFrame({
        'shape_name': ['electronics', 'grocery'],
        'shape_unique_id': ['ZONE_001', 'ZONE_002'],
        'shape_area': [500.0, 750.0],
        'shape_outer_coordinates_geo': [
            'POLYGON ((50 150, 150 150, 150 250, 50 250, 50 150))',
            'POLYGON ((100 100, 200 100, 200 260, 100 260, 100 100))'
        ]
    })
    
    # Load data
    extractor.load_camera_data(camera_data)
    extractor.load_shape_data(shape_zones, None)
    
    # ========== EXTRACT SINGLE CAMERA DETAILS ==========
    print("=" * 80)
    print("CAMERA DETAILS EXTRACTION - STORE 1234")
    print("=" * 80)
    
    camera_details = extractor.get_camera_details_by_name('CAM_001')
    
    print("\n📹 CAMERA DETAILS:")
    print(json.dumps(camera_details, indent=2))
    
    # ========== EXTRACT ALL CAMERAS ==========
    print("\n" + "=" * 80)
    print("ALL CAMERAS IN STORE")
    print("=" * 80)
    
    all_cameras = extractor.get_all_cameras_in_store()
    
    for i, cam in enumerate(all_cameras, 1):
        print(f"\n--- Camera {i} ---")
        print(json.dumps(cam, indent=2))
    
    # ========== EXPORT TO JSON ==========
    print("\n" + "=" * 80)
    print("EXPORT CAMERA DETAILS TO JSON")
    print("=" * 80)
    
    json_output = extractor.export_camera_details(camera_details, file_format='json')
    print(json_output)
    
    return extractor, camera_details


if __name__ == "__main__":
    extractor, camera_details = example_usage()
