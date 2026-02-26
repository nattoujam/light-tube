import requests
from datetime import datetime
from typing import List, Optional
from .base import PlatformBase, RemoteVideo

class Niconico(PlatformBase):
    def __init__(self, base_url: str):
        self.base_url = base_url

    def resolve_external_id(self, name: str) -> str:
        # Search for videos with the name and get userId
        params = {
            "q": name,
            "targets": "title,description,tags",
            "fields": "userId",
            "filters[userId][0]": "0", # Dummy filter to satisfy some API quirks or just search
            "_sort": "-startTime",
            "_context": "light-tube-app"
        }
        # Actually, the snapshot API doesn't support searching users directly.
        # But if the user has videos, we can find one and get their userId.
        # This is a bit hacky but follows the "use search API" instruction.

        # Let's try a simpler query first.
        params = {
            "q": name,
            "targets": "title,description,tags",
            "fields": "userId",
            "_sort": "-startTime",
            "_limit": 1,
            "_context": "light-tube-app"
        }
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data.get("data"):
            # Try to see if name is already a userId (numeric)
            if name.isdigit():
                return name
            raise ValueError(f"User not found or has no videos: {name}")
        return str(data["data"][0]["userId"])

    def fetch_videos(self, external_id: str, limit: int = 50, published_before: datetime = None) -> List[RemoteVideo]:
        # Search for videos by userId
        params = {
            "q": "*", # Wildcard search or just use filters
            "targets": "title", # Dummy target
            "fields": "contentId,title,startTime",
            "filters[userId][0]": external_id,
            "_sort": "-startTime",
            "_limit": limit,
            "_context": "light-tube-app"
        }

        if published_before:
            # filters[startTime][lt]=...
            params["filters[startTime][lt]"] = published_before.strftime("%Y-%m-%dT%H:%M:%S+09:00")

        response = requests.get(self.base_url, params=params)
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
