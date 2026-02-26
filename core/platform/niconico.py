import requests
import urllib.parse
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
        # Use _size instead of _limit (Snapshot API specification)
        params = {
            "q": external_id,
            "targets": "tags",
            "fields": "contentId,title,startTime",
            "_sort": "-startTime",
            "_size": limit,
            "_context": "light-tube-app"
        }

        if published_before:
            params["filters[startTime][lt]"] = published_before.strftime("%Y-%m-%dT%H:%M:%S+09:00")

        # Manually construct query string to avoid encoding '&' as '%2C' (as reported)
        # and to keep brackets in filter keys and commas in field lists unencoded as much as possible.
        query_parts = []
        for k, v in params.items():
            # Only encode values, but allow commas to stay as is in case the API is strict.
            # Keys like filters[startTime][lt] are kept as is.
            val = urllib.parse.quote(str(v), safe=',:-')
            query_parts.append(f"{k}={val}")

        query_string = "&".join(query_parts)
        url = f"{self.base_url}?{query_string}"

        response = requests.get(url, headers=headers)
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
