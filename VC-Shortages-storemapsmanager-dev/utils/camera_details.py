from ast import AsyncFunctionDef
import json
from logging import exception
import requests
import configparser
from urllib.parse import urljoin
from utils.oauth_token_generator import OAuthTokenGenerator

config = configparser.ConfigParser()
config.read('./config/config.ini')

oauth_token_object = OAuthTokenGenerator(config['Oauth-Token'])
env = config["application"]["env"]
CERT_PATH = config["application"]["ssl_cafile"]

def camera_register_mapping(location, register):
    try:
        headers = {
            'Content-type': 'application/json',
            'Authorization': 'Bearer ' + oauth_token_object.get_token(env),
            }


        cameras = []
        payload = json.dumps({
            "locations_ids": [ "T" + location ]
        })

        response = requests.post(pos_api_url, headers=headers, data=payload, verify=CERT_PATH)

        if response.status_code == 200:
                cameras_reg = response.json()

                for entry in cameras_reg:
                    if str(register) == entry['register_id']:
                        cameras.append(entry['camera_id'])
                        # return entry['camera_id']

        return cameras 

    except Exception as e:

        print('Error occured while fetching the cameras to register mapping : ', location, register, e)
        return None        

def fetch_cameras(location_no):
    try:
        camera_api = config["application"]["get_cameras_api"]
        headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer ' +  oauth_token_object.get_token('prod')
        }

        camera_url = urljoin(camera_api,f'?location_id={location_no}')
        
        response = requests.get(camera_url, headers=headers, verify=CERT_PATH)
        if response.status_code == 200:
                cameras = response.json()

                return cameras  
        else:
            print("Error while fetching the cameras : ", response.status_code)
    except Exception as e:
        print("Error while fetching the cameras  - Theia server down: ", e)


def fetch_section_by_camera(location, camera_name):
    try:

        print("input", location, camera_name)
        headers = {
            'Content-type': 'application/json',
            'Authorization': 'Bearer ' + oauth_token_object.get_token(env)
            }

        rag_section_api = config["application"]["rag_section_api"]

        camera_response = {}
        payload = json.dumps({
            "query": camera_name,
              "location_id": location, 
              "top_k": 2, 
              "min_score": 0.8
        })

        response = requests.post(rag_section_api, headers=headers, data=payload, verify=CERT_PATH)

        if response.status_code == 200:
                camera_response = response.json()

        return camera_response 

    except Exception as e:
        print("Error while fetching the section mapping by camera name", e)

def fetch_section_by_camera_v2(location, camera_name):
    try:

        print("input", location, camera_name)
        headers = {
            'Content-type': 'application/json',
            'Authorization': 'Bearer ' + oauth_token_object.get_token(env)
            }

        rag_section_api = config["application"]["rag_section_api"]

        camera_response = {}
        payload = json.dumps({
            "query": camera_name,
            "location_id": location, 
            "top_k": 1, 
            "min_score": 0.7,
            "index_name": "store-camera-section-mapping-v3"
        })

        response = requests.post(rag_section_api, headers=headers, data=payload, verify=CERT_PATH)

        if response.status_code == 200:
                camera_response = response.json()

        return camera_response 

    except Exception as e:
        print("Error while fetching the section mapping by camera name", e)

def get_all_exit_cameras(cameras):
    try:
        exit_cameras = []
        
        for camera in cameras:
            if "Exit" in camera["friendly_name"] and "Vestibule" in camera["friendly_name"]:

                profiles_details = camera["profile_details"]

                camera_profiles = [p for p in profiles_details if p["record_stream"] == True]

                if(len(camera_profiles) > 0):
                    camera["encoder"] = camera_profiles[0]["encoder"]

                exit_cameras.append(camera)

        return exit_cameras        

    except Exception as e:
        print("Error while fetching the exit cameras : ", e)


def fetch_camera_info_by_id(cameras, camera_ids):
    try:
        total_cameras = []
        for camera_id in camera_ids:
            if len(camera_ids) >= 2:     
               camera_details = [p for p in cameras if p["id"] == camera_id and p["logical_delete"] == False and str(p["camera_status"]) == "true" and p["camera_condition"] == "online"]
            else:  
               camera_details = [p for p in cameras if p["id"] == camera_id]

            for camera in camera_details:
                camera_info = {}
                camera_info["friendly_name"] = camera["friendly_name"]
                camera_info["macid"] = camera["macid"]
                camera_info["hostname"] = camera["hostname"]

                profiles_details = camera["profile_details"]

                camera_profiles = [p for p in profiles_details if p["record_stream"] == True]

                if(len(camera_profiles) > 0):
                    camera_info["encoder"] = camera_profiles[0]["encoder"]

                total_cameras.append(camera_info)
                
        return total_cameras                

    except Exception as e:
        print("Error while fetching the camera details : ", e)

def fetch_camera_ids_by_camera_name(cameras, camera_name):
    try:
       camera_ids = [p["id"] for p in cameras if p["friendly_name"] == camera_name]
       return camera_ids                

    except Exception as e:
        print("Error while fetching the camera ids : ", e)        