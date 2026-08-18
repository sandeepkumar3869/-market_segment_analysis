from datetime import timezone
import datetime
import requests
import configparser
import pytz
import json

config = configparser.ConfigParser()
config.read("./config/config.ini")

location = {}

def utc_date_to_local_time(utc_time, tz_name):
    if "." in utc_time:
      utc_date = datetime.datetime.strptime(utc_time, "%Y-%m-%d %H:%M:%S.%f")
    else:
      utc_date = datetime.datetime.strptime(utc_time, "%Y-%m-%d %H:%M:%S")

    utc_time_res = utc_date.replace(tzinfo=timezone.utc)
    location_time = utc_time_res.astimezone(pytz.timezone(tz_name))
    return location_time

def epoch_to_date(epochtime, tz_name):
    # dt = datetime.datetime.fromtimestamp(epochtime/1000, timezone.utc) #To display results in UTC
    dt = datetime.datetime.fromtimestamp(epochtime/1000, pytz.timezone(tz_name)) #To display results in Store local time
    formated_date = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
    return formated_date[:-3]

def get_store_details(store_id):
    url = f"https://api.target.com/locations/v3/public/{store_id}"
    querystring = {"key": config["vdp"]["api_key_prod"]}

    payload = ""
    headers = {'accept': 'application/json'}
    store_info = {}
    store_address = ""

    try:
        if location.get(store_id) is None:
           response = requests.request("GET", url, data=payload, headers=headers, params=querystring)

           if response.status_code == 200:
            store_data = response.json()

            store_info["location_type"] =  store_data["type_code"]
            
            if "address" in store_data:

                if(len(store_data["address"]) > 0):
                    mail_address = store_data["address"][0]
                    store_address = mail_address["address_line1"] + "\n" + mail_address["city"] + ", " + mail_address["state"] + ", " +  mail_address["postal_code"] + "\n" + mail_address["county"] + " County"

                    store_info["address"] = store_address  

            if "geographic_specifications" in store_data:
                location_tz = store_data["geographic_specifications"].get("iso_time_zone_code", "")
                latitude = store_data["geographic_specifications"].get("latitude", "")
                longitude = store_data["geographic_specifications"].get("longitude", "")
                # location[store_id] = location_tz

                store_info["timezone"] = location_tz
                store_info["latitude"] = latitude
                store_info["longitude"] = longitude

                location[store_id] = store_info

            # return store_info
            return location.get(store_id) 
        else:
            return  location.get(store_id)      
    except Exception as e:
        print("locations-v3 server down: ", e)
        return None
    
    print("locations-v3 server down: ", response.text)
    return None

def convert_timezone(row):
        tx_details = {}

        tx_details["location_id"] = row[0]
        tx_details["tx_start_ts"] = row[1]

        store_info = get_store_details(str(tx_details["location_id"])[1:])

        location_tz = store_info["timezone"]

        local_time = utc_date_to_local_time(str(tx_details["tx_start_ts"]), location_tz)

        # Extract day of the week and hour of the day
        day_of_week = local_time.weekday()  # 0 = Monday, 6 = Sunday

        if day_of_week == 6:
            day_of_week = 0  # Sunday -> 0
        else:
            day_of_week += 1  # Monday -> 1, ..., Saturday -> 6

        hour_of_day = local_time.hour
        return (day_of_week, hour_of_day)


