import requests
from functools import wraps
import json
import re

### In theory maybe base url and endpoints etc could all go in a dataclass just so they're centralized
BASE_URL = "https://api.projectrio.app"

### decorator just so that we don't have to include the rio key in every post body ever. any function that has `@include_rio_key(RIO_KEY) above its definition will have the rio key added to the body automatically`
def include_rio_key(rio_key):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data = kwargs.get('data', {})
            if not isinstance(data, dict):
                data = {}

            data['rio_key'] = rio_key

            kwargs['data'] = data

            return func(*args, **kwargs)
        return wrapper
    return decorator

### this class would handle the requests in general. it sets up a requests session, includes the necessary headers. user can send requests, and it will differentiate between GET and POST in order to determine how to process the arguments that get passed to it
class APIManager:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def send_request(self, endpoint, method="GET", data=None):
        url = self.base_url + endpoint
        try:
            if method == "POST":
                response = self.session.post(url, json=data)
            elif method == "GET":
                response = self.session.get(url, params=data)
            else:
                raise ValueError(f"Unsupported request type: {method}")

            ### found this, apparently it's just a streamlined way of handling "if status == 200 etc etc etc"
            response.raise_for_status()

            # need to handle different response types? I think most are json but perhaps not
            return response.json()
        
        ### was printing html which bothered me so filter by both types, in case the error is json or html
        except requests.exceptions.HTTPError as err:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                try:
                    error_message = response.json().get('description', response.text)
                except json.JSONDecodeError:
                    error_message = response.text
            elif 'text/html' in content_type:
                error_message = self.extract_message_from_html(response.text)
            else:
                error_message = response.text
            print(f"HTTP error {response.status_code}: {error_message}")

        except Exception as e:
            print(f"Error occured: {e}")
        return None
    
    ### just to get rid of dumb html that I don't want to look at
    @staticmethod
    def extract_message_from_html(html):
        match = re.search(r"<p>(.*?)</p>", html)
        if match:
            return match.group(1)
        return html
    

### slight adjustment from my existing version of the request builder. this gets passed the api manager. the add function includes a list of tuples that include the endpoint, the method, and the parameters used. calling the execute function sends the actual requests
class RequestBuilder:
    def __init__(self, api_manager: APIManager):
        self.api_manager = api_manager
        self.requests = []

    ### edited add/execute that directly accept the endpoint functions
    def add(self, func, *args, **kwargs):
        self.requests.append((func, args, kwargs))
        return self
    
    def execute(self):
        results = []
        for func, args, kwargs in self.requests:
            result = func(*args, **kwargs)
            results.append(result)
        return results

    # def add(self, endpoint, method="GET", params=None):
    #     self.requests.append((endpoint, method, params))
    #     return self
    
    # def execute(self):
    #     results = []
    #     for endpoint, method, params in self.requests:
    #         result = self.api_manager.send_request(endpoint, method, params)
    #         results.append(result)
    #     return results