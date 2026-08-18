
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from repository.store_map_store import JobStore
import asyncio
import datetime
import logging
import random
import pandas as pd
import schedule
import time

import impala.dbapi
from impala.util import as_pandas
import json
import requests
import configparser
import tgt_certs

from store_map_service import JobService

config = configparser.ConfigParser()
_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
config.read(os.path.join(_BASE_DIR, 'config', 'config.ini'))

job_service = JobService()
job_store = JobStore()


def get_device_coordinates(date, store_id, device_id):

    try:
        conn = impala.dbapi.connect(
            host=config["bigred"]["host"],
            use_ssl=True,
            port=8443,
            http_path="gateway/bigred/hive",
            auth_mechanism="PLAIN",
            use_http_transport=True,
            user=config["bigred"]["username"],
            password=config["bigred"]["password"],
        )

        print(f"Fetching device coordinates for store_id: {store_id}, device_id: {device_id} and date: {date}")
        query = (''' SELECT
                        position_id, position_lcl_ts, store_map_local_x_coordinate, store_map_local_y_coordinate  
                        FROM prd_tpd_fnd.in_store_positioning_analytics 
                        WHERE 
                          position_date > %s
                          and location_id = %s
                          and device_id=  %s
                          AND position_source = 'assets'
                    ''')

        with conn.cursor() as cursor:
            cursor.execute(query, [date, store_id, device_id])
            df = as_pandas(cursor)

        if df.empty:
            print(f"No records found for device coordinates for store_id: {store_id}, device_id: {device_id} and date: {date}")
            return None
        else:
            print(f"Fetched {len(df)} records for device coordinates for store_id: {store_id}, device_id: {device_id} and date: {date}")
            return df

    except Exception as e:
        logging.error(f"Error fetching device coordinates for store_id: {store_id}, device_id: {device_id} and date: {date}. Error: {e}")
        return None

def get_nearest_camera_names(date, store_id, device_id):
    try:
        device_coordinates_df = get_device_coordinates(date, store_id, device_id)

        if device_coordinates_df is not None:
            total = len(device_coordinates_df)
            for index, row in device_coordinates_df.iterrows():
                count = index + 1
                print(f"Processing device coordinate {count}/{total} ----------------------------------------")
                position_id = row['position_id']
                position_lcl_ts = row['position_lcl_ts']
                x_coordinate = row['store_map_local_x_coordinate']
                y_coordinate = row['store_map_local_y_coordinate']
                logging.info(f"Device coordinates - Position ID: {position_id}, Timestamp: {position_lcl_ts}, X: {x_coordinate}, Y: {y_coordinate}")
                proximity_url = config["application"]["proximity_api"]
                result = requests.get(url=f"{proximity_url}?x={x_coordinate}&y={y_coordinate}", verify=tgt_certs.where())

                if result:

                    zone_name = result.json()[0]["section_name"]
                    section_id = result.json()[0]["section_id"]
                    print(zone_name)
                    url = config["application"]["rag_api"]

                    payload = json.dumps({
                        "query": zone_name,
                        "top_k": 1,
                        "min_score": 0.3
                    })
                    headers = {
                        'Content-Type': 'application/json'
                    }

                    response = requests.request("POST", url, headers=headers, data=payload, verify=tgt_certs.where())

                    rag_results = response.json()
                    if rag_results:
                        camera_name = rag_results["rag_documents"][0]["metadata"]["camera_friendly_name"]
                        print(f"Nearest camera: {camera_name} and section_is is {section_id}")
                        update_response = job_service.update_camera_name(section_id, camera_name)
                        print(f"Camera friendly name update response for section_id {section_id}: {update_response}")
                    else:
                        print("No camera found for the given zone.")

                else:
                    print(f"Failed to fetch nearest camera for device coordinates with Position ID: {position_id}. Response: {result.text}")
        else:
            print("No device coordinates found.")
            return None


    except Exception as e:
        logging.error(f"Error fetching nearest camera names for store_id: {store_id}. Error: {e}")
        return []

def main():
    print("Starting the BigRed Service script.")
    date = '2026-04-07'
    store_id = '2193'
    device_id = 'E1:D2:02:FB:7D:E8'
    get_nearest_camera_names(date, store_id, device_id)

if __name__ == "__main__":
    main()