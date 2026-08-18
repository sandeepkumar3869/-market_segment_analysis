import yaml
import logging
import datetime
import configparser
import os
import shutil
import requests
import json
from utils.oauth_token_generator import OAuthTokenGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('./config/config.ini')

oauth_token_object = OAuthTokenGenerator(config['Oauth-Token'])

def pagination(raw_data, page=1, items_per_page=10):
    current_page_items = []
    if raw_data is not None:
        result_length = len(raw_data)

        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page

        if start_index > result_length:
            current_page_items = []
        else:
            if end_index > result_length:
                end_index = result_length

            current_page_items = raw_data[start_index:end_index]
    response = {
        'page': page,
        'items_per_page': len(current_page_items),
        'total_items': len(raw_data) if raw_data is not None else len(current_page_items),
        'data': current_page_items
    }
    return response

def get_api_content_header(auth_string: str ) -> dict:
    try:
        return {
            "Authorization": auth_string,
            "Content-Type": "application/json",
        }
    except Exception as e:
        # Log the exception here if needed
        return None

def format_date(tx_date, offset=False):
    try:
        if offset:
            dt_object = datetime.datetime.strptime(tx_date, "%Y-%m-%d %H:%M:%S.%f%z")
        else:
           dt_object = datetime.datetime.strptime(tx_date, "%Y-%m-%d %H:%M:%S.%f")
       
        formated_tx_date = dt_object.strftime("%Y-%m-%d %H:%M:%S")

    except:
        if offset:
            dt_object = datetime.datetime.strptime(tx_date, "%Y-%m-%d %H:%M:%S%z")
            formated_tx_date = dt_object.strftime("%Y-%m-%d %H:%M:%S")
        return formated_tx_date


    return formated_tx_date

def delete_video(filePath):
    try:
        print('now deleting the video')
        if(os.path.isdir(filePath)):
          shutil.rmtree(filePath)
    except:
        print('Error while deleting the directory', filePath)     

  
def fetch_receipt_image(receipt_info):
    try:
        headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer ' + oauth_token_object.get_token('prod'),
        }
        receipt_api = config["application"]["receipt_api"] + '?key=' + config["vdp"]["api_key_prod"]
        payload = json.dumps(receipt_info)

        response = requests.post(receipt_api, headers=headers, data=payload, verify=config['Oauth-Token']['tgt_ca_bundle_path'])

        if response.status_code == 200:

            if receipt_info.get('printer_type') == 'png':
               result = response.json()
            else:
               result = response.text

            return result
        elif response.status_code == 401:
            return response.status_code

    except Exception as error:
        logger.error(f"Exception occurred due to: {error}")
        return None

def fetch_guest_store_trips_info(guest_info):
    try:
        headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer ' + oauth_token_object.get_token('prod'),
        'x-api-key': config["vdp"]["api_key_prod"],
        'x-guest-profile-id': guest_info.get('guest_profile_id')
        }

        guest_store_trips_api = config["application"]["guest_store_trips_api"] + '?days=' + str(guest_info.get('days', 90))
        response = requests.get(guest_store_trips_api, headers=headers, verify=config['Oauth-Token']['tgt_ca_bundle_path'])
        return response.status_code, response.json()

    except Exception as error:
        logger.error(f"Exception occurred while fetching guest store trips due to: {error}")
        return {'msg': 'Error occurred!'}
    
def fetch_guest_graph_details(guest_info):
    try:
        headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer ' + oauth_token_object.get_token(config["application"]["env"]),
        }

        if guest_info.get('guest_profile_id') is not None:
            payload = json.dumps({
                'guest_id': guest_info.get('guest_profile_id'),
                'depth': guest_info.get('depth', 5)
            })

        if guest_info.get('receipt_id') is not None:
            payload = json.dumps({
                'receipt_id': guest_info.get('receipt_id'),
                'depth': guest_info.get('depth', 5)
            })    

        guest_graph_api = config["application"]["guest_graph_api"]
        response = requests.post(guest_graph_api, headers=headers, data=payload, verify=config['Oauth-Token']['tgt_ca_bundle_path'])
        return response.status_code, response.json()

    except Exception as error:
        logger.error(f"Exception occurred while fetching guest graph due to: {error}")
        return {'msg': 'Error occurred!'}

def fetch_guest_store_trips_info(guest_info):
    try:
        headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer ' + oauth_token_object.get_token('prod'),
        'x-api-key': config["vdp"]["api_key_prod"],
        'x-guest-profile-id': guest_info.get('guest_profile_id')
        }

        guest_store_trips_api = config["application"]["guest_store_trips_api"] + '?days=' + str(guest_info.get('days', 90))
        response = requests.get(guest_store_trips_api, headers=headers, verify=config['Oauth-Token']['tgt_ca_bundle_path'])
        return response.status_code, response.json()

    except Exception as error:
        logger.error(f"Exception occurred while fetching guest store trips due to: {error}")
        return {'msg': 'Error occurred!'}
    
     