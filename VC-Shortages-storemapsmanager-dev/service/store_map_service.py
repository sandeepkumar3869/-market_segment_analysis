import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import time
from datetime import datetime
from unittest import result
from fastapi import HTTPException
from typing import Dict
from typing import Optional
import requests, json
import logging
from utils.utility import format_date
import base64
import asyncio
from functools import partial
import uuid
import configparser
from utils.timezoneutils import utc_date_to_local_time, get_store_details , convert_timezone
from utils.oauth_token_generator import OAuthTokenGenerator
from repository.store_map_store import JobStore
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import math
import traceback
import httpx
import re

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

config = configparser.ConfigParser()
_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config.read(os.path.join(_BASE_DIR, "config", "config.ini"))

oauth_token_object = OAuthTokenGenerator(config['Oauth-Token'])
env = config["application"]["env"]



class JobService:
    """
    Service to save the job details
    """

    def __init__(self):
        self.job_store = JobStore()

    def get_map_rendering_details(self, location_id):
        try:
            store_maps_api = config["application"]["store_maps_api"] + "/map_rendering_details"

            store_maps_api = store_maps_api + "?location_id=" + location_id + '&key='+ config["Oauth-Token"]["prod_api_key"]

            response = requests.get(store_maps_api, verify=config['Oauth-Token']['tgt_ca_bundle_path'])
            return response.json()

        except Exception as error:
            logger.error(f"Exception occurred while fetching store maps to: {error}")
            return {'msg': 'Error occurred!'}       

    def get_all_by_location_id(self, location_id):
        try:
            return self.job_store.get_all_by_location_id(location_id)
        except Exception as e:
            logger.error(f"Error fetching store maps for location_id {location_id}: {e}")
            return []

    def get_all_by_location_id_v2(self, location_id):
        try:
            results = self.job_store.get_all_by_location_id_v2(location_id)
            for row in results:
                for field in ("create_ts", "position_lcl_ts"):
                    val = row.get(field)
                    if val:
                        try:
                            row[field] = datetime.fromisoformat(str(val)).strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError):
                            pass
            return results
        except Exception as e:
            logger.error(f"Error fetching store maps for location_id {location_id}: {e}")
            return []

    async def get_section_proximity(self, location_id, x, y):
        try:
            results = self.job_store.get_section_proximity(location_id, x, y)

            maps=[]
           
            for job_info in results:
                    map_details = {}
                    map_details["section_id"] = job_info[0]
                    map_details["location_id"] = job_info[1]                   
                    map_details["floor_id"] = job_info[2]
                    map_details["section_name"] = job_info[3]
                    map_details["coordinates"] = job_info[4]
                    map_details["create_ts"] = job_info[5]
                    
                    maps.append(map_details)

            return maps
            
        except Exception as e:
            return None, self.__get_exception_message(e) 
        
    def get_store_maps(self, location_id, floor_id):
        try:
            store_maps_api = config["application"]["store_maps_api"] + "/internal/svg_images"

            store_maps_api = store_maps_api + "?location_id=" + location_id + "&floor_id=" + floor_id + '&layers=wall-shapes,aisle-shapes,adjacency-icons,adjacency-names&css_name=basic&key='+ config["Oauth-Token"]["prod_api_key"]
            response = requests.get(store_maps_api, verify=config['Oauth-Token']['tgt_ca_bundle_path'])
            return response.content

        except Exception as error:
            logger.error(f"Exception occurred while fetching store maps to: {error}")
            return {'msg': 'Error occurred!'}       

    def update_camera_name(self, section_id, camera_friendly_name):
        try:
            update_response = self.job_store.update_camera_friendly_name(section_id, camera_friendly_name)
            return update_response
        except Exception as e:
            return None, self.__get_exception_message(e)

    def get_store_shapes(self, location_id, floor_id, section_name, cam_name):
        try:
            section_to_area_lookup = {}

            section_to_area_lookup["intimates"] = "Intimate Basics"
            section_to_area_lookup["mens"] = "Mens Basics"
            section_to_area_lookup["womens"] = "RTW"
            section_to_area_lookup["entrance"] = "ENTRANCE_A"
            section_to_area_lookup["exit"] = "ENTRANCE_B"

            if "exit" in cam_name.lower():
                section_name = "exit"

            section_name = section_to_area_lookup[section_name] or section_name

            store_maps_api = config["application"]["store_shapes_api"] + "/internal"

            store_maps_api = store_maps_api + "?location_id=" + location_id + f'&floor_id={floor_id}&key='+ config["Oauth-Token"]["prod_api_key"]

            response = requests.get(store_maps_api, verify=config['Oauth-Token']['tgt_ca_bundle_path'])
            
            shapes_res = response.json()

            outer_coordinates = None

            section = None

            if len(shapes_res) > 0:
                for item in shapes_res:
                    if (("ENTRANCE" not in section_name  and item.get("shape_type") == "MERCHANDISE_AREAS") or ("ENTRANCE"  in section_name and item.get("shape_type") == "HAND_DRAWN_ZONES") or (item.get("shape_type").lower() == section_name.lower().replace(' ', '_'))):
                        for shape in item.get("shapes", []):
                            if shape.get("name").lower() == section_name.lower():
                            # if section_name and shape.get("name") and (section_name.lower() in shape.get("name").lower() or shape.get("name").lower() in section_name.lower()):
                                section = shape.get("name")
                                outer_coordinates = shape.get("outer_coordinates")
                                break

            return {"section": section, "outer_coordinates":  outer_coordinates}

        except Exception as error:
            logger.error(f"Exception occurred while fetching store shapes to: {error}")
            return {'msg': 'Error occurred!'}  

    async def get_store_demography(self, ip_payload):
        try:
            ads_demography_api = (
                config["application"]["ads_demography_api"]
                + "?asset_source=store-demographics&pageSize=100000"
            )
            max_parallel = int(ip_payload.get("max_parallel_pages", 16))
            locations = ip_payload.get("store_numbers") or []

            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + oauth_token_object.get_token(env),
            }

            payload = [
                {
                    "field": "source_properties.video_start_time",
                    "operator": "BETWEEN",
                    "value": [
                        ip_payload.get("start_datetime"),
                        ip_payload.get("end_datetime"),
                    ],
                }
            ]

            if locations:
                payload.append(
                    {
                        "field": "source_properties.location_id",
                        "operator": "IN",
                        "value": locations,
                    }
                )

            def normalize_text(value):
                return re.sub(r"\s+", " ", str(value or "")).strip().lower()

            def extract_location_id(asset):
                sp = (asset or {}).get("source_properties", {}) or {}
                return sp.get("location_id")

            def extract_camera_name(asset):
                sp = (asset or {}).get("source_properties", {}) or {}
                camera_raw = sp.get("camera_friendly_name")
                return str(camera_raw).strip() if camera_raw else None

            def process_page(parsed, store_map):
                assets = parsed.get("asset_list", []) or []

                for asset in assets:
                    loc_id = extract_location_id(asset)
                    camera_name = extract_camera_name(asset)

                    if loc_id is None or not camera_name:
                        continue

                    loc_key = str(loc_id).strip()
                    if not loc_key:
                        continue

                    if loc_key not in store_map:
                        store_map[loc_key] = {
                            "location_id": loc_key,
                            "cameras": {},   # camera_name -> {"section_name": ..., "floor_id": ...}
                        }

                    store_map[loc_key]["cameras"].setdefault(
                        camera_name,
                        {
                            "section_name": None,
                            "floor_id": None,
                        },
                    )

            def extract_camera_lookup(resp_payload):
                """
                Returns:
                {
                    "camera 1": {"section_name": "...", "floor_id": 1},
                    ...
                }

                Supports either:
                - list[dict]
                - dict with common nested list keys like data/results/items
                """
                lookup = {}

                if not resp_payload:
                    return lookup

                records = resp_payload
                if isinstance(resp_payload, dict):
                    for key in ("data", "results", "items", "response"):
                        if isinstance(resp_payload.get(key), list):
                            records = resp_payload[key]
                            break

                if not isinstance(records, list):
                    records = [records]

                for item in records:
                    if not isinstance(item, dict):
                        continue

                    cam = (
                        item.get("camera_friendly_name")
                        or item.get("camera_name")
                        or item.get("name")
                    )
                    if not cam:
                        continue

                    lookup[normalize_text(cam)] = {
                        "section_name": item.get("section_name"),
                        "floor_id": item.get("floor_id"),
                    }

                return lookup

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=5.0),
                limits=httpx.Limits(
                    max_connections=max_parallel,
                    max_keepalive_connections=max_parallel,
                ),
                verify=config["Oauth-Token"]["tgt_ca_bundle_path"],
                headers=headers,
            ) as client:

                async def fetch_demography_page(idx: int):
                    resp = await client.post(
                        ads_demography_api + f"&pageNumber={idx}",
                        json=payload,
                    )
                    resp.raise_for_status()
                    return resp.json()

                # Page 0
                first = await fetch_demography_page(0)

                total_records = first.get("total_records", 0) or 0
                rpp = first.get("records_per_page", 1) or 1
                total_pages = first.get("total_pages") or (
                    math.ceil(total_records / rpp) if total_records else 1
                )

                store_map = {}
                process_page(first, store_map)

                # Remaining pages
                if total_pages > 1:
                    sem = asyncio.Semaphore(max_parallel)

                    async def bounded_fetch(idx: int):
                        async with sem:
                            try:
                                return await fetch_demography_page(idx)
                            except Exception as e:
                                logger.warning(f"Demography page {idx} failed: {e}")
                                return None

                    pages = await asyncio.gather(
                        *(bounded_fetch(i) for i in range(1, total_pages)),
                        return_exceptions=False,
                    )

                    for page in pages:
                        if page:
                            process_page(page, store_map)

            # Enrich each location -> camera -> section_name/floor_id
            async def enrich_location(data):
                try:
                    resp = await asyncio.to_thread(
                        self.get_all_by_location_id,
                        data["location_id"],
                    )
                    camera_lookup = extract_camera_lookup(resp)

                    enriched_cameras = {}
                    for cam_name, meta in data["cameras"].items():
                        cam_key = normalize_text(cam_name)
                        mapped = camera_lookup.get(cam_key, {})

                        enriched_cameras[cam_name] = {
                            "section_name": mapped.get("section_name") or meta.get("section_name"),
                            "floor_id": mapped.get("floor_id") if mapped.get("floor_id") is not None else meta.get("floor_id"),
                        }

                    return {
                        "location_id": data["location_id"],
                        "cameras": enriched_cameras,
                    }

                except Exception as e:
                    logger.error(
                        f"Error enriching location_id={data.get('location_id')}: {e}"
                    )
                    return {
                        "location_id": data.get("location_id"),
                        "cameras": {
                            cam: {"section_name": None, "floor_id": None}
                            for cam in data["cameras"].keys()
                        },
                    }

            sem = asyncio.Semaphore(max_parallel)

            async def bounded_enrich(data):
                async with sem:
                    return await enrich_location(data)

            enriched_locations = await asyncio.gather(
                *(bounded_enrich(data) for data in store_map.values())
            )

            # Cache get_store_shapes results by unique (location_id, floor_id, section_name)
            shape_cache = {}

            async def fetch_store_shape(location_id, floor_id, section_name, cam_name):
                loc_key = str(location_id).strip()
                floor_key = str(floor_id).strip() if floor_id is not None else ""
                section_key = normalize_text(section_name)

                cache_key = (loc_key, floor_key, section_key)
                if cache_key in shape_cache:
                    return shape_cache[cache_key]

                try:
                    result = await asyncio.to_thread(
                        self.get_store_shapes,
                        loc_key[1:],
                        floor_id,
                        section_name,
                        cam_name
                    )

                except Exception as e:
                    logger.error(
                        f"Error calling get_store_shapes for "
                        f"location_id={loc_key}, floor_id={floor_id}, section_name={section_name}: {e}"
                    )
                    result = {"section": section_name, "outer_coordinates": None}

                shape_cache[cache_key] = result
                return result

            # Final enrichment: add section + outer_coordinates per camera
            async def enrich_camera(location_id, cam_name, meta):
                section_name = meta.get("section_name")
                floor_id = meta.get("floor_id")

                if not section_name:
                    return {
                        "camera_name": cam_name,
                        "section_name": None,
                        "floor_id": floor_id,
                        "section": None,
                        "outer_coordinates": None,
                    }

                shape = await fetch_store_shape(location_id, floor_id, section_name, cam_name)

                return {
                    "camera_name": cam_name,
                    "section_name": section_name,
                    "floor_id": floor_id,
                    "section": shape.get("section"),
                    "outer_coordinates": shape.get("outer_coordinates"),
                }

            async def enrich_location_shapes(loc):
                cameras = await asyncio.gather(
                    *(
                        enrich_camera(loc["location_id"], cam_name, meta)
                        for cam_name, meta in loc["cameras"].items()
                    )
                )
                return {
                    "location_id": loc["location_id"],
                    "cameras": cameras,
                }

            store_shapes = await asyncio.gather(
                *(enrich_location_shapes(loc) for loc in enriched_locations)
            )

            return {"store_shapes": store_shapes}

        except Exception as error:
            logger.error(
                f"Exception occurred while fetching store demography: {error}\n{traceback.format_exc()}"
            )
            return {"msg": "Error occurred!"}