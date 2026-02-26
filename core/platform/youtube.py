import requests
from datetime import datetime
from typing import List, Optional
from .base import PlatformBase, RemoteVideo

class YouTube(PlatformBase):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def resolve_external_id(self, name: str) -> str:
        headers = {
            "User-Agent": "light-tube-app/0.1.0"
        }
        params = {
            "part": "snippet",
            "q": name,
            "type": "channel",
            "key": self.api_key,
            "maxResults": 1
        }
        response = requests.get(f"{self.base_url}/search", params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not data.get("items"):
            raise ValueError(f"Channel not found: {name}")
        return data["items"][0]["snippet"]["channelId"]

    def fetch_videos(self, external_id: str, limit: int = 50, published_before: datetime = None) -> List[RemoteVideo]:
        headers = {
            "User-Agent": "light-tube-app/0.1.0"
        }
        params = {
            "part": "snippet",
            "channelId": external_id,
            "type": "video",
            "order": "date",
            "maxResults": limit,
            "key": self.api_key
        }
        if published_before:
            params["publishedBefore"] = published_before.isoformat() + "Z"

        response = requests.get(f"{self.base_url}/search", params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        videos = []
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            published_at_str = item["snippet"]["publishedAt"]
            # publishedAt is like "2023-01-01T00:00:00Z"
            published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

            videos.append(RemoteVideo(
                video_id=video_id,
                title=title,
                published_at=published_at,
                watch_url=f"https://www.youtube.com/watch?v={video_id}"
            ))
        return videos
