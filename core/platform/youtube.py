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
        # First, try to find the channel and get its ID.
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
            # If not found by name, it might be a channel ID itself.
            return name
        return data["items"][0]["snippet"]["channelId"]

    def _get_uploads_playlist_id(self, channel_id: str) -> str:
        headers = {
            "User-Agent": "light-tube-app/0.1.0"
        }
        params = {
            "part": "contentDetails",
            "id": channel_id,
            "key": self.api_key
        }
        response = requests.get(f"{self.base_url}/channels", params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if not data.get("items"):
            raise ValueError(f"Channel not found: {channel_id}")

        # The uploads playlist ID is usually the channel ID with 'UU' instead of 'UC' at the start.
        return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def fetch_videos(self, external_id: str, limit: int = 50, published_before: datetime = None) -> List[RemoteVideo]:
        headers = {
            "User-Agent": "light-tube-app/0.1.0"
        }

        # Use playlistItems API instead of search API for better reliability and quota usage.
        try:
            playlist_id = self._get_uploads_playlist_id(external_id)
        except:
            # Fallback to search if playlist ID cannot be found
            return self._fetch_videos_via_search(external_id, limit, published_before)

        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": limit,
            "key": self.api_key
        }

        response = requests.get(f"{self.base_url}/playlistItems", params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        videos = []
        for item in data.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            title = snippet["title"]
            published_at_str = snippet["publishedAt"]
            published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

            if published_before and published_at >= published_before:
                continue

            videos.append(RemoteVideo(
                video_id=video_id,
                title=title,
                published_at=published_at,
                watch_url=f"https://www.youtube.com/watch?v={video_id}"
            ))
        return videos

    def _fetch_videos_via_search(self, external_id: str, limit: int = 50, published_before: datetime = None) -> List[RemoteVideo]:
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
            published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

            videos.append(RemoteVideo(
                video_id=video_id,
                title=title,
                published_at=published_at,
                watch_url=f"https://www.youtube.com/watch?v={video_id}"
            ))
        return videos
