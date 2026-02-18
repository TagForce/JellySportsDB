# helpers/jellyfin_client.py
import json
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .plexlog import log, LL_ERROR, LL_DEBUG

class JellyfinClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f'MediaBrowser Token="{token}"',
            "Accept": "application/json",
        }
        self.ssl_ctx = ssl._create_unverified_context()

    def _request(self, method: str, endpoint: str, params: dict = None, json_data=None):
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())

        url = f"{self.base_url}/{endpoint.lstrip('/')}{query}"

        headers = self.headers.copy()
        data = None
        if json_data is not None:
            data = json.dumps(json_data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url, data=data, headers=headers, method=method.upper())

        try:
            with urlopen(req, context=self.ssl_ctx) as resp:
                if resp.getcode() in (200, 204):
                    return json.load(resp) if resp.headers.get("Content-Type", "").startswith("application/json") else {}
                return {}
        except HTTPError as e:
            log(f"Jellyfin HTTP {e.code} on {endpoint}", "JELLY", LL_ERROR)
            return {}
        except Exception as e:
            log(f"Jellyfin request failed: {e}", "JELLY", LL_ERROR)
            return {}

    def get_item(self, item_id: str, fields: str = None):
        params = {"Fields": fields} if fields else None
        data = self._request("GET", f"Items/{item_id}", params)
        return data

    def update_item(self, item_id: str, payload: dict):
        return self._request("POST", f"Items/{item_id}", json_data=payload)

    def refresh_item(self, item_id: str, recursive: bool = True):
        params = {"Recursive": "true"} if recursive else {}
        return self._request("POST", f"Items/{item_id}/Refresh", params)

    def upload_image(self, item_id: str, image_type: str, filepath: str):
        if not Path(filepath).is_file():
            return False
        with open(filepath, "rb") as f:
            data = f.read()
        headers = self.headers.copy()
        headers["Content-Type"] = "image/jpeg"  # assume jpeg for simplicity
        url = f"{self.base_url}/Items/{item_id}/Images/{image_type}"
        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, context=self.ssl_ctx) as resp:
                return resp.getcode() in (200, 204)
        except Exception as e:
            log(f"Image upload failed: {e}", "JELLY", LL_ERROR)
            return False

    # Add more methods as needed (get_series, get_seasons, get_episodes, etc.)