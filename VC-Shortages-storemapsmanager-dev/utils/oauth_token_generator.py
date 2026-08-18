import requests
from beaker.cache import CacheManager

cache = CacheManager()
TOKEN_INVALIDATION_TIME = 86400


class OAuthTokenGenerator:
    """
    OAuth token generator in order to communicate with VDP.
    Will be used with VDO interface.
    All the credentials are in config, refer config['oauth].
    Methods:
        set_url: Set url for VDP based upon the environment.
                Called by constructor at the time of initialisation.
        get_token: Fetch the token if it's in the cache else generate new token and return
        get_new_token: Generates new token based for corresponding environment
    """
    def __init__(self, oauth_cred_json):
        self.user = oauth_cred_json['user']
        self.password = oauth_cred_json['password']
        self.client_id = oauth_cred_json['client_id']
        self.tgt_ca_bundle_path = oauth_cred_json['tgt_ca_bundle_path']
        self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        self.generator_api_prod = oauth_cred_json['generator_api_prod']
        self.generator_api_dev = oauth_cred_json['generator_api_dev']

        self.client_secret_prod = oauth_cred_json['client_secret_prod']
        self.client_secret_dev = oauth_cred_json['client_secret_dev']

        self.url_prod = self.generator_api_prod.format(self.user, self.password)
        self.url_dev = self.generator_api_dev.format(self.user, self.password)

    @cache.cache("token", expire=TOKEN_INVALIDATION_TIME)
    def get_token(self, env):
        """
        Provide the token if it's available in cache, else call get_new_token method to generate new one.
        It automatically invalidates the existing token after 86400 seconds (24 hours).
        :return: Access token for VDP.
        """
        return self.get_new_token(env)

    def get_new_token(self, env):
        """
        Generate new token for VDP access. URL is set according to the env variable in config, by set_url method.
        Refer config['oauth'] for all the credentials and configs
        :return: Token generation status and access token if status is true, empty string otherwise.
        """
        # print(f"Generating new token for {env} environment")
        if env == "prod":
            url = self.url_prod
            client_secret = self.client_secret_prod
        else:
            url = self.url_dev
            client_secret = self.client_secret_dev

        response = requests.post(url, headers=self.headers, verify=self.tgt_ca_bundle_path, auth=(self.client_id, client_secret))
        if response.status_code == 200:
            response_dict = response.json()
            # print('token', response_dict['access_token'])
            return response_dict['access_token']
        else:
            print("Error in generating access token !")
            return ""
