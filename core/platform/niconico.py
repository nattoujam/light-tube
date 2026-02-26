import requests
from datetime import datetime
from typing import List, Optional
from .base import PlatformBase, RemoteVideo

class Niconico(PlatformBase):
    def __init__(self, base_url: str):
        self.base_url = base_url

    def resolve_external_id(self, name: str) -> str:
        # Use the input directly as a tag.
        return name

    def fetch_videos(self, external_id: str, limit: int = 50, published_before: datetime = None) -> List[RemoteVideo]:
        # Search for videos by tag
        # Use application name as User-Agent as required by niconico API.
        headers = {
            "User-Agent": "light-tube-app/0.1.0"
        }

        # Snapshot API Search by Tag
        # Use requests.get(url, params=...) but ensure targets/fields are simple strings.
        # If multiple targets are needed, they should be comma-separated strings.
        params = {
            "q": external_id, # external_id is the tag string
            "targets": "tags",
            "fields": "contentId,title,startTime",
            "_sort": "-startTime",
            "_limit": limit,
            "_context": "light-tube-app"
        }

        if published_before:
            # filters[startTime][lt]=...
            # The user pointed out that '&' might be encoded as '%2C'.
            # In requests, dict params are typically encoded correctly.
            # But let's be careful with nested keys if any.
            params["filters[startTime][lt]"] = published_before.strftime("%Y-%m-%dT%H:%M:%S+09:00")

        # To avoid any automatic encoding issues that requests might do differently,
        # we can use a PreparedRequest or just trust requests.get but let's double check.
        # Actually, %2C is the encoding for ',', not '&'.
        # If '&' is being encoded as something else, or if ',' is being encoded as '%2C' where it shouldn't be...
        # The Snapshot API documentation says targets/fields should be comma separated.

        response = requests.get(self.base_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        videos = []
        for item in data.get("data", []):
            content_id = item["contentId"]
            title = item["title"]
            start_time_str = item["startTime"]
            # startTime is like "2023-01-01T00:00:00+09:00"
            published_at = datetime.fromisoformat(start_time_str)

            videos.append(RemoteVideo(
                video_id=content_id,
                title=title,
                published_at=published_at,
                watch_url=f"https://www.nicovideo.jp/watch/{content_id}"
            ))
        return videos
