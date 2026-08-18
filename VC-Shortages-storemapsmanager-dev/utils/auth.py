import logging
import base64
import requests, json
from fastapi import HTTPException, Depends, Header
from utils.utility import get_api_content_header
import configparser
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read("./config/config.ini")

def authenticate(token: str = Header(None)):
    try:
        oauth_url = config["Oauth-Token"]["auth_user_info"]

        if token is not None and token.startswith("Bearer"):
            oauth_response = requests.get(url=oauth_url,
                                        headers=get_api_content_header(token),
                                        )
            oauth_data = json.loads(json.dumps(oauth_response.json()))
 
            ad_groups = []

            for member in oauth_data.get('memberof'):
                group = member[3:member.index(',')]
                ad_groups.append(group)

            user_info = {
                "lanid": oauth_data.get('lanid'),
                "username": oauth_data.get('firstname') + " " + oauth_data.get('lastname'),
                "ad_groups": ad_groups
            }
            return user_info
        else:
            raise HTTPException(status_code=401, detail="Unauthorized")
    
    except Exception as e:
       raise HTTPException(status_code=401, detail="Unauthorized")

def decode(token):
    # Option 2:  base64 decoding

    decoded_bytes = base64.b64decode(token)
    # Convert the decoded bytes to a string
    data_index = decoded_bytes.find(b'+')
    decoded_user_info = decoded_bytes[data_index + 1:].decode('utf-8')
    print("Decoded Base64:", decoded_user_info)

def app_authorization(authorization: str = Header(None)):
    if authorization is None:
        raise HTTPException(status_code=400, detail="Authorization header is missing")
    else:
        return authenticate(authorization)
class RBAC:
    def __init__(self, required_permissions: list[str]) -> None:
        self.required_permissions = required_permissions

    def __call__(self, user_info: str = Depends(app_authorization)) -> bool:
        has_access = any(user_group in self.required_permissions for user_group in user_info["ad_groups"])

        return has_access

class APP_RBAC:
    def __init__(self, applications: List[Dict], super_admin: List[str]) -> None:
        self.applications = applications
        self.super_admin = set(super_admin)

    def __call__(self, user_info: Dict = Depends(app_authorization)) -> Dict[str, object]:
        user_groups = set(user_info.get("ad_groups", []))
        is_super_admin = bool(user_groups & self.super_admin)
        
        access_result = {}

        for app in self.applications:
            app_name = app["name"]
            role_access = {}

            for role in app.get("roles", []):
                role_name = role.get("role_name", "").lower().replace(" ", "_")
                role_groups = set(role.get("ad_groups", []))

                # Determine access based on super admin or matching AD groups
                role_access[role_name] = is_super_admin or bool(user_groups & role_groups)

            access_result[app_name] = role_access


        return {
            "super_admin": is_super_admin,
            "access": access_result
        }

