import base64
from datetime import datetime, time, timezone
from urllib.parse import urlencode

from praw import Reddit
import requests

from django.conf import settings


class RedditAPIClient:
    def __init__(self):
        self.api_base_url = "https://oauth.reddit.com"
        self.api_client_id = settings.REDDIT_API_CLIENT_ID
        self.api_client_secret = settings.REDDIT_API_CLIENT_SECRET
        self.account_username = settings.REDDIT_ACCOUNT_USERNAME
        self.account_password = settings.REDDIT_ACCOUNT_PASSWORD
        self.user_agent = "LLM_use_case_tracker/1.0"
        self.access_token = self.request_api_access_token()

    def retrieve_subreddit_threads(self, subreddit_name: str, after_dt: datetime = None, before_dt: datetime = None):
        # if not after_dt:
        #     today = datetime.now(timezone.utc).date()
        #     start_of_day_utc = datetime.combine(today, time.min, tzinfo=timezone.utc)
        #     after_dt = start_of_day_utc
        # after_timestamp = int(after_dt.timestamp())

        # before_timestamp = None
        # if before_dt:
        #     before_timestamp = int(before_dt.timestamp())

        # "/r/subreddit_name/search?q=&restrict_sr=true&sort=new&after=UNIX_TIMESTAMP_START&before=UNIX_TIMESTAMP_END"
        url = self.api_base_url + f"/r/{subreddit_name}/search?restrict_sr=on&sort=new"
        api_headers = {
            "User-Agent": self.user_agent,
            "Authorization": f"Bearer {self.access_token}",
        }
        response = requests.get(url, headers=api_headers, params={})


    
    def request_api_access_token(self):
        # Create the authentication header
        auth = base64.b64encode(f"{self.api_client_id}:{self.api_client_secret}".encode()).decode()
        headers = {
            "User-Agent": self.user_agent,
            "Authorization": f"Basic {auth}"
        }

        # Authentication data
        auth_data = {
            "grant_type": "password",
            "username": self.account_username,
            "password": self.account_password
        }

        # Get access token
        auth_response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            headers=headers,
            data=auth_data
        )

        if auth_response.status_code == 200:
            return auth_response.json()["access_token"]
        else:
            raise Exception(f"Request for API access token failed with status code: {auth_response.status_code}")
